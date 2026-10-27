from pathlib import Path
import pytest
from doclint.topic_case import sentence_case
from doclint.engine import inspect,edit,read_package,NS,validate_integrity,DocumentError
from tests.test_cover import fixture_cover

@pytest.mark.parametrize('text,expected',[
 ('HỆ THỐNG QUẢN LÝ MƯỢN THIẾT BỊ','Hệ thống quản lý mượn thiết bị'),
 ('THIẾT KẾ HỆ THỐNG TỰ ĐỘNG ĐIỀU CHỈNH','Thiết kế hệ thống tự động điều chỉnh'),
 ('THIẾT KẾ HỆ THỐNG API TẠI HÀ NỘI','Thiết kế hệ thống API tại Hà Nội'),
 ('Thiết kế hệ thống IoT','Thiết kế hệ thống IoT'),
])
def test_topic_cases(text,expected):
 assert sentence_case(text)[0]==expected

def test_split_title_only_changes_case_and_never_inserts_indexes():
 data=fixture_cover(['ĐỒ ÁN TỐT NGHIỆP','THIẾT KẾ HỆ THỐNG TỰ ĐỘNG ĐIỀU CHỈNH','NHIỆT ĐỘ TRONG THIẾT BỊ SẤY HOA QUẢ','Sinh viên: Người thử nghiệm'])
 out,report=edit(data,inspect(data),{});_,root=read_package(out);_,before=read_package(data)
 body=root.find('w:body',NS)
 assert ''.join(body[1].xpath('.//w:t/text()',namespaces=NS))=='Thiết kế hệ thống tự động điều chỉnh'
 assert ''.join(body[2].xpath('.//w:t/text()',namespaces=NS))=='nhiệt độ trong thiết bị sấy hoa quả'
 assert len(body)==len(before.find('w:body',NS))
 assert root.xpath('//w:instrText/text()',namespaces=NS)==before.xpath('//w:instrText/text()',namespaces=NS)
 again,_=edit(out,inspect(out),{})
 assert read_package(again)[0]==read_package(out)[0]

def test_keep_decision_preserves_uppercase():
 data=fixture_cover(['ĐỒ ÁN TỐT NGHIỆP','HỆ THỐNG QUẢN LÝ MƯỢN THIẾT BỊ','Sinh viên: Người thử nghiệm'])
 a=inspect(data);b=next(b for b in a['blocks'] if b['role']=='cover_subject')
 out,r=edit(data,a,{b['id']:'keep'})
 assert b['text'] in read_package(out)[1].xpath('//w:t/text()',namespaces=NS)
 assert not r['topic_case_changes']
