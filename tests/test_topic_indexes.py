"""Focused regressions for the two changes requested on the restored 0.1.3."""
from pathlib import Path
import copy
from lxml import etree as E
import pytest
from doclint.engine import inspect,edit,read_package,NS,tag,validate_integrity,DocumentError
from doclint.index_fields import kind
from doclint.topic_indexes import sentence_case
from scripts.make_complex_fixtures import Fixture,DEST,zip_bytes
from tests.output_projection import source_body,assert_source_text


def process(data):
    output,report=edit(data,inspect(data),{})
    parts,root=read_package(output)
    return output,report,parts,root


@pytest.mark.parametrize('path',[
    DEST/'01_do_an_tong_hop.docx',Path('tests/fixtures/topic_indexes/previous_output.docx')])
def test_real_input_and_previous_output_fix_only_topic_casing_and_indexes(path):
    source=path.read_bytes();old,before=read_package(source)
    output,r,parts,root=process(source);projected=source_body(root,r)
    assert ''.join(projected[2].xpath('.//w:t/text()',namespaces=NS))=='Hệ thống quản lý mượn thiết bị'
    assert projected[2].find('w:r/w:rPr/w:rFonts',NS).get(tag('ascii'))=='ArnoPro'
    assert projected[2].find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='46'
    assert projected[2].find('w:pPr/w:spacing',NS).get(tag('before'))=='480'
    assert projected[1].find('w:pPr/w:spacing',NS).get(tag('before'))=='3200'
    assert_source_text(before,root,r)
    for name in old:
        if name.startswith(('word/header','word/footer','word/media/')):assert parts[name]==old[name]
    generated=[n for n in root.find('w:body',NS) if kind(n) in {'toc','figures','tables'}]
    assert [kind(n) for n in generated]==['toc','figures','tables']
    assert [len(n.findall('.//w:hyperlink',NS)) for n in generated]==[13,1,1]
    assert sum(t=='MỤC LỤC' for t in root.xpath('//w:t/text()',namespaces=NS))==1
    assert projected[8].find('w:fldSimple',NS) is None
    again=inspect(output)
    assert again['document_type']['accepted']
    assert sum(b['role']=='chapter' and not b['protected'] for b in again['blocks'])==3
    assert process(output)[2]==parts


def test_original_cover_layout_properties_are_preserved_against_previous_export():
    _,before=read_package(Path('tests/fixtures/topic_indexes/previous_output.docx').read_bytes())
    _,r,_,root=process((DEST/'01_do_an_tong_hop.docx').read_bytes())
    after=source_body(root,r)
    for i in range(4):
        assert E.tostring(before.find('w:body',NS)[i].find('w:pPr',NS))==E.tostring(after[i].find('w:pPr',NS))
        assert E.tostring(before.find('w:body',NS)[i].find('w:r/w:rPr',NS))==E.tostring(after[i].find('w:r/w:rPr',NS))


@pytest.mark.parametrize('value,expected',[
    ('HỆ THỐNG QUẢN LÝ MƯỢN THIẾT BỊ','Hệ thống quản lý mượn thiết bị'),
    ('THIẾT KẾ HỆ THỐNG TỰ ĐỘNG ĐIỀU CHỈNH','Thiết kế hệ thống tự động điều chỉnh'),
    ('Thiết kế hệ thống IoT tại Hà Nội','Thiết kế hệ thống IoT tại Hà Nội'),
    ('THIẾT KẾ HỆ THỐNG API TẠI HÀ NỘI','Thiết kế hệ thống API tại Hà Nội'),
    ('HỆ THỐNG HUST ABC','Hệ thống HUST ABC'),
])
def test_sentence_case_does_not_blindly_lowercase_unknown_names(value,expected):
    assert sentence_case(value)[0]==expected


def test_split_topic_keeps_runs_and_continuation_lowercase():
    from tests.test_cover import fixture_cover
    data=fixture_cover(['ĐỒ ÁN TỐT NGHIỆP','THIẾT KẾ HỆ THỐNG TỰ ĐỘNG ĐIỀU CHỈNH','NHIỆT ĐỘ TRONG THIẾT BỊ SẤY HOA QUẢ','Sinh viên: Người thử nghiệm'])
    _,r,_,root=process(data);body=source_body(root,r)
    assert ''.join(body[1].xpath('.//w:t/text()',namespaces=NS))=='Thiết kế hệ thống tự động điều chỉnh'
    assert ''.join(body[2].xpath('.//w:t/text()',namespaces=NS))=='nhiệt độ trong thiết bị sấy hoa quả'


@pytest.mark.parametrize('objects,expected',[
    ('none',['toc']),('figure',['toc','figures']),('table',['toc','tables']),('both',['toc','figures','tables'])])
def test_missing_indexes_use_template_order_and_do_not_create_empty_lists(objects,expected):
    f=Fixture('indexes','Index cases')
    f.chapter(1,'TỔNG QUAN');f.paragraph('1.1 Phạm vi','heading')
    if objects in {'figure','both'}:f.image();f.paragraph('Hình 1.1. Sơ đồ thử nghiệm',style='Caption')
    if objects in {'table','both'}:f.paragraph('Bảng 1.1. Dữ liệu thử nghiệm',style='Caption');f.table(1)
    _,_,_,root=process(f.finish()[0])
    generated=[n for n in root.find('w:body',NS) if kind(n) in {'toc','figures','tables'}]
    assert [kind(n) for n in generated]==expected
    assert all(n.find('w:sdtContent/w:p/w:pPr/w:pageBreakBefore',NS).get(tag('val'))=='1' for n in generated)


