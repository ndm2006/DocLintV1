"""Template-specific title recognition, including safe nested content-control headings.

Field codes, numbering, text, SDT metadata and all non-formatting nodes remain immutable.
"""
import re
import unicodedata
from .template import SPECIAL_ROLES, PROFILE
from .cover import recognize as recognize_cover, DETAIL_ROLES

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W};Q='{'+W+'}'


def block_id(index,path=()):
    return f'b{index}'+''.join(f'.{name}{number}' for name,number in path)


def locate(body,index,path=()):
    node=body[index]
    for name,number in path:node=node.findall('w:'+name,NS)[number]
    return node


def structural_path(top,node):
    chain=[]
    while node is not top:
        parent=node.getparent()
        if not isinstance(node.tag,str) or not node.tag.startswith(Q):return None
        name=node.tag.split('}')[-1]
        chain.append((name,list(parent.findall('w:'+name,NS)).index(node)));node=parent
    return list(reversed(chain))


def clean(text):return ' '.join(unicodedata.normalize('NFC',text).split()).strip().rstrip(':').strip()


def role_for_title(text,level=None):
    folded=clean(text).casefold()
    names={'đề tài tốt nghiệp':'assignment_title','mục lục':'toc_title',
           'danh mục hình':'list_figures_title','danh mục hình vẽ':'list_figures_title',
           'danh mục bảng':'list_tables_title','danh mục bảng biểu':'list_tables_title',
           'tài liệu tham khảo':'references_title'}
    if folded in names:return names[folded]
    if re.match(r'^phụ lục(?:\s+[a-z0-9]+)?(?:\s*[:–—-].*)?$',folded) and level not in (2,3,4):return 'appendix_title'
    return None


