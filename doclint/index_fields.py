"""Deterministic Word TOC/list fields with visible cached links and page refs.

Generated blocks and source anchors are validated as exact structural operations.
Page numbers are deliberately unknown until Word updates PAGEREF/TOC fields.
"""
import re
from lxml import etree as E
from .structure import WordContext
from .template import PROFILE

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W};Q='{'+W+'}'
PREFIX='DocLint.Generated.'
LABELS={'toc':'MỤC LỤC','figures':'DANH MỤC HÌNH VẼ','tables':'DANH MỤC BẢNG'}


def el(parent,name,**attrs):
    node=E.SubElement(parent,Q+name)
    for k,v in attrs.items():node.set(Q+k,str(v))
    return node


def owned(node):
    prop=node.find('w:sdtPr/w:tag',NS)
    return prop is not None and prop.get(Q+'val','').startswith(PREFIX)


def kind(node):
    prop=node.find('w:sdtPr/w:tag',NS)
    return prop.get(Q+'val','')[len(PREFIX):].split('.')[0] if owned(node) else None


def text(node):return ''.join(node.xpath('.//w:t/text()',namespaces=NS))


def section(body,analysis,which):
    for node in body:
        if kind(node)==which:return node,body.index(node)+1
    role={'toc':'toc_title','figures':'list_figures_title','tables':'list_tables_title'}[which]
    block=next((b for b in analysis['blocks'] if b['role']==role and not b.get('path')),None)
    if block is None:return None,None
    node=body[block['index']];end=block['index']+1
    # The native TOC/list is frequently the SDT immediately after its title.
    if end<len(body) and body[end].tag==Q+'sdt':end+=1
    else:
        depth=0
        for i in range(block['index'],len(body)):
            current=body[i]
            for f in current.findall('.//w:fldChar',NS):
                depth+=1 if f.get(Q+'fldCharType')=='begin' else -1 if f.get(Q+'fldCharType')=='end' else 0
            if i>block['index']:
                ps=current.find('w:pPr/w:pStyle',NS)
                if depth<=0 and (ps is None or not re.match(r'^(?:TOC\d+|TableofFigures)$',ps.get(Q+'val',''),re.I)):break
                end=i+1
            if depth<=0 and i==block['index']:
                while end<len(body):
                    ps=body[end].find('w:pPr/w:pStyle',NS)
                    styled=ps is not None and re.match(r'^(?:TOC\d+|TableofFigures)$',ps.get(Q+'val',''),re.I)
                    manual=body[end].find('.//w:tab',NS) is not None and re.search(r'(?:\d+|[ivxlcdm]+)\s*$',text(body[end]),re.I)
                    if not styled and not manual:break
                    end+=1
                break
    return node,end


def field(paragraph,instruction,cache=None):
    start=el(el(paragraph,'r'),'fldChar',fldCharType='begin',dirty='true')
    instruction_node=el(el(paragraph,'r'),'instrText');instruction_node.set('{http://www.w3.org/XML/1998/namespace}space','preserve');instruction_node.text=' '+instruction+' '
    el(el(paragraph,'r'),'fldChar',fldCharType='separate')
    if cache is not None:el(el(paragraph,'r'),'t').text=cache


def close_field(paragraph):el(el(paragraph,'r'),'fldChar',fldCharType='end')


def mark_native_indexes(nodes):
    """Mark only TOC fields, including split instructions and nested PAGEREF."""
    stack=[];found=False
    for node in nodes:
        for item in node.iter():
            if item.tag==Q+'fldSimple' and re.match(r'^\s*TOC\b',item.get(Q+'instr',''),re.I):
                item.set(Q+'dirty','true');found=True
            elif item.tag==Q+'instrText' and stack:
                stack[-1][1].append(item.text or '')
            elif item.tag==Q+'fldChar':
                mode=item.get(Q+'fldCharType')
                if mode=='begin':stack.append([item,[]])
                elif mode in {'separate','end'} and stack:
                    if re.match(r'^\s*TOC\b',''.join(stack[-1][1]),re.I):
                        stack[-1][0].set(Q+'dirty','true');found=True
                    if mode=='end':stack.pop()
    return found


