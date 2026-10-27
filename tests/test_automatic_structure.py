from tests.output_projection import source_body,assert_source_text,without_index_anchors
"""Independent small authored documents to exercise the resolver and integrity gates."""
import copy
from lxml import etree as E
import pytest
from scripts.make_complex_fixtures import Fixture, thesis, ambiguous, body_only, W, NS, el
from doclint.engine import inspect, edit, read_package, validate_integrity, DocumentError, tag
from doclint.styles import signature
from scripts.make_complex_fixtures import zip_bytes as repack


def make_document(paragraphs, styled=False):
    f=Fixture('held_out','Independent authored structure probe')
    for text,role in paragraphs:
        f.paragraph(text,role)
    if styled:
        styles=E.fromstring(f.parts['word/styles.xml'])
        for level in (1,2,3):
            style=el('w:style',type='paragraph',styleId=f'Heading{level}')
            el('w:name',style,val=f'heading {level}')
            props=el('w:pPr',style); el('w:outlineLvl',props,val=level-1)
            numbering=el('w:numPr',props);el('w:ilvl',numbering,val=level-1);el('w:numId',numbering,val=1)
            styles.append(style)
        f.parts['word/styles.xml']=E.tostring(styles)
        for p,(_,role) in zip(f.body,paragraphs):
            level={'chapter':1,'heading':2}.get(role)
            if level is not None:p.find('w:pPr',NS).insert(0,el('w:pStyle',val=f'Heading{level}'))
    return f.finish()[0]


def test_numbered_unstyled_titles_automatically_resolve_without_review():
    source=make_document([('CHƯƠNG 1. THIẾT KẾ TRẠM ĐO KHÍ HẬU','chapter'),
      ('1.1 Giao thức thu nhận','heading'),('1.1.1 Cơ chế đồng bộ tín hiệu','heading'),
      ('Bộ thu tiếp nhận tín hiệu từ cảm biến và ghi nhận thời điểm lấy mẫu để đối chiếu dữ liệu.','body'),
      ('CHƯƠNG 2. ĐÁNH GIÁ ĐỘ ỔN ĐỊNH','chapter'),('2.1 Thiết lập thực nghiệm','heading')])
    a=inspect(source)
    assert [b['role'] for b in a['blocks']]==['chapter','heading','heading','body','chapter','heading']
    assert not any(b['needs_review'] for b in a['blocks'])
    assert a['blocks'][2]['parent_block_id']==a['blocks'][1]['id']
    _,r=edit(source,a,{})
    assert len(r['changes'])==6


def test_styles_with_inherited_auto_numbering_are_not_lists_or_duplicated():
    source=make_document([('THIẾT KẾ MẠNG GIÁM SÁT','chapter'),('Giao thức truyền dữ liệu','heading'),
                         ('Bản tin được ghi nhận nguyên vẹn ở phía nhận.','body')],styled=True)
    a=inspect(source)
    assert [b['role'] for b in a['blocks']]==['chapter','heading','body']
    assert a['statistics']['review_blocks']==0
    result,r=edit(source,a,{})
    old,root=read_package(source);new,edited=read_package(result)
    assert old['word/styles.xml']==new['word/styles.xml']
    assert not r['heading_styles_added']
    assert source_body(edited,r)[0].find('w:pPr/w:pStyle',NS).get(tag('val'))=='Heading1'
    assert_source_text(root,edited,r)


def test_custom_heading_alias_and_inherited_outline():
    source=make_document([('THIẾT KẾ MẠNG GIÁM SÁT','chapter'),('Kênh truyền','heading')],styled=True)
    parts,root=read_package(source);styles=E.fromstring(parts['word/styles.xml'])
    custom=el('w:style',type='paragraph',styleId='TruongHeading')
    el('w:name',custom,val='Vai trò riêng');el('w:basedOn',custom,val='Heading1');styles.append(custom)
    parts['word/styles.xml']=E.tostring(styles)
    root.find('w:body',NS)[0].find('w:pPr/w:pStyle',NS).set(tag('val'),'TruongHeading')
    parts['word/document.xml']=E.tostring(root)
    a=inspect(repack(parts));assert a['blocks'][0]['role']=='chapter';assert not a['blocks'][0]['needs_review']


def test_orphan_and_duplicate_numbering_require_review():
    source=make_document([('CHƯƠNG 1. THIẾT KẾ','chapter'),('1.4.1 Mục thiếu cha','heading'),
                          ('1.1 Phạm vi','heading'),('1.1 Đề mục trùng','heading')])
    a=inspect(source)
    assert a['blocks'][1]['needs_review'];assert a['blocks'][3]['needs_review']
    assert not a['blocks'][2]['needs_review']
    with pytest.raises(DocumentError):edit(source,a,{'b1':'heading'})


def test_numbered_bare_chapter_needs_child_evidence():
    source=make_document([('1 Khảo sát hiện trạng','chapter'),('1.1 Đối tượng khảo sát','heading'),
                          ('Các phép đo được thực hiện tại ba vị trí độc lập.','body')])
    a=inspect(source);assert a['statistics']['auto_chapters']==1;assert a['statistics']['auto_headings']==1
    other=make_document([('1. Gửi thư xác nhận.','keep'),('2. Nhận phản hồi.','keep')])
    assert all(b['role']=='keep' for b in inspect(other)['blocks'])


def test_normalization_does_not_keep_appending_heading_styles():
    data=body_only()[0];first,_=edit(data,inspect(data),{})
    second,report=edit(first,inspect(first),{})
    old,_=read_package(first);new,_=read_package(second)
    assert not report['heading_styles_added']
    assert old['word/styles.xml']==new['word/styles.xml']


