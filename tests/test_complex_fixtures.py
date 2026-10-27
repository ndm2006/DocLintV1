from tests.output_projection import source_body,assert_source_text,without_index_anchors
"""Hand-authored labels and independent structural assertions for complex DOCX."""
import copy
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree as E

from doclint.engine import inspect, edit, read_package, NS, tag
from scripts.make_complex_fixtures import BUILDERS, DEST

MANIFEST = json.loads((DEST / 'manifest.json').read_text(encoding='utf-8'))


def canonical(node):
    return E.tostring(node, method='c14n')


@pytest.mark.parametrize('case', MANIFEST['cases'], ids=lambda case: case['file'])
def test_complex_package_preserves_authored_invariants(case):
    source = (DEST / case['file']).read_bytes()
    assert hashlib.sha256(source).hexdigest() == case['sha256']
    analysis = inspect(source)
    labels = {label['id']: label for label in case['labels']}
    by_id = {block['id']: block for block in analysis['blocks']}
    assert labels.keys() == by_id.keys()
    for bid, label in labels.items():
        assert by_id[bid]['text'] == label['text']
        if label['protected']:
            assert by_id[bid]['protected'], (bid, label['text'])
    if case['expected_status']=='REJECTED':
        assert not analysis['document_type']['accepted']
        assert analysis['document_type']['code']==case['expected_error']
        return
    decisions = {bid: labels[bid]['role'] for bid, block in by_id.items() if block['needs_review']}
    output, report = edit(source, analysis, decisions)
    original, before = read_package(source)
    candidate, after = read_package(output)
    assert report['status'] == 'PARTIAL'
    assert report['checks']['layout'] == 'NOT_CHECKED'
    assert_source_text(before,after,report)
    assert set(candidate)-set(original) <= {'word/styles.xml','word/_rels/document.xml.rels'}
    for name, data in original.items():
        if name not in {'word/document.xml','word/styles.xml','word/_rels/document.xml.rels','[Content_Types].xml'}:
            assert data == candidate[name], name
    # Table cell content and merges remain immutable; only reported explicit widths may change.
    changed_tables={c['block_id'] for c in report['table_geometry_changes']}
    def immutable_table(node,strip):
        node=copy.deepcopy(node)
        if strip:
            for path in ('w:tblPr/w:tblW','w:tblPr/w:tblInd','w:tr/w:tc/w:tcPr/w:tcW'):
                for prop in node.findall(path,NS):prop.getparent().remove(prop)
            for col in node.findall('w:tblGrid/w:gridCol',NS):col.attrib.pop(tag('w'),None)
        return canonical(node)
    for index,node in enumerate(before.find('w:body',NS)):
        if node.tag==tag('tbl'):
            assert immutable_table(node,f'b{index}' in changed_tables)==immutable_table(source_body(after,report)[index],f'b{index}' in changed_tables)
    math_path='.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'
    assert [canonical(n) for n in before.findall(math_path)]==[canonical(n) for n in after.findall(math_path)]
    before_body, after_body = before.find('w:body', NS), source_body(after,report)
    for bid, label in labels.items():
        if label['protected'] or label['role'] == 'keep':
            index = int(bid[1:])
            old=copy.deepcopy(before_body[index]);new=without_index_anchors(after_body[index])
            if bid in report['front_page_breaks']:
                for paragraph in (old,new):
                    props=paragraph.find('w:pPr',NS)
                    if props is not None:
                        for prop in props.findall('w:pageBreakBefore',NS):props.remove(prop)
                        if not len(props) and not props.attrib:paragraph.remove(props)
            if old.find('w:pPr/w:sectPr',NS) is not None:
                for paragraph in (old,new):
                    for path in ('w:pPr/w:sectPr/w:pgSz','w:pPr/w:sectPr/w:pgMar'):
                        for prop in paragraph.findall(path,NS):prop.getparent().remove(prop)
            assert canonical(old)==canonical(new),bid
    if case['file'].startswith('05_'):
        assert report['changes'] == []  # This is not evidence of document-type rejection.
    elif case['file'].startswith('06_'):
        assert report['page_geometry_applied']
        assert len(report['changes']) == 66
        for label in case['labels']:
            if label['role'] == 'body':
                p = after_body[int(label['id'][1:])]
                assert p.find('w:pPr/w:spacing', NS).get(tag('line')) == '264'
                assert p.find('w:r/w:rPr/w:sz', NS).get(tag('val')) == '26'
        assert after.find('.//w:pgMar', NS).get(tag('left')) == '1985'
    elif case['file'].startswith('03_'):
        assert report['page_sections_applied']==[0,1]
        for old,new in zip(before.findall('.//w:sectPr',NS),after.findall('.//w:sectPr',NS)):
            assert old.find('w:pgSz',NS).get(tag('orient'))==new.find('w:pgSz',NS).get(tag('orient'))
            assert new.find('w:pgMar',NS).get(tag('left'))=='1985'
            assert new.find('w:pgMar',NS).get(tag('right'))=='1418'
    elif not case['file'].startswith('05_'):
        assert report['page_geometry_applied']
    # Original shared styles stay intact; only isolated, approved style definitions append.
    old_styles=E.fromstring(original['word/styles.xml'])
    new_styles=E.fromstring(candidate['word/styles.xml'])
    additions=report['styles_added']
    for child in list(new_styles):
        if child.get(tag('styleId')) in additions:new_styles.remove(child)
    assert canonical(old_styles)==canonical(new_styles)
    assert analysis['statistics']['review_blocks']==(2 if case['file'].startswith('02_') else 0)



@pytest.mark.parametrize('builder', BUILDERS, ids=lambda fn: fn.__name__)
def test_committed_inputs_are_reproducible(builder):
    data, metadata = builder()
    assert data == (DEST / metadata['file']).read_bytes()


def test_math_guard_does_not_depend_on_classifier(monkeypatch):
    from doclint import engine, structure
    source = (DEST / '04_tham_chieu_cong_thuc.docx').read_bytes()
    monkeypatch.setattr(structure, 'predict', lambda *args: ('body', 0.99))
    analysis = engine.inspect(source)
    math_block = next(b for b in analysis['blocks'] if b['text'].startswith('Sai số được tính'))
    assert math_block['protected'] and math_block['role'] == 'keep'


def test_deep_heading_guard_does_not_depend_on_classifier(monkeypatch):
    from doclint import engine, structure
    source = (DEST / '02_de_muc_mo_ho.docx').read_bytes()
    monkeypatch.setattr(structure, 'predict', lambda *args: ('body', 0.99))
    block = next(b for b in engine.inspect(source)['blocks'] if b['text'].startswith('1.1.1.1'))
    assert block['level'] == 4 and block['protected']