def paragraph(parent,title=False,which='toc'):
    p=el(parent,'p');props=el(p,'pPr')
    if title:el(props,'keepNext',val=1);el(props,'pageBreakBefore',val=1)
    role={'toc':'toc_title','figures':'list_figures_title','tables':'list_tables_title'}[which]
    rules=PROFILE['paragraphs'][role]
    el(props,'spacing',before=rules['before'] if title else 60,
       after=rules['after'] if title else 100 if which=='toc' else 0,
       line=rules['line'] if title else 264,lineRule='auto')
    el(props,'jc',val='center' if title else 'both');el(props,'outlineLvl',val=9)
    return p


def run(parent,value,bold=False):
    r=el(parent,'r');props=el(r,'rPr');el(props,'rFonts',ascii='Times New Roman',hAnsi='Times New Roman',eastAsia='Times New Roman',cs='Times New Roman');el(props,'b',val=int(bold));el(props,'sz',val=26)
    el(r,'t').text=value
    return r


def container(which):
    node=E.Element(Q+'sdt');props=el(node,'sdtPr');el(props,'alias',val=LABELS.get(which,'Khoảng bìa theo mẫu'));el(props,'tag',val=PREFIX+which+'.v1')
    return node,el(node,'sdtContent')


def contains_math(node):
    return any(isinstance(n.tag,str) and n.tag.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/math}') for n in node.iter())


def reusable_property_order(node):
    for props in node.findall('.//w:pPr',NS):
        names=[E.QName(n).localname for n in props]
        for first,last in [('keepNext','pageBreakBefore'),('spacing','ind')]:
            if first in names and last in names and names.index(first)>names.index(last):return False
    return True


def tc_type(instruction):
    match=re.search(r'\bTC\s+".*?"\s+.*?\\f\s+([A-Za-z])\b',instruction,re.I)
    return match.group(1).upper() if match else None


def tc_instruction(label,collection,level):
    escaped=label.replace('"',"'").replace('\\','/').replace('\n',' ')
    return f' TC "{escaped}" \\f {collection} \\l {level} '