@pytest.mark.parametrize('target',['shared_style','relationship','content_type','new_style'])
def test_styles_gate_rejects_changes_outside_append_only_plan(target):
    source=thesis()[0];analysis=inspect(source);result,r=edit(source,analysis,{})
    parts,_=read_package(result)
    if target in {'shared_style','new_style'}:
        node=E.fromstring(parts['word/styles.xml'])
        if target=='shared_style':node.find('w:style',NS).set(tag('default'),'0')
        else:node.xpath('./w:style[@w:styleId=$sid]',namespaces=NS,sid=next(iter(r['heading_styles_added'])))[0].set(tag('default'),'1')
        parts['word/styles.xml']=E.tostring(node)
    elif target=='relationship':
        node=E.fromstring(parts['word/_rels/document.xml.rels']);node[0].set('Target','numbering.xml');parts['word/_rels/document.xml.rels']=E.tostring(node)
    else:
        node=E.fromstring(parts['[Content_Types].xml']);node[0].set('ContentType','unexpected/type');parts['[Content_Types].xml']=E.tostring(node)
    allowed={int(c['block_id'][1:]) for c in r['changes']}
    with pytest.raises(DocumentError) as exc:
        validate_integrity(source,repack(parts),allowed,r['page_geometry_applied'],style_additions=r['styles_added'],page_sections=r['page_sections_applied'],table_indices={int(c['block_id'][1:]) for c in r['table_geometry_changes']})
    assert exc.value.code=='INTEGRITY_FAILED'


def test_numbering_schema_cannot_be_tampered_before_edit():
    source=body_only()[0];a=inspect(source);a['blocks'][1]['parent_block_id']='invented'
    with pytest.raises(DocumentError):edit(source,a,{})


def test_explicit_numbering_definition_can_supply_heading_semantics():
    source=make_document([('HỆ THỐNG THU THẬP KHÍ TƯỢNG','chapter'),('Kênh truyền','heading')])
    parts,root=read_package(source)
    numbering=E.fromstring(parts['word/numbering.xml'])
    abstract=numbering.find('w:abstractNum',NS)
    abstract.find('w:lvl/w:lvlText',NS).set(tag('val'),'CHƯƠNG %1.')
    second=el('w:lvl',ilvl=1);el('w:numFmt',second,val='decimal');el('w:lvlText',second,val='%1.%2');abstract.append(second)
    parts['word/numbering.xml']=E.tostring(numbering)
    for i,p in enumerate(root.find('w:body',NS)):
        if p.tag==tag('p'):
            props=p.find('w:pPr',NS);n=el('w:numPr');el('w:ilvl',n,val=i);el('w:numId',n,val=1);props.insert(0,n)
    parts['word/document.xml']=E.tostring(root)
    a=inspect(repack(parts))
    assert [b['role'] for b in a['blocks']]==['chapter','heading']
    assert a['statistics']['review_blocks']==0


def test_duplicate_chapter_also_defers_descendant_headings():
    source=make_document([('CHƯƠNG 1. TỔNG QUAN','chapter'),('1.1 Bối cảnh','heading'),
                          ('CHƯƠNG 1. NỘI DUNG KHÁC','chapter'),('1.2 Phương pháp','heading')])
    a=inspect(source)
    assert a['blocks'][2]['needs_review']
    assert a['blocks'][3]['needs_review']
    _,report=edit(source,a,{})
    assert {c['block_id'] for c in report['changes']}=={'b0','b1'}


@pytest.mark.parametrize('part',['[Content_Types].xml','_rels/.rels'])
def test_invalid_opc_main_registration_rejected(part):
    data=body_only()[0];parts,_=read_package(data)
    node=E.fromstring(parts[part])
    if part=='[Content_Types].xml':
        for child in node:
            if child.get('PartName')=='/word/document.xml':child.set('ContentType','application/incorrect')
    else:node[0].set('Type','urn:incorrect')
    parts[part]=E.tostring(node)
    with pytest.raises(DocumentError):inspect(repack(parts))


def test_multicolumn_section_is_kept_instead_of_claimed_as_supported_body():
    source=make_document([('CHƯƠNG 1. BỐ CỤC HAI CỘT','chapter'),('1.1 Thiết kế','heading'),
                         ('Đoạn này nằm trong hai cột và phải giữ định dạng.','body')])
    parts,root=read_package(source);section=root.find('.//w:sectPr',NS);el('w:cols',section,num=2)
    parts['word/document.xml']=E.tostring(root);data=repack(parts)
    a=inspect(data);assert all(b['protected'] for b in a['blocks'])
    _,report=edit(data,a,{})
    assert not report['changes'] and not report['page_geometry_applied']


def test_empty_field_end_paragraph_does_not_lock_the_rest_of_document():
    source=make_document([('MỤC LỤC','keep'),('CHƯƠNG 1. CƠ SỞ THỰC NGHIỆM','chapter'),
                         ('1.1 Phương pháp quan sát','heading')])
    parts,root=read_package(source);body=root.find('w:body',NS)
    first=body[0];el('w:fldChar',el('w:r',first),fldCharType='begin')
    empty=el('w:p');el('w:fldChar',el('w:r',empty),fldCharType='end');body.insert(1,empty)
    parts['word/document.xml']=E.tostring(root);a=inspect(repack(parts))
    assert a['statistics']['auto_chapters']==1
    assert a['statistics']['auto_headings']==1
    assert not a['blocks'][1]['protected']
