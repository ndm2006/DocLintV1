"""Deterministic suitability gate, not a universal semantic thesis classifier."""
import re
import unicodedata


def assess(blocks):
    leading=[' '.join(unicodedata.normalize('NFC',b['text']).split()) for b in blocks[:20]]
    positive=any(re.match(r'^(?:báo cáo\s+)?(?:đồ án(?:\s+tốt nghiệp)?|khóa luận(?:\s+tốt nghiệp)?|luận văn)(?:\s|$|[–—:.-])',t,re.I) for t in leading)
    negative=any(re.match(r'^(?:báo cáo công việc(?:\s+tuần)?|báo cáo tuần|báo cáo quá trình|báo cáo tiến độ|biên bản họp|đơn xin(?: việc| nghỉ phép)?|sơ yếu lý lịch|curriculum vitae|hóa đơn)(?:\s*[:–—-].*|\s+(?:\d|năm|tháng|số).*)?$',t,re.I) for t in leading[:5])
    chapters=sum(b['role']=='chapter' and not b['protected'] for b in blocks)
    headings=sum(b['role']=='heading' and not b['protected'] for b in blocks)
    body=sum(b['role']=='body' and len(b['text'].split())>=12 for b in blocks)
    structured=chapters>=1 and (headings>=1 or body>=2)
    accepted=structured and not negative
    if accepted:
        code='THESIS_COMPATIBLE'
        message='Tài liệu có cấu trúc chương và nội dung phù hợp để chuẩn hóa theo mẫu đồ án.'
    elif positive and not negative:
        code='THESIS_STRUCTURE_REQUIRED'
        message='Có tiêu đề đồ án nhưng chưa xác định được cấu trúc chương–đề mục. Vui lòng tải file đồ án có cấu trúc rõ hoặc bổ sung Heading/chương rồi thử lại.'
    else:
        code='NOT_A_THESIS'
        message='Tài liệu không phù hợp với đồ án tốt nghiệp trong phạm vi hỗ trợ: chưa có đủ cấu trúc chương–đề mục hoặc là loại văn bản khác. Vui lòng tải lên một file đồ án khác.'
    return {'accepted':accepted,'code':code,'message':message,
            'signals':{'thesis_title':positive,'other_document_title':negative,'chapters':chapters,'headings':headings,'body_paragraphs':body},
            'method':'Dấu hiệu tiêu đề kết hợp cấu trúc; không dùng tên file, không khẳng định phân loại ngữ nghĩa tuyệt đối.'}