def heading_labels(blocks,nodes,parts):
    labels={b['id']:b['text'] for b in blocks}
    if not parts:return labels
    context=WordContext(parts,lambda data:E.fromstring(data))
    counters={}
    for b in blocks:
        if b.get('source')!='word_style' or not b.get('has_numbering'):continue
        node=nodes[b['id']];num=context.property(node,'w:numPr/w:numId');depth=context.property(node,'w:numPr/w:ilvl')
        if num is None:continue
        number_id=num.get(Q+'val');level=int(depth.get(Q+'val','0')) if depth is not None else 0
        abstract=context.numbering.get(number_id)
        definition=abstract.find(f'w:lvl[@w:ilvl="{level}"]',NS) if abstract is not None else None
        if definition is None:continue
        values=counters.setdefault(number_id,{})
        start=definition.find('w:start',NS);initial=int(start.get(Q+'val','1')) if start is not None else 1
        values[level]=values[level]+1 if level in values else initial
        for deeper in list(values):
            if deeper>level:del values[deeper]
        label=definition.find('w:lvlText',NS)
        if label is None:continue
        def number(match):
            ancestor=int(match.group(1))-1;value=values.get(ancestor,1)
            fmt=abstract.find(f'w:lvl[@w:ilvl="{ancestor}"]/w:numFmt',NS)
            mode=fmt.get(Q+'val','decimal') if fmt is not None else 'decimal'
            if mode in {'upperRoman','lowerRoman'}:
                remaining=value;result=''
                for count,letters in [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]:
                    result+=letters*(remaining//count);remaining%=count
                return result.lower() if mode=='lowerRoman' else result
            if mode in {'upperLetter','lowerLetter'}:
                result='';remaining=value
                while remaining>0:remaining,digit=divmod(remaining-1,26);result=chr(65+digit)+result
                return result.lower() if mode=='lowerLetter' else result
            return str(value)
        prefix=re.sub(r'%([1-9])',number,label.get(Q+'val','')).strip()
        if prefix:labels[b['id']]=prefix+' '+b['text']
    return labels


def generate(body,analysis,decisions,original=None,parts=None):
    """Use dedicated TC collections, never broad Word outline/style scanning.

    Only confirmed chapter/heading/section titles can receive the TOC collection.
    A math/object paragraph cannot receive it even if its source style is Heading1.
    Existing foreign TC collections are reserved and never silently collected.
    """
    original=list(body) if original is None else original;nodes={};selected={k:[] for k in LABELS};created=[];anchors=[];updated=[];warnings=[]
    for b in analysis['blocks']:
        role=decisions.get(b['id'],'keep' if b['needs_review'] else b['role'])
        if b['protected']:continue
        node=original[b['index']]
        for name,number in b.get('path',[]):node=node.findall('w:'+name,NS)[number]
        if node.tag!=Q+'p' or contains_math(node):continue
        if node.xpath('.//w:drawing|.//w:pict|.//w:object|.//w:ins|.//w:del',namespaces=NS):continue
        which='toc' if role in {'chapter','heading','references_title','appendix_title'} else 'figures' if role=='figure_caption' else 'tables' if role=='table_caption' else None
        if which:
            selected[which].append(b);nodes[b['id']]=node
    if not any(b['role']=='chapter' for b in selected['toc']):return {'created':[],'anchors':[],'collections':{}}
    labels={b['id']:b['text'] for blocks in selected.values() for b in blocks}
    labels.update(heading_labels(selected['toc'],nodes,parts))
    first_chapter=min(b['index'] for b in selected['toc'] if b['role']=='chapter')
    for key in ('figures','tables'):
        selected[key]=[b for b in selected[key] if b['index']>=first_chapter]
    region=original[first_chapter:]
    # An uncaptioned object is not enough evidence for a meaningful list. In
    # particular, layout tables and decorative images must not create empty lists.
    wants={'toc':True,'figures':bool(selected['figures']),'tables':bool(selected['tables'])}
    for offset,node in enumerate(region,first_chapter):
        if owned(node):continue
        for key,present,label in [('figures',bool(node.xpath('.//w:drawing|.//w:pict',namespaces=NS)),'Hình'),
                                  ('tables',node.tag==Q+'tbl' or node.find('.//w:tbl',NS) is not None,'Bảng')]:
            if not present:continue
            if not any(abs(b['index']-offset)<=1 for b in selected[key]):
                warnings.append(f'{label} tại b{offset}: chưa tìm thấy chú thích liền kề. Vui lòng bổ sung nếu là đối tượng nội dung; nếu là logo/trang trí hoặc bảng dàn trang thì giữ nguyên, không tự đặt tên hoặc tạo danh mục rỗng.')
    # Migrate old generated fields; never treat their cached text as source headings.
    # Resolve source title positions through original node references, because a
    # cover may have gained ordinary blank paragraphs before these sections.
    # section() reads source indices; run it against the unmodified source-order
    # list via a minimal view, without detaching live source nodes.
    class View:
        def __iter__(self):return iter(original)
        def __len__(self):return len(original)
        def __getitem__(self,i):return original[i]
        def index(self,n):return original.index(n)
    existing={k:section(View(),analysis,k) for k in LABELS}
    previous_types={}
    for key in LABELS:
        node=existing[key][0]
        if node is not None and owned(node):
            instr=' '.join(node.xpath('.//w:instrText/text()',namespaces=NS))
            match=re.search(r'\bTOC\s+\\f\s+([A-Za-z])\b',instr,re.I)
            if match:previous_types[key]=match.group(1).upper()
    # Owned fields must have both an owned index and an eligible source paragraph
    # with an exact TC label/level. A TC attached to math stays foreign.
    owned_fields=set()
    for key,blocks in selected.items():
        for b in blocks:
            node=nodes[b['id']];level=b['level'] if b['role']=='heading' else 1
            if not any((n.get(Q+'name') or '').startswith('DocLintIndex_') for n in node.findall('w:bookmarkStart',NS)):continue
            for f in node.findall('w:fldSimple',NS):
                collection=tc_type(f.get(Q+'instr',''))
                if collection and previous_types.get(key)==collection:
                    owned_fields.add(f)
    # A formerly selected heading/caption may have been removed or reclassified.
    # Retire its private TC entry too, or Word would collect stale entries even
    # after the visible generated list has been refreshed.
    active={nodes[b['id']] for key,blocks in selected.items() if wants[key] for b in blocks}
    for node in original:
        for p in ([node] if node.tag==Q+'p' else node.findall('.//w:p',NS)):
            if owned(node) or contains_math(p):continue
            if not any((n.get(Q+'name') or '').startswith('DocLintIndex_') for n in p.findall('w:bookmarkStart',NS)):continue
            for f in list(p.findall('w:fldSimple',NS)):
                if tc_type(f.get(Q+'instr','')) in previous_types.values() and p not in active:
                    p.remove(f)
    foreign=set()
    for f in body.findall('.//w:fldSimple',NS):
        collection=tc_type(f.get(Q+'instr',''))
        if collection and f not in owned_fields:foreign.add(collection)
    # Complex native TC fields also reserve their type.
    for p in body.findall('.//w:p',NS):
        collection=tc_type(''.join(p.xpath('./w:r/w:instrText/text()',namespaces=NS)))
        if collection:foreign.add(collection)
    collections={};used=set(foreign)
    for key,preferred in [('toc','H'),('figures','D'),('tables','E')]:
        prior=previous_types.get(key,preferred)
        available=[c for c in prior+preferred+'HJKLMNOPQRSTUVWXYZABCDEFGI' if c not in used]
        if not available:raise ValueError('Không còn mã trường TC riêng để tạo mục lục an toàn.')
        collections[key]=available[0];used.add(available[0])
    next_id=max([int(n.get(Q+'id')) for n in body.findall('.//w:bookmarkStart',NS) if n.get(Q+'id','').isdigit()]+[0])+1
    names={n.get(Q+'name') for n in body.findall('.//w:bookmarkStart',NS)}

    def anchor(b):
        nonlocal next_id
        node=nodes[b['id']]
        for n in node.findall('w:bookmarkStart',NS):
            if (n.get(Q+'name') or '').startswith('DocLintIndex_'):return n.get(Q+'name')
        name='DocLintIndex_'+str(next_id)
        while name in names:next_id+=1;name='DocLintIndex_'+str(next_id)
        start=E.Element(Q+'bookmarkStart');start.set(Q+'id',str(next_id));start.set(Q+'name',name)
        end=E.Element(Q+'bookmarkEnd');end.set(Q+'id',str(next_id))
        node.insert(1 if node.find('w:pPr',NS) is not None else 0,start);node.append(end)
        anchors.append({'block_id':b['id'],'bookmark':name});names.add(name);next_id+=1
        return name

    for key in ('toc','figures','tables'):
        title,end=existing[key];old=title if title is not None and owned(title) else None
        empty=None
        if title is not None and not owned(title):
            f=title.find('w:fldSimple',NS)
            if f is not None and re.match(r'^\s*TOC\b',f.get(Q+'instr',''),re.I) and text(f).strip() in {'','[chưa cập nhật trường]'}:empty=f
        bare=title is not None and not owned(title) and end==original.index(title)+1 and not title.xpath('.//w:instrText|.//w:fldSimple',namespaces=NS)
        if not wants[key]:
            if old is not None:
                body.remove(old)
                updated.append({'kind':key,'operation':'REMOVE_EMPTY_OWNED_INDEX'})
            continue
        if title is not None and not owned(title) and empty is None and not bare:
            native=mark_native_indexes(original[original.index(title):end])
            if native:
                updated.append({'kind':key,'operation':'NATIVE_FIELD_UPDATE_IN_WORD'})
            else:
                warnings.append(f'{LABELS[key]} đã có nội dung thủ công: giữ nguyên để tránh mất nội dung; cần cập nhật mục và số trang trong Word, không tạo thêm bản trùng.')
            continue
        collection=collections[key]
        expected_instruction=f'TOC \\f {collection} \\h \\z'
        keep=old is not None and old.find('w:sdtPr/w:tag',NS).get(Q+'val','').endswith('.v3') and reusable_property_order(old) and not contains_math(old) and any((n.text or '').strip()==expected_instruction for n in old.findall('.//w:instrText',NS))
        targets=[]
        for b in selected[key]:
            name=anchor(b);targets.append((b,name))
            node=nodes[b['id']];level=b['level'] if b['role']=='heading' else 1
            instruction=tc_instruction(labels[b['id']],collection,level)
            # Remove only obsolete owned TC fields; foreign user fields are immutable.
            for f in list(node.findall('w:fldSimple',NS)):
                if f in owned_fields and f.get(Q+'instr')!=instruction:node.remove(f)
            if not any(f.get(Q+'instr')==instruction for f in node.findall('w:fldSimple',NS)):
                f=el(node,'fldSimple',instr=instruction);el(el(el(f,'r'),'rPr'),'vanish',val=1)
        if keep:
            links=old.findall('.//w:hyperlink',NS)
            cached=[(n.get(Q+'anchor'),text(n),n.getparent().find('w:pPr/w:ind',NS).get(Q+'left','0') if n.getparent().find('w:pPr/w:ind',NS) is not None else '0') for n in links]
            expected=[(name,labels[b['id']],str(max(0,(b['level'] if b['role']=='heading' else 1)-1)*240)) for b,name in targets]
            if cached==expected:continue
        generated,content=container(key);generated.find('w:sdtPr/w:tag',NS).set(Q+'val',PREFIX+key+'.v3')
        # Keep a separate source title when it already exists.
        title_included=title is None or old is not None and any(t==LABELS[key] for t in old.xpath('.//w:t/text()',namespaces=NS))
        if title_included:run(paragraph(content,True,which=key),LABELS[key],True)
        start=paragraph(content,which=key);field(start,expected_instruction)
        # Place the TOC begin field in the first entry, as in the template.
        # A field-only paragraph created an unintended blank line after the title.
        for index,(b,name) in enumerate(targets):
            p=start if index==0 else paragraph(content,which=key);props=p.find('w:pPr',NS)
            level=b['level'] if b['role']=='heading' else 1
            ind=E.Element(Q+'ind');ind.set(Q+'left',str(max(0,level-1)*240));props.insert(0,ind)
            tabs=E.Element(Q+'tabs');el(tabs,'tab',val='right',leader='dot',pos=8494);props.insert(0,tabs)
            # Word requires CT_PPr sequence order, even if other readers accept
            # arbitrary XML child order. In particular spacing precedes ind.
            order={Q+name:i for i,name in enumerate(('keepNext','pageBreakBefore','tabs','spacing','ind','jc','outlineLvl'))}
            props[:]=sorted(props,key=lambda child:order.get(child.tag,len(order)))
            bold=key=='toc' and b['role'] in {'chapter','references_title','appendix_title'}
            link=el(p,'hyperlink',anchor=name,history=1);run(link,labels[b['id']],bold);el(el(p,'r'),'tab')
            field(p,'PAGEREF '+name+' \\h','?');close_field(p)
        close_field(list(content)[-1])
        if old is not None:
            pos=body.index(old);body.remove(old);body.insert(pos,generated)
        else:
            if empty is not None:title.remove(empty)
            if title is not None:
                pos=body.index(original[end-1])+1
            elif key=='toc':
                first_list=min([original.index(n) for k,(n,_) in existing.items() if k!='toc' and n is not None]+[first_chapter])
                pos=body.index(original[first_list])
            else:
                previous=None
                for predecessor in (('figures','toc') if key=='tables' else ('toc',)):
                    previous=next((n for n in body if kind(n)==predecessor),None)
                    if previous is not None:break
                    if existing[predecessor][0] is not None:
                        previous=original[existing[predecessor][1]-1];break
                pos=body.index(previous)+1 if previous is not None else body.index(original[first_chapter])
            body.insert(pos,generated)
        created.append({'kind':key,'entries':len(targets),'field':expected_instruction,'page_numbers':'UPDATE_IN_WORD'})
    return {'created':created,'anchors':anchors,'collections':collections,'updated':updated,'warnings':warnings}
