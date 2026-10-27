from tests.output_projection import source_body,assert_source_text,without_index_anchors
"""Regressions for user-reported margins, front matter and unsuitable inputs."""
import copy
from pathlib import Path
from lxml import etree as E
from fastapi.testclient import TestClient
import pytest

from doclint import app as service
from doclint.engine import inspect,edit,read_package,validate_integrity,DocumentError,NS,tag
from scripts.make_complex_fixtures import Fixture,DEST,zip_bytes


def fixture(name):return (DEST/name).read_bytes()


def test_all_merged_table_sections_get_standard_margins_without_losing_landscape():
    source=fixture('03_bang_gop_section_ngang.docx');a=inspect(source);out,r=edit(source,a,{})
    _,before=read_package(source);_,after=read_package(out)
    assert r['page_sections_applied']==[0,1]
    sections=after.findall('.//w:sectPr',NS)
    for section in sections:
        margins=section.find('w:pgMar',NS)
        assert {k:margins.get(tag(k)) for k in ('left','right','top','bottom')}=={'left':'1985','right':'1418','top':'1134','bottom':'1134'}
    page=sections[1].find('w:pgSz',NS)
    assert page.get(tag('orient'))=='landscape'
    assert (page.get(tag('w')),page.get(tag('h')))==('16840','11907')
    # The portrait table is too wide after margins; its grid and cell widths must fit.
    table=after.find('.//w:tbl',NS)
    assert int(table.find('w:tblPr/w:tblW',NS).get(tag('w')))==8504
    assert sum(int(n.get(tag('w'))) for n in table.findall('w:tblGrid/w:gridCol',NS))==8504
    for row in table.findall('w:tr',NS):
        assert sum(int(n.get(tag('w'))) for n in row.findall('w:tc/w:tcPr/w:tcW',NS))==8504
    assert_source_text(before,after,r)
    for path in ('.//w:gridSpan','.//w:vMerge'):
        assert [E.tostring(n) for n in before.findall(path,NS)]==[E.tostring(n) for n in after.findall(path,NS)]
    assert [E.tostring(n) for n in before.findall('.//w:tc/w:tbl',NS)]==[E.tostring(n) for n in after.findall('.//w:tc/w:tbl',NS)]


def test_front_matter_uses_source_template_format_not_chapter_format():
    source=fixture('01_do_an_tong_hop.docx');a=inspect(source);out,r=edit(source,a,{})
    roles={b['id']:b['role'] for b in a['blocks']}
    assert [roles[f'b{i}'] for i in range(4,8)]==['acknowledgement_title','acknowledgement','abstract_title','abstract']
    assert a['statistics']['front_matter_blocks']==4
    old,_=read_package(source);parts,after=read_package(out);body=after.find('w:body',NS)
    for index,before,align,bold in [(4,'480','center','1'),(5,'60','both',None),(6,'960','center','1'),(7,'60','both',None)]:
        node=body[index];spacing=node.find('w:pPr/w:spacing',NS)
        assert spacing.get(tag('before'))==before and spacing.get(tag('line'))=='264'
        assert node.find('w:pPr/w:jc',NS).get(tag('val'))==align
        assert node.find('w:pPr/w:outlineLvl',NS).get(tag('val'))=='9'
        assert node.find('w:pPr/w:numPr/w:numId',NS).get(tag('val'))=='0'
        for run in node.findall('w:r',NS):
            assert run.find('w:rPr/w:rFonts',NS).get(tag('ascii'))=='Times New Roman'
            assert run.find('w:rPr/w:sz',NS).get(tag('val'))=='26'
            if bold:assert run.find('w:rPr/w:b',NS).get(tag('val'))==bold
    assert body[4].find('w:pPr/w:pageBreakBefore',NS).get(tag('val'))=='1'
    assert body[6].find('w:pPr/w:pageBreakBefore',NS).get(tag('val'))=='0'
    # An empty TOC placeholder is populated without duplicating its source title.
    _,before=read_package(source);original=before.find('w:body',NS)
    assert body[8].find('w:fldSimple',NS) is None
    assert len(r['derived']['indexes']['created'])==3
    assert body[8].find('w:pPr/w:pageBreakBefore',NS).get(tag('val'))=='1'
    assert [g['block_ids'] for g in r['front_matter']]==[['b5'],['b7']]
    assert r['front_matter'][0]['status']=='WARNING'  # The synthetic acknowledgement is short.
    for name in old:
        if name.startswith('word/media/'):assert old[name]==parts[name]


def test_long_abstract_warns_without_rewriting_or_shrinking_and_stops_at_signature():
    f=Fixture('abstract','Thesis front sections')
    f.paragraph('ĐỒ ÁN TỐT NGHIỆP','keep')
    f.paragraph('Tóm tắt nội dung đồ án tốt nghiệp','abstract_title')
    summary=' '.join(['Nội dung']*151)
    f.paragraph(summary,'abstract')
    f.paragraph('Sinh viên thực hiện','keep')
    f.paragraph('Người kiểm thử A','keep',size=16)
    f.chapter(1,'THIẾT KẾ');f.paragraph('1.1 Phạm vi','heading')
    source,_=f.finish();a=inspect(source);out,r=edit(source,a,{})
    assert a['document_type']['accepted']
    group=r['front_matter'][0]
    assert group['word_count']==302 and group['status']=='WARNING' and group['block_ids']==['b2']
    _,root=read_package(out)
    assert ''.join(root.find('w:body',NS)[2].xpath('.//w:t/text()',namespaces=NS))==summary
    assert root.find('w:body',NS)[2].find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='26'
    assert root.find('w:body',NS)[4].find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='32'


