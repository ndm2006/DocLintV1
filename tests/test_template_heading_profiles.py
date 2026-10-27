"""Synthetic controls for every title family present/defined in the HUST template."""
import copy
from lxml import etree as E
import pytest
from doclint.engine import inspect,edit,read_package,validate_integrity,DocumentError,NS,tag
from doclint.template_headings import locate
from scripts.make_complex_fixtures import Fixture,el,zip_bytes


def heading_fixture():
    f=Fixture('heading_profiles','All heading categories')
    styles=E.fromstring(f.parts['word/styles.xml'])
    for level in (1,2,3,4):
        node=el('w:style',type='paragraph',styleId=f'Heading{level}')
        el('w:name',node,val=f'heading {level}');props=el('w:pPr',node);el('w:outlineLvl',props,val=level-1);styles.append(node)
    subtitle=el('w:style',type='paragraph',styleId='Subtitle');el('w:name',subtitle,val='Subtitle');styles.append(subtitle)
    f.parts['word/styles.xml']=E.tostring(styles)
    f.paragraph('TRƯỜNG ĐẠI HỌC BÁCH KHOA HÀ NỘI',style='Subtitle')
    f.paragraph('ĐỒ ÁN TỐT NGHIỆP',style='Subtitle')
    f.paragraph('THIẾT KẾ THIẾT BỊ GIÁM SÁT',style='Subtitle')
    f.paragraph('TRONG PHÒNG THỰC HÀNH',style='Subtitle')
    f.paragraph('Sinh viên: Người thử nghiệm A',size=16)
    f.paragraph('ĐỀ TÀI TỐT NGHIỆP')
    f.paragraph('Biểu mẫu giao đề tài giữ nội dung và chữ ký.')
    f.paragraph('LỜI CẢM ƠN');f.paragraph('Nội dung cảm ơn được giữ nguyên.')
    f.paragraph('TÓM TẮT');f.paragraph('Mô tả vấn đề và kết quả thử nghiệm.')
    f.field('MỤC LỤC',' TOC \\o "1-3" \\h ')
    f.paragraph('DANH MỤC HÌNH VẼ')
    f.paragraph('Hình 1.1 Sơ đồ 1',style='TableofFigures')
    f.paragraph('DANH MỤC HÌNH VẼ')  # Known typo in template: next entries are tables.
    f.paragraph('Bảng 1.1 Dữ liệu 2',style='TableofFigures')
    for text,level in [('TỔNG QUAN',1),('Phương pháp',2),('Cấu hình',3),('Chi tiết được gán Heading 4',4)]:
        f.paragraph(text,style=f'Heading{level}')
    f.paragraph('Hình 1.1 Sơ đồ kiến trúc',style='Caption')
    f.paragraph('Bảng 1.1 Dữ liệu đầu vào',style='Caption')
    table=f.table(1)
    cell=table.find('w:tr',NS).findall('w:tc',NS)[2]
    f.paragraph('PT 1.1',style='Caption',parent=cell)
    sdt=el('w:sdt',f.body);props=el('w:sdtPr',sdt)
    part=el('w:docPartObj',props);el('w:docPartGallery',part,val='Bibliographies')
    content=el('w:sdtContent',sdt)
    f.paragraph('TÀI LIỆU THAM KHẢO',style='Heading1',parent=content)
    f.paragraph('[1] Tác giả thử nghiệm, Tên tài liệu, 2026.',parent=content)
    f.paragraph('PHỤ LỤC',style='Heading1')
    p=f.paragraph('Chi tiết số liệu thí nghiệm',bold=True)
    props=p.find('w:pPr',NS);number=el('w:numPr');el('w:numId',number,val=1);el('w:ilvl',number,val=0);props.insert(0,number)
    f.paragraph('Dữ liệu phụ lục phải giữ nguyên.')
    return f.finish()[0]


def metadata_kwargs(report):
    return {'style_additions':report['styles_added'],'page_sections':report['page_sections_applied'],
            'table_indices':{int(c['block_id'][1:]) for c in report['table_geometry_changes']},
            'page_break_indices':{int(b[1:]) for b in report['front_page_breaks']},
            'allowed_nested':{(c['body_index'],tuple(tuple(p) for p in c['path'])) for c in report['changes'] if c.get('path')}}


