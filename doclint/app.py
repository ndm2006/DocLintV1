import asyncio
import hashlib
import hmac
import io
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from .engine import inspect, edit, DocumentError, TEMPLATE
from .recognizer import REVISION

TTL=1800
sessions={}; runs={}; lock=threading.RLock()
executor=ThreadPoolExecutor(max_workers=1)
TERMINAL={'PARTIAL','READY','FAILED','CANCELLED'}

def cleanup():
    with lock:
        for sid,s in list(sessions.items()):
            if s['expires_at']<=time.time(): remove(sid)
def remove(sid):
    s=sessions.pop(sid,None)
    if s:
        for rid in s['runs']: runs.pop(rid,None)

@asynccontextmanager
async def lifespan(app):
    async def janitor():
        while True:
            await asyncio.sleep(10); cleanup()
    task=asyncio.create_task(janitor())
    yield
    task.cancel()

app=FastAPI(title='DocLint',version='0.1.2',lifespan=lifespan)
@app.middleware('http')
async def safety(request:Request, call_next):
    if request.headers.get('content-length','0').isdigit() and int(request.headers.get('content-length','0'))>21*1024**2:
        return JSONResponse({'code':'RESOURCE_LIMIT','message':'Yêu cầu vượt 21 MiB.'},413)
    # Bound chunked uploads too, before multipart parsing allocates storage.
    received=0; receive=request._receive
    async def limited_receive():
        nonlocal received
        message=await receive(); received+=len(message.get('body',b''))
        if received>21*1024**2: raise DocumentError('Yêu cầu vượt 21 MiB.','RESOURCE_LIMIT')
        return message
    request._receive=limited_receive
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response
@app.exception_handler(DocumentError)
async def document_error(request,exc):
    status={'NOT_FOUND':404,'UNAUTHORIZED':403,'SESSION_EXPIRED':410,'QUEUE_FULL':429,'CONFLICT':409,'RESOURCE_LIMIT':413}.get(exc.code,422)
    return JSONResponse({'code':exc.code,'message':exc.message},status)

def auth(sid,authorization):
    s=sessions.get(sid)
    if not s: raise DocumentError('Phiên không tồn tại hoặc đã hết hạn.','NOT_FOUND')
    token=(authorization or '').removeprefix('Bearer ')
    if not hmac.compare_digest(s['token_hash'],hashlib.sha256(token.encode()).hexdigest()):
        raise DocumentError('Không có quyền truy cập phiên.','UNAUTHORIZED')
    if time.time()>=s['expires_at']:
        remove(sid); raise DocumentError('Phiên đã hết hạn.','SESSION_EXPIRED')
    return s

def getrun(rid,authorization):
    r=runs.get(rid)
    if not r: raise DocumentError('Không tìm thấy lần xử lý.','NOT_FOUND')
    return r,auth(r['session_id'],authorization)

def active(r):
    s=sessions.get(r['session_id'])
    return runs.get(r['id']) is r and s and s['expires_at']>time.time() and r['state'] not in {'CANCELLED','CANCEL_REQUESTED'}
def state(r,value):
    with lock:
        if not active(r): return False
        r['state']=value; r['history'].append({'stage':value,'at':time.time()}); return True

def capacity():
    if sum(r['state'] not in TERMINAL and r['state']!='REVIEW_WAIT' for r in runs.values())>=5:
        raise DocumentError('Hàng đợi đầy. Vui lòng thử lại.','QUEUE_FULL')

def process(r,source,decisions=None):
    started=time.monotonic()
    try:
        if decisions is None:
            if not state(r,'ANALYZING'): return
            analysis=inspect(source)
            if not analysis['document_type']['accepted']:
                result=analysis['document_type'];raise DocumentError(result['message'],result['code'])
            with lock:
                if not active(r): return
                r['analysis']=analysis
            if any(b['needs_review'] for b in analysis['blocks']): state(r,'REVIEW_WAIT'); return
        if not state(r,'PLANNING'): return
        if not state(r,'EDITING'): return
        output,report=edit(source,r['analysis'],decisions or {})
        if not state(r,'VALIDATING'): return
        if time.monotonic()-started>300: raise DocumentError('Vượt thời gian xử lý.','RESOURCE_LIMIT')
        if not state(r,'FINAL_CHECK'): return
        with lock:
            if not active(r): return
            r['output']=output; r['report']=report; state(r,'PARTIAL')
    except DocumentError as e:
        with lock:
            if active(r): r['error']={'code':e.code,'message':e.message}; state(r,'FAILED')
    except Exception:
        with lock:
            if active(r): r['error']={'code':'PROCESSING_FAILED','message':'Không xử lý được tài liệu; chưa công bố kết quả.'}; state(r,'FAILED')

def newrun(sid):
    capacity(); rid=str(uuid.uuid4()); s=sessions[sid]
    r={'id':rid,'session_id':sid,'state':'QUEUED','created_at':time.time(),'history':[{'stage':'QUEUED','at':time.time()}]}
    runs[rid]=r; s['runs'].append(rid); executor.submit(process,r,s['source']); return r

