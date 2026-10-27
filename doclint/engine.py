import copy
import hashlib
import io
import posixpath
import re
import zipfile
from lxml import etree as ET
from .recognizer import REVISION, ROLES
from .structure import analyze
from .template import PROFILE
from .styles import ensure_heading_styles, validate_style_parts

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
TEMPLATE = PROFILE
class DocumentError(Exception):
    def __init__(self, message, code='INVALID_DOCX'):
        self.code, self.message = code, message
        super().__init__(message)
def tag(n): return '{'+W+'}'+n
def parse(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise DocumentError('XML chứa DTD hoặc entity không được hỗ trợ.')
    try:
        root = ET.fromstring(data, ET.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False))
        if root.getroottree().docinfo.doctype:
            raise DocumentError('XML chứa DTD không được hỗ trợ.')
        if sum(1 for _ in root.iter()) > 200000:
            raise DocumentError('XML vượt giới hạn 200.000 nút.', 'RESOURCE_LIMIT')
        return root
    except ET.XMLSyntaxError as e:
        raise DocumentError('XML không hợp lệ.') from e

def read_package(data):
    if len(data) > 20*1024**2: raise DocumentError('Tệp vượt 20 MiB.', 'RESOURCE_LIMIT')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos=z.infolist(); names=[i.filename for i in infos]
            if len(infos)>2000 or sum(i.file_size for i in infos)>100*1024**2:
                raise DocumentError('Gói vượt giới hạn giải nén.', 'RESOURCE_LIMIT')
            if len(set(names)) != len(names): raise DocumentError('Gói ZIP có mục trùng tên.')
            parts={}
            for i in infos:
                name=i.filename
                if name.startswith('/') or '\\' in name or '..' in name.split('/') or i.flag_bits & 1:
                    raise DocumentError('Đường dẫn hoặc mã hóa ZIP không hợp lệ.')
                if 'vbaproject' in name.lower() or name.startswith('_xmlsignatures/'):
                    raise DocumentError('Không hỗ trợ macro hoặc tài liệu có chữ ký số.', 'SIGNED_DOCUMENT')
                if name.endswith(('.xml','.rels')) and i.file_size>10*1024**2:
                    raise DocumentError('XML vượt 10 MiB.', 'RESOURCE_LIMIT')
                parts[name]=z.read(i)
            if not {'[Content_Types].xml','word/document.xml','_rels/.rels'} <= parts.keys():
                raise DocumentError('Thiếu thành phần bắt buộc của DOCX.')
            total_nodes=0
            for n,b in parts.items():
                if n.endswith(('.xml','.rels')):
                    total_nodes+=sum(1 for _ in parse(b).iter())
                    if total_nodes>200000: raise DocumentError('Gói vượt 200.000 nút XML.', 'RESOURCE_LIMIT')
            types=parse(parts['[Content_Types].xml'])
            if types.tag!='{http://schemas.openxmlformats.org/package/2006/content-types}Types' or not any(n.get('PartName')=='/word/document.xml' and n.get('ContentType')=='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml' for n in types):
                raise DocumentError('Content Types không mô tả tài liệu DOCX hợp lệ.')
            root_rels=parse(parts['_rels/.rels'])
            if root_rels.tag!='{http://schemas.openxmlformats.org/package/2006/relationships}Relationships' or not any(n.get('Type')=='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' and n.get('Target','').lstrip('/')=='word/document.xml' and n.get('TargetMode')!='External' for n in root_rels):
                raise DocumentError('Thiếu quan hệ chính của tài liệu DOCX.')
            root=parse(parts['word/document.xml'])
            if root.tag!=tag('document') or root.find('w:body',NS) is None:
                raise DocumentError('Không có nội dung Word hợp lệ.')
            if 'word/settings.xml' in parts and parse(parts['word/settings.xml']).find('w:documentProtection',NS) is not None:
                raise DocumentError('Tài liệu đang được bảo vệ.', 'UNSUPPORTED_PROTECTION')
            # Validate internal OPC relationships without following any external target.
            for n,b in parts.items():
                if not n.endswith('.rels'): continue
                base=posixpath.dirname(posixpath.dirname(n)) if n!='_rels/.rels' else ''
                for rel in parse(b):
                    if rel.get('TargetMode')=='External': continue
                    target=rel.get('Target','').split('#')[0]
                    resolved=posixpath.normpath(posixpath.join(base,target)) if not target.startswith('/') else target.lstrip('/')
                    if resolved not in parts: raise DocumentError('Quan hệ tài nguyên bị thiếu.')
            return parts,root
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, ValueError) as e:
        raise DocumentError('Không đọc được gói DOCX.') from e

def canonical(el): return ET.tostring(el,method='c14n')
def fingerprint(data): return hashlib.sha256(data).hexdigest()
def inspect(data):
    parts,root=read_package(data)
    analysis=analyze(parts,root,parse)
    analysis.update({'fingerprint':fingerprint(data), 'tables':len(root.findall('.//w:tbl',NS)),
                     'images':sum(n.startswith('word/media/') for n in parts)})
    return analysis

