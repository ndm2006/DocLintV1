"""Build deterministic, anonymous OOXML fixtures. No Word installation required.

Labels are authored alongside content, not inferred from the classifier.
Run from the repository root: python -m scripts.make_complex_fixtures
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import zlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from lxml import etree as E

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'w': W, 'r': R, 'm': M,
      'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'}
DEST = Path(__file__).resolve().parents[1] / 'tests/fixtures/complex'


def el(qname, parent=None, **attrs):
    prefix, local = qname.split(':')
    node = E.Element(f'{{{NS[prefix]}}}{local}')
    for key, value in attrs.items():
        node.set(f'{{{W}}}{key}', str(value))
    if parent is not None:
        parent.append(node)
    return node


def xml(node):
    return E.tostring(node, encoding='UTF-8', xml_declaration=True, standalone=True)


def zip_bytes(parts):
    out = io.BytesIO()
    with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(parts.items()):
            info = ZipInfo(name, date_time=(2026, 10, 27, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)
    return out.getvalue()


def diagram_png():
    """A small raster architecture diagram, with valid per-chunk CRCs."""
    width, height = 600, 180
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            color = (246, 249, 244)
            for left in (25, 225, 425):
                if left <= x < left + 150 and 45 <= y < 135:
                    color = (39, 115, 90) if x < left + 4 or x >= left + 146 or y < 49 or y >= 131 else (222, 237, 216)
            if (175 <= x < 225 or 375 <= x < 425) and 87 <= y <= 92:
                color = (39, 115, 90)
            raw.extend(color)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw))) + chunk(b'IEND', b''))


class Fixture:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.root = E.Element(f'{{{W}}}document', nsmap=NS)
        self.body = el('w:body', self.root)
        self.labels = []
        self.parts = {}
        self.relationships = E.Element(f'{{{REL}}}Relationships', nsmap={None: REL})
        self.overrides = {}
        self.image_id = 0
        self.relationship('styles', 'styles.xml', 'styles')
        self.relationship('numbering', 'numbering.xml', 'numbering')
        self.parts['word/styles.xml'] = xml(E.fromstring(f'''<w:styles xmlns:w="{W}">
          <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
          <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:rPr><w:i/><w:sz w:val="24"/></w:rPr></w:style>
          <w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/><w:basedOn w:val="Normal"/></w:style>
        </w:styles>'''))
        self.parts['word/numbering.xml'] = xml(E.fromstring(f'''<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''))

    def relationship(self, rid, target, kind, external=False):
        attrs = {'Id': rid, 'Target': target, 'Type': R + '/' + kind}
        if external:
            attrs['TargetMode'] = 'External'
        E.SubElement(self.relationships, f'{{{REL}}}Relationship', **attrs)

    def run(self, parent, text, font='Arial', size=11, bold=False):
        run = el('w:r', parent)
        props = el('w:rPr', run)
        el('w:rFonts', props, ascii=font, hAnsi=font)
        if bold:
            el('w:b', props)
        el('w:sz', props, val=int(size * 2))
        t = el('w:t', run)
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = text
        return run

    def paragraph(self, text, role='body', *, protected=False, note='', size=11,
                  bold=False, font='Arial', style=None, parent=None):
        parent = self.body if parent is None else parent
        p = el('w:p', parent)
        props = el('w:pPr', p)
        if style:
            el('w:pStyle', props, val=style)
        el('w:spacing', props, before=0, after=180, line=360, lineRule='auto')
        el('w:jc', props, val='left')
        self.run(p, text, font, size, bold)
        if parent is self.body:
            self.labels.append({'id': f'b{len(self.body)-1}', 'text': text, 'role': role,
                                'protected': protected, 'note': note})
        return p

    def chapter(self, n, title):
        return self.paragraph(f'CHƯƠNG {n}. {title}', 'chapter', size=16, bold=True)

    def section(self, landscape=False):
        sec = el('w:sectPr')
        attrs = {'w': 16838 if landscape else 11906, 'h': 11906 if landscape else 16838}
        if landscape:
            attrs['orient'] = 'landscape'
        el('w:pgSz', sec, **attrs)
        el('w:pgMar', sec, top=900, right=900, bottom=900, left=1100, header=500, footer=500, gutter=0)
        return sec

    def table(self, rows, merged=False, nested=False, width=9000):
        table = el('w:tbl', self.body)
        props = el('w:tblPr', table)
        el('w:tblW', props, w=width, type='dxa')
        borders = el('w:tblBorders', props)
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            el('w:' + side, borders, val='single', sz=4, color='7F9C89')
        grid = el('w:tblGrid', table)
        for _ in range(3):
            el('w:gridCol', grid, w=width // 3)
        for i in range(rows):
            row = el('w:tr', table)
            if i == 0:
                el('w:tblHeader', el('w:trPr', row))
            for j in range(3):
                if merged and i == 0 and j == 1:
                    continue
                cell = el('w:tc', row)
                cp = el('w:tcPr', cell)
                el('w:tcW', cp, w=width // 3 * (2 if merged and i == 0 and j == 0 else 1), type='dxa')
                if merged and i == 0 and j == 0:
                    el('w:gridSpan', cp, val=2)
                if merged and i in (1, 2) and j == 0:
                    el('w:vMerge', cp, **({'val': 'restart'} if i == 1 else {}))
                if merged and i == 2 and j == 0:
                    el('w:p', cell)
                    continue
                self.paragraph(f'Ô {i+1}.{j+1}: ' + ('Chỉ tiêu kiểm thử' if i == 0 else f'Giá trị {i*13+j},50 ± 0,05'), parent=cell)
                if nested and i == 3 and j == 1:
                    sub = el('w:tbl', cell)
                    el('w:tblW', el('w:tblPr', sub), w=1800, type='dxa')
                    el('w:gridCol', el('w:tblGrid', sub), w=1800)
                    nested_cell = el('w:tc', el('w:tr', sub))
                    self.paragraph('Bảng lồng: không làm mất ô này', parent=nested_cell)
                    el('w:p', cell)  # A cell containing a nested table must end in a paragraph.
        return table

    def image(self):
        self.image_id += 1
        rid = f'image{self.image_id}'
        self.relationship(rid, 'media/architecture.png', 'image')
        self.parts['word/media/architecture.png'] = diagram_png()
        p = self.paragraph('Sơ đồ: tiếp nhận → kiểm chứng → công bố. ', 'keep', protected=True,
                           note='Ảnh inline trộn chữ: giữ toàn bộ đoạn, kích thước và dữ liệu ảnh.')
        drawing = el('w:drawing', el('w:r', p))
        inline = el('wp:inline', drawing)
        # DrawingML attributes are unqualified, unlike WordprocessingML attributes.
        extent = el('wp:extent', inline); extent.set('cx', '4572000'); extent.set('cy', '1371600')
        docpr = el('wp:docPr', inline); docpr.set('id', str(self.image_id)); docpr.set('name', 'Sơ đồ hệ thống')
        graphic = el('a:graphic', inline)
        data = el('a:graphicData', graphic); data.set('uri', NS['pic'])
        pic = el('pic:pic', data)
        nv = el('pic:nvPicPr', pic)
        cn = el('pic:cNvPr', nv); cn.set('id', '0'); cn.set('name', 'architecture.png')
        el('pic:cNvPicPr', nv)
        fill = el('pic:blipFill', pic)
        el('a:blip', fill).set(f'{{{R}}}embed', rid)
        el('a:fillRect', el('a:stretch', fill))
        sp = el('pic:spPr', pic)
        transform = el('a:xfrm', sp)
        offset = el('a:off', transform); offset.set('x', '0'); offset.set('y', '0')
        ext = el('a:ext', transform); ext.set('cx', '4572000'); ext.set('cy', '1371600')
        geom = el('a:prstGeom', sp); geom.set('prst', 'rect'); el('a:avLst', geom)

    def math(self):
        p = self.paragraph('Sai số được tính theo công thức: ', 'keep', protected=True,
                           note='Đoạn có chữ + OMML phải được bảo vệ, không đổi công thức thành chữ/ảnh.')
        math = el('m:oMath', p)
        frac = el('m:f', math)
        for name, text in [('num', 'a + b'), ('den', 'n − 1')]:
            el('m:t', el('m:r', el('m:' + name, frac))).text = text
        el('m:t', el('m:r', math)).text = ' = ε'

    def field(self, text, instruction, style=None):
        p = self.paragraph(text,'toc_title' if text=='MỤC LỤC' else 'keep',protected=text!='MỤC LỤC',style=style,note='Định dạng tiêu đề nếu nhận hỗ trợ; giữ nguyên field và bộ nhớ đệm.')
        field = el('w:fldSimple', p, instr=instruction)
        self.run(field, ' [chưa cập nhật trường]')
        return p

    def header_footer(self):
        for name, text in [('header', 'DOCLINT · DỮ LIỆU KIỂM THỬ TỔNG HỢP'), ('footer', 'Trang ' )]:
            root = el('w:' + name.replace('header', 'hdr').replace('footer', 'ftr'))
            p = self.paragraph(text, parent=root, size=9)
            if name == 'footer':
                self.run(el('w:fldSimple', p, instr='PAGE'), '?', size=9)
            self.parts[f'word/{name}1.xml'] = xml(root)
            self.relationship(name, f'{name}1.xml', name)
            self.overrides[f'/word/{name}1.xml'] = f'application/vnd.openxmlformats-officedocument.wordprocessingml.{name}+xml'
        self.with_header_footer = True

    def finish(self, landscape=False):
        sec = self.section(landscape)
        if getattr(self, 'with_header_footer', False):
            for name in ('footer', 'header'):
                ref = el('w:' + name + 'Reference', type='default')
                ref.set(f'{{{R}}}id', name)
                sec.insert(0, ref)
        self.body.append(sec)
        self.parts['word/document.xml'] = xml(self.root)
        self.parts['word/_rels/document.xml.rels'] = xml(self.relationships)
        root_rels = E.Element(f'{{{REL}}}Relationships', nsmap={None: REL})
        E.SubElement(root_rels, f'{{{REL}}}Relationship', Id='document', Target='word/document.xml', Type=R+'/officeDocument')
        self.parts['_rels/.rels'] = xml(root_rels)
        types = E.Element(f'{{{CT}}}Types', nsmap={None: CT})
        E.SubElement(types, f'{{{CT}}}Default', Extension='rels', ContentType='application/vnd.openxmlformats-package.relationships+xml')
        E.SubElement(types, f'{{{CT}}}Default', Extension='png', ContentType='image/png')
        self.overrides.update({'/word/document.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
                               '/word/styles.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml',
                               '/word/numbering.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml'})
        for name, content_type in sorted(self.overrides.items()):
            E.SubElement(types, f'{{{CT}}}Override', PartName=name, ContentType=content_type)
        self.parts['[Content_Types].xml'] = xml(types)
        for label in self.labels:
            node=self.body[int(label['id'][1:])]
            label['text']=''.join(node.xpath('.//w:t/text()',namespaces=NS))
        data = zip_bytes(self.parts)
        return data, {'file': self.name + '.docx', 'title': self.title, 'sha256': hashlib.sha256(data).hexdigest(),
                      'labels': self.labels, 'expected_status': 'PARTIAL', 'landscape': landscape}


PARAGRAPHS = [
    'Hệ thống quản lý mượn thiết bị được xây dựng để theo dõi vòng đời của thiết bị trong phòng thực hành. Mỗi yêu cầu phải ghi nhận người mượn, thời điểm tiếp nhận và trạng thái bàn giao; dữ liệu trong tài liệu này hoàn toàn giả lập.',
    'Trong khảo sát ban đầu, nhóm xác định ba nhóm thao tác thường xuyên gồm đăng ký, phê duyệt và trả thiết bị. Những thao tác này có ràng buộc khác nhau nên cần tách biệt yêu cầu nghiệp vụ với chi tiết triển khai.',
    'Các phép đo chỉ có ý nghĩa khi giữ nguyên điều kiện thử nghiệm. Độ trễ được ghi theo mili giây, dung lượng theo MiB và thời điểm theo múi giờ đã công bố; không thay đổi đơn vị để làm đẹp kết quả.',
    'Tính toàn vẹn được kiểm tra theo từng vị trí: đoạn văn, ô bảng, đối tượng hình ảnh và biểu thức toán học. Việc nối tất cả chữ thành một chuỗi không đủ để phát hiện dữ liệu đã chuyển nhầm ô.',
    'Trường hợp không đủ căn cứ để suy luận cấu trúc, hệ thống cần giữ nội dung gốc và yêu cầu xác nhận. Một dòng ngắn được in đậm có thể là đề mục, nhưng cũng có thể chỉ là ghi chú của tác giả.',
    'Giới hạn của phương pháp phải được trình bày cùng kết quả. Các số liệu 125,50; 0,05 và 98% dưới đây là dữ liệu thử tổng hợp, không phải kết quả đánh giá mô hình hoặc cam kết chất lượng sản phẩm.',
]


def thesis():
    f = Fixture('01_do_an_tong_hop', 'Đồ án tổng hợp: bìa, mục lục, 3 chương, bảng, ảnh và công thức')
    for text in ['TRƯỜNG ĐẠI HỌC KIỂM THỬ', 'ĐỒ ÁN TỐT NGHIỆP — TÀI LIỆU GIẢ LẬP', 'HỆ THỐNG QUẢN LÝ MƯỢN THIẾT BỊ', 'Sinh viên: Người kiểm thử A · Mã: TEST-001']:
        role='cover_institution' if text.startswith('TRƯỜNG ') else 'cover_title' if text.startswith('ĐỒ ÁN ') else 'keep'
        f.paragraph(text,role,protected=role=='keep',size=18,bold=True,note='Tiêu đề trường/loại đồ án theo mẫu; thông tin bìa chưa đủ căn cứ vẫn giữ.')
    f.paragraph('LỜI CẢM ƠN', 'acknowledgement_title', note='TNR 13, đậm, căn giữa, trước 24 pt theo mẫu.')
    f.paragraph(PARAGRAPHS[0], 'acknowledgement')
    f.paragraph('TÓM TẮT', 'abstract_title', note='TNR 13, đậm, căn giữa, trước 48 pt theo mẫu.')
    f.paragraph('Tài liệu này mô phỏng đồ án thực tế để kiểm tra định dạng, không chứa thông tin cá nhân.', 'abstract')
    f.field('MỤC LỤC', ' TOC \\o "1-3" \\h \\z \\u ', style='TOC1')
    for chapter, title in enumerate(['TỔNG QUAN', 'PHÂN TÍCH VÀ THIẾT KẾ', 'THỰC NGHIỆM VÀ ĐÁNH GIÁ'], 1):
        f.chapter(chapter, title)
        for section in range(1, 4):
            f.paragraph(f'{chapter}.{section} ' + ['Bối cảnh và phạm vi', 'Phương pháp thực hiện', 'Phân tích kết quả'][section-1], 'heading', bold=section != 2)
            for index, text in enumerate(PARAGRAPHS):
                f.paragraph(f'[{chapter}.{section}-{index+1}] {text}', size=[10, 11, 14, 15][index % 4], font=['Arial', 'Calibri', 'Courier New'][index % 3])
        if chapter == 1:
            f.paragraph('Bảng 1.1. Dữ liệu mượn thiết bị', 'table_caption', style='Caption')
            f.table(9)
        if chapter == 2:
            f.image(); f.paragraph('Hình 2.1. Luồng xử lý giả lập', 'figure_caption', style='Caption'); f.math()
    f.paragraph('TÀI LIỆU THAM KHẢO', 'references_title')
    f.paragraph('[1] Tài liệu mô phỏng do nhóm kiểm thử tạo; không phải nguồn học thuật thực tế.', 'keep', protected=True)
    f.header_footer()
    return f.finish()


def ambiguous():
    f = Fixture('02_de_muc_mo_ho', 'Đề mục mơ hồ, danh sách, cấp sâu và cấp cha còn thiếu')
    f.chapter(1, 'NHẬN DIỆN CẤU TRÚC')
    f.paragraph('1.1 Yêu cầu hệ thống', 'heading')
    f.paragraph('1.1.1 Yêu cầu chức năng', 'heading')
    f.paragraph('1.1.1.1 Chi tiết vượt cấp tự động', 'keep', protected=True, note='Mức sâu phải giữ, không tự hạ cấp hoặc xóa.')
    f.paragraph('Lưu ý quan trọng', 'keep', bold=True, note='Dòng in đậm không mặc nhiên là đề mục; chọn Giữ nguyên khi được hỏi.')
    f.paragraph('1. Sao lưu dữ liệu trước khi thao tác.', 'keep', note='Số nhập tay của danh sách, không phải chương.')
    for text in ['Đăng ký tài khoản kiểm thử.', 'Chọn thiết bị cần mượn.', 'Xác nhận thời gian hoàn trả.']:
        p = f.paragraph(text, 'keep', protected=True, note='Danh sách đánh số tự động phải giữ numbering.')
        props = p.find(f'{{{W}}}pPr'); numbering = el('w:numPr'); props.insert(0, numbering)
        el('w:ilvl', numbering, val=0); el('w:numId', numbering, val=1)
    f.paragraph(PARAGRAPHS[4])
    f.chapter(2, 'TÌNH HUỐNG NGOẠI LỆ')
    f.paragraph('2.3.1 Mục chưa có cha 2.3', 'keep', note='Cố ý thiếu cha: chọn Giữ nguyên, không tự thêm 2.3.')
    f.paragraph('2.1 Phạm vi được xác nhận', 'heading')
    f.paragraph(PARAGRAPHS[3])
    return f.finish()


def tables():
    f = Fixture('03_bang_gop_section_ngang', 'Bảng gộp, bảng lồng, bảng dài và section ngang')
    f.chapter(1, 'DỮ LIỆU VÀ BỐ CỤC')
    f.paragraph('1.1 Bảng gộp và bảng lồng', 'heading')
    f.paragraph(PARAGRAPHS[3]); f.table(6, merged=True, nested=True)
    f.image()
    p = f.paragraph('Ranh giới section: trang dọc chuyển sang trang ngang.', 'keep', protected=True,
                    note='Giữ ngắt section, không xóa hoặc ép tất cả trang về dọc.')
    p.find(f'{{{W}}}pPr').append(f.section())
    f.chapter(2, 'BẢNG THỐNG KÊ TRANG NGANG')
    f.paragraph('2.1 Bảng dài có hàng tiêu đề lặp', 'heading'); f.table(46, width=13000)
    f.paragraph(PARAGRAPHS[5]); f.header_footer()
    return f.finish(landscape=True)


def academic():
    f = Fixture('04_tham_chieu_cong_thuc', 'OMML, bookmark, hyperlink, footnote, endnote, comment và track changes')
    f.chapter(1, 'ĐỐI TƯỢNG HỌC THUẬT'); f.paragraph('1.1 Bảo toàn đối tượng', 'heading')
    f.math(); f.image()
    p = f.paragraph('Vị trí tham chiếu gốc: REF_TEST_01', 'keep', protected=True)
    p.insert(1, el('w:bookmarkStart', id=1, name='REF_TEST_01')); el('w:bookmarkEnd', p, id=1)
    f.field('Tham chiếu tới vị trí gốc: ', ' REF REF_TEST_01 \\h ')
    f.relationship('link1', 'https://example.org/doclint-test', 'hyperlink', external=True)
    p = f.paragraph('Liên kết tham khảo: ', 'keep', protected=True)
    link = el('w:hyperlink', p); link.set(f'{{{R}}}id', 'link1'); f.run(link, 'example.org — dữ liệu thử')
    for name, ref in [('footnotes', 'footnoteReference'), ('endnotes', 'endnoteReference')]:
        singular = name[:-1]
        p = f.paragraph(f'Đoạn có {singular} cần bảo toàn.', 'keep', protected=True)
        el('w:' + ref, el('w:r', p), id=1)
        root = el('w:' + name)
        for number, kind in [(-1, 'separator'), (0, 'continuationSeparator')]:
            note = el('w:' + singular, root, id=number, type=kind)
            el('w:' + kind, el('w:r', el('w:p', note)))
        f.paragraph('Ghi chú giả lập: giữ nguyên chữ, ID và quan hệ.', parent=el('w:' + singular, root, id=1))
        f.parts[f'word/{name}.xml'] = xml(root)
        f.relationship(name, name+'.xml', name)
        f.overrides['/word/'+name+'.xml'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.'+name+'+xml'
    p = f.paragraph('Đoạn có bình luận cần giữ nguyên.', 'keep', protected=True)
    p.insert(1, el('w:commentRangeStart', id=1)); el('w:commentRangeEnd', p, id=1)
    el('w:commentReference', el('w:r', p), id=1)
    comments = el('w:comments'); comment = el('w:comment', comments, id=1, author='Người kiểm thử', date='2026-10-27T00:00:00Z')
    f.paragraph('Không xóa bình luận này.', parent=comment)
    f.parts['word/comments.xml'] = xml(comments); f.relationship('comments', 'comments.xml', 'comments')
    f.overrides['/word/comments.xml'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml'
    p = f.paragraph('Lịch sử chỉnh sửa: ', 'keep', protected=True)
    inserted = el('w:ins', p, id=7, author='Người kiểm thử', date='2026-10-27T00:00:00Z'); f.run(inserted, 'phần thêm chưa chấp nhận')
    deleted = el('w:del', p, id=8, author='Người kiểm thử', date='2026-10-27T00:00:00Z')
    el('w:delText', el('w:r', deleted)).text = 'phần xóa chưa chấp nhận'
    f.paragraph(PARAGRAPHS[0]); f.header_footer()
    return f.finish()


def non_thesis():
    f = Fixture('05_khong_phai_do_an', 'Báo cáo công việc không có chương — không được coi là đồ án hợp lệ')
    for text in ['BÁO CÁO CÔNG VIỆC TUẦN', 'Đơn vị: Bộ phận kiểm thử giả lập', 'Hạng mục đã hoàn thành',
                 '1. Kiểm tra hệ thống.', '2. Tổng hợp phản hồi.', 'Hạng mục còn tồn đọng', PARAGRAPHS[4]]:
        f.paragraph(text, 'keep', protected=True, note='Không đủ cấu trúc đồ án: API phải từ chối trước khi tạo phiên/run.')
    f.table(7); f.image()
    data,metadata=f.finish()
    metadata.update({'expected_status':'REJECTED','expected_error':'NOT_A_THESIS'})
    return data,metadata


def body_only():
    f = Fixture('06_than_bai_sai_dinh_dang', 'Ca dương: 2 chương, 60 đoạn, không có vùng khóa để kiểm tra cả lề')
    for chapter in (1, 2):
        f.chapter(chapter, 'KIỂM TRA ĐỊNH DẠNG')
        for section in (1, 2):
            f.paragraph(f'{chapter}.{section} Phương pháp đánh giá', 'heading')
            for i in range(15):
                f.paragraph(f'Đoạn {chapter}-{section}-{i+1}. '+PARAGRAPHS[i % len(PARAGRAPHS)],
                            font=['Arial', 'Calibri', 'Courier New'][i % 3], size=[10, 11, 14, 15][i % 4])
    return f.finish()


BUILDERS = [thesis, ambiguous, tables, academic, non_thesis, body_only]


def build_all(destination=DEST):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    cases = []
    for builder in BUILDERS:
        data, metadata = builder()
        (destination / metadata['file']).write_bytes(data)
        cases.append(metadata)
    manifest = {'version': 1, 'origin': 'Hand-authored synthetic test content, not a real thesis or independent AI evaluation set.',
                'word_validation': 'Not yet validated by Microsoft Word.', 'cases': cases}
    (destination/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return manifest


def bundle(destination=DEST):
    destination = Path(destination)
    parts = {p.name: p.read_bytes() for p in destination.iterdir() if p.suffix in {'.docx', '.json', '.md'}}
    path = destination/'DocLint-bo-mau-phuc-tap.zip'
    path.write_bytes(zip_bytes(parts))
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEST)
    args = parser.parse_args()
    manifest = build_all(args.output)
    print(f"Created {len(manifest['cases'])} DOCX files in {args.output}")
    print(bundle(args.output))