@pytest.mark.parametrize('damage',['cell_text','merge','nested_table'])
def test_table_width_permissions_do_not_allow_changing_cell_content_or_merges(damage):
    source=fixture('03_bang_gop_section_ngang.docx');a=inspect(source);out,r=edit(source,a,{})
    parts,root=read_package(out)
    if damage=='cell_text':root.find('.//w:tbl//w:t',NS).text='Changed'
    elif damage=='merge':root.find('.//w:gridSpan',NS).set(tag('val'),'1')
    else:root.find('.//w:tc/w:tbl//w:t',NS).text='Changed nested cell'
    parts['word/document.xml']=E.tostring(root)
    kwargs={'style_additions':r['styles_added'],'page_sections':r['page_sections_applied'],
            'table_indices':{int(c['block_id'][1:]) for c in r['table_geometry_changes']}}
    allowed={int(c['block_id'][1:]) for c in r['changes']}
    validate_integrity(source,out,allowed,True,**kwargs)
    with pytest.raises(DocumentError) as err:validate_integrity(source,zip_bytes(parts),allowed,True,**kwargs)
    assert err.value.code=='INTEGRITY_FAILED'


@pytest.mark.parametrize('filename',['05_khong_phai_do_an.docx','Đồ án tốt nghiệp.docx'])
def test_unsuitable_document_is_rejected_before_session_or_worker(filename,monkeypatch):
    before_sessions=set(service.sessions);before_runs=set(service.runs)
    def forbidden(*args,**kwargs):raise AssertionError('Rejected input must not reach worker')
    monkeypatch.setattr(service.executor,'submit',forbidden)
    with TestClient(service.app) as client:
        response=client.post('/api/v1/sessions',files={'file':(filename,fixture('05_khong_phai_do_an.docx'))})
    assert response.status_code==422
    assert response.json()['code']=='NOT_A_THESIS'
    assert 'tải lên' in response.json()['message']
    assert set(service.sessions)==before_sessions and set(service.runs)==before_runs


def test_word_do_an_alone_is_not_enough_and_positive_without_literal_keyword_is_accepted():
    f=Fixture('not_thesis','No structure')
    f.paragraph('ĐỒ ÁN TỐT NGHIỆP','keep')
    f.paragraph('Chỉ có tiêu đề, chưa có nội dung hoặc chương.','keep')
    data,_=f.finish()
    with TestClient(service.app) as client:
        response=client.post('/api/v1/sessions',files={'file':('thesis.docx',data)})
        assert response.status_code==422 and response.json()['code']=='THESIS_STRUCTURE_REQUIRED'
        response=client.post('/api/v1/sessions',files={'file':('report.docx',fixture('03_bang_gop_section_ngang.docx'))})
        assert response.status_code==202
        session=response.json()
        assert client.delete('/api/v1/sessions/'+session['session_id'],headers={'Authorization':'Bearer '+session['access_token']}).status_code==200


def test_other_document_heading_is_not_overridden_by_incidental_thesis_keyword():
    f=Fixture('weekly','Progress report')
    f.paragraph('BÁO CÁO QUÁ TRÌNH','keep')
    f.paragraph('ĐỒ ÁN TỐT NGHIỆP','keep')
    f.chapter(1,'CÔNG VIỆC');f.paragraph('1.1 Kết quả tuần','heading')
    data,_=f.finish();a=inspect(data)
    assert not a['document_type']['accepted'] and a['document_type']['code']=='NOT_A_THESIS'


@pytest.mark.parametrize('name',['01_do_an_tong_hop.docx','03_bang_gop_section_ngang.docx'])
def test_repeating_front_and_table_formatting_is_idempotent(name):
    source=fixture(name);first,_=edit(source,inspect(source),{})
    second,r=edit(first,inspect(first),{})
    old,_=read_package(first);new,_=read_package(second)
    assert old==new
    assert not r['styles_added'] and not r['table_geometry_changes']


def test_generated_toc_field_cannot_be_modified_outside_plan():
    source=fixture('01_do_an_tong_hop.docx');a=inspect(source);out,r=edit(source,a,{})
    allowed={int(c['block_id'][1:]) for c in r['changes'] if c.get('operation')!='page_break_before'}
    kwargs={'style_additions':r['styles_added'],'page_sections':r['page_sections_applied'],
            'table_indices':{int(c['block_id'][1:]) for c in r['table_geometry_changes']},
            'page_break_indices':{int(b[1:]) for b in r['front_page_breaks']}}
    validate_integrity(source,out,allowed,True,**kwargs)
    parts,root=read_package(out);paragraph=root.find('w:body',NS)[8]
    root.find('.//w:instrText',NS).text=' REF changed '
    parts['word/document.xml']=E.tostring(root)
    with pytest.raises(DocumentError):validate_integrity(source,zip_bytes(parts),allowed,True,**kwargs)