def test_all_title_families_are_detected_and_numbered_instructions_are_not_titles():
    data=heading_fixture();a=inspect(data);roles={b['role'] for b in a['blocks']}
    expected={'cover_institution','cover_title','cover_subject','cover_subject_continuation','assignment_title','acknowledgement_title','abstract_title','toc_title','list_figures_title','list_tables_title','references_title','appendix_title','appendix_item_title','figure_caption','table_caption','equation_caption'}
    assert expected<=roles
    assert any(b['role']=='heading' and b['level']==4 and not b['protected'] for b in a['blocks'])
    issue=a['template_heading_issues'][0];assert issue['code']=='LIST_TITLE_MISMATCH' and issue['detected']=='list_tables_title'
    out,r=edit(data,a,{})
    _,original=read_package(data);_,after=read_package(out)
    assert original.xpath('//w:t/text()',namespaces=NS)==after.xpath('//w:t/text()',namespaces=NS)
    for c in r['changes']:
        node=locate(after.find('w:body',NS),c['body_index'] if 'body_index' in c else int(c['block_id'][1:]),c.get('path',[]))
        if c['role']=='cover_title':assert node.find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='50';assert node.find('w:r/w:rPr/w:rFonts',NS).get(tag('ascii'))=='ArnoPro'
        if c['role'] in {'figure_caption','table_caption','equation_caption'}:
            assert node.find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='24'
            assert node.find('w:r/w:rPr/w:i',NS).get(tag('val'))=='1'
            assert node.find('w:pPr/w:spacing',NS).get(tag('line'))=='240'
        if c['role']=='heading' and c['format_after']['before_pt']==2:
            assert node.find('w:r/w:rPr/w:b',NS).get(tag('val'))=='0';assert node.find('w:r/w:rPr/w:i',NS).get(tag('val'))=='1'
    assert r['integrity']=='PASS'


def test_nested_reference_and_equation_caption_do_not_authorize_other_cell_or_sdt_changes():
    data=heading_fixture();a=inspect(data);out,r=edit(data,a,{})
    assert len([c for c in r['changes'] if c.get('path')])==2
    allowed={c['body_index'] for c in r['changes'] if not c.get('path') and c.get('operation')!='page_break_before'}
    kwargs=metadata_kwargs(r);validate_integrity(data,out,allowed,True,**kwargs)
    for kind in ['reference_body','caption_field']:
        parts,root=read_package(out)
        if kind=='reference_body':
            p=root.find('.//w:sdtContent',NS).findall('w:p',NS)[1];p.find('.//w:t',NS).text='Corrupted source'
        else:
            caption=next(b for b in a['blocks'] if b['role']=='equation_caption');p=locate(root.find('w:body',NS),caption['index'],caption['path']);p.find('.//w:t',NS).text='PT 9.9'
        parts['word/document.xml']=E.tostring(root)
        with pytest.raises(DocumentError):validate_integrity(data,zip_bytes(parts),allowed,True,**kwargs)


def test_running_template_headings_twice_does_not_change_content_or_append_more_styles():
    data=heading_fixture();first,_=edit(data,inspect(data),{})
    second,r=edit(first,inspect(first),{})
    old,_=read_package(first);new,_=read_package(second)
    assert old==new and not r['styles_added']


def test_list_of_requirements_and_cached_toc_headings_stay_protected():
    f=Fixture('instructions','Do not interpret enumerated requirements as sections')
    f.chapter(1,'QUY ĐỊNH');f.paragraph('1.1 Nội dung','heading')
    p=f.paragraph('Mục lục');num=el('w:numPr');el('w:numId',num,val=1);p.find('w:pPr',NS).insert(0,num)
    sdt=el('w:sdt',f.body);content=el('w:sdtContent',sdt)
    f.paragraph('PHỤ LỤC',style='TOC1',parent=content)
    data,_=f.finish();a=inspect(data)
    assert next(b for b in a['blocks'] if b['text']=='Mục lục')['protected']
    assert not any(b.get('path') for b in a['blocks'])
