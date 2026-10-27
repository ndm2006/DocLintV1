"""Recognize an existing thesis cover as a bounded group, never generate its text.

Only ordinary cover paragraphs are returned. Logos, signatures, tables and shapes
keep their source XML. The title gap compensates for absent spacer paragraphs in
compact covers; it is not added to covers already using spacers or explicit breaks.
"""
import re
import unicodedata

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W};Q='{'+W+'}'
TYPE=re.compile(r'^(?:đồ án|khóa luận|luận văn) tốt nghiệp(?:\s*[–—-].*)?$',re.I)
SCHOOL=re.compile(r'^(?:trường\s+(?:đại học|đh)|đại học|học viện)\b',re.I)
BOUNDARY=re.compile(r'^(?:đề tài tốt nghiệp|lời cảm ơn|lời cam đoan|tóm tắt|abstract|mục lục|danh mục|chương\s+\S)',re.I)
DETAIL_ROLES={'cover_author','cover_author_label','cover_student_detail','cover_email',
              'cover_major','cover_specialization','cover_advisor','cover_place_date'}


def clean(text):return ' '.join(unicodedata.normalize('NFC',text).split()).strip()


def field_role(text):
    if re.fullmatch(r'(?:sinh viên(?:\s+thực hiện)?|họ(?:\s+và)? tên)\s*[:：]?',text,re.I):return 'cover_author_label'
    if re.match(r'^(?:sinh viên(?:\s+thực hiện)?|họ(?:\s+và)? tên)\s*[:：]\s*\S',text,re.I):return 'cover_author'
    if re.match(r'^(?:mã(?: số)?(?: sinh viên)?|mssv|lớp)\s*[:：]\s*\S',text,re.I):return 'cover_student_detail'
    if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',text):return 'cover_email'
    if re.match(r'^chuyên ngành\b',text,re.I):return 'cover_specialization'
    if re.match(r'^ngành\b',text,re.I):return 'cover_major'
    if re.match(r'^(?:giảng viên|giáo viên|cán bộ) hướng dẫn\s*[:：]',text,re.I):return 'cover_advisor'
    if re.match(r'^(?:hà nội|hồ chí minh|đà nẵng)\s*[,–—-].*\b(?:19|20)\d{2}\b',text,re.I):return 'cover_place_date'
    return None


def recognize(body,context):
    rows=[]
    for index,node in enumerate(body):
        if index>=40:break
        if node.tag!=Q+'p':continue
        text=clean(''.join(node.xpath('.//w:t/text()',namespaces=NS)))
        if not text:continue
        if BOUNDARY.match(text):break
        if context.heading_level(node) and not TYPE.match(text) and not SCHOOL.match(text):break
        if len(text)>250 or len(text.split())>40:break
        rows.append((index,node,text))
    title_position=next((i for i,(_,_,text) in enumerate(rows) if TYPE.match(text)),None)
    if title_position is None:return {},{}
    # Do not collect preceding body text just because a thesis phrase appears later.
    if any(not SCHOOL.match(text) and not re.match(r'^(?:khoa|viện|bộ môn|bộ giáo dục)\b',text,re.I)
           for _,_,text in rows[:title_position]):return {},{}
    roles={};before={};subject=False;details=False;pending_author=False
    for position,(index,node,text) in enumerate(rows):
        if position<title_position:
            roles[index]='cover_institution' if SCHOOL.match(text) else 'cover_faculty'
        elif position==title_position:roles[index]='cover_title'
        else:
            role=field_role(text)
            following=rows[position+1][2] if position+1<len(rows) else ''
            if pending_author and role is None and len(text.split())<=8:
                role='cover_author';before[index]=0;pending_author=False
            # A bare name is supported when the following email supplies context.
            if role is None and subject and text.isupper() and len(text.split())<=8 and field_role(following)=='cover_email':role='cover_author'
            if role:
                roles[index]=role;details=True
                pending_author=role=='cover_author_label'
            elif details:
                # Unlabelled values/signatures after personal fields remain untouched.
                continue
            else:
                sid=node.find('w:pPr/w:pStyle',NS)
                sid=sid.get(Q+'val','') if sid is not None else ''
                bold=context.property(node,'w:b',run=True)
                centered=context.property(node,'w:jc')
                prominent=(bold is not None and bold.get(Q+'val','1') not in {'0','false','off'}) or (centered is not None and centered.get(Q+'val')=='center') or sid.casefold()=='subtitle'
                if not prominent and not field_role(following):break
                roles[index]='cover_subject_continuation' if subject else 'cover_subject';subject=True
    # Match the source's large school-to-title gap for compact text-only covers.
    # Existing blank/logo/page/section spacers are preserved without a second gap.
    title_index=rows[title_position][0]
    if title_position and rows[title_position-1][0]+1==title_index:
        title_node=body[title_index]
        previous=body[title_index-1]
        objects=previous.xpath('.//w:drawing|.//w:pict|.//w:object|.//w:br|.//w:sectPr',namespaces=NS)
        breaks=title_node.xpath('.//w:br|.//w:sectPr|./w:pPr/w:pageBreakBefore[not(@w:val="0")]',namespaces=NS)
        if not objects and not breaks:before[title_index]=3200
    return roles,before
