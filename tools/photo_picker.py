"""
服裝照片選片工具（本機用）：列出每款服裝的全部照片，勾選要放上網站的、調整順序，按「儲存」後
寫入 data/photo-picks.json 並自動重轉網站用的照片。

  python tools/photo_picker.py          # 開啟 http://localhost:5180
  python tools/photo_picker.py --port 5181

第一張 = 商品卡封面。建議每款 6～10 張。
縮圖快取在 _source/_picker_cache/（不上傳）。
"""
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_assets as B  # noqa: E402

ROOT = B.ROOT
PICKS = os.path.join(ROOT, 'data', 'photo-picks.json')
CACHE = os.path.join(ROOT, '_source', '_picker_cache')
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'photo_picker.html')
NAMES = {'miadop-nightwatch': '儆夜者・圍巾後背披風款', 'miadop-watcher': '守望者・背心款', 'miadop-herder': '巡牧者・大斗篷款',
         'miadop-seer': '洞見者・短斗篷款', 'miadop-listener': '聽風者・圍巾款'}
lock = threading.Lock()


def catalog():
    """每款服裝：所有模特兒資料夾與照片（相對 OUTFITS_DIR）。"""
    out = []
    dirs = sorted(d for d in os.listdir(B.OUTFITS_DIR) if os.path.isdir(os.path.join(B.OUTFITS_DIR, d)))
    for prefix, pid in B.OUTFITS.items():
        groups = []
        for d in dirs:
            if not d.startswith(prefix):
                continue
            files = sorted(f for f in os.listdir(os.path.join(B.OUTFITS_DIR, d)) if f.lower().endswith(B.IMG_EXT))
            groups.append({'folder': d, 'model': d.split('_')[-1], 'files': [os.path.join(d, f) for f in files]})
        out.append({'id': pid, 'name': NAMES[pid], 'groups': groups})
    return out


def thumb(rel):
    path = os.path.normpath(os.path.join(B.OUTFITS_DIR, rel))
    if not path.startswith(os.path.normpath(B.OUTFITS_DIR)) or not os.path.exists(path):
        return None
    key = hashlib.md5((rel + str(os.path.getmtime(path))).encode()).hexdigest()
    cp = os.path.join(CACHE, key + '.jpg')
    if not os.path.exists(cp):
        os.makedirs(CACHE, exist_ok=True)
        im = B.load(path)
        im.thumbnail((420, 420))
        im.save(cp, quality=80)
    return open(cp, 'rb').read()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ('/', '/index.html'):
            return self.send(200, open(PAGE, encoding='utf-8').read(), 'text/html; charset=utf-8')
        if u.path == '/api/data':
            picks = json.load(open(PICKS, encoding='utf-8')) if os.path.exists(PICKS) else {}
            return self.send(200, json.dumps({'outfits': catalog(), 'picks': picks}, ensure_ascii=False), 'application/json; charset=utf-8')
        if u.path == '/thumb':
            rel = parse_qs(u.query).get('f', [''])[0]
            try:
                data = thumb(rel)
            except Exception as e:
                return self.send(500, str(e), 'text/plain; charset=utf-8')
            return self.send(200, data, 'image/jpeg') if data else self.send(404, 'not found', 'text/plain')
        self.send(404, 'not found', 'text/plain')

    def do_POST(self):
        if urlparse(self.path).path != '/api/save':
            return self.send(404, 'not found', 'text/plain')
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8'))
        with lock:
            picks = json.load(open(PICKS, encoding='utf-8')) if os.path.exists(PICKS) else {}
            for pid, lst in body.get('picks', {}).items():
                if pid in B.OUTFITS.values() and isinstance(lst, list):
                    picks[pid] = [p for p in lst if isinstance(p, str)]
            json.dump(picks, open(PICKS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build_assets.py'), '--only', 'photos'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        ok = r.returncode == 0
        return self.send(200 if ok else 500, json.dumps({'ok': ok, 'log': (r.stdout + r.stderr)[-2000:]}, ensure_ascii=False), 'application/json; charset=utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=5180)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), H)
    url = f'http://localhost:{a.port}/'
    print('選片工具：', url, '（Ctrl+C 結束）')
    if not a.no_browser:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
