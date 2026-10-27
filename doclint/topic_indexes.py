"""Only topic casing and missing Word indexes; no cover layout operations."""
import re
import copy
from .index_fields import generate,NS,Q

# Lower only ordinary words we can identify. Unknown uppercase names/acronyms
# remain unchanged instead of guessing their spelling. Mixed-case topics stay as-is.
WORDS=set('hệ thống quản lý mượn thiết bị thiết kế tự động điều chỉnh nhiệt độ trong sấy hoa quả giám sát và ứng dụng xây dựng nghiên cứu phân tích đánh giá mô hình dữ liệu mạng xử lý thông tin phát triển phần mềm nhận diện học máy thử nghiệm phòng thực hành sử dụng công nghệ kết nối cho với của các tại từ trên dưới bằng phương pháp tối ưu hóa hỗ trợ'.split())
PROPER={'HÀ NỘI':'Hà Nội','HỒ CHÍ MINH':'Hồ Chí Minh','ĐÀ NẴNG':'Đà Nẵng'}


def recognition_view(root):
    """Private empty TC entries must not hide headings on the next upload.

    Foreign fields and all source XML remain intact; only recognition uses a copy.
    """
    from .index_fields import owned,tc_type
    result=copy.deepcopy(root);collections=set()
    for node in result.find('w:body',NS):
        if owned(node):
            for instruction in node.xpath('.//w:instrText/text()',namespaces=NS):
                match=re.match(r'\s*TOC\s+\\f\s+([A-Za-z])\b',instruction,re.I)
                if match:collections.add(match.group(1).upper())
    for paragraph in result.findall('.//w:p',NS):
        if not any(n.get(Q+'name','').startswith('DocLintIndex_') for n in paragraph.findall('w:bookmarkStart',NS)):continue
        for field in list(paragraph.findall('w:fldSimple',NS)):
            if tc_type(field.get(Q+'instr','')) in collections and not ''.join(field.xpath('.//w:t/text()',namespaces=NS)).strip():paragraph.remove(field)
    return result


def sentence_case(value,first=True):
    if not value.isupper():return value,[]
    unknown=[]
    def word(match):
        token=match.group()
        if token.casefold() in WORDS:return token.lower()
        unknown.append(token);return token
    result=re.sub(r'[^\W\d_]+',word,value,flags=re.UNICODE)
    for source,target in PROPER.items():result=re.sub(re.escape(source),lambda _:target,result,flags=re.I)
    if first:
        result=re.sub(r'[^\W\d_]',lambda m:m.group().upper(),result,count=1)
    return result,unknown


def apply(root,analysis,decisions,parts):
    body=root.find('w:body',NS);original=list(body);case_changes=[];warnings=[]
    for block in analysis['blocks']:
        if block['protected'] or block.get('path') or block['role'] not in {'cover_subject','cover_subject_continuation'}:continue
        node=original[block['index']]
        # Do not rewrite field results, tracked changes, links or embedded objects.
        if node.xpath('.//w:fldSimple|.//w:fldChar|.//w:hyperlink|.//w:drawing|.//w:pict|.//w:ins|.//w:del',namespaces=NS):continue
        before=''.join(node.xpath('.//w:t/text()',namespaces=NS))
        after,unknown=sentence_case(before,first=block['role']=='cover_subject')
        if len(before)!=len(after):continue
        if before!=after:
            offset=0
            for value in node.findall('.//w:t',NS):
                length=len(value.text or '');value.text=after[offset:offset+length];offset+=length
            case_changes.append({'block_id':block['id'],'before':before,'after':after})
        if unknown:warnings.append('Tên đề tài '+block['id']+': giữ nguyên các từ chưa đủ căn cứ đổi hoa/thường ('+', '.join(dict.fromkeys(unknown))+'); vui lòng kiểm tra tên riêng/chữ viết tắt.')
    indexes=generate(body,analysis,decisions,original=original,parts=parts)
    return {'case_changes':case_changes,'indexes':indexes,'warnings':warnings+indexes.get('warnings',[]),
            'source_positions':{i:body.index(node) if node in body else None for i,node in enumerate(original)}}
