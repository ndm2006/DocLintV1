"""Hand-authored labels and independent structural assertions for complex DOCX."""
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
    decisions = {bid: labels[bid]['role'] for bid, block in by_id.items() if block['needs_review']}
    output, report = edit(source, analysis, decisions)
    original, before = read_package(source)
    candidate, after = read_package(output)
    assert report['status'] == 'PARTIAL'
    assert report['checks']['layout'] == 'NOT_CHECKED'
    assert before.xpath('//w:t/text()', namespaces=NS) == after.xpath('//w:t/text()', namespaces=NS)
    assert set(candidate)-set(original) <= {'word/styles.xml','word/_rels/document.xml.rels'}
    for name, data in original.items():
        if name not in {'word/document.xml','word/styles.xml','word/_rels/document.xml.rels','[Content_Types].xml'}:
            assert data == candidate[name], name
    for path in ['.//w:tbl', './/{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath']:
        assert [canonical(n) for n in before.findall(path, NS)] == [canonical(n) for n in after.findall(path, NS)]
    before_body, after_body = before.find('w:body', NS), after.find('w:body', NS)
    for bid, label in labels.items():
        if label['protected'] or label['role'] == 'keep':
            index = int(bid[1:])
            assert canonical(before_body[index]) == canonical(after_body[index]), bid
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
        assert not report['page_geometry_applied']
        assert [canonical(n) for n in before.findall('.//w:sectPr', NS)] == [canonical(n) for n in after.findall('.//w:sectPr', NS)]
    elif not case['file'].startswith('05_'):
        assert report['page_geometry_applied']
    # Original shared styles stay intact; only isolated, approved style definitions append.
    old_styles=E.fromstring(original['word/styles.xml'])
    new_styles=E.fromstring(candidate['word/styles.xml'])
    additions=report['heading_styles_added']
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
