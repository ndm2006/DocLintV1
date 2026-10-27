"""Pinned formatting profile extracted from the user-supplied HUST 2019.1 template."""
PROFILE = {
    'id': 'HUST20191_S11', 'version': '0.1.1',
    'font': 'Times New Roman', 'size_pt': 13, 'line': 1.1,
    'margins_cm': {'left': 3.5, 'right': 2.5, 'top': 2, 'bottom': 2},
    'page_twips': {'w': 11907, 'h': 16840},
    'margin_twips': {'left': 1985, 'right': 1418, 'top': 1134, 'bottom': 1134, 'gutter': 0},
    'paragraphs': {
        'body': {'before': 60, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'both'},
        'chapter': {'before': 120, 'after': 240, 'line': 264, 'lineRule': 'auto', 'alignment': 'center'},
        'heading': {'before': 120, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'both'},
    },
    'source': {'filename': 'Mẫu ĐATN_2019_version 1_1 (1).docx',
               'sha256': '5003fc2fab89b7fc1bead02e9d004607610cf8984e32230e12a0c903470917d5',
               'note': 'Extracted docDefaults, Heading1–3 inheritance and section properties; original document is not redistributed.'},
}
