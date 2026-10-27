"""Exercise the real API/worker and save input/output pairs for manual Word review.

Outputs are current-program results, NOT independent golden reference documents.
No running server is needed. Uses only the committed anonymous fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from doclint.app import app
from scripts.make_complex_fixtures import DEST


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def require(response, expected=200):
    if response.status_code != expected:
        raise RuntimeError(f'HTTP {response.status_code}: {response.text}')
    return response


def await_run(client, rid, headers):
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        run = require(client.get(f'/api/v1/runs/{rid}', headers=headers)).json()
        if run['state'] in {'REVIEW_WAIT', 'PARTIAL', 'READY', 'FAILED', 'CANCELLED'}:
            return run
        time.sleep(0.03)
    raise RuntimeError('Timed out waiting for the worker.')


def run_all(destination):
    manifest = json.loads((DEST/'manifest.json').read_text(encoding='utf-8'))
    summaries = []
    with TestClient(app) as client:
        for case in manifest['cases']:
            folder = destination/Path(case['file']).stem
            folder.mkdir()
            source = (DEST/case['file']).read_bytes()
            (folder/'01_GOC.docx').write_bytes(source)
            session = None
            try:
                session = require(client.post('/api/v1/sessions', files={'file': (case['file'], source)}), 202).json()
                headers = {'Authorization': 'Bearer '+session['access_token']}
                rid = session['run_id']
                run = await_run(client, rid, headers)
                if run['state'] == 'REVIEW_WAIT':
                    labels = {label['id']: label for label in case['labels']}
                    decisions = {b['id']: labels[b['id']]['role'] for b in run['analysis']['blocks'] if b['needs_review']}
                    dump(folder/'03_LUA_CHON_XAC_NHAN.json', {'note': 'Hand-authored review choices, not model predictions.', 'decisions': decisions})
                    require(client.post(f'/api/v1/runs/{rid}/decisions', headers=headers,
                                        json={'fingerprint': run['analysis']['fingerprint'], 'decisions': decisions}), 202)
                    run = await_run(client, rid, headers)
                if run['state'] != case['expected_status']:
                    raise RuntimeError(f"Unexpected state {run['state']}: {run.get('error')}")
                report = require(client.get(f'/api/v1/runs/{rid}/artifacts/report', headers=headers)).json()
                output = require(client.get(f'/api/v1/runs/{rid}/artifacts/docx', headers=headers)).content
                if report['integrity'] != 'PASS' or report['source_sha256'] != hashlib.sha256(source).hexdigest():
                    raise RuntimeError('Integrity/fingerprint check failed.')
                (folder/'02_DA_XU_LY.docx').write_bytes(output)
                dump(folder/'04_BAO_CAO.json', report)
                dump(folder/'05_KY_VONG_THU_CONG.json', case)
                summaries.append({'file': case['file'], 'result': 'PASS', 'state': run['state'],
                                  'changed_blocks': len(report['changes']), 'kept_blocks': report['kept_blocks'],
                                  'page_geometry_applied': report['page_geometry_applied']})
            except Exception as error:
                summaries.append({'file': case['file'], 'result': 'FAIL', 'error': str(error)})
            finally:
                if session:
                    require(client.delete('/api/v1/sessions/'+session['session_id'], headers=headers))
            print(case['file'], summaries[-1]['result'])
    dump(destination/'KET_QUA.json', summaries)
    (destination/'DOC_TOI_TRUOC.txt').write_text(
        'Mỗi thư mục có 01_GOC.docx và 02_DA_XU_LY.docx để mở cạnh nhau trong Microsoft Word.\n'
        'File 02 là kết quả của chương trình hiện tại, KHÔNG phải bản chuẩn độc lập.\n'
        'Đọc tests/fixtures/complex/HUONG_DAN.md để biết tiêu chí đối chiếu từng mẫu.\n'
        'Các lựa chọn duyệt được lấy từ nhãn do người viết mẫu đặt, không lấy từ dự đoán mô hình.\n'
        'PASS ở đây: luồng API hoàn tất và cổng toàn vẹn báo đạt, chưa xác minh bố cục/Word.\n'
        'Chạy python -m pytest -q để kiểm tra các bất biến độc lập (bảng, ảnh, công thức, vùng giữ nguyên).\n', encoding='utf-8')
    return all(summary['result'] == 'PASS' for summary in summaries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='A new or empty directory; existing files are never overwritten.')
    args = parser.parse_args()
    if args.output:
        destination = args.output.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            parser.error('--output must be an empty directory.')
    else:
        parent = Path('.runtime/complex-results')
        parent.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=parent)).resolve()
    success = run_all(destination)
    print('Input/output pairs:', destination)
    raise SystemExit(0 if success else 1)
