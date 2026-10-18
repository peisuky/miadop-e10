"""
用「去背的角色原稿 PNG」直接做壓克力吊飾（keychain 類型）的 3D 資料（不需要實拍照）。

  外形：圖案（alpha）往外留 --margin-mm 的透明邊（分開的小圖塊會一起包進去）
        → 在最高點加一個圓形凸耳、開孔 → 總高 = --height-mm
  圓環、鏈條：沒有實拍可量，用預設值（假設值）
  輸出：print.png、shape.json

  python tools/make_art_keychain.py _source/miadop/keychain/KULAS_SHAKE_4cm.png \
      assets/3d/miadop-keychain__kulas --height-mm 40
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('art')
    ap.add_argument('out_dir')
    ap.add_argument('--height-mm', type=float, required=True, help='壓克力總高（含凸耳）')
    ap.add_argument('--thickness-mm', type=float, default=5)
    ap.add_argument('--margin-mm', type=float, default=2, help='圖案外的透明留邊')
    ap.add_argument('--tab-mm', type=float, default=3.2, help='穿孔凸耳半徑')
    ap.add_argument('--hole-mm', type=float, default=1.3, help='孔半徑')
    ap.add_argument('--ring-mm', type=float, default=22, help='圓環外徑（假設值）')
    ap.add_argument('--chain-mm', type=float, default=20, help='鏈條長（假設值）')
    a = ap.parse_args()

    art = Image.open(a.art).convert('RGBA')
    W, H = art.size
    alpha = np.array(art)[..., 3] > 128
    ys, xs = np.nonzero(alpha)
    # 先用圖案高度估比例，最後再用外框總高校正
    px_per_mm = (ys.max() - ys.min()) / (a.height_mm - 2 * a.margin_mm - a.tab_mm)
    m = max(2, round(a.margin_mm * px_per_mm))
    pad = m * 4 + round(a.tab_mm * px_per_mm * 2)
    mask = np.pad(alpha.astype(np.uint8) * 255, pad)
    # 分開的小圖塊（例如甩動線）用閉運算和本體連起來，再整圈往外長留邊
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, disk(m * 2))
    outer = cv2.dilate(mask, disk(m))
    n, lab, st, _ = cv2.connectedComponentsWithStats(outer)
    outer = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255

    # 凸耳：放在外框最高點，圓心往下 0.35 個半徑
    tys, txs = np.nonzero(outer)
    top = tys.min()
    tx = int(np.median(txs[tys == top]))
    tab_r = round(a.tab_mm * px_per_mm)
    tab_cy = top + round(tab_r * 0.35)
    cv2.circle(outer, (tx, tab_cy), tab_r, 255, -1)
    outer = cv2.morphologyEx(outer, cv2.MORPH_CLOSE, disk(int(tab_r * 0.6)))
    outer = (cv2.GaussianBlur(outer, (0, 0), m * 0.3) > 127).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(outer, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    cnt = cv2.approxPolyDP(cnt, max(1.0, px_per_mm * 0.15), True)[:, 0, :]
    bx, by, bw, bh = cv2.boundingRect(cnt)
    mm = a.height_mm / bh

    x0, y0 = bx - pad, by - pad
    canvas = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    canvas.paste(art.crop((max(0, x0), max(0, y0), min(W, x0 + bw), min(H, y0 + bh))), (max(0, -x0), max(0, -y0)))
    os.makedirs(a.out_dir, exist_ok=True)
    canvas.save(os.path.join(a.out_dir, 'print.png'), optimize=True)

    spec = {
        'type': 'keychain',
        'w': round(bw * mm, 2), 'h': round(bh * mm, 2),
        'thickness': a.thickness_mm,
        'print': 'print.png',
        'outline': [[round((x - bx) * mm, 2), round((by + bh - y) * mm, 2)] for x, y in cnt],
        'hole': {'x': round((tx - bx) * mm, 2), 'y': round((by + bh - tab_cy) * mm, 2), 'r': a.hole_mm},
        'ring': {'diameter': a.ring_mm, 'wire': 1.2},
        'chain': {'length': a.chain_mm},
    }
    with open(os.path.join(a.out_dir, 'shape.json'), 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False)
    print(f"{a.out_dir}: {spec['w']} x {spec['h']} mm, hole {spec['hole']}")


if __name__ == '__main__':
    main()
