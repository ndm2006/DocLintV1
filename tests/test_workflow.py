import copy
import io
import time
import zipfile
import pytest
from fastapi.testclient import TestClient
from doclint import app as service
from doclint.engine import inspect, edit, read_package, parse, NS, tag, canonical, DocumentError
from scripts.make_demo import demo_bytes

@pytest.fixture
def client():
    with service.lock: service.sessions.clear(); service.runs.clear()
    with TestClient(service.app) as c: yield c
    with service.lock: service.sessions.clear(); service.runs.clear()

def upload(c,data=None):
    response=c.post('/api/v1/sessions',files={'file':('thesis.docx',demo_bytes() if data is None else data)})
    assert response.status_code==202,response.text
    s=response.json(); return s,{'Authorization':'Bearer '+s['access_token']}
def wait(c,rid,h,target):
    for _ in range(200):
        res=c.get('/api/v1/runs/'+rid,headers=h); assert res.status_code==200,res.text
        r=res.json()
        if r['state'] in target:return r
        time.sleep(.01)
    pytest.fail('worker did not reach target state')
def approved(c,s,h):
    r=wait(c,s['run_id'],h,{'REVIEW_WAIT','FAILED'}); assert r['state']=='REVIEW_WAIT',r
    payload={'fingerprint':r['analysis']['fingerprint'],'decisions':{b['id']:b['role'] for b in r['analysis']['blocks'] if b['needs_review']}}
    assert c.post('/api/v1/runs/'+s['run_id']+'/decisions',headers=h,json=payload).status_code==202
    return wait(c,s['run_id'],h,{'PARTIAL','FAILED'})
def repack(parts):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    return out.getvalue()

