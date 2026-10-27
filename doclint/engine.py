import copy
import hashlib
import io
import posixpath
import re
import zipfile
from lxml import etree as ET
from .recognizer import predict, REVISION, ROLES

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
TEMPLATE = {'id': 'HUST20191_S11', 'version': '0.1.0', 'font': 'Times New Roman', 'size_pt': 13, 'line': 1.1,
            'margins_cm': {'left': 3.5, 'right': 2.5, 'top': 2, 'bottom': 2}}
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
    styles={}
    if 'word/styles.xml' in parts:
        styles={n.get(tag('styleId')):n for n in parse(parts['word/styles.xml']).findall('w:style',NS)}
    def style_protected(style_id):
        visited=set()
        while style_id in styles and style_id not in visited:
            visited.add(style_id); node=styles[style_id]
            if node.find('w:pPr/w:numPr',NS) is not None or node.find('w:pPr/w:framePr',NS) is not None:return True
            base=node.find('w:basedOn',NS);style_id=base.get(tag('val')) if base is not None else None
        return False
    blocks=[]; started=False; special=False
    multicolumn=any(c.get(tag('num'),'1')!='1' for c in root.findall('.//w:sectPr/w:cols',NS))
    for i,node in enumerate(root.find('w:body',NS)):
        if node.tag!=tag('p'): continue
        text=''.join(node.xpath('.//w:t/text()',namespaces=NS))
        if not text.strip(): continue
        chapter=bool(re.match(r'^chương\s+[\dIVX]+',text,re.I))
        style=node.find('w:pPr/w:pStyle',NS)
        style_id=style.get(tag('val'),'') if style is not None else ''
        if chapter: started=True; special=False
        if re.match(r'^(tài liệu tham khảo|phụ lục|mục lục|danh mục|lời cảm|tóm tắt|abstract|kết luận)\b',text,re.I): special=True
        complex_node=bool(node.xpath('.//w:drawing|.//w:pict|.//w:object|.//w:fldChar|.//w:fldSimple|.//w:instrText|.//w:hyperlink|.//w:sdt|.//w:ins|.//w:del|.//w:sectPr|.//w:numPr|.//w:footnoteReference|.//w:endnoteReference|.//w:commentReference|.//w:framePr|.//w:bookmarkStart|.//w:sym|.//w:customXml|.//w:altChunk',namespaces=NS))
        complex_node=complex_node or any('officedocument/2006/math' in str(x.tag).lower() for x in node.iter())
        bold=bool(node.xpath('.//w:b[not(@w:val="0")]',namespaces=NS))
        size_node=node.find('.//w:sz',NS)
        try:size=float(size_node.get(tag('val')))/2 if size_node is not None else 13
        except (ValueError,TypeError):size=13
        role,conf=predict(text,bold,size)
        numbered_heading=re.match(r'^(\d+(?:\.\d+)+)(?:[.)]?\s|$)',text)
        level=min(4,len(numbered_heading.group(1).split('.'))) if numbered_heading else 1 if role=='chapter' else 2
        protected=multicolumn or complex_node or style_protected(style_id) or special or not started or style_id.lower().startswith(('toc','caption')) or level>3
        if protected: role='keep'
        needs_review=not protected and (role in {'heading','chapter'} or conf<0.85 or (bold and len(text)<120))
        blocks.append({'id':f'b{i}', 'index':i,'text':text,'role':role,'confidence':conf,'level':level,
                       'protected':protected,'needs_review':needs_review,
                       'reason':'Vùng đặc biệt, phần đầu hoặc cấu trúc cần giữ nguyên' if protected else 'Xác nhận vai trò trước khi sửa' if needs_review else 'Phân loại nội bộ'})
    return {'fingerprint':fingerprint(data),'model_revision':REVISION,'blocks':blocks,
            'tables':len(root.findall('.//w:tbl',NS)), 'images':sum(n.startswith('word/media/') for n in parts),
            'warnings':['Mô hình thử nghiệm học từ dữ liệu tổng hợp; chưa có số đo chất lượng trên đồ án độc lập.',
                        'Giữ nguyên bìa, bảng, ảnh, công thức, danh sách, trường và vùng phức tạp.',
                        'Chưa dựng PDF, chưa xác minh bố cục, mục lục và số trang trên Microsoft Word.']}

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
    parts,root=read_package(data); before=copy.deepcopy(root)
    body=root.find('w:body',NS); changes=[]; allowed=set(); seen=set()
    chapter_seen=False; heading_seen=False
    for b in analysis['blocks']:
        role=decisions.get(b['id'],'keep' if b['needs_review'] else b['role'])
        if b['protected'] or role=='keep': continue
        if role=='chapter':chapter_seen=True;heading_seen=False
        if role=='heading':
            if not chapter_seen or (b['level']==3 and not heading_seen):
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
        setprop(ppr,'spacing',{'line':264,'lineRule':'auto','before':60 if role=='body' else 120,'after':0 if role=='body' else 240})
        setprop(ppr,'jc',{'val':'both' if role=='body' else 'center' if role=='chapter' else 'left'})
        if role!='body':
            setprop(ppr,'outlineLvl',{'val':0 if role=='chapter' else b['level']-1})
            setprop(ppr,'keepNext',{'val':1})
            if role=='chapter': setprop(ppr,'pageBreakBefore',{'val':1})
        for run in node.findall('w:r',NS):
            rpr=properties(run,'rPr')
            setprop(rpr,'rFonts',{'ascii':'Times New Roman','hAnsi':'Times New Roman','eastAsia':'Times New Roman','cs':'Times New Roman'})
            setprop(rpr,'sz',{'val':26}); setprop(rpr,'szCs',{'val':26})
            if role!='body': setprop(rpr,'b',{'val':1})
            if role=='chapter': setprop(rpr,'caps',{'val':1})
            order_properties(rpr,R_ORDER)
        order_properties(ppr,P_ORDER)
        allowed.add(b['index']); changes.append({'block_id':b['id'],'role':role,'rules':['BODY01–05' if role=='body' else 'HEAD01–07'],'before_sha256':fingerprint(canonical(before.find('w:body',NS)[b['index']])),'after_sha256':fingerprint(canonical(node))})
    # Conservatively change page geometry only for a simple single-section document without front matter.
    # Shared section properties affect protected content; preserve them in all other cases.
    page_changed=False
    sections=root.findall('.//w:sectPr',NS)
    if len(sections)==1 and all(n.tag==tag('sectPr') or (n.tag==tag('p') and i in allowed) for i,n in enumerate(body)) and analysis['blocks'] and not any(b['protected'] or decisions.get(b['id'])=='keep' or (b['needs_review'] and b['id'] not in decisions) for b in analysis['blocks']):
        sec=sections[0]; size=sec.find('w:pgSz',NS); cols=sec.find('w:cols',NS)
        if (size is None or size.get(tag('orient'))!='landscape') and (cols is None or cols.get(tag('num'),'1')=='1'):
            setprop(sec,'pgSz',{'w':11906,'h':16838}); setprop(sec,'pgMar',{'left':1984,'right':1417,'top':1134,'bottom':1134,'gutter':0}); order_properties(sec,S_ORDER); page_changed=True
    parts['word/document.xml']=ET.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    result=out.getvalue()
    validate_integrity(data,result,allowed,page_changed)
    return result, {'template':TEMPLATE,'model_revision':REVISION,'source_sha256':fingerprint(data),'output_sha256':fingerprint(result),
                    'status':'PARTIAL','integrity':'PASS','changes':changes,'page_geometry_applied':page_changed,
                    'checks':{'content_structure':'PASS','other_package_parts':'PASS','protected_regions':'PASS','layout':'NOT_CHECKED','word_fields':'NOT_CHECKED'},
                    'warnings':analysis['warnings']+([] if page_changed else ['Giữ hình học trang: section có vùng bảo vệ hoặc bố cục đặc biệt.']),
                    'kept_blocks':len(analysis['blocks'])-len(changes)}


def validate_integrity(source,candidate,allowed,page_changed=False):
    """Verify serialized output against source, with an explicit formatting allowlist."""
    original,before=read_package(source); checked,after=read_package(candidate)
    if original.keys()!=checked.keys() or any(checked[n]!=v for n,v in original.items() if n!='word/document.xml'):
        raise DocumentError('Tài nguyên đã thay đổi.','INTEGRITY_FAILED')
    def stripped(tree):
        tree=copy.deepcopy(tree); body=tree.find('w:body',NS)
        for i in allowed:
            if i>=len(body) or body[i].tag!=tag('p'):
                raise DocumentError('Cấu trúc khối đã thay đổi.','INTEGRITY_FAILED')
            for path in ('w:pPr','w:r/w:rPr'):
                for n in body[i].findall(path,NS): n.getparent().remove(n)
        if page_changed:
            for sec in tree.findall('.//w:sectPr',NS):
                for name in ('pgSz','pgMar'):
                    for n in sec.findall('w:'+name,NS): sec.remove(n)
        return canonical(tree)
    if stripped(before)!=stripped(after):
        raise DocumentError('Nội dung hoặc vùng bảo vệ đã thay đổi.','INTEGRITY_FAILED')
