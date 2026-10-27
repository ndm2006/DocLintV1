import copy
import hashlib
import io
import posixpath
import re
import zipfile
from lxml import etree as ET
from .recognizer import REVISION, ROLES
from .structure import analyze, WordContext
from .template import PROFILE, SPECIAL_ROLES
from .template_headings import enrich, block_id, locate
from .eligibility import assess
from .topic_indexes import apply as apply_topic_indexes, recognition_view
from .table_geometry import fit_table, without_geometry
from .styles import ensure_heading_styles, ensure_front_styles, validate_style_parts

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
    analysis=enrich(analyze(parts,recognition_view(root),parse),parts,root,parse,WordContext(parts,parse))
    analysis['document_type']=assess(analysis['blocks'])
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
    body=root.find('w:body',NS); changes=[]; allowed=set(); allowed_nested=set(); seen=set()
    chapter_seen=False; heading_seen=False; parent_levels=set()
    effective_roles={b['id']:decisions.get(b['id'],'keep' if b['needs_review'] else b['role']) for b in analysis['blocks']}
    style_levels=[(1 if effective_roles[b['id']]=='chapter' else b['level']) for b in analysis['blocks'] if not b['protected'] and effective_roles[b['id']] in {'chapter','heading'} and not b.get('has_numbering')]
    heading_styles,style_additions=ensure_heading_styles(parts,style_levels,parse)
    front_roles=SPECIAL_ROLES
    front_styles,front_additions=ensure_front_styles(parts,[effective_roles[b['id']] for b in analysis['blocks'] if not b['protected'] and effective_roles[b['id']] in front_roles],parse)
    style_additions.update(front_additions)
    for b in analysis['blocks']:
        role=decisions.get(b['id'],'keep' if b['needs_review'] else b['role'])
        if b['protected'] or role=='keep': continue
        if role=='chapter':chapter_seen=True;heading_seen=False;parent_levels={1}
        if role=='heading':
            if not chapter_seen or b['level']-1 not in parent_levels or (b.get('parent_block_id') and effective_roles.get(b['parent_block_id']) not in {'chapter','heading'}) or (b['needs_review'] and b.get('number_path') and b.get('parent_block_id') is None):
                raise DocumentError('Đề mục cần có chương và cấp cha được xác nhận trước đó.', 'AI_OUTPUT_INVALID')
            if b['level']==2:heading_seen=True
            parent_levels={n for n in parent_levels if n<b['level']};parent_levels.add(b['level'])
    for b in analysis['blocks']:
        if b['id'] in seen or b['id']!=block_id(b['index'],b.get('path',[])) or b['index']>=len(body): raise DocumentError('Mã khối không hợp lệ.','AI_OUTPUT_INVALID')
        seen.add(b['id'])
        node=locate(body,b['index'],b.get('path',[]))
        if node.tag!=tag('p') or ''.join(node.xpath('.//w:t/text()',namespaces=NS))!=b['text'] or b['role'] not in ROLES:
            raise DocumentError('Phân tích không hợp lệ.','AI_OUTPUT_INVALID')
        role=decisions.get(b['id'],'keep' if b['needs_review'] else b['role'])
        if role not in ROLES: raise DocumentError('Vai trò không hợp lệ.','AI_OUTPUT_INVALID')
        if b['protected'] or role=='keep': continue
        ppr=properties(node,'pPr')
        rules=TEMPLATE['paragraphs']['heading4' if role=='heading' and b['level']==4 else role]
        if 'cover_before_twips' in b:rules={**rules,'before':b['cover_before_twips']}
        if 'cover_indent_twips' in b:rules={**rules,'indent':{'left':b['cover_indent_twips'],'right':b['cover_indent_twips']}}
        setprop(ppr,'spacing',{k:rules[k] for k in ('line','lineRule','before','after')})
        if role.startswith('cover_'):
            # Word's automatic/line-based spacing overrides explicit twips.
            spacing=ppr.find('w:spacing',NS)
            for key in ('beforeAutospacing','afterAutospacing','beforeLines','afterLines'):spacing.attrib.pop(tag(key),None)
            setprop(ppr,'keepLines',{'val':1})
        setprop(ppr,'jc',{'val':rules['alignment']})
        if role in front_roles:
            if not rules.get('preserve_numbering') or not b.get('has_numbering'):
                setprop(ppr,'pStyle',{'val':front_styles[role]})
            setprop(ppr,'outlineLvl',{'val':rules.get('outline',9)})
            if not rules.get('preserve_numbering'):
                setprop(ppr,'numPr',{})
                setprop(ppr.find('w:numPr',NS),'numId',{'val':0})
                setprop(ppr,'ind',{'left':0,'right':0,'firstLine':0,'hanging':0,**rules.get('indent',{})})
            setprop(ppr,'keepNext',{'val':int(rules.get('keep_next',role.endswith('_title')))})
            setprop(ppr,'pageBreakBefore',{'val':1 if b.get('starts_front_page') else 0})
        elif role!='body':
            if not b.get('has_numbering'):
                setprop(ppr,'pStyle',{'val':heading_styles[1 if role=='chapter' else b['level']]})
            setprop(ppr,'outlineLvl',{'val':0 if role=='chapter' else b['level']-1})
            setprop(ppr,'keepNext',{'val':1})
            if role=='chapter': setprop(ppr,'pageBreakBefore',{'val':1})
        for run in node.findall('w:r',NS):
            rpr=properties(run,'rPr')
            font=rules.get('font',TEMPLATE['font']);size=rules.get('size_pt',13)
            fonts=setprop(rpr,'rFonts',{'ascii':font,'hAnsi':font,'eastAsia':font,'cs':font})
            for key in list(fonts.attrib):
                if key.lower().endswith('theme'): del fonts.attrib[key]
            setprop(rpr,'sz',{'val':int(size*2)}); setprop(rpr,'szCs',{'val':int(size*2)})
            if role in {'chapter','heading'} or role in front_roles and role not in {'acknowledgement','abstract'}:
                setprop(rpr,'b',{'val':int(rules.get('bold',True))}); setprop(rpr,'i',{'val':int(rules.get('italic',False))})
                color=setprop(rpr,'color',{'val':rules.get('color','000000')})
                for key in list(color.attrib):
                    if key != tag('val'): del color.attrib[key]
            if role=='chapter': setprop(rpr,'caps',{'val':1})
            elif role in front_roles:setprop(rpr,'caps',{'val':0})
            if role.startswith('cover_'):
                setprop(rpr,'bCs',{'val':int(rules.get('bold',True))})
                setprop(rpr,'iCs',{'val':int(rules.get('italic',False))})
                for name,value in [('smallCaps',0),('spacing',0),('position',0),('w',100)]:setprop(rpr,name,{'val':value})
            order_properties(rpr,R_ORDER)
        order_properties(ppr,P_ORDER)
        (allowed_nested if b.get('path') else allowed).add((b['index'],tuple(tuple(p) for p in b['path'])) if b.get('path') else b['index']); changes.append({'block_id':b['id'],'body_index':b['index'],'path':b.get('path',[]),'role':role,'rules':['FRONT05–08' if role in front_roles else 'BODY01–05' if role=='body' else 'HEAD01–07'],'before_sha256':fingerprint(canonical(locate(before.find('w:body',NS),b['index'],b.get('path',[])))),'after_sha256':fingerprint(canonical(node)),'format_after':{'font':rules.get('font',TEMPLATE['font']),'size_pt':rules.get('size_pt',13),'line':rules['line']/240,'alignment':rules['alignment'],'before_pt':rules['before']/20,'after_pt':rules['after']/20}})
    # Keep TOC/field contents locked while starting the next front section on a new page.
    front_page_breaks=set()
    for b in analysis['blocks']:
        if not b.get('front_boundary_page') or b['index'] in allowed or b.get('path'):continue
        node=body[b['index']];ppr=properties(node,'pPr')
        setprop(ppr,'pageBreakBefore',{'val':1});order_properties(ppr,P_ORDER)
        front_page_breaks.add(b['index'])
        changes.append({'block_id':b['id'],'role':'keep','operation':'page_break_before','rules':['FRONT07'],
                        'format_after':{'page_break_before':True},'before_sha256':fingerprint(canonical(locate(before.find('w:body',NS),b['index'],b.get('path',[])))),
                        'after_sha256':fingerprint(canonical(node))})
    # Margins and table-content protection are independent operations.
    # Normalize both portrait/landscape sections while preserving orientation and column setup.
    page_sections=[];page_operations=[];table_changes=[];table_warnings=[]
    sections=root.findall('.//w:sectPr',NS)
    ranges=[];first=0
    for index,node in enumerate(body):
        section=node.find('w:pPr/w:sectPr',NS) if node.tag==tag('p') else node if node.tag==tag('sectPr') else None
        if section is not None:ranges.append((first,index,section));first=index+1
    for section_index,(first,last,section) in enumerate(ranges):
        has_content=any(first<=b['index']<=last and b['role']!='keep' and not b['protected'] for b in analysis['blocks'])
        size=section.find('w:pgSz',NS);cols=section.find('w:cols',NS)
        landscape=size is not None and size.get(tag('orient'))=='landscape'
        multicol=cols is not None and cols.get(tag('num'),'1')!='1'
        if not has_content or multicol:
            page_operations.append({'section':section_index,'status':'KEPT','reason':'Không có khối định dạng được hoặc section nhiều cột.'});continue
        dims=dict(TEMPLATE['page_twips'])
        if landscape:dims={'w':dims['h'],'h':dims['w'],'orient':'landscape'}
        setprop(section,'pgSz',dims);setprop(section,'pgMar',TEMPLATE['margin_twips'])
        order_properties(section,S_ORDER);page_sections.append(section_index)
        page_operations.append({'section':section_index,'status':'APPLIED','orientation':'landscape' if landscape else 'portrait','margins_cm':TEMPLATE['margins_cm']})
        available=int(dims['w'])-TEMPLATE['margin_twips']['left']-TEMPLATE['margin_twips']['right']
        for index in range(first,last+1):
            if body[index].tag!=tag('tbl'):continue
            change,warning=fit_table(body[index],available)
            if change:table_changes.append({'block_id':f'b{index}',**change})
            if warning:table_warnings.append(f'Bảng b{index}: '+warning)
    page_changed=bool(page_sections)
    derived=apply_topic_indexes(root,analysis,decisions,parts)
    for change in changes:
        if 'body_index' in change:
            change['output_body_index']=derived['source_positions'][change['body_index']]
            change['after_sha256']=fingerprint(canonical(locate(body,change['output_body_index'],change.get('path',[]))))
    parts['word/document.xml']=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    result=out.getvalue()
    validate_integrity(data,result,allowed,page_changed,style_additions=style_additions,page_sections=page_sections,table_indices={int(c['block_id'][1:]) for c in table_changes},page_break_indices=front_page_breaks,allowed_nested=allowed_nested,decisions=decisions)
    return result, {'template':TEMPLATE,'model_revision':REVISION,'source_sha256':fingerprint(data),'output_sha256':fingerprint(result),
                    'status':'PARTIAL','integrity':'PASS','changes':changes,'page_geometry_applied':page_changed,
                    'page_sections_applied':page_sections,'page_operations':page_operations,'table_geometry_changes':table_changes,
                    'styles_added':style_additions,'heading_styles_added':{k:v for k,v in style_additions.items() if isinstance(v,int)},
                    'front_page_breaks':[f'b{i}' for i in sorted(front_page_breaks)],'derived':derived,
                    'template_heading_issues':analysis['template_heading_issues'],
                    'front_matter':analysis['front_matter'],'document_type':analysis['document_type'],
                    'recognition':analysis['statistics'],'recognizer_revision':analysis['recognizer_revision'],
                    'checks':{'content_structure':'PASS','other_package_parts':'PASS','shared_styles':'PASS','protected_regions':'PASS','layout':'NOT_CHECKED','word_fields':'NOT_CHECKED'},
                    'warnings':analysis['warnings']+table_warnings+derived['warnings']+(['Mục lục/danh mục dùng trường Word tự động. Mở Word, Ctrl+A → F9 → cập nhật toàn bộ mục lục để tính số trang; dấu ? chưa phải số trang đã tính.'] if derived['indexes'].get('created') else [])+([] if page_changed else ['Không đổi hình học trang: không có thân bài nhận diện được hoặc section có bố cục đặc biệt.']),
                    'kept_blocks':len(analysis['blocks'])-len(changes),
                    'kept':[{'block_id':b['id'],'reason':b['reason'] if b['protected'] else 'Người dùng chọn giữ nguyên hoặc chưa xác nhận.'} for b in analysis['blocks'] if b['index'] not in allowed|front_page_breaks and (b['index'],tuple(tuple(p) for p in b.get('path',[]))) not in allowed_nested]}


