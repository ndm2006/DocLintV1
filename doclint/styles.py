"""Append isolated heading styles without changing a shared source style."""
import copy
from lxml import etree as E
from .template import PROFILE

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'w': W}
Q = '{'+W+'}'


def signature(node):
    return (node.tag, tuple(sorted(node.attrib.items())), node.text or '',
            tuple(signature(child) for child in node))


def style_definition(sid, level):
    root = E.Element(Q+'style', nsmap={'w': W})
    root.set(Q+'type', 'paragraph'); root.set(Q+'styleId', sid)
    def child(parent, name, **attrs):
        node = E.SubElement(parent, Q+name)
        for key, value in attrs.items(): node.set(Q+key, str(value))
        return node
    child(root, 'name', val=f'heading {level}' if sid == f'Heading{level}' else f'DocLint Heading {level}')
    alias='CHUONG' if level==1 else f'Cap {level-1}'
    child(root, 'aliases', val=alias if sid==f'Heading{level}' else 'DocLint '+alias)
    child(root, 'qFormat')
    props = child(root, 'pPr')
    child(props, 'keepNext', val=1)
    if level == 1: child(props, 'pageBreakBefore', val=1)
    rules = PROFILE['paragraphs']['chapter' if level == 1 else 'heading']
    child(props, 'spacing', **{k:rules[k] for k in ('before', 'after', 'line', 'lineRule')})
    child(props, 'jc', val=rules['alignment']); child(props, 'outlineLvl', val=level-1)
    runs = child(root, 'rPr')
    child(runs, 'rFonts', ascii=PROFILE['font'], hAnsi=PROFILE['font'], eastAsia=PROFILE['font'], cs=PROFILE['font'])
    child(runs, 'b', val=1); child(runs, 'i', val=0)
    if level == 1: child(runs, 'caps', val=1)
    child(runs, 'color', val='000000'); child(runs, 'sz', val=26); child(runs, 'szCs', val=26)
    return root


def serialize(node):
    return E.tostring(node, xml_declaration=True, encoding='UTF-8', standalone=True)


def ensure_heading_styles(parts, levels, parser):
    if not levels: return {}, {}
    root = parser(parts['word/styles.xml']) if 'word/styles.xml' in parts else E.Element(Q+'styles', nsmap={'w': W})
    existing = {node.get(Q+'styleId'):node for node in root.findall('w:style', NS)}
    selected, added = {}, {}
    for level in sorted(set(levels)):
        # Never bind a manually numbered heading to an existing auto-numbering style.
        standard=f'Heading{level}'
        sid=standard if standard not in existing or signature(existing[standard]) == signature(style_definition(standard,level)) else f'DocLintHeading{level}'
        suffix = 1
        while sid in existing and signature(existing[sid]) != signature(style_definition(sid, level)):
            suffix += 1; sid = f'DocLintHeading{level}_{suffix}'
        if sid not in existing:
            root.append(style_definition(sid, level)); added[sid] = level
        selected[level] = sid
    if not added: return selected, {}
    parts['word/styles.xml'] = serialize(root)
    relname = 'word/_rels/document.xml.rels'
    rels = parser(parts[relname]) if relname in parts else E.Element('{'+REL+'}Relationships', nsmap={None:REL})
    if not any(n.get('Type') == R+'/styles' for n in rels):
        ids = {n.get('Id') for n in rels}; rid = 'DocLintStyles'
        while rid in ids: rid += '_'
        E.SubElement(rels, '{'+REL+'}Relationship', Id=rid, Type=R+'/styles', Target='styles.xml')
        parts[relname] = serialize(rels)
    types = parser(parts['[Content_Types].xml'])
    if not any(n.get('PartName') == '/word/styles.xml' for n in types):
        E.SubElement(types, '{'+CT+'}Override', PartName='/word/styles.xml', ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml')
        parts['[Content_Types].xml'] = serialize(types)
    return selected, added


def validate_style_parts(original, candidate, additions, parser):
    """Only approved style definitions and their two OPC registrations may differ."""
    names = {'word/styles.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}
    if not additions:
        return set()
    old = parser(original['word/styles.xml']) if 'word/styles.xml' in original else E.Element(Q+'styles', nsmap={'w':W})
    new = copy.deepcopy(parser(candidate['word/styles.xml']))
    for sid, level in additions.items():
        found = new.xpath('./w:style[@w:styleId=$sid]', namespaces=NS, sid=sid)
        if len(found) != 1 or signature(found[0]) != signature(style_definition(sid, level)):
            raise ValueError('Unexpected heading style definition')
        new.remove(found[0])
    if signature(old) != signature(new):
        raise ValueError('A shared style or defaults changed')
    for name, root_name, selector in [
        ('word/_rels/document.xml.rels', '{'+REL+'}Relationships', 'relationship'),
        ('[Content_Types].xml', '{'+CT+'}Types', 'content_type'),
    ]:
        old = parser(original[name]) if name in original else E.Element(root_name)
        new = copy.deepcopy(parser(candidate[name]))
        if selector == 'relationship':
            existing = any(n.get('Type') == R+'/styles' for n in old)
            added = [n for n in new if n.get('Type') == R+'/styles' and n.get('Id') not in {c.get('Id') for c in old}]
            if not existing:
                if len(added) != 1 or added[0].attrib != {'Id':added[0].get('Id'), 'Type':R+'/styles', 'Target':'styles.xml'}:
                    raise ValueError('Invalid styles relationship')
                new.remove(added[0])
        else:
            if not any(n.get('PartName') == '/word/styles.xml' for n in old):
                added = [n for n in new if n.get('PartName') == '/word/styles.xml']
                if len(added) != 1 or added[0].attrib != {'PartName':'/word/styles.xml', 'ContentType':'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'}:
                    raise ValueError('Invalid styles content type')
                new.remove(added[0])
        if signature(old) != signature(new): raise ValueError('Unapproved package metadata changed')
    return names
