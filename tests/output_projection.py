"""Project source blocks after permitted topic/index operations for old assertions."""
import copy
from lxml import etree as E
from doclint.engine import NS,tag


def source_body(root,report):
    report=report.get('report',report)
    body=root.find('w:body',NS);positions=report['derived']['source_positions']
    return [body[positions[i] if i in positions else positions[str(i)]] for i in range(len(positions))]


def assert_source_text(before,after,report):
    report=report.get('report',report)
    old=list(before.find('w:body',NS));new=source_body(after,report)
    casing={int(c['block_id'][1:]):c for c in report['derived']['case_changes']}
    for i,(p,q) in enumerate(zip(old,new)):
        left=''.join(p.xpath('.//w:t/text()',namespaces=NS))
        right=''.join(q.xpath('.//w:t/text()',namespaces=NS))
        if i in casing:
            assert left==casing[i]['before'] and right==casing[i]['after']
            assert left.casefold()==right.casefold()
        elif '[chưa cập nhật trường]' in left and p.find('w:fldSimple',NS) is not None and q.find('w:fldSimple',NS) is None:
            assert right==''.join(p.xpath('./w:r/w:t/text()',namespaces=NS))
        else:assert left==right,(i,left,right)


def without_index_anchors(node):
    node=copy.deepcopy(node)
    for item in list(node.findall('.//w:fldSimple',NS)):
        if (item.get(tag('instr'),'').lstrip().startswith('TC ')
            and item.getparent().find('w:bookmarkStart',NS) is not None):item.getparent().remove(item)
    for item in list(node.findall('.//w:bookmarkStart',NS)):
        if item.get(tag('name'),'').startswith('DocLintIndex_'):
            key=item.get(tag('id'));parent=item.getparent();parent.remove(item)
            for end in parent.findall('w:bookmarkEnd',NS):
                if end.get(tag('id'))==key:parent.remove(end)
    return node
