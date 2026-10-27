"""Audit the supplied template's heading inventory without redistributing its DOCX.

Usage: python -m scripts.audit_template_headings TEMPLATE.docx --output audit.json
The expected inventory uses source styles/literal titles, separately from recognition.
"""
import argparse
import hashlib
import json
import unicodedata
from pathlib import Path

from doclint.engine import inspect, edit, read_package, parse, NS, tag
from doclint.structure import WordContext
from doclint.template import PROFILE
from doclint.template_headings import structural_path, block_id, locate


def inventory(data):
    parts, root = read_package(data)
    body = root.find('w:body', NS)
    expected = []
    lists = 0
    literals = {'ĐỀ TÀI TỐT NGHIỆP':'assignment_title', 'Lời cảm ơn':'acknowledgement_title',
                'Tóm tắt nội dung đồ án':'abstract_title', 'MỤC LỤC':'toc_title',
                'TÀI LIỆU THAM KHẢO':'references_title', 'PHỤ LỤC':'appendix_title'}
    for index, top in enumerate(body):
        for node in ([top] if top.tag == tag('p') else top.findall('.//w:p', NS)):
            text = unicodedata.normalize('NFC',''.join(node.xpath('.//w:t/text()', namespaces=NS)).strip())
            if not text:
                continue
            style = node.find('w:pPr/w:pStyle', NS)
            sid = style.get(tag('val')) if style is not None else ''
            role = None
            if sid in {'Heading1','Heading2','Heading3','Heading4'}:
                role = 'chapter' if sid == 'Heading1' else 'heading'
            if sid == 'Subtitle':
                role = 'cover_institution' if index == 0 else 'cover_title' if text == 'ĐỒ ÁN TỐT NGHIỆP' else 'cover_subject' if index == 8 else 'cover_subject_continuation'
            if sid == 'Caption':
                role = 'table_caption' if text.startswith('Bảng') else 'equation_caption' if text.startswith('PT') else 'figure_caption'
            if text in literals and sid not in {'ListParagraph','TOC1','TOC2','TOC3'}:
                role = literals[text]
            if text == 'DANH MỤC HÌNH VẼ' and sid != 'ListParagraph':
                lists += 1
                role = 'list_figures_title' if lists == 1 else 'list_tables_title'
            number = node.find('w:pPr/w:numPr/w:numId', NS)
            if sid == 'ListParagraph' and number is not None and number.get(tag('val')) == '17':
                role = 'appendix_item_title'
            if role:
                path = structural_path(top,node)
                expected.append({'block_id':block_id(index,path), 'body_index':index, 'path':path,
                                 'text':text, 'source_style':sid, 'expected_role':role,
                                 'expected_level':int(sid[-1]) if role == 'heading' else None})
    return expected


def effective_format(node, context):
    """Resolve individual attributes, including missing attributes of direct overrides."""
    style = node.find('w:pPr/w:pStyle', NS)
    chain = list(context.chain(style.get(tag('val')) if style is not None else context.default_style))
    text_runs = [r for r in node.findall('w:r', NS) if r.find('w:t',NS) is not None]
    direct_run = text_runs[0].find('w:rPr',NS) if text_runs else None

    def value(name, attribute='val', run=False, default=None):
        containers = [direct_run if run else node.find('w:pPr',NS)]
        containers += [s.find('w:rPr' if run else 'w:pPr',NS) for s in chain]
        if context.defaults is not None:
            containers.append(context.defaults.find('w:rPrDefault/w:rPr' if run else 'w:pPrDefault/w:pPr',NS))
        for container in containers:
            prop = container.find('w:'+name,NS) if container is not None else None
            if prop is not None:
                result = prop.get(tag(attribute))
                if result is not None:
                    return result
                if name in {'b','i'}:
                    return '1'
        return default

    return {'font':value('rFonts','ascii',True), 'size_pt':int(value('sz',run=True,default='26'))/2,
            'bold':value('b',run=True,default='0') not in {'0','false'},
            'italic':value('i',run=True,default='0') not in {'0','false'},
            'alignment':value('jc',default='both'),
            **{key:int(value('spacing',key,default='0')) for key in ('before','after','line')}}


def audit(data):
    if hashlib.sha256(data).hexdigest() != PROFILE['source']['sha256']:
        raise ValueError('This inventory is pinned to the original supplied template SHA-256.')
    source_parts, source_root = read_package(data)
    source_context = WordContext(source_parts,parse)
    analysis = inspect(data)
    by_id = {b['id']:b for b in analysis['blocks']}
    output, report = edit(data,analysis,{})
    output_parts, output_root = read_package(output)
    output_context = WordContext(output_parts,parse)
    records = inventory(data)
    for item in records:
        block = by_id.get(item['block_id'],{})
        item['recognized_role'] = block.get('role')
        item['recognized'] = (block.get('role') == item['expected_role'] and not block.get('protected',True)
                              and not block.get('needs_review',True)
                              and (item['expected_level'] is None or block.get('level') == item['expected_level']))
        item['source_format'] = effective_format(locate(source_root.find('w:body',NS),item['body_index'],item['path']),source_context)
        item['output_format'] = effective_format(locate(output_root.find('w:body',NS),item['body_index'],item['path']),output_context)
        item['format_matches_source'] = item['source_format'] == item['output_format']
    return {'template':PROFILE['source'], 'app_version':PROFILE['version'],
            'expected_titles':len(records), 'recognized_titles':sum(r['recognized'] for r in records),
            'formats_matching_source':sum(r['format_matches_source'] for r in records),
            'integrity':report['integrity'], 'issues':analysis['template_heading_issues'],
            'note':'Source text and field codes are immutable. Second figure-list label actually precedes table entries. Heading4 is defined in the source but has no nonempty occurrence; covered by synthetic tests. Page starts are additional normalization policy. This is a template inventory, not independent precision/recall.',
            'titles':records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('template',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = audit(args.template.read_bytes())
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print({k:v for k,v in result.items() if k not in {'titles','template','issues','note'}})
    raise SystemExit(0 if result['expected_titles']==result['recognized_titles']==result['formats_matching_source']==51 else 1)
