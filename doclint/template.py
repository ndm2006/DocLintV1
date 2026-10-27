"""Pinned formatting profile extracted from the user-supplied HUST 2019.1 template."""
PROFILE = {
    'id': 'HUST20191_S11', 'version': '0.1.2',
    'font': 'Times New Roman', 'size_pt': 13, 'line': 1.1,
    'margins_cm': {'left': 3.5, 'right': 2.5, 'top': 2, 'bottom': 2},
    'page_twips': {'w': 11907, 'h': 16840},
    'margin_twips': {'left': 1985, 'right': 1418, 'top': 1134, 'bottom': 1134, 'gutter': 0},
    'paragraphs': {
        'acknowledgement_title': {'before': 480, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'center'},
        'abstract_title': {'before': 960, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'center'},
        'acknowledgement': {'before': 60, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'both'},
        'abstract': {'before': 60, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'both'},
        'body': {'before': 60, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'both'},
        'chapter': {'before': 120, 'after': 240, 'line': 264, 'lineRule': 'auto', 'alignment': 'center'},
        'heading': {'before': 120, 'after': 0, 'line': 264, 'lineRule': 'auto', 'alignment': 'both'},
    },
    'source': {'filename': 'Mẫu ĐATN_2019_version 1_1 (1).docx',
               'sha256': '5003fc2fab89b7fc1bead02e9d004607610cf8984e32230e12a0c903470917d5',
               'note': 'Extracted docDefaults, Heading1–4 inheritance, section geometry, cover/front matter, lists, references, appendix and caption formatting; original document is not redistributed.'},
}

# Explicit title profiles: direct properties in the supplied document override defaults.
# Cover font ArnoPro comes from Subtitle; it must be installed legally for visual parity.
def title_rule(before=60, after=0, line=264, alignment='center', size=13,
               font='Times New Roman', bold=True, italic=False, outline=9, **extra):
    return {'before':before,'after':after,'line':line,'lineRule':'auto','alignment':alignment,
            'size_pt':size,'font':font,'bold':bold,'italic':italic,'outline':outline,**extra}

PROFILE['paragraphs'].update({
    'heading4':title_rule(before=40,alignment='both',bold=False,italic=True,outline=3),
    'cover_institution':title_rule(size=15,font='ArnoPro',label='Trường / học viện'),
    'cover_title':title_rule(size=25,font='ArnoPro',label='Tên loại đồ án'),
    'cover_subject':title_rule(before=480,size=23,font='ArnoPro',label='Tên đề tài'),
    'cover_subject_continuation':title_rule(before=0,size=23,font='ArnoPro',label='Tên đề tài (tiếp)'),
    'assignment_title':title_rule(before=480,label='Đề tài tốt nghiệp'),
    'toc_title':title_rule(label='Mục lục'),
    'list_figures_title':title_rule(after=160,line=259,label='Danh mục hình vẽ'),
    'list_tables_title':title_rule(after=160,line=259,label='Danh mục bảng'),
    'references_title':title_rule(before=0,label='Tài liệu tham khảo',outline=0,indent={'left':567,'hanging':567}),
    'appendix_title':title_rule(before=120,after=240,label='Phụ lục',outline=0,indent={'left':567}),
    'appendix_item_title':title_rule(alignment='both',label='Đề mục phụ lục',preserve_numbering=True),
    'figure_caption':title_rule(after=200,line=240,size=12,bold=False,italic=True,color='404040',label='Chú thích hình',keep_next=False),
    'table_caption':title_rule(after=200,line=240,size=12,bold=False,italic=True,color='404040',label='Chú thích bảng'),
    'equation_caption':title_rule(alignment='both',after=200,line=240,size=12,bold=False,italic=True,color='404040',label='Nhãn phương trình',keep_next=False),
})
for role,label in [('acknowledgement_title','Lời cảm ơn'),('abstract_title','Tóm tắt'),('acknowledgement','Nội dung cảm ơn'),('abstract','Nội dung tóm tắt')]:
    PROFILE['paragraphs'][role].update({'label':label,'outline':9})
SPECIAL_ROLES=set(PROFILE['paragraphs'])-{'body','chapter','heading','heading4'}
