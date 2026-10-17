"""
從商品照片擷取壓克力牌的「印刷圖」與「切割外形」，給 viewer 的 3D 預覽使用。

做法：
  1. 找黑色線稿 + 紅色等高飽和色塊 → 閉運算封口 → 補洞，得到圖案範圍
  2. 上色兩種模式：
       --mode poster：歸成幾個乾淨色（黑線 / 灰底 / 白 / 紅），適合色塊簡單的圖
       --mode photo ：保留照片顏色，只校正白平衡與亮度，適合全彩細緻的插畫
  3. 圖案範圍往外擴 margin → 底部拉平（立牌要站得住）→ 平滑 → 描出外框多邊形
  4. 輸出 print.png（RGBA，裁到外框大小）+ shape.json（外框座標，單位 mm）

用法：
  python tools/extract_acrylic.py Dog_whitedog/IMG_0993.jpg assets/dog_whitedog \
      --crop 650,550,1500,1480 --height-mm 50 --thickness-mm 10

  圓形底座立牌：
  python tools/extract_acrylic.py Discover_whitedog/IMG_1012.jpg assets/discover_whitedog \
      --mode photo --crop 550,550,1550,2120 --height-mm 80 --width-mm 53 --thickness-mm 5 \
      --base disc:45:5 --tab-mm 16
"""
import argparse
import json
import os

import cv2
import numpy as np


