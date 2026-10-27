"""Contextual structure resolver: Word semantics, numbering, text and local ML.

Evidence scores describe rules, not independently calibrated precision estimates.
The classifier proposes only genuinely ambiguous short titles; it cannot edit XML.
"""
import re
import statistics
import unicodedata
from .recognizer import predict, REVISION

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
Q = '{' + W + '}'
CHAPTER = re.compile(r'^chương\s+(\d+|[IVXLCDM]+)(?=[\s.:–—-]|$)', re.I)
NUMBERED = re.compile(r'^(\d+(?:\.\d+)+)\.?\s+\S')
SINGLE = re.compile(r'^(\d{1,2})[.)]?\s+(.+)')
FRONT = re.compile(r'^(?:lời cảm ơn|lời cam đoan|tóm tắt(?: nội dung đồ án)?|abstract|mục lục|danh mục(?: hình vẽ| bảng biểu| hình| bảng)?|tài liệu tham khảo|phụ lục)(?:\s*[:–—-].*)?$', re.I)
FRONT_TITLES = {'lời cảm ơn':'acknowledgement','tóm tắt':'abstract','tóm tắt đồ án':'abstract','tóm tắt nội dung đồ án':'abstract','tóm tắt nội dung đồ án tốt nghiệp':'abstract','abstract':'abstract'}
SIGNOFF = re.compile(r'^(?:sinh viên thực hiện|người thực hiện|giáo viên hướng dẫn)(?=\s*(?:$|ký|:))|^ký(?: và)? ghi rõ họ tên\b',re.I)
CAPTION = re.compile(r'^(?:hình|bảng|biểu đồ|sơ đồ|phương trình)\s+\d+(?:[.\-]\d+)*\b', re.I)


def normalize(text):
    return unicodedata.normalize('NFC', text).strip()


def roman(value):
    if value.isdigit():
        return int(value)
    total, previous = 0, 0
    for char in reversed(value.upper()):
        current = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}.get(char, 0)
        total += -current if current < previous else current
        previous = max(previous, current)
    return total


class WordContext:
    def __init__(self, parts, parser):
        self.styles = {}
        self.defaults = None
        self.default_style = 'Normal'
        self.numbering = {}
        if 'word/styles.xml' in parts:
            root = parser(parts['word/styles.xml'])
            self.styles = {s.get(Q+'styleId'): s for s in root.findall('w:style', NS)}
            self.defaults = root.find('w:docDefaults', NS)
            for sid,style in self.styles.items():
                if style.get(Q+'type')=='paragraph' and style.get(Q+'default') in {'1','true'}:self.default_style=sid
        if 'word/numbering.xml' in parts:
            root = parser(parts['word/numbering.xml'])
            abstracts = {n.get(Q+'abstractNumId'): n for n in root.findall('w:abstractNum', NS)}
            for num in root.findall('w:num', NS):
                aid = num.find('w:abstractNumId', NS)
                if aid is not None:
                    self.numbering[num.get(Q+'numId')] = abstracts.get(aid.get(Q+'val'))

    def chain(self, style):
        seen = set()
        while style in self.styles and style not in seen:
            seen.add(style)
            node = self.styles[style]
            yield node
            base = node.find('w:basedOn', NS)
            style = base.get(Q+'val') if base is not None else None

    def property(self, paragraph, path, run=False):
        if run:
            direct = paragraph.find('w:r/w:rPr/'+path, NS)
        else:
            direct = paragraph.find('w:pPr/'+path, NS)
        if direct is not None:
            return direct
        style = paragraph.find('w:pPr/w:pStyle', NS)
        for node in self.chain(style.get(Q+'val') if style is not None else self.default_style):
            value = node.find(('w:rPr/' if run else 'w:pPr/')+path, NS)
            if value is not None:
                return value
        if self.defaults is not None:
            return self.defaults.find(('w:rPrDefault/w:rPr/' if run else 'w:pPrDefault/w:pPr/')+path, NS)
        return None

    def heading_level(self, paragraph):
        style = paragraph.find('w:pPr/w:pStyle', NS)
        sid = style.get(Q+'val') if style is not None else ''
        node = self.styles.get(sid)
        names = sid
        if node is not None:
            for path in ('w:name', 'w:aliases'):
                value = node.find(path, NS)
                if value is not None:
                    names += ' '+value.get(Q+'val', '')
        if re.search(r'toc|tableof|caption', names, re.I):
            return None
        outline = self.property(paragraph, 'w:outlineLvl')
        if outline is not None and outline.get(Q+'val', '').isdigit():
            level = int(outline.get(Q+'val'))+1
            if level <= 4:
                return level
        heading = re.search(r'(?:heading|tiêu đề|doclintheading)\s*([1-4])', names, re.I)
        if heading:
            return int(heading.group(1))
        if re.search(r'\bchuong\b', names, re.I):
            return 1
        alias = re.search(r'\bcap\s+([1-3])\b', names, re.I)
        if alias:return int(alias.group(1))+1
        num_id=self.property(paragraph,'w:numPr/w:numId')
        ilvl=self.property(paragraph,'w:numPr/w:ilvl')
        abstract=self.numbering.get(num_id.get(Q+'val')) if num_id is not None else None
        depth=ilvl.get(Q+'val','0') if ilvl is not None else '0'
        if abstract is not None and depth.isdigit() and int(depth)<4:
            root_level=abstract.find('w:lvl[@w:ilvl="0"]/w:lvlText',NS)
            current=abstract.find('w:lvl[@w:ilvl="'+depth+'"]/w:pStyle',NS)
            if (root_level is not None and re.match(r'^chương\s+%1',normalize(root_level.get(Q+'val','')),re.I)) or (current is not None and re.match(r'^heading[1-4]$',current.get(Q+'val',''),re.I)):
                return int(depth)+1
        return None

    def list_numbering(self, paragraph):
        value = self.property(paragraph, 'w:numPr/w:numId')
        return value is not None and value.get(Q+'val') not in {'0', None}


