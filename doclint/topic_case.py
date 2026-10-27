"""Conservative sentence casing of recognized cover topics only."""
import re

WORDS=set('hệ thống quản lý mượn thiết bị thiết kế tự động điều chỉnh nhiệt độ trong sấy hoa quả giám sát và ứng dụng xây dựng nghiên cứu phân tích đánh giá mô hình dữ liệu mạng xử lý thông tin phát triển phần mềm nhận diện học máy thử nghiệm phòng thực hành sử dụng công nghệ kết nối cho với của các tại từ trên dưới bằng phương pháp tối ưu hóa hỗ trợ'.split())
PROPER={'HÀ NỘI':'Hà Nội','HỒ CHÍ MINH':'Hồ Chí Minh','ĐÀ NẴNG':'Đà Nẵng'}


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


def apply(root, analysis, allowed):
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    body=root.find('w:body',ns);changes=[];warnings=[]
    for block in analysis['blocks']:
        if block['index'] not in allowed or block['protected'] or block.get('path') or block['role'] not in {'cover_subject','cover_subject_continuation'}:continue
        node=body[block['index']]
        if node.xpath('.//w:fldSimple|.//w:fldChar|.//w:hyperlink|.//w:drawing|.//w:pict|.//w:ins|.//w:del',namespaces=ns):continue
        before=''.join(node.xpath('.//w:t/text()',namespaces=ns))
        after,unknown=sentence_case(before,first=block['role']=='cover_subject')
        if len(before)!=len(after):continue
        if before!=after:
            offset=0
            for text in node.findall('.//w:t',ns):
                length=len(text.text or '');text.text=after[offset:offset+length];offset+=length
            changes.append({'block_id':block['id'],'before':before,'after':after})
        if unknown:warnings.append('Tên đề tài '+block['id']+': giữ nguyên từ chưa rõ tên riêng/chữ viết tắt: '+', '.join(dict.fromkeys(unknown)))
    return changes,warnings
