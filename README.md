# Mi'adop 巡獵部落【E10】— 2026 Infurnity 獸無限

攤位商品展示網站：https://peisuky.github.io/miadop-e10/

## 現場最常用：改價格、標完售

打開 Google 試算表「Mi'adop巡獵部落 E10 商品價格與狀態」：

| 欄位 | 填法 |
|---|---|
| 價格 | 只填數字，例如 `350`；留空會顯示「價格待公布」 |
| 狀態 | `販售中` / `完售` / `即將公開` |
| 備註（中／英） | 顯示在商品視窗裡的小字 |
| `@公告` 那一列的備註 | 網站最上方的公告橫幅，留空就不顯示 |
| `@活動狀態` 的狀態 | `活動前` / `活動中` / `活動結束`（結束後首頁顯示「感謝光臨」） |

改完 1～2 分鐘內網站會自動更新（開著的頁面每 2 分鐘重新讀一次）。試算表讀不到時，網站會用 `data/site.json` 裡的備份資料。

## 檔案結構

- `index.html`、`css/`、`js/site.js` — 網站本體
- `data/products.json` — 商品與創作者的文字（中英）
- `data/media.json` — 照片、影片清單（由 `tools/build_assets.py` 產生，不要手改）
- `data/photo-picks.json` — 服裝照片挑選結果，要換照片改這裡再重跑轉檔
- `data/site.json` — 試算表 ID、GA 評估 ID、備份價格
- `viewer/product3d.js` — 3D 預覽（壓克力、徽章、鑰匙圈物理）
- `assets/3d/` — 3D 模型資料；`assets/img/`、`assets/video/`、`assets/brand/` — 轉檔後的圖片影片
- `tools/` — 素材轉檔、3D 擷取腳本
- `_source/` — 原始素材（不上傳 GitHub）

## 更新素材

```bash
python tools/build_assets.py            # 新素材放進 _source/ 後重跑（已轉過的會跳過）
python tools/build_assets.py --force    # 全部重轉
```

改了 CSS / JS / 3D 程式後，把 `index.html` 與 `js/site.js` 裡的 `?v=` 版本號改掉，避免瀏覽器讀到舊檔。

## 本機預覽

```bash
python -m http.server 5173
```

打開 http://localhost:5173/