def analyze(parts, root, parser):
    context = WordContext(parts, parser)
    rows = []
    field_depth=0
    body = root.find('w:body', NS)
    multicolumn_positions=set();section_start=0
    for index,node in enumerate(body):
        section=node.find('w:pPr/w:sectPr',NS) if node.tag==Q+'p' else node if node.tag==Q+'sectPr' else None
        if section is not None:
            cols=section.find('w:cols',NS)
            if cols is not None and cols.get(Q+'num','1')!='1':multicolumn_positions.update(range(section_start,index+1))
            section_start=index+1
    for index, node in enumerate(body):
        field_open=field_depth>0
        for field in node.findall('.//w:fldChar',NS):
            kind=field.get(Q+'fldCharType')
            if kind=='begin':field_depth+=1
            elif kind=='end':field_depth=max(0,field_depth-1)
        if node.tag != Q+'p':
            continue
        text = ''.join(node.xpath('.//w:t/text()', namespaces=NS))
        if not text.strip():
            continue
        clean = normalize(text)
        style = node.find('w:pPr/w:pStyle', NS)
        sid = style.get(Q+'val', '') if style is not None else ''
        level = context.heading_level(node)
        size_node = context.property(node, 'w:sz', run=True)
        try:
            size = float(size_node.get(Q+'val'))/2 if size_node is not None else 13
        except (TypeError, ValueError):
            size = 13
        bold_node = context.property(node, 'w:b', run=True)
        bold = bold_node is not None and bold_node.get(Q+'val', '1') not in {'0', 'false', 'off'}
        chapter = CHAPTER.match(clean)
        numbered = NUMBERED.match(clean)
        path = tuple(map(int, numbered.group(1).split('.'))) if numbered else ()
        shape = len(clean) <= 160 and len(clean.split()) <= 22 and not clean.endswith(('.', ';', ':', '?', '!'))
        structural_level = len(path) if path else level
        # Keep rich objects and their formatting, but bookmarks do not disqualify headings.
        rich = bool(node.xpath('.//w:drawing|.//w:pict|.//w:object|.//w:fldChar|.//w:fldSimple|.//w:instrText|.//w:hyperlink|.//w:sdt|.//w:ins|.//w:del|.//w:footnoteReference|.//w:endnoteReference|.//w:commentReference|.//w:framePr|.//w:sym|.//w:customXml|.//w:altChunk|.//w:smartTag', namespaces=NS))
        rich = rich or any('officedocument/2006/math' in str(child.tag).lower() for child in node.iter())
        rich = rich or field_open
        rich = rich or node.find('w:pPr/w:sectPr', NS) is not None or (node.find('w:bookmarkStart', NS) is not None and not (level or chapter or path))
        numbered_list = context.list_numbering(node) and level is None
        protected = index in multicolumn_positions or rich or numbered_list or bool(CAPTION.match(clean)) or bool(re.search(r'toc|caption|tableof|code', sid, re.I)) or (structural_level is not None and structural_level > 3 and level != 4)
        if context.property(node, 'w:framePr') is not None:
            protected = True
        # A section break can be retained while changing safe paragraph formatting.
        rows.append({'id': f'b{index}', 'index': index, 'text': text, 'clean': clean,
                     'style_id': sid, 'style_level': level, 'font_size': size, 'bold': bold,
                     'shape': shape, 'chapter_match': chapter, 'number_path': path,
                     'protected': protected, 'numbered_list': numbered_list})
    typical_size = statistics.median([b['font_size'] for b in rows if len(b['clean']) > 140] or [13])
    # A bare "1 Introduction" needs corroborating children, never just a leading number.
    child_roots = {b['number_path'][0] for b in rows if b['number_path']}
    started = False
    special = False
    chapter_id = None
    chapter_number = None
    chapter_count = 0
    seen_chapters=set()
    uncertain_parents=set()
    parents = {}
    numbered_parents = {}
    result = []
    warnings = []
    front_region=None;front_title=None;front_groups=[];ack_on_page=False
    for position, row in enumerate(rows):
        text = row['clean']
        path = row['number_path']
        level = len(path) if path else row['style_level']
        explicit = row['chapter_match']
        single = SINGLE.match(text)
        bare_chapter = bool(single and row['shape'] and int(single.group(1)) in child_roots and (row['bold'] or row['font_size'] > typical_size or re.match(r'^\d+\s', text)))
        is_chapter = bool((explicit and len(text)<=160 and len(text.split())<=22) or level == 1 or bare_chapter)
        # Appendix/references are retained even if someone assigned Heading 1 to them.
        front = bool(FRONT.match(text)) and not row['numbered_list']
        front_kind=FRONT_TITLES.get(text.casefold().rstrip(':').strip()) if not started else None
        starts_front_page=False
        boundary_page=bool(front_groups and not started and not front_kind and len(text)<100 and re.match(r'^(?:mục lục|danh mục(?: hình| bảng))\b',text,re.I))
        if front_kind:
            starts_front_page=front_kind=='acknowledgement' or not ack_on_page
            front_region=front_kind;front_title=row['id']
            front_groups.append({'kind':front_kind,'title_block_id':front_title,'block_ids':[],'word_count':0})
            if front_kind=='acknowledgement':ack_on_page=True
        elif front or is_chapter or SIGNOFF.match(text) or re.search(r'toc|tableof',row['style_id'],re.I) or (len(text)<100 and re.match(r'^(?:mục lục|danh mục(?: hình| bảng)|tài liệu tham khảo|phụ lục)\b',text,re.I)):
            front_region=None;front_title=None
            if front or is_chapter:ack_on_page=False
        if front:
            special = True
        if is_chapter and not front and not row['protected']:
            started = True
            special = False
        role, confidence, source, review, reason = 'keep', 1.0, 'protected', False, 'Giữ nguyên vùng đặc biệt hoặc phần đầu.'
        parent_id = None
        numbering_path = list(path)
        if not row['protected'] and started and not special:
            if is_chapter:
                role, level, source, confidence = 'chapter', 1, 'word_style' if row['style_level'] == 1 else 'explicit_chapter' if explicit else 'numbered_context', 0.99
                chapter_count += 1
                previous_chapter=chapter_number
                chapter_number = roman(explicit.group(1)) if explicit else int(single.group(1)) if single else chapter_count
                chapter_id = row['id']
                parents = {1: row['id']}
                numbered_parents = {(chapter_number,): row['id']}
                numbering_path = [chapter_number]
                reason = 'Chương được xác định từ cấu trúc Word hoặc nhãn chương có ngữ cảnh.'
                if chapter_number in seen_chapters or (previous_chapter is not None and chapter_number != previous_chapter+1) or (explicit and row['style_level'] not in {None,1}):
                    review=True;confidence=0.55;reason='Số chương trùng, nhảy thứ tự hoặc mâu thuẫn Style; cần xác nhận.'
                    uncertain_parents.add(row['id'])
                seen_chapters.add(chapter_number)
            elif path or row['style_level'] in (2, 3, 4):
                level = len(path) if path else row['style_level']
                role, source, confidence = 'heading', 'numbered_context' if path else 'word_style', 0.98
                parent_id = numbered_parents.get(path[:-1]) if path else parents.get(level-1)
                wrong_chapter = bool(path and path[0] != chapter_number)
                if not row['shape'] and row['style_level'] is None:
                    role, review, confidence = 'keep', True, 0.55
                    reason = 'Chuỗi số có thể là danh sách hoặc câu văn; mặc định giữ nguyên.'
                elif wrong_chapter or parent_id is None or parent_id in uncertain_parents or (path and path in numbered_parents) or (path and row['style_level'] is not None and row['style_level'] != len(path)):
                    review, confidence = True, 0.55
                    reason = 'Thiếu hoặc mâu thuẫn cấp cha; giữ nguyên nếu chưa xác định được cấu trúc.'
                else:
                    reason = 'Đề mục có cấp cha hợp lệ, tự động áp dụng.'
                if review:uncertain_parents.add(row['id'])
                if not review:
                    parents[level] = row['id']
                    for deeper in list(parents):
                        if deeper > level:
                            parents.pop(deeper)
                    if path:
                        numbered_parents[path] = row['id']
            else:
                # ML is an advisory tie-breaker for unnumbered, short title-like text.
                ml_role, score = predict(text, row['bold'], row['font_size'])
                title_like = row['shape'] and 2 <= len(text.split()) <= 16
                next_long = position+1 < len(rows) and len(rows[position+1]['clean']) > 140
                if title_like and (row['bold'] or row['font_size'] >= typical_size+2 or (ml_role == 'heading' and next_long)):
                    role, level, source, confidence, review = 'heading', 2, 'ml_layout_candidate', score, True
                    parent_id = chapter_id
                    reason = 'Tiêu đề không đánh số còn mơ hồ; cần xác nhận một lần.'
                elif re.match(r'^\d+[.)]\s', text):
                    role, source, reason = 'keep', 'manual_list', 'Giữ nhãn danh sách nhập tay, không đổi thành đề mục.'
                else:
                    role, level, source, confidence = 'body', 0, 'body_context', 0.95
                    reason = 'Thân bài trong chương đã xác định.'
        protected = row['protected'] or not started or special
        if protected:
            role, review = 'keep', False
        if front_kind or front_region:
            # Only safe text is formatted; signatures, fields, rich objects and lists stay locked.
            if not row['protected']:
                role=front_kind+'_title' if front_kind else front_region
                level=0;review=False;protected=False;confidence=0.99;source='front_matter_context'
                parent_id=None if front_kind else front_title
                reason='Tiêu đề phần đầu theo mẫu HUST.' if front_kind else 'Nội dung lời cảm ơn/tóm tắt theo tiêu đề và ranh giới phần.'
            if not front_kind:
                front_groups[-1]['block_ids'].append(row['id'])
                front_groups[-1]['word_count']+=len(text.split())
        result.append({'id': row['id'], 'index': row['index'], 'text': row['text'], 'role': role,
                       'level': level or 0, 'confidence': confidence, 'needs_review': review,
                       'protected': protected, 'reason': reason, 'source': source,
                       'parent_block_id': parent_id, 'number_path': numbering_path,
                       'front_section':front_region,'starts_front_page':starts_front_page,'front_boundary_page':boundary_page,
                       'style_id': row['style_id'], 'has_numbering': context.list_numbering(body[row['index']])})
    for group in front_groups:
        count=group['word_count'];kind=group['kind']
        group['count_method']='Số đơn vị phân cách bởi khoảng trắng; quy ước kỹ thuật, không tự coi là chuẩn đếm chính thức.'
        group['status']='PASS' if (100<=count<=150 if kind=='acknowledgement' else count<=300) else 'WARNING'
        group['layout']='NOT_CHECKED'
        if group['status']=='WARNING':
            warnings.append(('Lời cảm ơn' if kind=='acknowledgement' else 'Tóm tắt')+f' tại {group["title_block_id"]}: {count} đơn vị theo khoảng trắng; '+('khuyến nghị 100–150.' if kind=='acknowledgement' else 'giới hạn 300.'))
    if front_groups:warnings.append('Đã định dạng phần lời cảm ơn/tóm tắt an toàn; chưa xác minh hai phần nằm trong một trang, không tự rút gọn nội dung hoặc giảm cỡ chữ.')
    if not started:
        warnings.append('Không tìm thấy cấu trúc chương đáng tin cậy: không tự nhận đây là đồ án, giữ nguyên tài liệu.')
    warnings.extend(['Bảng, ảnh, công thức và vùng phức tạp được bảo toàn; không tự sửa dữ liệu học thuật.',
                     'Chưa dựng PDF hoặc xác minh phân trang, mục lục và trường trên Microsoft Word.',
                     'Nhận diện kết hợp cấu trúc Word, quy tắc quan hệ và ML nội bộ; chưa có số đo trên tập đồ án độc lập.'])
    return {'blocks': result, 'model_revision': REVISION,
            'recognizer_revision': 'structure-context-0.3', 'front_matter':front_groups, 'warnings': warnings,
            'statistics': {'blocks': len(result), 'auto_chapters': sum(b['role']=='chapter' and not b['needs_review'] for b in result),
                           'auto_headings': sum(b['role']=='heading' and not b['needs_review'] for b in result),
                           'review_blocks': sum(b['needs_review'] for b in result),
                           'protected_blocks': sum(b['protected'] for b in result),
                           'front_matter_blocks':sum(b['role'] in {'acknowledgement_title','acknowledgement','abstract_title','abstract'} and not b['protected'] for b in result)}}
