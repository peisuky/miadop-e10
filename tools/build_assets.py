"""
把原始素材（_source/ 與服裝資料夾）轉成網站用的檔案，並產生 data/media.json。

  python tools/build_assets.py            # 全部（已存在的檔案會跳過）
  python tools/build_assets.py --force    # 全部重做
  python tools/build_assets.py --only photos|videos|brand

輸出：
  assets/img/<商品>/<款式>/NN.webp      長邊 1600px（視窗大圖）
  assets/img/<商品>/<款式>/NN_t.webp    長邊 520px（縮圖、商品卡）
  assets/video/<商品>/NN.mp4 + NN.webp  720p 直式短片 + 封面
  assets/brand/…                        主視覺、Logo、創作者頭像、地圖
  data/media.json                       每個商品／款式有哪些照片、影片（網站讀這份）

服裝照片：每款自動挑 OUTFIT_PICKS 張（每個模特兒資料夾平均分配、挑最清楚的），
挑選結果會寫在 data/media.json；要換照片就改 data/photo-picks.json 後重跑。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '_source')
OUTFITS_DIR = r'D:\Videos\kulas-harcy-shirts'
OUTFIT_PICKS = 8
BIG, THUMB = 1600, 520

OUTFITS = {   # 資料夾名稱開頭 → 商品編號
    '儆夜者': 'miadop-nightwatch', '守望者': 'miadop-watcher', '巡牧者': 'miadop-herder',
    '洞見者': 'miadop-seer', '聽風者': 'miadop-listener',
}
PHOTO_SETS = [   # (商品/款式, 資料夾)
    ('whitedog-dinner/whitedog', 'whitedog/dinner-standee/whitedog'),
    ('whitedog-dinner/che', 'whitedog/dinner-standee/che'),
    ('whitedog-dinner/peisuky', 'whitedog/dinner-standee/peisuky'),
    ('whitedog-explorer/whitedog', 'whitedog/explorer-standee/whitedog'),
    ('whitedog-explorer/harcy', 'whitedog/explorer-standee/harcy'),
    ('whitedog-explorer/kulas', 'whitedog/explorer-standee/kulas'),
    ('whitedog-explorer/peisuky', 'whitedog/explorer-standee/peisuky'),
    ('peisuky-taro-badge', 'peisuky/taro-badge'),
    ('miadop-dreamcatcher', 'miadop/dreamcatcher'),
    # 以下第三欄：只取檔名包含這段文字的檔案；第四欄 False = 不做置中裁切（書頁、明信片、情境照要完整呈現）
    ('miadop-grassbag', 'miadop/grassbag', '', False),
    ('kenku-book', 'kenku/book', '', False),
    ('kenku-postcard', 'kenku/postcard', '', False),
    ('kenku-standee/survival', 'kenku/standee', 'Survival Guide', True),
    ('kenku-standee/ken', 'kenku/standee', 'Ken與Fred', True),
    ('kenku-standee/fred', 'kenku/standee', 'Ken與Fred', True),
    ('kenku-standee/kenku', 'kenku/standee', 'Kenku雙面差分', True),
]
IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.heic')
COVERS = {   # 商品卡封面另外指定（沒指定就用第一款的第一張照片）
    'whitedog-dinner': 'whitedog/dinner-standee/IMG_1009.jpg',
}
CARD_ASPECT = 4 / 5   # 商品卡圖片比例（寬 / 高），和 css 的 .card .ph 一致
CARD_FIT = 0.72       # 商品最長邊佔畫面的比例；一般正面照的商品面積會 > 1/3


def load(path):
    """讀圖並轉正；HEIC 交給 ffmpeg 解碼。"""
    if path.lower().endswith('.heic'):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'x.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-frames:v', '1', '-y', out], check=True)
            return Image.open(out).convert('RGB')
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert('RGB')


def save_pair(im, out_base, force):
    """存大圖 + 縮圖，回傳 media 項目。"""
    big, thumb = out_base + '.webp', out_base + '_t.webp'
    if force or not os.path.exists(big):
        os.makedirs(os.path.dirname(big), exist_ok=True)
        b = im.copy(); b.thumbnail((BIG, BIG), Image.LANCZOS); b.save(big, 'WEBP', quality=80, method=6)
        t = im.copy(); t.thumbnail((THUMB, THUMB), Image.LANCZOS); t.save(thumb, 'WEBP', quality=74, method=6)
    w, h = Image.open(big).size
    rel = lambda p: os.path.relpath(p, ROOT).replace('\\', '/')
    return {'src': rel(big), 'thumb': rel(thumb), 'w': w, 'h': h}


def product_bbox(im):
    """商品在照片裡的位置 (x, y, w, h)：找「有邊緣或有顏色」的區域，扣掉橫跨整張的桌緣線，
    取最大塊再併入貼著它的小塊（底座、壓克力邊）。背景是素色牆面＋桌面的商品照適用。"""
    W, H = im.size
    s = 640 / max(W, H)
    small = np.array(im.resize((max(1, round(W * s)), max(1, round(H * s)))))
    g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    mag = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    sat = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)[..., 1]
    m = ((mag > 60) | (sat > 70)).astype(np.uint8) * 255      # 門檻夠高，柔和的陰影邊不會被算進去
    horiz = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (small.shape[1] // 3, 1)))
    m = cv2.subtract(m, cv2.dilate(horiz, np.ones((5, 5), np.uint8)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(v) for v in st[big, :4])
    for i in range(1, n):
        if i == big or st[i, cv2.CC_STAT_AREA] < st[big, cv2.CC_STAT_AREA] * 0.05:
            continue
        xi, yi, wi, hi = (int(v) for v in st[i, :4])
        if xi < x + w + 20 and xi + wi > x - 20 and yi < y + h + 20 and yi + hi > y - 20:
            x2, y2 = max(x + w, xi + wi), max(y + h, yi + hi); x, y = min(x, xi), min(y, yi); w, h = x2 - x, y2 - y
    return tuple(round(v / s) for v in (x, y, w, h))


def card_crop(im, bbox=None, fit=CARD_FIT):
    """裁成商品卡比例，商品置中、最長邊佔約 CARD_FIT。照片不夠大時就用到照片邊界為止。"""
    bbox = bbox or product_bbox(im)
    if not bbox:
        return im
    x, y, w, h = bbox
    cw = max(w / fit, h / fit * CARD_ASPECT)
    ch = cw / CARD_ASPECT
    cx, cy = x + w / 2, y + h / 2
    left, top = round(cx - cw / 2), round(cy - ch / 2)
    right, bottom = round(cx + cw / 2), round(cy + ch / 2)
    # 裁切框超出照片時不移動框（會讓商品偏掉），而是把照片邊緣的顏色往外延伸補滿
    pad = [max(0, -left), max(0, -top), max(0, right - im.width), max(0, bottom - im.height)]
    if any(pad):
        a = cv2.copyMakeBorder(np.array(im), pad[1], pad[3], pad[0], pad[2], cv2.BORDER_REPLICATE)
        im = Image.fromarray(a)
        left, top, right, bottom = left + pad[0], top + pad[1], right + pad[0], bottom + pad[1]
    return im.crop((left, top, right, bottom))


def sharpness(path):
    try:
        im = load(path); im.thumbnail((640, 640))
        g = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2GRAY)
        return float(cv2.Laplacian(g, cv2.CV_64F).var())
    except Exception as e:
        print('  skip', path, e)
        return -1


def pick_outfit_photos(folders, n):
    """每個模特兒資料夾平均分配名額，資料夾內挑最清楚的（維持原本拍攝順序）。"""
    files = {f: sorted(os.path.join(f, x) for x in os.listdir(f) if x.lower().endswith(IMG_EXT)) for f in folders}
    files = {f: v for f, v in files.items() if v}
    quota = {f: n // len(files) for f in files}
    for f in sorted(files, key=lambda f: -len(files[f]))[: n - sum(quota.values())]:
        quota[f] += 1
    picks = []
    for f, lst in files.items():
        q = min(quota[f], len(lst))
        # 先在時間軸上均勻取候選（避免同一組連拍），再依清晰度挑
        step = max(1, len(lst) // (q * 2))
        cands = lst[::step]
        scored = sorted(cands, key=sharpness, reverse=True)[:q]
        picks += sorted(scored, key=lst.index)
    return picks


def build_photos(media, force):
    picks_path = os.path.join(ROOT, 'data', 'photo-picks.json')
    picks = json.load(open(picks_path, encoding='utf-8')) if os.path.exists(picks_path) else {}

    # 服裝
    for prefix, pid in OUTFITS.items():
        folders = sorted(os.path.join(OUTFITS_DIR, d) for d in os.listdir(OUTFITS_DIR)
                         if d.startswith(prefix) and os.path.isdir(os.path.join(OUTFITS_DIR, d)))
        if pid not in picks:
            print('picking', pid)
            picks[pid] = [os.path.relpath(p, OUTFITS_DIR) for p in pick_outfit_photos(folders, OUTFIT_PICKS)]
        # 檔名用「模特兒資料夾最後一段 + 原檔名」：換照片時不會撞到舊檔，沒用到的舊檔順手清掉
        out_dir = os.path.join(ROOT, 'assets', 'img', pid)
        items, keep = [], set()
        for rel in picks[pid]:
            folder, fname = os.path.split(rel.replace('/', os.sep))
            stem = (folder.split('_')[-1] + '-' + os.path.splitext(fname)[0]).replace(' ', '')
            keep |= {stem + '.webp', stem + '_t.webp'}
            items.append(save_pair(load(os.path.join(OUTFITS_DIR, rel)), os.path.join(out_dir, stem), force))
        if os.path.isdir(out_dir):
            for f in os.listdir(out_dir):
                if f not in keep:
                    os.remove(os.path.join(out_dir, f))
        media.setdefault(pid, {})['photos'] = items
        print(pid, len(items), 'photos')

    # 其他商品：資料夾裡全部照片，裁成商品置中的卡片比例（服裝照是情境照，不裁）
    for key, rel, *opt in PHOTO_SETS:
        match, crop = (opt + ['', True])[:2] if opt else ('', True)
        d = os.path.join(SRC, rel)
        files = sorted(os.path.join(d, x) for x in os.listdir(d) if x.lower().endswith(IMG_EXT) and match in x) if os.path.isdir(d) else []
        files.sort(key=lambda f: ('Back' in f, f))          # 雙面立牌：正面在前
        items = [save_pair(card_crop(load(p)) if crop else load(p), os.path.join(ROOT, 'assets', 'img', key, f'{i + 1:02d}'), force) for i, p in enumerate(files)]
        media.setdefault(key, {})['photos'] = items
        print(key, len(items), 'photos')

    # 指定的商品卡封面
    for key, rel in COVERS.items():
        media.setdefault(key, {})['cover'] = save_pair(card_crop(load(os.path.join(SRC, rel)), fit=0.92),   # 封面多為橫排合照：撐滿寬度
                                             os.path.join(ROOT, 'assets', 'img', key, 'cover'), force)
        print(key, 'cover')

    # Kenku 吊飾：示意圖左右各裁一支
    kc = load(os.path.join(SRC, 'kenku', 'keychain', 'keychain.png'))
    W = kc.width
    for key, box in [('kenku-keychain/ken', (0, 0, int(W * .45), kc.height)), ('kenku-keychain/fread', (int(W * .45), 0, W, kc.height))]:
        part = kc.crop(box)
        bb = ImageOps.invert(part.convert('L')).point(lambda v: 255 if v > 12 else 0).getbbox()   # 白底，直接找非白色範圍
        media.setdefault(key, {})['photos'] = [save_pair(card_crop(part, (bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1])), os.path.join(ROOT, 'assets', 'img', key, '01'), force)]

    os.makedirs(os.path.dirname(picks_path), exist_ok=True)
    json.dump(picks, open(picks_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def build_videos(media, force):
    out_dir = os.path.join(OUTFITS_DIR, 'output')
    vids = sorted(os.listdir(out_dir))
    order_path = os.path.join(ROOT, 'data', 'video-order.json')
    order = json.load(open(order_path, encoding='utf-8')) if os.path.exists(order_path) else {}
    for prefix, pid in OUTFITS.items():
        mine = [v for v in vids if v.endswith('.mp4') and f'-{prefix}-' in v]
        mine.sort(key=lambda v: ('版' in v, v))          # 基本款在前，模特兒版本在後
        items = []
        for i, v in enumerate(mine):
            base = os.path.join(ROOT, 'assets', 'video', pid, f'{i + 1:02d}')
            os.makedirs(os.path.dirname(base), exist_ok=True)
            if force or not os.path.exists(base + '.mp4'):
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(out_dir, v),
                                '-vf', 'scale=720:-2', '-c:v', 'libx264', '-preset', 'slow', '-crf', '28',
                                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '96k', base + '.mp4'], check=True)
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '3.5', '-i', base + '.mp4', '-frames:v', '1',
                                '-vf', 'scale=540:-2', '-c:v', 'libwebp', '-quality', '75', base + '.webp'], check=True)
            rel = lambda p: os.path.relpath(p, ROOT).replace('\\', '/')
            label = v.replace('miadop-', '').replace('.mp4', '')
            items.append({'src': rel(base + '.mp4'), 'poster': rel(base + '.webp'), 'label': label})
        # 顯示順序：data/video-order.json 有列的照列的順序排在前面，其餘維持預設（檔名編號不變，不用重轉）
        want = order.get(pid, [])
        rank = {it['label']: (want.index(it['label']) if it['label'] in want else len(want) + i) for i, it in enumerate(items)}
        items.sort(key=lambda it: rank[it['label']])
        media.setdefault(pid, {})['videos'] = items
        print(pid, len(items), 'videos:', ' / '.join(it['label'] for it in items))


def build_brand(force):
    out = os.path.join(ROOT, 'assets', 'brand')
    os.makedirs(out, exist_ok=True)
    hero = os.path.join(SRC, 'hero')
    for name, w in [('wide', 1920), ('portrait', 1080)]:
        im = Image.open(os.path.join(hero, 'out', f'miadop-e10-{name}.png')).convert('RGB')
        im.save(os.path.join(out, f'hero-{name}.webp'), 'WEBP', quality=82, method=6)
        small = im.copy(); small.thumbnail((w // 2, w // 2)); small.save(os.path.join(out, f'hero-{name}-sm.webp'), 'WEBP', quality=80, method=6)
    Image.open(os.path.join(hero, 'out', 'miadop-e10-link.png')).convert('RGB').save(os.path.join(out, 'og.jpg'), quality=86, optimize=True)
    for name in ['logo_ink', 'logo_paper']:
        im = Image.open(os.path.join(hero, name + '.png')); im.thumbnail((256, 256)); im.save(os.path.join(out, name.replace('_', '-') + '.png'), optimize=True)
    for sid in ['axi', 'gugu', 'pei', 'baigou', 'kenku']:
        im = Image.open(os.path.join(hero, 'stickers', sid + '.png')); im.thumbnail((420, 420))
        im.save(os.path.join(out, f'avatar-{sid}.webp'), 'WEBP', quality=82, method=6)
    # 地圖：完整版 + E 排放大版
    m = Image.open(os.path.join(SRC, 'event', 'map.webp')).convert('RGB')
    m.save(os.path.join(out, 'map.webp'), 'WEBP', quality=82)
    m.crop((195, 252, 565, 328)).resize((740, 152), Image.LANCZOS).save(os.path.join(out, 'map-e-row.webp'), 'WEBP', quality=88)
    # favicon：Logo 放在紙色圓上
    logo = Image.open(os.path.join(hero, 'logo_ink.png')).convert('RGBA')
    ico = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(ico).ellipse((4, 4, 252, 252), fill=(246, 238, 216, 255))
    lg = logo.copy(); lg.thumbnail((168, 168)); ico.paste(lg, ((256 - lg.width) // 2, (256 - lg.height) // 2), lg)
    ico.save(os.path.join(out, 'favicon.png'))
    print('brand assets ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--only', choices=['photos', 'videos', 'brand'])
    a = ap.parse_args()
    media_path = os.path.join(ROOT, 'data', 'media.json')
    media = json.load(open(media_path, encoding='utf-8')) if os.path.exists(media_path) else {}
    if a.only in (None, 'brand'):
        build_brand(a.force)
    if a.only in (None, 'photos'):
        build_photos(media, a.force)
    if a.only in (None, 'videos'):
        build_videos(media, a.force)
    os.makedirs(os.path.dirname(media_path), exist_ok=True)
    json.dump(media, open(media_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote', media_path)


if __name__ == '__main__':
    sys.exit(main())
