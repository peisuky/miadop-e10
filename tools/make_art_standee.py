"""
用「去背的角色原稿 PNG」直接做壓克力立牌的 3D 資料（不需要實拍照）。

  外形：角色圖案（alpha）往外留 --margin-mm 的透明邊 → 底部拉平 → 加插腳 → 圓形底座
  雙面：--back 另一張圖（檔案方向 = 從背面看過去的樣子，畫布左右和正面互為鏡像）
        --back-same 背面印同一張（從背面看也是正的）
  輸出：print.png（正面）、back.png（若有）、shape.json

  python tools/make_art_standee.py _source/kenku/standee/front.png assets/3d/kenku-standee__kenku \
      --back _source/kenku/standee/back.png --height-mm 100

尺寸：--height-mm 是角色板高度（不含插腳），厚度、留邊、底座沒給就用預設值（假設值）。
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('front')
    ap.add_argument('out_dir')
    ap.add_argument('--back', help='背面圖（從背面看的方向）')
    ap.add_argument('--back-same', action='store_true', help='背面印同一張')
    ap.add_argument('--height-mm', type=float, required=True, help='角色板高度（mm，不含插腳）')
    ap.add_argument('--thickness-mm', type=float, default=5)
    ap.add_argument('--margin-mm', type=float, default=3, help='圖案外的透明留邊')
    ap.add_argument('--base-mm', type=float, default=0, help='圓形底座直徑；0 = 依寬度自動（假設值）')
    ap.add_argument('--base-thickness-mm', type=float, default=5)
    ap.add_argument('--tab-mm', type=float, default=0, help='插腳寬；0 = 依寬度自動')
    a = ap.parse_args()

    front = Image.open(a.front).convert('RGBA')
    W, H = front.size
    alpha = np.array(front)[..., 3] > 128
    back = None
    if a.back:
        back = Image.open(a.back).convert('RGBA')
        if back.size != front.size:
            raise SystemExit('正反面圖尺寸要一樣')
        alpha |= np.array(back)[..., 3][:, ::-1] > 128      # 背面圖左右翻回正面座標再合併
    ys, xs = np.nonzero(alpha)
    art_top, art_bottom = ys.min(), ys.max()
    px_per_mm = (art_bottom - art_top) / (a.height_mm - 2 * a.margin_mm)
    m = max(2, round(a.margin_mm * px_per_mm))

    # 畫布四周補空白，留邊才不會被邊界切到
    pad = m * 3
    mask = np.pad(alpha.astype(np.uint8) * 255, pad)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    outer = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * m + 1, 2 * m + 1)))
    bottom = art_bottom + pad
    base_y = bottom + round(m * 0.7)
    band_h = round((art_bottom - art_top) * 0.08)
    band = outer[bottom - band_h: bottom]
    cols = np.nonzero(band.any(axis=0))[0]
    outer[bottom - band_h: base_y + 1, cols.min(): cols.max() + 1] = 255     # 底部拉成平的，立得住
    outer[base_y + 1:] = 0
    outer = (cv2.GaussianBlur(outer, (0, 0), m * 0.3) > 127).astype(np.uint8) * 255
    outer[base_y + 1:] = 0
    cnts, _ = cv2.findContours(outer, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    cnt = cv2.approxPolyDP(cnt, max(1.0, px_per_mm * 0.15), True)[:, 0, :]
    bx, by, bw, bh = cv2.boundingRect(cnt)
    mm = 1 / px_per_mm

    # 貼圖：和外框同一個框（換回原圖座標）；背面用左右鏡像的框，對齊正面
    x0, y0, x1, y1 = bx - pad, by - pad, bx - pad + bw, by - pad + bh
    os.makedirs(a.out_dir, exist_ok=True)
    def crop(im, box):
        canvas = Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
        canvas.paste(im.crop((max(0, box[0]), max(0, box[1]), min(W, box[2]), min(H, box[3]))), (max(0, -box[0]), max(0, -box[1])))
        return canvas
    crop(front, (x0, y0, x1, y1)).save(os.path.join(a.out_dir, 'print.png'), optimize=True)
    if back:
        crop(back, (W - x1, y0, W - x0, y1)).save(os.path.join(a.out_dir, 'back.png'), optimize=True)

    w_mm, h_mm = round(bw * mm, 2), round(bh * mm, 2)
    # 底部那條平邊的寬度 → 插腳、底座的預設大小
    bottom_w = (cols.max() - cols.min()) * mm
    tab = a.tab_mm or round(min(bottom_w * 0.5, max(12, w_mm * 0.25)), 1)
    base = a.base_mm or round(max(45, min(w_mm * 0.8, h_mm * 0.55)), 1)
    shape = {
        'w': w_mm, 'h': h_mm, 'thickness': a.thickness_mm, 'print': 'print.png',
        'outline': [[round((x - bx) * mm, 2), round((by + bh - y) * mm, 2)] for x, y in cnt],
        'base': {'type': 'disc', 'diameter': base, 'thickness': a.base_thickness_mm},
        'tab': {'w': tab, 'h': a.base_thickness_mm},
    }
    if back:
        shape['printBack'] = 'back.png'
    elif a.back_same:
        shape['backSame'] = True
    with open(os.path.join(a.out_dir, 'shape.json'), 'w', encoding='utf-8') as f:
        json.dump(shape, f, ensure_ascii=False)
    print(f'{a.out_dir}: {w_mm} x {h_mm} mm, base {base}mm, tab {tab}mm, back={"file" if back else "same" if a.back_same else "mirror"}')


if __name__ == '__main__':
    main()
