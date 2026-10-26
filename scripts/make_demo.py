"""Generate an anonymous, editable DOCX fixture with real image/table/math parts."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from html import escape
import struct
import zlib

def demo_png():
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    pixels=b''.join(b'\x00'+bytes((39,115,90))*32 for _ in range(32))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')

def demo_bytes():
    from io import BytesIO
    paragraphs=['CHƯƠNG 1. TỔNG QUAN','1.1 Bối cảnh nghiên cứu','Đây là nội dung tiếng Việt có định dạng chưa đồng nhất. DocLint cần giữ nguyên toàn bộ nội dung này.',
                '1.1.1 Mục tiêu','Hệ thống chuẩn hóa định dạng và kiểm tra nội dung trước khi cung cấp bản Word.']
    content=''.join(f'<w:p><w:r><w:rPr><w:rFonts w:ascii="Arial"/><w:sz w:val="22"/></w:rPr><w:t>{escape(t)}</w:t></w:r></w:p>' for t in paragraphs)
    content+='''<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="dxa"/></w:tblPr><w:tblGrid><w:gridCol w:w="2500"/><w:gridCol w:w="2500"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Dữ liệu ô thứ nhất</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Dữ liệu ô thứ hai</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:p><m:oMath><m:r><m:t>x + y = 2</m:t></m:r></m:oMath></w:p>
    <w:p><w:r><w:drawing><wp:inline><wp:extent cx="914400" cy="914400"/><wp:docPr id="1" name="Ảnh thử nghiệm"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="pixel.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rImg"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="914400"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:left="900" w:right="900" w:top="900" w:bottom="900"/></w:sectPr>'''
    doc='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>'''+content+'</w:body></w:document>'
    parts={'word/document.xml':doc,
      '[Content_Types].xml':'''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>''',
      '_rels/.rels':'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rDoc" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>''',
      'word/_rels/document.xml.rels':'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/pixel.png"/></Relationships>''',
      'word/media/pixel.png':demo_png()}
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    return out.getvalue()
if __name__=='__main__':
    path=Path('.runtime/demo.docx');path.parent.mkdir(exist_ok=True);path.write_bytes(demo_bytes());print(path)