def setprop(parent,name,attrs):
    el=parent.find('w:'+name,NS)
    if el is None: el=ET.SubElement(parent,tag(name))
    for k,v in attrs.items(): el.set(tag(k),str(v))
    return el

def properties(node,name):
    el=node.find('w:'+name,NS)
    if el is None: el=ET.Element(tag(name)); node.insert(0,el)
    return el

def order_properties(parent, names):
    order={tag(name):i for i,name in enumerate(names.split())}
    parent[:]=sorted(parent,key=lambda child:order.get(child.tag,len(order)))

P_ORDER='pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange'
R_ORDER='rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange'
S_ORDER='headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange'

def edit(data,analysis,decisions):
    if analysis['fingerprint']!=fingerprint(data): raise DocumentError('Bản phân tích không khớp bản gốc.','AI_OUTPUT_INVALID')
    fresh=inspect(data)
    if analysis != fresh: raise DocumentError('Phân tích đã thay đổi hoặc không hợp lệ.','AI_OUTPUT_INVALID')
    parts,root=read_package(data); before=copy.deepcopy(root)
    body=root.find('w:body',NS); changes=[]; allowed=set(); seen=set()
    chapter_seen=False; heading_seen=False
    effective_roles={b['id']:decisions.get(b['id'],'keep' if b['needs_review'] else b['role']) for b in analysis['blocks']}
    style_levels=[(1 if effective_roles[b['id']]=='chapter' else b['level']) for b in analysis['blocks'] if not b['protected'] and effective_roles[b['id']] in {'chapter','heading'} and not b.get('has_numbering')]
    heading_styles,style_additions=ensure_heading_styles(parts,style_levels,parse)
    for b in analysis['blocks']:
        role=decisions.get(b['id'],'keep' if b['needs_review'] else b['role'])
        if b['protected'] or role=='keep': continue
        if role=='chapter':chapter_seen=True;heading_seen=False
        if role=='heading':
            if not chapter_seen or (b['level']==3 and not heading_seen) or (b.get('parent_block_id') and effective_roles.get(b['parent_block_id']) not in {'chapter','heading'}) or (b['needs_review'] and b.get('number_path') and b.get('parent_block_id') is None):
                raise DocumentError('Đề mục cần có chương và cấp cha được xác nhận trước đó.', 'AI_OUTPUT_INVALID')
            if b['level']==2:heading_seen=True
    for b in analysis['blocks']:
        if b['id'] in seen or b['id']!=f"b{b['index']}" or b['index']>=len(body): raise DocumentError('Mã khối không hợp lệ.','AI_OUTPUT_INVALID')
        seen.add(b['id'])
        node=body[b['index']]
        if node.tag!=tag('p') or ''.join(node.xpath('.//w:t/text()',namespaces=NS))!=b['text'] or b['role'] not in ROLES:
            raise DocumentError('Phân tích không hợp lệ.','AI_OUTPUT_INVALID')
        role=decisions.get(b['id'],'keep' if b['needs_review'] else b['role'])
        if role not in ROLES: raise DocumentError('Vai trò không hợp lệ.','AI_OUTPUT_INVALID')
        if b['protected'] or role=='keep': continue
        ppr=properties(node,'pPr')
        rules=TEMPLATE['paragraphs'][role]
        setprop(ppr,'spacing',{k:rules[k] for k in ('line','lineRule','before','after')})
        setprop(ppr,'jc',{'val':rules['alignment']})
        if role!='body':
            if not b.get('has_numbering'):
                setprop(ppr,'pStyle',{'val':heading_styles[1 if role=='chapter' else b['level']]})
            setprop(ppr,'outlineLvl',{'val':0 if role=='chapter' else b['level']-1})
            setprop(ppr,'keepNext',{'val':1})
            if role=='chapter': setprop(ppr,'pageBreakBefore',{'val':1})
        for run in node.findall('w:r',NS):
            rpr=properties(run,'rPr')
            fonts=setprop(rpr,'rFonts',{'ascii':'Times New Roman','hAnsi':'Times New Roman','eastAsia':'Times New Roman','cs':'Times New Roman'})
            for key in list(fonts.attrib):
                if key.lower().endswith('theme'): del fonts.attrib[key]
            setprop(rpr,'sz',{'val':26}); setprop(rpr,'szCs',{'val':26})
            if role!='body':
                setprop(rpr,'b',{'val':1}); setprop(rpr,'i',{'val':0})
                color=setprop(rpr,'color',{'val':'000000'})
                for key in list(color.attrib):
                    if key != tag('val'): del color.attrib[key]
            if role=='chapter': setprop(rpr,'caps',{'val':1})
            order_properties(rpr,R_ORDER)
        order_properties(ppr,P_ORDER)
        allowed.add(b['index']); changes.append({'block_id':b['id'],'role':role,'rules':['BODY01–05' if role=='body' else 'HEAD01–07'],'before_sha256':fingerprint(canonical(before.find('w:body',NS)[b['index']])),'after_sha256':fingerprint(canonical(node)),'format_after':{'font':TEMPLATE['font'],'size_pt':13,'line':1.1,'alignment':rules['alignment'],'before_pt':rules['before']/20,'after_pt':rules['after']/20}})
    # Page geometry is an explicit plan operation; body objects retain their XML/data.
    # Freeze landscape, multicolumn and unsupported floating/merged layouts.
    page_sections=[]
    sections=root.findall('.//w:sectPr',NS)
    ranges=[]; first=0
    for index,node in enumerate(body):
        section=node.find('w:pPr/w:sectPr',NS) if node.tag==tag('p') else node if node.tag==tag('sectPr') else None
        if section is not None:
            ranges.append((first,index,section)); first=index+1
    for section_index,(first,last,section) in enumerate(ranges):
        nodes=list(body)[first:last+1]
        size=section.find('w:pgSz',NS); cols=section.find('w:cols',NS)
        has_body=any(b['id'] in {f'b{i}' for i in range(first,last+1)} and b['role'] in {'body','chapter','heading'} and not b['protected'] for b in analysis['blocks'])
        unsafe=any(n.tag not in {tag('p'),tag('tbl'),tag('sectPr')} or n.xpath('.//w:tblpPr|.//w:framePr|.//w:pict|.//w:object|.//w:txbxContent|.//w:gridSpan|.//w:vMerge|.//w:tbl//w:tbl',namespaces=NS) or any(str(c.tag).endswith('}anchor') for c in n.iter()) for n in nodes)
        if has_body and not unsafe and (size is None or size.get(tag('orient'))!='landscape') and (cols is None or cols.get(tag('num'),'1')=='1'):
            setprop(section,'pgSz',TEMPLATE['page_twips'])
            setprop(section,'pgMar',TEMPLATE['margin_twips'])
            order_properties(section,S_ORDER); page_sections.append(section_index)
    page_changed=bool(page_sections)
    parts['word/document.xml']=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    result=out.getvalue()
    validate_integrity(data,result,allowed,page_changed,style_additions=style_additions,page_sections=page_sections)
    return result, {'template':TEMPLATE,'model_revision':REVISION,'source_sha256':fingerprint(data),'output_sha256':fingerprint(result),
                    'status':'PARTIAL','integrity':'PASS','changes':changes,'page_geometry_applied':page_changed,
                    'page_sections_applied':page_sections,'heading_styles_added':style_additions,
                    'recognition':analysis['statistics'],'recognizer_revision':analysis['recognizer_revision'],
                    'checks':{'content_structure':'PASS','other_package_parts':'PASS','shared_styles':'PASS','protected_regions':'PASS','layout':'NOT_CHECKED','word_fields':'NOT_CHECKED'},
                    'warnings':analysis['warnings']+([] if page_changed else ['Không đổi hình học trang: không có thân bài nhận diện được hoặc section có bố cục đặc biệt.']),
                    'kept_blocks':len(analysis['blocks'])-len(changes),
                    'kept':[{'block_id':b['id'],'reason':b['reason'] if b['protected'] else 'Người dùng chọn giữ nguyên hoặc chưa xác nhận.'} for b in analysis['blocks'] if b['index'] not in allowed]}


