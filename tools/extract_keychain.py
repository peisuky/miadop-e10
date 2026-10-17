"""
從鑰匙圈商品圖（白底示意圖，可以一張圖放好幾支）擷取每支壓克力吊飾的印刷圖、外形，
以及圓環大小、鏈條長度、穿孔位置，給 viewer 的 keychain 類型用。

做法（每支各自處理）：
  1. 白底：從圖片邊緣灌水填滿「外面」，剩下的就是 壓克力 + 鏈條 + 圓環（鏈節中間的洞也被包住）
  2. 用比鏈節還粗的圓做開運算 → 鏈條、圓環消失，只剩壓克力本體（每支一塊，照左到右排序）
  3. 開運算會把細的尖角磨掉：在原遮罩內「長回去」有限距離，但鏈條正上方那一條不長（不然會帶出鏈條殘段）
  4. 鏈條穿過的位置加回一個圓形小凸耳，中間開孔
  5. 量圓環直徑、圓環底到凸耳的鏈條長度（換算 mm）
  6. 印刷圖：壓克力範圍內，深色線稿 / 有彩度的像素封口補洞 = 圖案；其餘是透明留邊

用法：
  python tools/extract_keychain.py kenku_keychain/keychain.png assets \
      --items ken:50,fread:70 --thickness-mm 5
  （--items 依圖中由左到右的順序：資料夾名:壓克力高度 mm）
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


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out_root")
    ap.add_argument("--items", required=True, help="由左到右：名稱:高度mm,名稱:高度mm")
    ap.add_argument("--thickness-mm", type=float, default=5)
    ap.add_argument("--chain-width", type=int, default=0, help="鏈節寬（像素），0 = 自動估")
    ap.add_argument("--tab-mm", type=float, default=3.2, help="穿孔凸耳半徑（mm）")
    ap.add_argument("--hole-mm", type=float, default=1.3, help="孔半徑（mm）")
    ap.add_argument("--tab-drop", type=float, default=0.35, help="凸耳圓心相對本體頂端往下多少（以凸耳半徑為單位）")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    items = [(n, float(h)) for n, h in (s.split(":") for s in a.items.split(","))]
    img = cv2.imread(a.image)
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1]

    # ---- 1. 所有物件（壓克力 + 鏈條 + 圓環）----
    ink = ((gray < 236) | (sat > 30)).astype(np.uint8) * 255
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, disk(6))      # 外框線很細、有斷點，先封口才填得滿
    allm = fill_holes(ink)

    # ---- 2. 去掉鏈條：開運算 ----
    cw = a.chain_width or int(W * 0.022)              # 鏈節寬，示意圖約佔圖寬 2%
    r_open = int(cw * 0.65)
    body_all = cv2.morphologyEx(allm, cv2.MORPH_OPEN, disk(r_open))
    n, lab, stats, cents = cv2.connectedComponentsWithStats(body_all)
    order = sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA])[:len(items)]
    order.sort(key=lambda i: cents[i][0])            # 左到右
    if len(order) < len(items):
        raise SystemExit(f"只找到 {len(order)} 個壓克力本體，--items 有 {len(items)} 個")

    dbg = img.copy()
    for (name, height_mm), ci in zip(items, order):
        body = np.where(lab == ci, 255, 0).astype(np.uint8)
        x, y, w, h = stats[ci, :4]

        # 鏈條在本體正上方：取本體上緣往上一段的物件像素，水平位置中位數 = 鏈條 x
        band = allm[max(0, y - cw * 3): y, x: x + w]
        ys_, xs_ = np.nonzero(band)
        chain_x = int(np.median(xs_)) + x if xs_.size else x + w // 2

        # ---- 3. 長回尖角，但鏈條那一條不長 ----
        grow_limit = np.zeros_like(allm)
        grow_limit[:] = allm
        grow_limit[: y + cw, chain_x - cw: chain_x + cw] = 0   # 鏈條附近另外用凸耳處理
        grow_limit[: y + cw, chain_x - cw: chain_x + cw] |= body[: y + cw, chain_x - cw: chain_x + cw]
        regrown = body.copy()
        for _ in range(r_open // 2 + 2):
            regrown = cv2.dilate(regrown, disk(2)) & grow_limit
        # 只留和本體相連的那塊（防止長到旁邊的鏈條）
        nn, ll, ss, _ = cv2.connectedComponentsWithStats(regrown)
        regrown = np.where(ll == 1 + int(np.argmax(ss[1:, cv2.CC_STAT_AREA])), 255, 0).astype(np.uint8)

        # 本體高度（還沒加凸耳）→ 換算比例
        ys, xs = np.nonzero(regrown)
        top_at_chain = ys[np.abs(xs - chain_x) < cw // 2].min()
        # 高度含凸耳：先估凸耳高度再換算
        mm_per_px0 = height_mm / (ys.max() - ys.min())
        tab_r = a.tab_mm / mm_per_px0
        tab_cy = top_at_chain + tab_r * a.tab_drop
        mm = height_mm / (ys.max() - (tab_cy - tab_r))   # 最終比例：總高 = 凸耳頂到底部
        tab_r = a.tab_mm / mm
        tab_cy = top_at_chain + tab_r * a.tab_drop
        hole_r = a.hole_mm / mm

        acr = regrown.copy()
        cv2.circle(acr, (chain_x, int(round(tab_cy))), int(round(tab_r)), 255, -1)
        # 凸耳和頭頂接合處補圓順
        acr = cv2.morphologyEx(acr, cv2.MORPH_CLOSE, disk(int(tab_r * 0.6)))
        acr = (cv2.GaussianBlur(acr, (0, 0), 2) > 127).astype(np.uint8) * 255
        acr = cv2.erode(acr, disk(4))                  # 封口用的閉運算讓外框胖了一圈，收回到灰色外框線上

        cnts, _ = cv2.findContours(acr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cnt = max(cnts, key=cv2.contourArea)
        cnt = cv2.approxPolyDP(cnt, 1.2, True)[:, 0, :]
        bx, by, bw, bh = cv2.boundingRect(cnt)
        mm = height_mm / bh                            # 以最終外框重新校正，高度剛好等於指定值

        # ---- 5. 圓環與鏈條 ----
        above = allm[: by, max(0, chain_x - 6 * cw): chain_x + 6 * cw]
        rys, rxs = np.nonzero(above)
        ring_top = rys.min()
        widths = (above > 0).sum(axis=1)
        ring_d = int(widths[ring_top: ring_top + 8 * cw].max())   # 最寬那排 ≈ 圓環外徑
        ring_bottom = ring_top + ring_d
        chain_len = max(4.0, (tab_cy - ring_bottom) * mm)

        # ---- 6. 印刷圖 ----
        inner = cv2.erode(acr, disk(3))                # 去掉外框那條灰線
        seed = (((gray < 170) | (sat > 45)) & (inner > 0)).astype(np.uint8) * 255
        seed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, disk(5))
        art = fill_holes(seed)
        nn, ll, ss, _ = cv2.connectedComponentsWithStats(art)
        keep = [i for i in range(1, nn) if ss[i, cv2.CC_STAT_AREA] > ss[1:, cv2.CC_STAT_AREA].max() * 0.02]
        art = np.isin(ll, keep).astype(np.uint8) * 255
        art = cv2.morphologyEx(art, cv2.MORPH_OPEN, disk(2))
        alpha = cv2.GaussianBlur(art, (0, 0), 0.8)
        rgba = np.dstack([img, alpha])[by: by + bh, bx: bx + bw]

        out = os.path.join(a.out_root, name)
        os.makedirs(out, exist_ok=True)
        cv2.imwrite(os.path.join(out, "print.png"), rgba)
        pts = [[round((px - bx) * mm, 2), round((by + bh - py) * mm, 2)] for px, py in cnt]
        hole = [round((chain_x - bx) * mm, 2), round((by + bh - tab_cy) * mm, 2)]
        spec = {
            "type": "keychain",
            "w": round(bw * mm, 2), "h": round(bh * mm, 2),
            "thickness": a.thickness_mm,
            "print": "print.png",
            "outline": pts,
            "hole": {"x": hole[0], "y": hole[1], "r": a.hole_mm},
            "ring": {"diameter": round(ring_d * mm, 1), "wire": 1.2},
            "chain": {"length": round(chain_len, 1)},
        }
        with open(os.path.join(out, "shape.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False)
        print(f"{name}: {spec['w']} x {spec['h']} mm, ring {spec['ring']['diameter']}mm, "
              f"chain {spec['chain']['length']}mm, hole {hole}")

        if a.debug:
            cv2.polylines(dbg, [cnt.reshape(-1, 1, 2)], True, (0, 0, 255), 3)
            cv2.circle(dbg, (chain_x, int(tab_cy)), int(hole_r), (255, 0, 0), 2)
            cv2.line(dbg, (chain_x - ring_d // 2, ring_bottom), (chain_x + ring_d // 2, ring_bottom), (0, 160, 0), 2)
            dbg[(art > 0) & (cv2.erode(art, disk(2)) == 0)] = (255, 0, 255)

    if a.debug:
        cv2.imwrite(os.path.join(a.out_root, "_keychain_debug.jpg"), dbg)


if __name__ == "__main__":
    main()
