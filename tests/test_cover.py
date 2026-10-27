from tests.output_projection import source_body,assert_source_text,without_index_anchors
"""Cover regressions: unstyled topic/author, grouping, boundaries and preservation."""
from lxml import etree as E
import pytest

from doclint.engine import inspect,edit,read_package,NS,tag,parse
from doclint.structure import WordContext
from scripts.make_complex_fixtures import Fixture,DEST,el,zip_bytes


def result(data):
    a=inspect(data);out,r=edit(data,a,{})
    parts,root=read_package(out)
    return a,out,r,parts,root.find('w:body',NS)


def fixture_cover(lines,spacer=False):
    f=Fixture('cover_context','Cover recognition')
    for i,text in enumerate(lines):
        f.paragraph(text,size=18,font='Arial',bold=True)
        if spacer and i==0:f.paragraph('')
    f.paragraph('LỜI CẢM ƠN');f.paragraph('Nội dung cần được giữ nguyên.')
    f.chapter(1,'TỔNG QUAN');f.paragraph('1.1 Phạm vi','heading')
    f.paragraph('TRƯỜNG ĐẠI HỌC TRONG MỘT VÍ DỤ THÂN BÀI',bold=True)
    return f.finish()[0]


def test_composite_cover_without_subtitle_formats_topic_and_author_as_template():
    source=(DEST/'01_do_an_tong_hop.docx').read_bytes()
    a,out,r,parts,body=result(source)
    assert [b['role'] for b in a['blocks'][:4]]==['cover_institution','cover_title','cover_subject','cover_author']
    assert a['statistics']['cover_blocks']==4
    assert body[2].find('w:pPr/w:ind',NS).get(tag('left'))=='1276'
    assert body[2].find('w:pPr/w:ind',NS).get(tag('right'))=='1276'
    for i,font,size,before in [(0,'ArnoPro','30','60'),(1,'ArnoPro','50','3200'),(2,'ArnoPro','46','480'),(3,'Times New Roman','28','360')]:
        node=body[i]
        assert node.find('w:pPr/w:jc',NS).get(tag('val'))=='center'
        assert node.find('w:pPr/w:spacing',NS).get(tag('before'))==before
        for run in node.findall('w:r',NS):
            assert run.find('w:rPr/w:rFonts',NS).get(tag('ascii'))==font
            assert run.find('w:rPr/w:sz',NS).get(tag('val'))==size
    old,root=read_package(source)
    assert_source_text(root,body.getparent(),r)
    for name,value in old.items():
        if name.startswith('word/media/') or 'header' in name or 'footer' in name:assert parts[name]==value
    assert r['integrity']=='PASS'


def test_context_identifies_split_topic_bare_author_and_academic_fields():
    lines=['TRƯỜNG ĐẠI HỌC THỬ NGHIỆM','ĐỒ ÁN TỐT NGHIỆP','THIẾT KẾ HỆ THỐNG','GIÁM SÁT THIẾT BỊ','NGƯỜI THỬ NGHIỆM','demo@example.org','MSSV: TEST-003','Ngành Kỹ thuật điện','Chuyên ngành Hệ thống điện','Giảng viên hướng dẫn: Người thử nghiệm','Hà Nội, 10/2026']
    source=fixture_cover(lines);a,out,r,_,body=result(source)
    assert [b['role'] for b in a['blocks'][:len(lines)]]==['cover_institution','cover_title','cover_subject','cover_subject_continuation','cover_author','cover_email','cover_student_detail','cover_major','cover_specialization','cover_advisor','cover_place_date']
    assert not a['blocks'][-1]['role'].startswith('cover_')
    assert body[3].find('w:pPr/w:spacing',NS).get(tag('before'))=='0'
    assert body[5].find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='26'
    assert body[7].find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='28'


def test_author_label_and_value_are_not_mistaken_for_more_topic_lines():
    source=fixture_cover(['ĐỒ ÁN TỐT NGHIỆP','Hệ thống thử nghiệm','Sinh viên thực hiện:','NGƯỜI THỬ NGHIỆM','MSSV: TEST-004'])
    a,_,_,_,body=result(source)
    assert [b['role'] for b in a['blocks'][:5]]==['cover_title','cover_subject','cover_author_label','cover_author','cover_student_detail']
    assert body[3].find('w:pPr/w:spacing',NS).get(tag('before'))=='0'


@pytest.mark.parametrize('spacer',[False,True])
def test_cover_spacing_and_font_corrections_are_idempotent_and_keep_existing_spacers(spacer):
    source=fixture_cover(['TRƯỜNG ĐẠI HỌC THỬ NGHIỆM','ĐỒ ÁN TỐT NGHIỆP','HỆ THỐNG THỬ NGHIỆM','Sinh viên: Người kiểm thử'],spacer)
    a,first,_,parts,body=result(source)
    title=next(b for b in a['blocks'] if b['role']=='cover_title')
    assert title.get('cover_before_twips')==(None if spacer else 3200)
    _,second,r,again,_=result(first)
    assert parts==again and not r['styles_added']
    if spacer:
        _,root=read_package(source)
        assert E.tostring(root.find('w:body',NS)[1])==E.tostring(body[1])


def test_inherited_subtitle_and_wrong_auto_spacing_do_not_override_cover_font_and_gaps():
    source=fixture_cover(['TRƯỜNG ĐẠI HỌC THỬ NGHIỆM','ĐỒ ÁN TỐT NGHIỆP','Hệ thống thử nghiệm','Sinh viên: Người kiểm thử'])
    parts,root=read_package(source);body=root.find('w:body',NS)
    spacing=body[2].find('w:pPr/w:spacing',NS)
    spacing.set(tag('beforeAutospacing'),'1');spacing.set(tag('beforeLines'),'999')
    runprops=body[2].find('w:r/w:rPr',NS)
    for name,value in [('spacing',120),('position',24),('w',20),('smallCaps',1)]:el('w:'+name,runprops,val=value)
    parts['word/document.xml']=E.tostring(root)
    _,_,_,_,body=result(zip_bytes(parts))
    spacing=body[2].find('w:pPr/w:spacing',NS)
    assert spacing.get(tag('before'))=='480' and spacing.get(tag('beforeLines')) is None and spacing.get(tag('beforeAutospacing')) is None
    assert body[2].find('w:r/w:rPr/w:w',NS).get(tag('val'))=='100'
    assert body[2].find('w:r/w:rPr/w:position',NS).get(tag('val'))=='0'


def test_thesis_phrase_in_body_and_protected_logo_are_not_rebuilt():
    f=Fixture('cover_negative','Keep unsafe covers')
    f.paragraph('Đây là báo cáo công việc thử nghiệm, không phải bìa đồ án.')
    f.paragraph('ĐỒ ÁN TỐT NGHIỆP');f.paragraph('Một ví dụ trong thân bài',bold=True)
    f.chapter(1,'VÍ DỤ');f.paragraph('1.1 Nội dung','heading')
    source,_=f.finish();a=inspect(source)
    assert not any(b['role'].startswith('cover_') for b in a['blocks'])
    f=Fixture('cover_logo','Keep image objects')
    p=f.image();f.paragraph('ĐỒ ÁN TỐT NGHIỆP');f.paragraph('Hệ thống thử nghiệm',bold=True)
    f.chapter(1,'VÍ DỤ');f.paragraph('1.1 Nội dung','heading')
    source,_=f.finish();a,out,r,_,body=result(source)
    _,original=read_package(source)
    assert E.tostring(original.find('w:body',NS)[0])==E.tostring(body[0])