def test_generated_fields_are_balanced_and_property_order_matches_word_schema():
    _,_,_,root=process((DEST/'01_do_an_tong_hop.docx').read_bytes())
    depth=0
    for n in root.findall('.//w:fldChar',NS):
        depth+=1 if n.get(tag('fldCharType'))=='begin' else -1 if n.get(tag('fldCharType'))=='end' else 0
        assert depth>=0
    assert depth==0
    for node in root.find('w:body',NS):
        if kind(node) not in {'toc','figures','tables'}:continue
        for props in node.findall('.//w:pPr',NS):
            names=[E.QName(n).localname for n in props]
            if 'keepNext' in names:assert names.index('keepNext')<names.index('pageBreakBefore')
            if 'ind' in names:assert names.index('spacing')<names.index('ind')


def test_missing_toc_title_is_created_without_touching_cover_or_body_text():
    parts,root=read_package((DEST/'01_do_an_tong_hop.docx').read_bytes())
    root.find('w:body',NS).remove(root.find('w:body',NS)[8]);parts['word/document.xml']=E.tostring(root)
    source=zip_bytes(parts);_,r,_,result=process(source)
    assert sum(t=='MỤC LỤC' for t in result.xpath('//w:t/text()',namespaces=NS))==1
    assert_source_text(root,result,r)


def test_populated_existing_indexes_are_preserved_without_duplicates():
    data=(DEST/'01_do_an_tong_hop.docx').read_bytes();parts,root=read_package(data)
    field=root.find('w:body',NS)[8].find('w:fldSimple',NS)
    field.find('.//w:t',NS).text='Mục lục người dùng đã cập nhật 1'
    parts['word/document.xml']=E.tostring(root)
    _,_,_,result=process(zip_bytes(parts))
    assert not any(kind(n)=='toc' for n in result.find('w:body',NS))
    assert 'Mục lục người dùng đã cập nhật 1' in result.xpath('//w:t/text()',namespaces=NS)


def test_unauthorized_topic_wording_or_field_code_change_fails_integrity():
    source=(DEST/'01_do_an_tong_hop.docx').read_bytes();output,r,parts,root=process(source)
    for target in ('topic','field'):
        checked,tree=read_package(output)
        if target=='topic':source_body(tree,r)[2].find('w:r/w:t',NS).text='Đề tài khác'
        else:tree.find('.//w:instrText',NS).text=' INCLUDETEXT "file.docx" '
        checked['word/document.xml']=E.tostring(tree)
        with pytest.raises(DocumentError):validate_integrity(source,zip_bytes(checked),{c['body_index'] for c in r['changes'] if 'body_index' in c},r['page_geometry_applied'],style_additions=r['styles_added'],page_sections=r['page_sections_applied'],table_indices={int(c['block_id'][1:]) for c in r['table_geometry_changes']},page_break_indices={int(v[1:]) for v in r['front_page_breaks']})


def test_empty_list_titles_stay_before_their_generated_entries():
    f=Fixture('bare_titles','Existing list headings')
    for text in ('MỤC LỤC','DANH MỤC HÌNH VẼ','DANH MỤC BẢNG'):f.paragraph(text)
    f.chapter(1,'TỔNG QUAN');f.paragraph('1.1 Phạm vi','heading')
    f.image();f.paragraph('Hình 1.1. Sơ đồ',style='Caption')
    f.paragraph('Bảng 1.1. Dữ liệu',style='Caption');f.table(1)
    _,_,_,root=process(f.finish()[0]);body=root.find('w:body',NS)
    for name,label in [('toc','MỤC LỤC'),('figures','DANH MỤC HÌNH VẼ'),('tables','DANH MỤC BẢNG')]:
        index=next(i for i,n in enumerate(body) if ''.join(n.xpath('./w:r/w:t/text()',namespaces=NS))==label)
        assert kind(body[index+1])==name
        assert sum(t==label for t in root.xpath('//w:t/text()',namespaces=NS))==1


def test_missing_toc_is_inserted_before_an_existing_figure_list():
    f=Fixture('existing_figures','Preserve native lists')
    f.paragraph('DANH MỤC HÌNH VẼ');f.paragraph('Hình 1.1. Sơ đồ 1',style='TableofFigures')
    f.chapter(1,'TỔNG QUAN');f.paragraph('1.1 Phạm vi','heading')
    f.image();f.paragraph('Hình 1.1. Sơ đồ',style='Caption')
    f.paragraph('Bảng 1.1. Dữ liệu',style='Caption');f.table(1)
    _,_,_,root=process(f.finish()[0]);body=root.find('w:body',NS)
    assert kind(body[0])=='toc'
    figure_title=next(i for i,n in enumerate(body) if ''.join(n.xpath('./w:r/w:t/text()',namespaces=NS))=='DANH MỤC HÌNH VẼ')
    table_index=next(i for i,n in enumerate(body) if kind(n)=='tables')
    assert table_index>figure_title
    assert not any(kind(n)=='figures' for n in body)


def test_invalid_property_order_in_owned_old_index_is_rebuilt():
    output,_,parts,root=process((DEST/'01_do_an_tong_hop.docx').read_bytes())
    toc=next(n for n in root.find('w:body',NS) if kind(n)=='toc')
    props=toc.find('w:sdtContent/w:p/w:pPr',NS);indent=props.find('w:ind',NS)
    props.remove(indent);props.insert(0,indent)
    parts['word/document.xml']=E.tostring(root)
    _,r,_,fixed=process(zip_bytes(parts))
    assert any(c['kind']=='toc' for c in r['derived']['indexes']['created'])
    toc=next(n for n in fixed.find('w:body',NS) if kind(n)=='toc')
    props=toc.find('w:sdtContent/w:p/w:pPr',NS)
    names=[E.QName(n).localname for n in props]
    assert names.index('spacing')<names.index('ind')