def validate_integrity(source,candidate,allowed,page_changed=False,*,style_additions=None,page_sections=None):
    """Verify serialized output against source, with an explicit formatting allowlist."""
    original,before=read_package(source); checked,after=read_package(candidate)
    try:
        permitted=validate_style_parts(original,checked,style_additions or {},parse)
    except (ValueError,KeyError) as error:
        raise DocumentError('Style hoặc quan hệ đã thay đổi ngoài kế hoạch.','INTEGRITY_FAILED') from error
    if (set(checked)-set(original))-permitted or set(original)-set(checked) or any(checked[n]!=v for n,v in original.items() if n!='word/document.xml' and n not in permitted):
        raise DocumentError('Tài nguyên đã thay đổi.','INTEGRITY_FAILED')
    def stripped(tree):
        tree=copy.deepcopy(tree); body=tree.find('w:body',NS)
        for i in allowed:
            if i>=len(body) or body[i].tag!=tag('p'):
                raise DocumentError('Cấu trúc khối đã thay đổi.','INTEGRITY_FAILED')
            for path in ('w:pPr','w:r/w:rPr'):
                for n in body[i].findall(path,NS): n.getparent().remove(n)
        if page_changed:
            for si,sec in enumerate(tree.findall('.//w:sectPr',NS)):
                if page_sections is not None and si not in page_sections: continue
                for name in ('pgSz','pgMar'):
                    for n in sec.findall('w:'+name,NS): sec.remove(n)
        return canonical(tree)
    if stripped(before)!=stripped(after):
        raise DocumentError('Nội dung hoặc vùng bảo vệ đã thay đổi.','INTEGRITY_FAILED')
