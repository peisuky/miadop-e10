"""把每個 3D 商品拍成一張模擬商品圖（斜側 3/4 視角），網站商品卡和社群宣傳圖都用這些圖。

  python tools/render_3d.py                          # 全部
  python tools/render_3d.py miadop-keychain__kulas   # 指定（assets/3d/ 底下的資料夾名）

要先開著本機預覽伺服器（.claude/launch.json 的 preview，port 5173）：3D 檢視器是 ES module，
直接開檔案讀不到。輸出原尺寸 PNG 到 _source/renders/，網站用的縮圖由 build_assets.py --only renders 產生。
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, '_source', 'renders')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
BASE = 'http://localhost:5173/tools/render3d.html'


def render(name):
    out = os.path.join(OUT, name + '.png')
    url = f'{BASE}?item=assets/3d/{name}/shape.json&view=threeQuarter&fit=1.3'   # 拉遠一點，底座、陰影不會碰到邊
    # headless 沒有 GPU：用 SwiftShader 軟體算圖；virtual-time 讓材質載完、鑰匙圈晃完再截
    subprocess.run([CHROME, '--headless=new', '--hide-scrollbars', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                    '--force-device-scale-factor=2', '--window-size=700,700', '--virtual-time-budget=9000',
                    f'--screenshot={out}', url], capture_output=True, timeout=120)
    if not os.path.exists(out):
        raise SystemExit(f'{name}: 沒有截到圖，預覽伺服器有開嗎？')
    print('rendered', name)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or sorted(d for d in os.listdir(os.path.join(ROOT, 'assets', '3d'))
                                   if os.path.exists(os.path.join(ROOT, 'assets', '3d', d, 'shape.json')))
    for n in names:
        render(n)