def enrich(analysis,parts,root,parser,context):
    body=root.find('w:body',NS);existing={b['id']:b for b in analysis['blocks']}
    cover_roles,cover_before=recognize_cover(body,context)
    compact_cover=any(cover_roles.get(i)=='cover_title' for i in cover_before)
    issues=[];appendix=False
    for index,top in enumerate(body):
        # Only semantically identifiable titles/captions inside SDTs or tables become nested blocks.
        candidates=[top] if top.tag==Q+'p' else top.findall('.//w:p',NS)
        for node in candidates:
            text=''.join(node.xpath('.//w:t/text()',namespaces=NS))
            if not text.strip():continue
            path=structural_path(top,node)
            if path is None:continue
            bid=block_id(index,path);block=existing.get(bid)
            level=context.heading_level(node)
            sid_node=node.find('w:pPr/w:pStyle',NS);sid=sid_node.get(Q+'val','') if sid_node is not None else ''
            if re.fullmatch(r'(?:TOC\d+|TableofFigures)',sid,re.I) and (path or node.find('.//w:hyperlink',NS) is not None):continue
            title=clean(text)
            # Exclude cached fldSimple results when determining a literal section-title prefix.
            direct=clean(''.join(node.xpath('./w:r/w:t/text()',namespaces=NS)))
            profile_roles=sorted(SPECIAL_ROLES,key=lambda r:len(r),reverse=True)
            own_role=next((r for r in profile_roles if re.fullmatch('DocLint'+''.join(w.title() for w in r.split('_'))+r'(?:_\d+)?',sid)),None)
            role=own_role or role_for_title(title,level) or role_for_title(direct,level)
            capsule=clean(text).casefold()
            before_main=not any(b['role']=='chapter' and b['index']<index for b in analysis['blocks'])
            numbered_list=context.list_numbering(node) and level is None
            if role in {'assignment_title','toc_title','list_figures_title','list_tables_title'} and (not before_main or numbered_list):role=None
            if role in {'references_title','appendix_title'} and numbered_list:role=None
            if role=='references_title' and level!=1 and not title.isupper():role=None
            if not path and index in cover_roles:role=cover_roles[index]
            if capsule=='kết luận' and level==1 and block is not None:block['section_kind']='conclusion'
            if role=='appendix_title':appendix=True
            if role=='references_title':appendix=False
            # Literal title can be wrong in the template: use following entries as evidence,
            # but never rewrite the source label without an explicit decision.
            if role in {'list_figures_title','list_tables_title'}:
                following=[]
                for sibling in list(body)[index+1:index+4]:following.extend(sibling.xpath('.//w:t/text()',namespaces=NS))
                first=clean(''.join(following)).casefold()
                inferred='list_tables_title' if re.match(r'^bảng\s+\d',first) else 'list_figures_title' if re.match(r'^hình\s+\d',first) else role
                if role!=inferred:
                    issues.append({'block_id':bid,'code':'LIST_TITLE_MISMATCH','detected':inferred,'message':'Tên danh mục không khớp các mục bên dưới. Nhận diện danh mục bảng/hình theo nội dung; giữ nguyên chữ tiêu đề để người dùng kiểm tra.'})
                    role=inferred
            nearby=list(body)[max(0,index-1):index+2]
            has_object=top.tag==Q+'tbl' or any(n.tag==Q+'tbl' or n.xpath('.//w:drawing|.//w:pict',namespaces=NS) for n in nearby)
            caption=sid.casefold()=='caption' or bool(len(title)<200 and has_object and re.match(r'^(?:hình|bảng|pt)\s+\d+(?:[.]\d+)*\b',capsule))
            if (caption or own_role in {'figure_caption','table_caption','equation_caption'}) and not re.search(r'toc|tableof',sid,re.I):
                role=own_role if own_role in {'figure_caption','table_caption','equation_caption'} else 'table_caption' if capsule.startswith('bảng') else 'equation_caption' if capsule.startswith('pt') else 'figure_caption'
            if appendix and role is None and context.list_numbering(node) and len(title)<180:
                bold=context.property(node,'w:b',run=True)
                if bold is not None and bold.get(Q+'val','1') not in {'0','false'}:role='appendix_item_title'
            if role is None:continue
            # Never modify actual drawing/math/signature objects, tracked changes or locked controls.
            unsafe=bool(node.xpath('.//w:drawing|.//w:pict|.//w:object|.//w:ins|.//w:del|.//w:footnoteReference|.//w:endnoteReference|.//w:commentReference|.//w:framePr|.//w:sym',namespaces=NS))
            unsafe=unsafe or any('officedocument/2006/math' in str(n.tag).lower() for n in node.iter())
            unsafe=unsafe or context.property(node,'w:framePr') is not None
            for ancestor in node.iterancestors():
                if ancestor.tag==Q+'sdt' and ancestor.find('w:sdtPr/w:lock',NS) is not None:unsafe=True
            if unsafe:
                if block is not None:block['semantic_kind']=role
                issues.append({'block_id':bid,'code':'TITLE_PROTECTED_OBJECT','detected':role,'message':'Đã nhận diện tiêu đề nhưng chứa đối tượng/khóa cần giữ; chưa chỉnh định dạng khối này.'})
                continue
            if block is None:
                block={'id':bid,'index':index,'path':path,'text':text,'level':0,'number_path':[],
                       'parent_block_id':None,'style_id':sid,'has_numbering':context.list_numbering(node),
                       'front_boundary_page':False,'starts_front_page':False,'front_section':None}
                analysis['blocks'].append(block);existing[bid]=block
            block.update({'role':role,'protected':False,'needs_review':False,'confidence':0.99,
                          'source':'template_title_profile','reason':'Tiêu đề/chú thích nhận diện theo Style và hồ sơ mẫu HUST.',
                          'semantic_kind':role,'level':0})
            if index in cover_before and not path:block['cover_before_twips']=cover_before[index]
            if compact_cover and not path and role in {'cover_title','cover_subject','cover_subject_continuation'} and len(title)>24:
                # A centered narrower text band balances long compact-cover titles
                # without inserting line breaks, rewriting runs or shrinking type.
                width=PROFILE['page_twips']['w']-PROFILE['margin_twips']['left']-PROFILE['margin_twips']['right']
                block['cover_indent_twips']=round(width*.15)
            block['starts_front_page']=role in {'acknowledgement_title','assignment_title','toc_title','list_figures_title','list_tables_title','references_title','appendix_title'}
            # Do not add a second page break when the original paragraph already contains one.
            if node.find('.//w:br[@w:type="page"]',NS) is not None:block['starts_front_page']=False
    analysis['blocks'].sort(key=lambda b:(b['index'],tuple(tuple(p) for p in b.get('path',[]))))
    analysis['template_heading_issues']=issues
    analysis['warnings'].extend(issue['message']+' ('+issue['block_id']+')' for issue in issues)
    if any(b['role'].startswith('cover_') and not b['protected'] for b in analysis['blocks']):
        analysis['warnings'].append('Tiêu đề bìa dùng ArnoPro theo Style Subtitle trong mẫu. Chưa xác minh phông trên máy mở Word; cần có phông hợp lệ để đối chiếu hiển thị.')
    analysis['statistics'].update({'blocks':len(analysis['blocks']),
        'protected_blocks':sum(b['protected'] for b in analysis['blocks']),
        'cover_blocks':sum(b['role'].startswith('cover_') and not b['protected'] for b in analysis['blocks']),
        'template_title_blocks':sum(b['role'] in SPECIAL_ROLES and b['role'] not in {'acknowledgement','abstract'}|DETAIL_ROLES and not b['protected'] for b in analysis['blocks'])})
    return analysis