def public(r):
    return {k:v for k,v in r.items() if k not in {'output'}}

@app.get('/api/v1/capabilities')
def capabilities():
    return {'ai':{'available':True,'revision':REVISION,'recognizer_revision':'structure-context-0.3','mode':'word-structure-rules-ml','experimental':True,'evaluated':False},'renderer':False,'max_upload_mib':20,'ttl_seconds':TTL,'max_sessions':5}
@app.get('/api/v1/template')
def template(): return TEMPLATE
@app.post('/api/v1/sessions',status_code=202)
async def upload(file:UploadFile=File(...)):
    try: data=await file.read(20*1024**2+1)
    finally: await file.close()
    # Validate in a thread to keep API responsive; no external network or XML resources.
    analysis=await asyncio.to_thread(inspect,data)
    if not analysis['document_type']['accepted']:
        result=analysis['document_type']
        raise DocumentError(result['message'],result['code'])
    with lock:
        cleanup(); capacity()
        if len(sessions)>=5: raise DocumentError('Đã đạt giới hạn 5 phiên; hãy xóa phiên cũ.','QUEUE_FULL')
        sid=str(uuid.uuid4()); token=secrets.token_urlsafe(32); now=time.time()
        sessions[sid]={'id':sid,'name':Path(file.filename or 'document.docx').name[:200], 'source':data,
                       'token_hash':hashlib.sha256(token.encode()).hexdigest(),'created_at':now,'expires_at':now+TTL,'runs':[]}
        r=newrun(sid)
        return {'session_id':sid,'run_id':r['id'],'access_token':token,'expires_at':now+TTL}
@app.get('/api/v1/sessions/{sid}')
def session(sid:str,authorization:str|None=Header(None)):
    with lock:
        s=auth(sid,authorization); return {k:v for k,v in s.items() if k not in {'source','token_hash'}}
@app.get('/api/v1/runs/{rid}')
def run(rid:str,authorization:str|None=Header(None)):
    with lock: r,_=getrun(rid,authorization); return public(r)
class Decisions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    fingerprint:str
    decisions:dict[str,str]
@app.post('/api/v1/runs/{rid}/decisions',status_code=202)
def decide(rid:str,payload:Decisions,authorization:str|None=Header(None)):
    with lock:
        r,s=getrun(rid,authorization)
        if r['state']!='REVIEW_WAIT': raise DocumentError('Lần xử lý không chờ xác nhận.','CONFLICT')
        a=r['analysis']; known={b['id']:b for b in a['blocks'] if b['needs_review']}
        if payload.fingerprint!=a['fingerprint'] or any(k not in known or v not in {'body','chapter','heading','keep'} for k,v in payload.decisions.items()):
            raise DocumentError('Quyết định không khớp tài liệu.','AI_OUTPUT_INVALID')
        capacity(); r['decisions']=payload.decisions; state(r,'QUEUED')
        executor.submit(process,r,s['source'],payload.decisions); return {'state':'QUEUED'}
@app.post('/api/v1/sessions/{sid}/runs',status_code=202)
def rerun(sid:str,authorization:str|None=Header(None)):
    with lock:
        s=auth(sid,authorization)
        if any(runs[rid]['state'] not in TERMINAL for rid in s['runs']): raise DocumentError('Hãy hoàn tất hoặc hủy lần đang chạy.','CONFLICT')
        # Keep at most ten runs to bound retained artifacts.
        if len(s['runs'])>=10: raise DocumentError('Đạt giới hạn 10 lượt; hãy tạo phiên mới.','RESOURCE_LIMIT')
        return {'run_id':newrun(sid)['id']}
@app.post('/api/v1/runs/{rid}/cancel')
def cancel(rid:str,authorization:str|None=Header(None)):
    with lock:
        r,_=getrun(rid,authorization)
        if r['state'] not in TERMINAL: r['state']='CANCELLED'; r['output']=None
        return {'state':r['state']}
@app.delete('/api/v1/sessions/{sid}')
def delete(sid:str,authorization:str|None=Header(None)):
    with lock: auth(sid,authorization); remove(sid); return {'state':'DELETED'}
@app.get('/api/v1/runs/{rid}/artifacts/{kind}')
def artifact(rid:str,kind:str,authorization:str|None=Header(None)):
    with lock:
        r,_=getrun(rid,authorization)
        if r['state'] not in {'READY','PARTIAL'}: raise DocumentError('Kết quả chưa được công bố.','CONFLICT')
        if kind=='report': return JSONResponse(r['report'])
        if kind!='docx': raise DocumentError('Không có loại sản phẩm này.','NOT_FOUND')
        return StreamingResponse(io.BytesIO(r['output']),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                 headers={'Content-Disposition':'attachment; filename="DocLint-normalized.docx"'})
app.mount('/',StaticFiles(directory=Path(__file__).parent/'static',html=True),name='web')