def test_end_to_end(client):
    s,h=upload(client); r=approved(client,s,h)
    assert r['state']=='PARTIAL'; assert r['report']['integrity']=='PASS'
    result=client.get('/api/v1/runs/'+s['run_id']+'/artifacts/docx',headers=h)
    assert result.status_code==200
    original,root=read_package(demo_bytes()); output,edited=read_package(result.content)
    assert root.xpath('//w:t/text()',namespaces=NS)==edited.xpath('//w:t/text()',namespaces=NS)
    assert canonical(root.find('.//w:tbl',NS))==canonical(edited.find('.//w:tbl',NS))
    assert canonical(root.find('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))==canonical(edited.find('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath'))
    for n in original:
        if n!='word/document.xml': assert original[n]==output[n]
    body=edited.find('w:body',NS)
    assert body[2].find('w:pPr/w:spacing',NS).get(tag('line'))=='264'
    assert body[2].find('w:r/w:rPr/w:sz',NS).get(tag('val'))=='26'
    assert body[2].find('w:r/w:rPr/w:rFonts',NS).get(tag('ascii'))=='Times New Roman'
    assert body[3].find('w:pPr/w:outlineLvl',NS).get(tag('val'))=='2'
    assert r['report']['page_geometry_applied'] is False
    report=client.get('/api/v1/runs/'+s['run_id']+'/artifacts/report',headers=h).json()
    assert report['checks']['layout']=='NOT_CHECKED'
    assert result.headers['cache-control']=='no-store'

def test_auth_delete_and_rerun(client):
    s,h=upload(client)
    assert client.get('/api/v1/runs/'+s['run_id']).status_code==403
    assert client.get('/api/v1/sessions/'+s['session_id'],headers={'Authorization':'Bearer wrong'}).status_code==403
    r=approved(client,s,h); assert r['state']=='PARTIAL'
    old=r['report']['source_sha256']
    retry=client.post('/api/v1/sessions/'+s['session_id']+'/runs',headers=h)
    assert retry.status_code==202
    s['run_id']=retry.json()['run_id']; r=approved(client,s,h)
    assert r['report']['source_sha256']==old
    assert client.delete('/api/v1/sessions/'+s['session_id'],headers=h).status_code==200
    assert client.get('/api/v1/runs/'+s['run_id']+'/artifacts/docx',headers=h).status_code==404

def test_cancel_and_no_early_download(client):
    s,h=upload(client); wait(client,s['run_id'],h,{'REVIEW_WAIT'})
    assert client.get('/api/v1/runs/'+s['run_id']+'/artifacts/docx',headers=h).status_code==409
    assert client.post('/api/v1/runs/'+s['run_id']+'/cancel',headers=h).json()['state']=='CANCELLED'
    assert client.get('/api/v1/runs/'+s['run_id']+'/artifacts/docx',headers=h).status_code==409

def test_expiry(client):
    s,h=upload(client)
    with service.lock:service.sessions[s['session_id']]['expires_at']=time.time()-1
    assert client.get('/api/v1/sessions/'+s['session_id'],headers=h).status_code==410
    assert s['session_id'] not in service.sessions

def test_decision_schema(client):
    s,h=upload(client); r=wait(client,s['run_id'],h,{'REVIEW_WAIT'})
    path='/api/v1/runs/'+s['run_id']+'/decisions'
    for data in [{'fingerprint':'wrong','decisions':{}},{'fingerprint':r['analysis']['fingerprint'],'decisions':{'unknown':'body'}},{'fingerprint':r['analysis']['fingerprint'],'decisions':{'b0':'invented'}}]:
        assert client.post(path,headers=h,json=data).status_code==422
    assert client.post(path,headers=h,json={'fingerprint':r['analysis']['fingerprint'],'decisions':{}}).status_code==202
    result=wait(client,s['run_id'],h,{'PARTIAL','FAILED'})
    assert result['state']=='PARTIAL'
    assert all(c['block_id']!='b0' for c in result['report']['changes'])

@pytest.mark.parametrize('mutation',['traversal','macro','dtd','missing_relationship','broken_xml','signature'])
def test_bad_packages(mutation):
    parts,_=read_package(demo_bytes())
    if mutation=='traversal':parts['../escape']='no'
    if mutation=='macro':parts['word/vbaProject.bin']=b'bad'
    if mutation=='dtd':parts['word/document.xml']=b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
    if mutation=='missing_relationship':del parts['word/media/pixel.png']
    if mutation=='broken_xml':parts['word/document.xml']=b'<broken'
    if mutation=='signature':parts['_xmlsignatures/sig1.xml']=b'<x/>'
    with pytest.raises(DocumentError):read_package(repack(parts))

def test_invalid_file(client):
    assert client.post('/api/v1/sessions',files={'file':('fake.docx',b'not zip')}).status_code==422

def test_duplicate_zip_entries():
    out=io.BytesIO()
    with pytest.warns(UserWarning):
        with zipfile.ZipFile(out,'w') as z:z.writestr('same','a');z.writestr('same','b')
    with pytest.raises(DocumentError):read_package(out.getvalue())

def test_analysis_tampering():
    data=demo_bytes(); a=inspect(data)
    a['blocks'][0]['text']='Rewritten'
    with pytest.raises(DocumentError):edit(data,a,{})

def test_simple_page_geometry():
    parts,root=read_package(demo_bytes());body=root.find('w:body',NS)
    for node in list(body):
        if node.tag not in {tag('p'),tag('sectPr')} or (node.tag==tag('p') and not node.xpath('.//w:t',namespaces=NS)):body.remove(node)
    from lxml import etree as E
    parts['word/document.xml']=E.tostring(root)
    data=repack(parts);a=inspect(data)
    result,report=edit(data,a,{b['id']:b['role'] for b in a['blocks'] if b['needs_review']})
    assert report['page_geometry_applied']
    _,root=read_package(result)
    assert root.find('.//w:pgMar',NS).get(tag('left'))=='1984'

def test_protected_and_landscape():
    parts,root=read_package(demo_bytes());root.find('.//w:pgSz',NS).set(tag('orient'),'landscape')
    from lxml import etree as E
    parts['word/document.xml']=E.tostring(root);data=repack(parts);a=inspect(data)
    result,r=edit(data,a,{})
    _,after=read_package(result)
    assert canonical(root.find('.//w:sectPr',NS))==canonical(after.find('.//w:sectPr',NS))

def test_web_and_capabilities(client):
    assert client.get('/').status_code==200
    assert client.get('/app.js').status_code==200
    assert client.get('/api/v1/capabilities').json()['ai']['evaluated'] is False

@pytest.mark.parametrize('damage',['text','image','table','math','protected'])
def test_integrity_gate_blocks_corruption(damage):
    from doclint.engine import validate_integrity
    from lxml import etree as E
    source=demo_bytes();parts,root=read_package(source)
    if damage=='text':root.find('.//w:t',NS).text='Changed'
    if damage=='image':parts['word/media/pixel.png']=b'corrupted image'
    if damage=='table':root.find('.//w:tbl//w:t',NS).text='Different cell'
    if damage=='math':root.find('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}t').text='x = 0'
    if damage=='protected':root.find('.//w:tbl/w:tblPr',NS).set('unexpected','change')
    parts['word/document.xml']=E.tostring(root)
    with pytest.raises(DocumentError) as exc:validate_integrity(source,repack(parts),{0,1,2,3,4})
    assert exc.value.code=='INTEGRITY_FAILED'

def test_invalid_parent_rejected():
    data=demo_bytes();a=inspect(data)
    with pytest.raises(DocumentError):edit(data,a,{'b0':'keep','b1':'heading','b3':'heading'})

def test_delete_while_worker_runs(client,monkeypatch):
    import threading
    entered=threading.Event(); release=threading.Event(); original=service.edit
    def slow(*args,**kwargs):
        entered.set();assert release.wait(3);return original(*args,**kwargs)
    monkeypatch.setattr(service,'edit',slow)
    s,h=upload(client);r=wait(client,s['run_id'],h,{'REVIEW_WAIT'})
    payload={'fingerprint':r['analysis']['fingerprint'],'decisions':{}}
    assert client.post('/api/v1/runs/'+s['run_id']+'/decisions',headers=h,json=payload).status_code==202
    assert entered.wait(2)
    assert client.delete('/api/v1/sessions/'+s['session_id'],headers=h).status_code==200
    release.set()
    service.executor.submit(lambda:None).result(timeout=3)
    assert s['run_id'] not in service.runs
    assert client.get('/api/v1/runs/'+s['run_id']+'/artifacts/docx',headers=h).status_code==404

def test_cancel_while_worker_runs(client,monkeypatch):
    import threading
    entered=threading.Event();release=threading.Event();original=service.edit
    def slow(*args,**kwargs):entered.set();assert release.wait(3);return original(*args,**kwargs)
    monkeypatch.setattr(service,'edit',slow)
    s,h=upload(client);r=wait(client,s['run_id'],h,{'REVIEW_WAIT'})
    assert client.post('/api/v1/runs/'+s['run_id']+'/decisions',headers=h,json={'fingerprint':r['analysis']['fingerprint'],'decisions':{}}).status_code==202
    assert entered.wait(2)
    assert client.post('/api/v1/runs/'+s['run_id']+'/cancel',headers=h).status_code==200
    release.set();service.executor.submit(lambda:None).result(timeout=3)
    r=client.get('/api/v1/runs/'+s['run_id'],headers=h).json()
    assert r['state']=='CANCELLED'
    assert client.get('/api/v1/runs/'+s['run_id']+'/artifacts/docx',headers=h).status_code==409

def test_utf16_dtd_rejected():
    with pytest.raises(DocumentError):parse('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x><x/>'.encode('utf-16'))