def fill_holes(mask):
    h, w = mask.shape
    flood = mask.copy()
    ff = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 255)
    return mask | cv2.bitwise_not(flood)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out_dir")
    ap.add_argument("--crop", help="x0,y0,x1,y1（原圖像素），只處理這個範圍")
    ap.add_argument("--scale", type=float, default=2.0, help="先放大再處理，線條比較平滑")
    ap.add_argument("--margin", type=float, default=0.045, help="壓克力留邊，佔圖案高度的比例")
    ap.add_argument("--mode", choices=["poster", "photo"], default="poster")
    ap.add_argument("--height-mm", type=float, default=50.0, help="實品外框高度（mm）")
    ap.add_argument("--width-mm", type=float, help="實品最寬處（mm）；不給就照照片比例")
    ap.add_argument("--base", help="底座，例如 disc:45:5（圓盤 直徑 45mm 厚 5mm）")
    ap.add_argument("--tab-mm", type=float, default=16, help="插進底座的插腳寬度（mm，有 --base 才用）")
    ap.add_argument("--white", type=float, default=246, help="photo 模式：白色毛校正後的亮度")
    ap.add_argument("--saturation", type=float, default=1.0,
                    help="photo 模式：彩度倍率。色彩濃的角色建議 0.75（校正對比時彩度會被一起拉高，容易過豔）")
    ap.add_argument("--thickness-mm", type=float, default=10.0, help="壓克力厚度（mm）")
    ap.add_argument("--dark", type=int, default=95, help="灰階低於此值算黑線")
    ap.add_argument("--base-gray", type=float, default=214, help="灰底提亮後的目標亮度")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    img = cv2.imread(a.image)
    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(","))
        img = img[y0:y1, x0:x1]
    img = cv2.resize(img, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_CUBIC)
    raw = img.copy()                       # photo 模式的貼圖用沒模糊過的
    img = cv2.bilateralFilter(img, 9, 40, 9)

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    s = hsv[..., 1].astype(int)
    v = hsv[..., 2].astype(int)

    dark = (gray < a.dark).astype(np.uint8) * 255
    color = ((s > 90) & (v > 60)).astype(np.uint8) * 255

    # 只留最大的幾塊（去掉桌面髒點）
    seed = dark | color
    k = max(3, int(9 * a.scale))
    closed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    art = fill_holes(closed)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(art)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        art = np.where(lab == big, 255, 0).astype(np.uint8)
    art = fill_holes(art)
    art = cv2.morphologyEx(art, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

    ys, xs = np.nonzero(art)
    art_h = ys.max() - ys.min()
    bottom = ys.max()

    # ---- 顏色歸類 ----
    inside = art > 0
    is_color = inside & (color > 0)
    is_dark = inside & (dark > 0) & ~is_color
    light = inside & ~is_dark & ~is_color
    # 淺色再分灰 / 白：明顯比底色亮的才算白（例如尾巴尖）
    base_v = np.median(gray[light])
    is_white = light & (gray > base_v + 22)
    is_gray = light & ~is_white

    labels = np.zeros(gray.shape, np.uint8)  # 0 透明 1 黑 2 灰 3 白 4 色
    labels[is_gray] = 2
    labels[is_white] = 3
    labels[is_color] = 4
    labels[is_dark] = 1
    labels = cv2.medianBlur(labels, 5)
    labels[~inside] = 0

    def med(mask, fallback):
        return np.median(img[mask], axis=0) if mask.any() else np.array(fallback)

    # 照片曝光偏暗：用灰底當基準，整體提亮到 --base-gray，其他顏色跟著同比例調
    g_med = med(is_gray, [205, 205, 205])
    gain = a.base_gray / max(1.0, float(g_med.mean()))
    pal = {
        1: np.array([34, 30, 30]),                                   # 線稿：近黑（BGR）
        2: np.clip(g_med * gain, 0, 255),
        3: np.clip(med(is_white, [245, 245, 245]) * gain, 0, 255),
        4: np.clip(med(is_color, [70, 40, 200]) * gain, 0, 255),
    }
    out = np.zeros((*gray.shape, 4), np.uint8)
    if a.mode == "poster":
        for kk, col in pal.items():
            out[labels == kk, :3] = col.astype(np.uint8)
    else:
        # 用圖案裡最亮、低飽和的像素（白毛）當白點，分通道校正 → 去掉照片偏色與偏暗
        ref = inside & (s < 40) & (gray > np.percentile(gray[inside], 80))
        wp = np.median(raw[ref].astype(float), axis=0)
        bal = raw.astype(float) * (a.white / np.maximum(wp, 1))
        # 黑色往下壓一點，對比回來（照片的黑線偏灰）
        lo = 28.0
        bal = np.clip((bal - lo) * 255.0 / (255.0 - lo), 0, 255)
        sharp = cv2.addWeighted(bal, 1.5, cv2.GaussianBlur(bal, (0, 0), 1.6), -0.5, 0)
        out[..., :3] = np.clip(sharp, 0, 255).astype(np.uint8)
        if a.saturation != 1.0:
            hsv2 = cv2.cvtColor(out[..., :3], cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv2[..., 1] *= a.saturation
            out[..., :3] = cv2.cvtColor(np.clip(hsv2, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
        print(f"white point {wp.round(1)}")
    out[..., 3] = inside.astype(np.uint8) * 255 if a.mode == "photo" else (labels > 0).astype(np.uint8) * 255
    # 邊緣反鋸齒
    out[..., 3] = cv2.GaussianBlur(out[..., 3], (3, 3), 0)

    # ---- 壓克力外框 ----
    m = int(a.margin * art_h)
    outer = cv2.dilate(art, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * m + 1, 2 * m + 1)))
    base_y = bottom + int(m * 0.7)
    # 底部一段拉成實心矩形，讓立牌有平底
    band = outer[bottom - int(art_h * 0.12): bottom]
    cols = np.nonzero(band.any(axis=0))[0]
    outer[bottom - int(art_h * 0.12): base_y + 1, cols.min(): cols.max() + 1] = 255
    outer[base_y + 1:] = 0
    outer = cv2.GaussianBlur(outer, (0, 0), m * 0.35)
    outer = (outer > 127).astype(np.uint8) * 255
    outer[base_y + 1:] = 0

    cnts, _ = cv2.findContours(outer, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    cnt = cv2.approxPolyDP(cnt, 0.6 * a.scale, True)[:, 0, :]

    bx, by, bw, bh = cv2.boundingRect(cnt)
    mm = a.height_mm / bh
    mmx = a.width_mm / bw if a.width_mm else mm
    # 印刷圖裁到外框大小（和外框共用同一個座標系）
    crop = out[by: by + bh, bx: bx + bw]
    os.makedirs(a.out_dir, exist_ok=True)
    cv2.imwrite(os.path.join(a.out_dir, "print.png"), crop)

    # mm 座標，原點左下，y 往上（three.js Shape 用）
    pts = [[round((x - bx) * mmx, 2), round((by + bh - y) * mm, 2)] for x, y in cnt]
    shape = {
        "w": round(bw * mmx, 2),
        "h": round(bh * mm, 2),
        "thickness": a.thickness_mm,
        "print": "print.png",
        "outline": pts,
    }
    if a.base:
        kind, dia, th = a.base.split(":")
        shape["base"] = {"type": kind, "diameter": float(dia), "thickness": float(th)}
        shape["tab"] = {"w": a.tab_mm, "h": float(th)}   # 插腳整段插進底座
    with open(os.path.join(a.out_dir, "shape.json"), "w", encoding="utf-8") as f:
        json.dump(shape, f, ensure_ascii=False)
    print(f"outline {len(pts)} pts, {shape['w']} x {shape['h']} mm, print {bw}x{bh}px")

    if a.debug:
        dbg = img.copy()
        cv2.polylines(dbg, [cnt.reshape(-1, 1, 2)], True, (0, 200, 0), 3)
        cv2.drawContours(dbg, cv2.findContours(art, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], -1, (255, 0, 0), 2)
        cv2.imwrite(os.path.join(a.out_dir, "_debug.jpg"), dbg)


if __name__ == "__main__":
    main()