def validate_integrity(source,candidate,allowed,page_changed=False,*,style_additions=None,page_sections=None,table_indices=None,page_break_indices=None,allowed_nested=None,decisions=None):
    """Verify serialized output against source, with an explicit formatting allowlist."""
    original,before=read_package(source); checked,after=read_package(candidate)
    expected=apply_topic_indexes(before,inspect(source),decisions or {},original)
    positions=expected['source_positions']
    try:
        permitted=validate_style_parts(original,checked,style_additions or {},parse)
    except (ValueError,KeyError) as error:
        raise DocumentError('Style hoặc quan hệ đã thay đổi ngoài kế hoạch.','INTEGRITY_FAILED') from error
    if (set(checked)-set(original))-permitted or set(original)-set(checked) or any(checked[n]!=v for n,v in original.items() if n!='word/document.xml' and n not in permitted):
        raise DocumentError('Tài nguyên đã thay đổi.','INTEGRITY_FAILED')
    def stripped(tree):
        tree=copy.deepcopy(tree); body=tree.find('w:body',NS)
        for index,path in allowed_nested or set():
            try:paragraph=locate(body,positions[index],path)
            except (IndexError,AttributeError):raise DocumentError('Vị trí tiêu đề lồng không còn hợp lệ.','INTEGRITY_FAILED')
            if paragraph.tag!=tag('p'):raise DocumentError('Tiêu đề lồng đã thay cấu trúc.','INTEGRITY_FAILED')
            for relative in ('w:pPr','w:r/w:rPr'):
                for n in paragraph.findall(relative,NS):n.getparent().remove(n)
        for i in allowed:
            i=positions[i]
            if i>=len(body) or body[i].tag!=tag('p'):
                raise DocumentError('Cấu trúc khối đã thay đổi.','INTEGRITY_FAILED')
            for path in ('w:pPr','w:r/w:rPr'):
                for n in body[i].findall(path,NS): n.getparent().remove(n)
        for index in page_break_indices or set():
            index=positions[index]
            if index>=len(body) or body[index].tag!=tag('p'):
                raise DocumentError('Ngắt trang ngoài kế hoạch.','INTEGRITY_FAILED')
            props=body[index].find('w:pPr',NS)
            if props is not None:
                for prop in props.findall('w:pageBreakBefore',NS):props.remove(prop)
                if not len(props) and not props.attrib:body[index].remove(props)
        for index in table_indices or set():
            index=positions[index]
            if index>=len(body) or body[index].tag!=tag('tbl'):
                raise DocumentError('Bảng thay đổi ngoài kế hoạch.','INTEGRITY_FAILED')
            original_table=body[index];original_table.getparent().replace(original_table,without_geometry(original_table))
        if page_changed:
            for si,sec in enumerate(tree.findall('.//w:sectPr',NS)):
                if page_sections is not None and si not in page_sections: continue
                for name in ('pgSz','pgMar'):
                    for n in sec.findall('w:'+name,NS): sec.remove(n)
        return canonical(tree)
    if stripped(before)!=stripped(after):
        raise DocumentError('Nội dung hoặc vùng bảo vệ đã thay đổi.','INTEGRITY_FAILED')
