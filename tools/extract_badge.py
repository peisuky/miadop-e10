"""
從徽章（金屬琺瑯章）正面照擷取 3D 預覽用的貼圖與外形。

做法：
  1. 背景是淺色桌面：低飽和又亮的算背景，其餘補洞後取最大一塊 = 徽章範圍
  2. 徽章裡分三種區塊：彩色琺瑯（高飽和）/ 白色琺瑯（亮、低飽和）/ 金屬（其餘，暗）
     彩色琺瑯可以有好幾種顏色：每一塊高飽和區域各自取中位數顏色
  3. 輸出三張貼圖（都裁到外框 bbox）：
       color.png  顏色（乾淨色塊，去掉照片反光）
       mat.png    G = 粗糙度、B = 金屬度（glTF 慣例），金屬亮面 / 琺瑯更亮
       bump.png   金屬線條凸起、琺瑯凹下，3D 裡做出細細的高低差
     以及 shape.json（外框 mm 座標、厚度、別針位置）

用法：
  python tools/extract_badge.py Badge_tarop/IMG_9148.JPG assets/badge_tarop \
      --crop 1250,800,2650,2000 --width-mm 30 --height-mm 30 --thickness-mm 2 --pin-depth-mm 8
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


def largest(mask):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n <= 1:
        return mask
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(lab == big, 255, 0).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out_dir")
    ap.add_argument("--crop", help="x0,y0,x1,y1（原圖像素）")
    ap.add_argument("--rotate", type=float, default=0, help="先轉正（度，逆時針為正）")
    ap.add_argument("--width-mm", type=float, default=30)
    ap.add_argument("--height-mm", type=float, default=30)
    ap.add_argument("--thickness-mm", type=float, default=2)
    ap.add_argument("--pin-depth-mm", type=float, default=8, help="背後別針（含扣頭）總深度")
    ap.add_argument("--tex", type=int, default=2048, help="貼圖長邊像素")
    ap.add_argument("--smooth", type=float, default=1.6, help="邊界磨順程度（照片像素），越大越圓滑但細節越少")
    ap.add_argument("--no-even-rim", dest="even_rim", action="store_false",
                    help="不要把最外圈金屬邊重建成等寬（外框不是金屬邊的特殊徽章才用）")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    img = cv2.imread(a.image)
    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(","))
        img = img[y0:y1, x0:x1]
    if a.rotate:
        h0, w0 = img.shape[:2]
        M = cv2.getRotationMatrix2D((w0 / 2, h0 / 2), a.rotate, 1)
        img = cv2.warpAffine(img, M, (w0, h0), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    img = cv2.bilateralFilter(img, 9, 30, 7)

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    s = hsv[..., 1].astype(int)

    # ---- 徽章範圍：外圈一定是金屬（暗）→ 用暗色 + 彩色封口後補洞 ----
    bg_v = np.median(gray[:20, :])                     # 上緣當作背景亮度
    dark = (gray < bg_v * 0.45).astype(np.uint8) * 255   # 門檻壓低，桌面上的軟陰影才不會被包進來
    colored = (s > 45).astype(np.uint8) * 255
    seed = dark | colored
    # 最外圈常是「金屬邊 + 白琺瑯 + 金屬線」，白色那圈會把外框和裡面切開 → 用夠大的閉運算把它們接起來
    k = max(15, int(min(gray.shape) * 0.02)) | 1
    seed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    badge = largest(fill_holes(largest(seed)))
    badge = cv2.morphologyEx(badge, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    # 閉運算會讓外框稍微膨脹，用原始的暗色外緣修回來
    badge = cv2.erode(badge, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    inside = badge > 0

    # ---- 分區塊 ----
    # 照片上方打光，線條旁的琺瑯常有一圈陰影；只看亮度會把陰影當成黑線，線條就忽粗忽細。
    # 改用 Lab 色彩空間比對：亮度權重調低、看「色相／彩度」(a, b)，陰影裡的紫色仍然是紫色。
    lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    sure = np.zeros(gray.shape, np.uint8)              # 0 不確定 1 金屬 2 白琺瑯 3 彩色琺瑯
    sure[inside & (gray < bg_v * 0.40)] = 1
    sure[inside & (s < 25) & (gray > bg_v * 0.85)] = 2
    sure[inside & (s > 60) & (gray > 70)] = 3
    protos = [np.median(lab_img[sure == c], axis=0) if (sure == c).any() else None for c in (1, 2, 3)]
    wL = 0.45                                          # 亮度的權重（陰影主要改變亮度）
    dist = []
    for pr in protos:
        if pr is None:
            dist.append(np.full(gray.shape, 1e9, np.float32))
            continue
        d = lab_img - pr
        dist.append((d[..., 0] * wL) ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)
    labels = np.zeros(gray.shape, np.uint8)            # 0 外面
    labels[inside] = (np.argmin(np.stack(dist), axis=0) + 1)[inside]

    # 小碎塊（反光、雜點）併到周圍最多的那種；白色小塊門檻比較大（琺瑯反光常是一條白）
    area = inside.sum()
    for c, thr in ((2, 0.004), (3, 0.0006), (1, 0.0004)):
        n, comp, stats, _ = cv2.connectedComponentsWithStats((labels == c).astype(np.uint8))
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < area * thr:
                m = comp == i
                ring = cv2.dilate(m.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~m & inside
                vals = labels[ring]
                vals = vals[(vals != c) & (vals != 0)]
                labels[m] = np.bincount(vals, minlength=4).argmax() if vals.size else 1
    labels[~inside] = 0

    # ---- 外圈金屬邊重建成等寬 ----
    # 照片的陰影、反光會讓某一段外緣被描得比較寬（外框鼓一塊）。
    # 琺瑯章最外圈的金屬邊實際上是等寬的 → 以最外面那圈琺瑯（通常是白色描邊）為基準，
    # 往外推「外緣寬度的中位數」重新得到外框；中位數不受局部鼓包影響。
    if a.even_rim:
        enamel = ((labels == 2) | (labels == 3)).astype(np.uint8) * 255
        core = largest(fill_holes(enamel))           # 先補洞：白色圈填滿後就是最大的一塊
        if core.sum() > badge.sum() * 0.5:             # 琺瑯圈是封閉的才做
            edge = badge.astype(bool) & ~cv2.erode(badge, np.ones((3, 3), np.uint8)).astype(bool)
            dist_out = cv2.distanceTransform(255 - core, cv2.DIST_L2, 5)
            rim = float(np.median(dist_out[edge]))
            new = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * round(rim) + 1,) * 2))
            new = (cv2.GaussianBlur(new.astype(np.float32), (0, 0), max(1.0, rim * 0.25)) > 127).astype(np.uint8) * 255
            labels[(new > 0) & (labels == 0)] = 1      # 新外框裡、原本外面的部分補成金屬
            labels[(new > 0) & ~(core > 0) & (labels != 1)] = 1   # 外緣一律是金屬
            labels[new == 0] = 0
            badge, inside = new, new > 0
            print(f"rim width {rim:.1f}px")

    # ---- 外框（徽章邊緣就是金屬邊，不另外留邊）----
    cnts, _ = cv2.findContours(badge, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea)
    cnt = cv2.approxPolyDP(cnt, 1.0, True)[:, 0, :]
    bx, by, bw, bh = cv2.boundingRect(cnt)
    sx, sy = a.width_mm / bw, a.height_mm / bh

    # ---- 貼圖：在貼圖解析度上把每種區塊的邊界磨順 ----
    # 每一類各自做成 0/1 遮罩 → 放大 → 高斯模糊 → 取最大的那一類。
    # 效果像把像素邊緣「描成向量」：鋸齒、抖動消失，線條寬度也比較一致。
    scale = a.tex / max(bw, bh)
    tw, th = round(bw * scale), round(bh * scale)
    sigma = a.smooth * scale
    crop_lab = labels[by:by + bh, bx:bx + bw]
    soft = []
    for c in (0, 1, 2, 3):
        m = cv2.resize((crop_lab == c).astype(np.float32), (tw, th), interpolation=cv2.INTER_LINEAR)
        soft.append(cv2.GaussianBlur(m, (0, 0), sigma))
    lab = np.argmax(np.stack(soft), axis=0).astype(np.uint8)
    lab[lab == 0] = 1                                  # 外框外面（貼圖邊角）當金屬，避免邊緣露底色
    src = cv2.resize(img[by:by + bh, bx:bx + bw], (tw, th), interpolation=cv2.INTER_AREA)
    hsrc = cv2.cvtColor(src, cv2.COLOR_BGR2HSV)

    color = np.zeros((th, tw, 3), np.uint8)
    color[:] = (28, 26, 30)                            # 金屬：黑鎳電鍍（BGR）
    color[lab == 2] = (244, 244, 244)
    # 彩色琺瑯：每一塊各自取顏色（同色多塊也沒關係），提亮到照片曝光不足前的樣子
    n, comp = cv2.connectedComponents((lab == 3).astype(np.uint8))
    for i in range(1, n):
        m = comp == i
        if m.sum() < 20:
            continue
        # 只取該塊中間（離邊緣遠、不受陰影影響）的像素算顏色
        core = cv2.erode(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        hh, ss, vv = np.median(hsrc[core if core.sum() > 50 else m], axis=0)
        if ss < 40:                                    # 幾乎沒有彩度 → 其實是陰影或金屬反光，不是琺瑯
            lab[m] = 1
            continue
        c = cv2.cvtColor(np.uint8([[[hh, min(255, ss * 1.25), min(255, vv * 1.05)]]]), cv2.COLOR_HSV2BGR)[0, 0]
        color[m] = c
    color = cv2.GaussianBlur(color, (0, 0), 0.8)       # 只做邊緣反鋸齒

    rough = np.where(lab == 1, 0.32, 0.12)             # 金屬亮面、琺瑯更亮
    metal = np.where(lab == 1, 1.0, 0.0)
    mat = np.zeros((th, tw, 3), np.uint8)
    mat[..., 1] = (rough * 255).astype(np.uint8)       # G
    mat[..., 0] = (metal * 255).astype(np.uint8)       # B（OpenCV 是 BGR）
    mat = cv2.GaussianBlur(mat, (0, 0), 0.8)

    bump = np.where(lab == 1, 255, 40).astype(np.uint8)
    bump = cv2.GaussianBlur(bump, (0, 0), 1.5 * scale)

    os.makedirs(a.out_dir, exist_ok=True)
    cv2.imwrite(os.path.join(a.out_dir, "color.png"), color)
    cv2.imwrite(os.path.join(a.out_dir, "mat.png"), mat)
    cv2.imwrite(os.path.join(a.out_dir, "bump.png"), bump)

    # 別針位置：徽章形狀的重心（照片正面座標）
    M = cv2.moments(badge)
    cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]

    pts = [[round((x - bx) * sx, 2), round((by + bh - y) * sy, 2)] for x, y in cnt]
    shape = {
        "type": "badge",
        "w": round(bw * sx, 2), "h": round(bh * sy, 2),
        "thickness": a.thickness_mm,
        "pin": {"x": round((cx - bx) * sx, 2), "y": round((by + bh - cy) * sy, 2), "depth": a.pin_depth_mm},
        "maps": {"color": "color.png", "mat": "mat.png", "bump": "bump.png"},
        "outline": pts,
    }
    with open(os.path.join(a.out_dir, "shape.json"), "w", encoding="utf-8") as f:
        json.dump(shape, f, ensure_ascii=False)
    print(f"outline {len(pts)} pts, {shape['w']} x {shape['h']} mm, tex {tw}x{th}, enamel blocks {n - 1}")

    if a.debug:
        dbg = img.copy()
        dbg[labels == 2] = (255, 200, 0)
        dbg[labels == 3] = (0, 200, 255)
        cv2.polylines(dbg, [cnt.reshape(-1, 1, 2)], True, (0, 0, 255), 2)
        cv2.imwrite(os.path.join(a.out_dir, "_debug.jpg"), dbg)


if __name__ == "__main__":
    main()
