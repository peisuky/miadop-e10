// 商品 3D 預覽（three.js）
// 共用：攝影棚環境光、地面陰影、拖曳旋轉／自動旋轉、視角切換。
// 各商品類型由 shape.json 的 type 決定要用哪個 builder：
//
//   acrylic（預設）壓克力立牌／厚磚
//     ・照刀模外形擠出成有厚度的板子，切邊導一點圓角，邊緣會亮
//     ・正反面 transmission 透明材質（ior 1.49 = 壓克力）；切邊透明度低一點、帶一點藍綠
//     ・兩片透明壓克力貼合，印刷夾在中間；雙面材質 → 從背面看是透過壓克力的鏡像
//     shape.json：{ w, h, thickness, print, outline, layers?, base?: {type:'disc', diameter, thickness}, tab?: {w, h} }
//
//   badge 金屬琺瑯徽章
//     ・本體照外形擠出；正面一張貼圖負責顏色＋金屬度／粗糙度＋凹凸（金屬線條凸起、琺瑯凹下）
//     ・背面霧黑塗裝，中間一顆銀色鎖扣別針（旋轉體）
//     shape.json：{ type:'badge', w, h, thickness, outline, maps: {color, mat, bump}, pin: {x, y, depth} }
//
// 單位一律 mm，外形座標原點在左下。
//
// 用法：
//   import { createProductViewer } from './product3d.js';
//   const v = await createProductViewer(el, { src: 'assets/badge_tarop/shape.json' });
//   v.view('front' | 'threeQuarter' | 'side' | 'back');  v.setAutoRotate(true);  v.dispose();

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const BEVEL = 0.6;          // 切邊圓角（mm）
const IDLE_RESUME = 4000;   // 放手幾毫秒後恢復自動旋轉
const INTRO_HOLD = 1000;    // 切換到商品時，先停在正面多久再開始自動旋轉

// ---------- 共用小工具 ----------

// holes：[{ x, y, r }] 圓孔（鑰匙圈的穿孔）
function slab(outline, t, mats, bevel = BEVEL, holes = []) {
  const b = Math.min(bevel, t / 4);      // 薄板時圓角跟著縮
  const shape = new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, y)));
  for (const { x, y, r } of holes) {
    const N = 32;                          // curveSegments 是 1，所以圓孔自己切成多邊形
    shape.holes.push(new THREE.Path(Array.from({ length: N }, (_, i) =>
      new THREE.Vector2(x + r * Math.cos(-i / N * Math.PI * 2), y + r * Math.sin(-i / N * Math.PI * 2)))));
  }
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: t - 2 * b, bevelEnabled: true,
    bevelThickness: b, bevelSize: b * 0.6, bevelSegments: 3, curveSegments: 1
  });
  geo.translate(0, 0, -(t - 2 * b) / 2);
  geo.computeVertexNormals();
  return new THREE.Mesh(geo, mats);      // ExtrudeGeometry：群組 0 = 正反面、1 = 切邊
}

// 背景：上牆下桌、中間一條柔和的地平線。透明材質要「看得到後面東西被折射」才有玻璃感，純色背景會像霧面
function backdrop(hex) {
  const c = document.createElement('canvas'); c.width = 4; c.height = 512;
  const g = c.getContext('2d'), base = new THREE.Color(hex);
  const css = (k) => '#' + base.clone().multiplyScalar(k).getHexString();
  const gr = g.createLinearGradient(0, 0, 0, 512);
  gr.addColorStop(0, css(0.90)); gr.addColorStop(0.50, css(0.95));
  gr.addColorStop(0.56, css(1.02)); gr.addColorStop(1, css(1.04));
  g.fillStyle = gr; g.fillRect(0, 0, 4, 512);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function loadTexture(url, renderer, srgb = true) {
  return new Promise((res, rej) => new THREE.TextureLoader().load(url, tex => {
    tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    res(tex);
  }, undefined, rej));
}

// ---------- 柔和陰影（PCSS）----------
// 真實光源有面積：物體貼地的地方陰影銳利，離地越遠半影越寬、越模糊。
// three.js 內建的 PCF 是整片同樣模糊，這裡改寫陰影 shader：
//   1. 在附近取樣找出「遮擋物的平均深度」
//   2. 遮擋物離接收面越遠 → 模糊半徑越大（半影寬 ≈ 距離 × 光源角大小）
//   3. 用旋轉的 Poisson 取樣做模糊
// 平行光的陰影相機是正交投影，深度是線性的，所以距離可以直接換算成 mm。
const ORIGINAL_SHADOW_CHUNK = THREE.ShaderChunk.shadowmap_pars_fragment;

function installSoftShadows({ depthRange, uvPerMm, maxDist, spread = 0.09, minBlurMm = 0.35 }) {
  const f = (x) => x.toFixed(6);
  const pcss = `
    #define PCSS_SAMPLES 32
    #define PCSS_RANGE ${f(depthRange)}          // 陰影相機 far - near（mm）
    #define PCSS_SPREAD ${f(spread * uvPerMm)}   // 每 1mm 距離增加的半影半徑（uv）
    #define PCSS_MIN ${f(minBlurMm * uvPerMm)}   // 貼地處最小的模糊（uv）
    #define PCSS_SEARCH ${f(maxDist * spread * uvPerMm)}
    vec2 pcssDisk[PCSS_SAMPLES];
    void pcssInit( const in vec2 seed ) {
      float angle = rand( seed ) * PI2, r = 1.0 / float( PCSS_SAMPLES );
      for ( int i = 0; i < PCSS_SAMPLES; i ++ ) {
        pcssDisk[i] = vec2( cos( angle ), sin( angle ) ) * pow( r, 0.75 );
        r += 1.0 / float( PCSS_SAMPLES );
        angle += PI2 * 11.0 / float( PCSS_SAMPLES );
      }
    }
    float PCSS( sampler2D shadowMap, vec4 coords ) {
      vec2 uv = coords.xy; float zr = coords.z;
      pcssInit( uv );
      float sum = 0.0; int n = 0;
      for ( int i = 0; i < PCSS_SAMPLES; i ++ ) {
        float d = unpackRGBAToDepth( texture2D( shadowMap, uv + pcssDisk[i] * PCSS_SEARCH ) );
        if ( d < zr ) { sum += d; n ++; }
      }
      if ( n == 0 ) return 1.0;
      float distMm = ( zr - sum / float( n ) ) * PCSS_RANGE;
      float radius = PCSS_MIN + distMm * PCSS_SPREAD;
      float lit = 0.0;
      for ( int i = 0; i < PCSS_SAMPLES; i ++ ) {
        lit += step( zr, unpackRGBAToDepth( texture2D( shadowMap, uv + pcssDisk[i] * radius ) ) );
        lit += step( zr, unpackRGBAToDepth( texture2D( shadowMap, uv - pcssDisk[i].yx * radius ) ) );
      }
      return lit / float( 2 * PCSS_SAMPLES );
    }
  `;
  THREE.ShaderChunk.shadowmap_pars_fragment = ORIGINAL_SHADOW_CHUNK
    .replace('#ifdef USE_SHADOWMAP', '#ifdef USE_SHADOWMAP\n' + pcss)
    .replace('#if defined( SHADOWMAP_TYPE_PCF )', 'return mix( 1.0, PCSS( shadowMap, shadowCoord ), shadowIntensity );\n#if defined( SHADOWMAP_TYPE_PCF )');
}

// ---------- 壓克力 ----------

function acrylicMats(env, t) {
  const face = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, metalness: 0, roughness: 0.02,
    transmission: 1, thickness: t, ior: 1.49,
    envMap: env, envMapIntensity: 0.45,
    clearcoat: 0.2, clearcoatRoughness: 0.02, specularIntensity: 0.6
  });
  const side = new THREE.MeshPhysicalMaterial({
    color: 0xf7fbfb, metalness: 0, roughness: 0.05,
    transmission: 1, thickness: t * 2, ior: 1.49,
    envMap: env, envMapIntensity: 0.6,
    clearcoat: 0.4, clearcoatRoughness: 0.05,
    attenuationColor: new THREE.Color(0.84, 0.92, 0.90), attenuationDistance: t * 4
  });
  return [face, side];
}

async function buildAcrylic(spec, { env, renderer, dir }) {
  const { w, h, thickness: t } = spec;
  const baseT = spec.base?.thickness ?? 0;
  const root = new THREE.Group();
  const group = new THREE.Group();
  group.position.set(-w / 2, baseT, 0);  // 以板子中心為旋轉軸；有底座時站在底座上
  root.add(group);

  // 實品是兩片透明壓克力貼合，印刷夾在中間。
  // 分成兩塊擠出：各自的切邊圓角在接合處形成一道細縫，側面看得到兩層的分界線。
  const nLayers = spec.layers ?? 2, lt = t / nLayers;
  const mats = acrylicMats(env, lt);
  // 插腳：角色板底部中央往下延伸，整段插在底座的孔裡
  const tabPts = spec.tab && [[(w - spec.tab.w) / 2, -spec.tab.h], [(w + spec.tab.w) / 2, -spec.tab.h],
                              [(w + spec.tab.w) / 2, 0.01], [(w - spec.tab.w) / 2, 0.01]];
  for (let i = 0; i < nLayers; i++) {
    const z = -t / 2 + lt * (i + 0.5);
    for (const pts of [spec.outline, tabPts].filter(Boolean)) {
      const layer = slab(pts, lt, mats);
      layer.position.z = z;
      group.add(layer);
    }
  }

  // 圓形底座：圓盤外形擠出後轉成水平，中心對齊角色板中心
  if (spec.base?.type === 'disc') {
    const r = spec.base.diameter / 2, N = 96;
    const disc = Array.from({ length: N }, (_, i) => [r * Math.cos(i / N * Math.PI * 2), r * Math.sin(i / N * Math.PI * 2)]);
    const plateBase = slab(disc, baseT, acrylicMats(env, baseT), 0.8);
    plateBase.rotation.x = -Math.PI / 2;
    plateBase.position.y = baseT / 2;
    root.add(plateBase);
  }

  const tex = await loadTexture(dir + spec.print, renderer);
  // 印刷圖用不受光的材質：顏色就是原稿顏色，不會被燈打白或背光變暗。
  // 位在兩層正中間（z = 0）：正面、背面都是隔著一片壓克力看到圖，背面自然是鏡像。
  const print = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide, alphaTest: 0.5 }));
  print.position.set(w / 2, h / 2, 0);
  print.castShadow = true;
  // 陰影只看圖案的 alpha（透明壓克力本身幾乎不擋光）
  print.customDepthMaterial = new THREE.MeshDepthMaterial({ map: tex, alphaTest: 0.5, depthPacking: THREE.RGBADepthPacking });
  group.add(print);

  const H = baseT + h;
  return {
    root, textures: [tex],
    size: Math.max(w, H), center: H / 2, top: H,
    foot: spec.base ? [spec.base.diameter * 1.25, spec.base.diameter * 1.25] : [w * 1.4, t * 3.2]
  };
}

// ---------- 徽章 ----------

// 鎖扣別針的剖面（r, 深度），沿 Y 軸旋轉成形，深度 d = 別針總深度
function pinProfile(d) {
  const k = d / 8;                       // 以 8mm 深的常見鎖扣為基準等比縮放
  return [
    [0, 0], [4.0, 0], [4.15, 0.15], [4.15, 0.45], [4.0, 0.6],      // 底座圓片（焊在徽章背面）
    [1.5, 0.65], [1.3, 0.8], [1.3, 3.0],                            // 針管
    [3.3, 3.05], [3.55, 3.25], [3.55, 6.9],                         // 扣頭側面
    [3.35, 7.25], [3.0, 7.45], [0.6, 7.95], [0, 8.0]                // 扣頭頂面（微凸、髮絲紋）
  ].map(([r, y]) => new THREE.Vector2(r * Math.min(1, k * 1.1), y * k));
}

async function buildBadge(spec, { env, renderer, dir }) {
  const { w, h, thickness: t } = spec;
  const lift = Math.max(6, h * 0.22);    // 徽章懸空立著，底下留一點空間看得到陰影
  const root = new THREE.Group();
  const group = new THREE.Group();
  group.position.set(-w / 2, lift, 0);
  root.add(group);

  const [color, mat, bump] = await Promise.all([
    loadTexture(dir + spec.maps.color, renderer),
    loadTexture(dir + spec.maps.mat, renderer, false),
    loadTexture(dir + spec.maps.bump, renderer, false)
  ]);
  // ShapeGeometry 的 UV 就是 mm 座標 → 用 repeat 換算成 0..1
  for (const tx of [color, mat, bump]) tx.repeat.set(1 / w, 1 / h);

  // 本體：背面霧黑塗裝、切邊是黑色電鍍金屬
  const back = new THREE.MeshPhysicalMaterial({ color: 0x232122, metalness: 0.35, roughness: 0.42, envMapIntensity: 1.0 });
  const edge = new THREE.MeshPhysicalMaterial({ color: 0x2a2627, metalness: 1, roughness: 0.28, envMapIntensity: 1.2 });
  const body = slab(spec.outline, t, [back, edge], 0.3);
  body.castShadow = true;
  group.add(body);

  // 正面：顏色 / 金屬度 / 粗糙度 / 凹凸 都從貼圖來；整面再上一層亮面（硬琺瑯拋光後很亮）
  const faceMat = new THREE.MeshPhysicalMaterial({
    map: color, metalnessMap: mat, roughnessMap: mat, metalness: 1, roughness: 1,
    bumpMap: bump, bumpScale: 0.6,
    clearcoat: 0.6, clearcoatRoughness: 0.06, envMapIntensity: 1.1
  });
  const shape = new THREE.Shape(spec.outline.map(([x, y]) => new THREE.Vector2(x, y)));
  const face = new THREE.Mesh(new THREE.ShapeGeometry(shape), faceMat);
  face.position.z = t / 2 + 0.01;
  group.add(face);

  // 背面別針：銀色金屬旋轉體，軸朝徽章背後（-z）
  const pinMat = new THREE.MeshPhysicalMaterial({ color: 0xdcd8ce, metalness: 1, roughness: 0.26, envMapIntensity: 1.3 });
  const pin = new THREE.Mesh(new THREE.LatheGeometry(pinProfile(spec.pin.depth), 64), pinMat);
  pin.rotation.x = -Math.PI / 2;
  pin.position.set(spec.pin.x, spec.pin.y, -t / 2);
  pin.castShadow = true;
  group.add(pin);

  return {
    root, textures: [color, mat, bump],
    size: Math.max(w, h + lift) * 1.4, center: lift + h / 2, top: lift + h,
    foot: [w * 1.3, (t + spec.pin.depth) * 2.2]
  };
}

// ---------- 鑰匙圈 ----------
// 圓環固定在最上方（像掛在鉤子上），使用者拖曳 = 拿著圓環轉動／傾斜。
// 鏈條與壓克力用 Verlet 積分 + 位置約束（PBD）模擬：
//   ・鏈條：一串質點，相鄰兩點距離不能超過一節的長度（可以鬆、不能拉長）
//   ・小扣環：最後一節到壓克力孔的距離
//   ・壓克力：孔 H、重心 C、重心旁一點 F 三個質點用剛性距離綁成一塊 → 自然會讓重心垂在孔的正下方
//   ・扭轉：鏈條對扭轉有一點阻力 → 轉動圓環時壓克力會慢半拍跟上、來回擺幾下
// 單位 mm、秒；重力 9810 mm/s²。

class LinkCurve extends THREE.Curve {       // 鏈節：跑道形（兩個半圓 + 兩段直線），長軸沿 Y
  constructor(hl, hw) { super(); this.hl = hl; this.hw = hw; }
  getPoint(t, out = new THREE.Vector3()) {
    const { hl, hw } = this, s = hl - hw;    // s：直線段的一半
    const per = 4 * s + 2 * Math.PI * hw;
    let d = t * per;
    if (d < 2 * s) return out.set(hw, -s + d, 0);
    d -= 2 * s;
    if (d < Math.PI * hw) { const a = d / hw; return out.set(hw * Math.cos(a), s + hw * Math.sin(a), 0); }
    d -= Math.PI * hw;
    if (d < 2 * s) return out.set(-hw, s - d, 0);
    d -= 2 * s;
    const a = Math.PI + d / hw;
    return out.set(hw * Math.cos(a), -s + hw * Math.sin(a), 0);
  }
}

class HelixCurve extends THREE.Curve {      // 圓環：繞兩圈的螺旋（真實鑰匙圈是兩圈鋼線疊起來）
  constructor(r, turns, gap) { super(); this.r = r; this.turns = turns; this.gap = gap; }
  getPoint(t, out = new THREE.Vector3()) {
    const a = t * this.turns * Math.PI * 2;
    return out.set(this.r * Math.sin(a), this.r * Math.cos(a), (t - 0.5) * this.gap);
  }
}

function polygonCentroid(pts) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % pts.length], k = x0 * y1 - x1 * y0;
    a += k; cx += (x0 + x1) * k; cy += (y0 + y1) * k;
  }
  return { area: Math.abs(a / 2), x: cx / (3 * a), y: cy / (3 * a) };
}

async function buildKeychain(spec, { env, renderer, dir }) {
  const { w, h, thickness: t, hole } = spec;
  const ringR = spec.ring.diameter / 2 - spec.ring.wire / 2;     // 圓環鋼線中心半徑
  const wire = 0.9, linkW = 3.6;                                  // 鏈條鋼線粗、鏈節寬
  const nLinks = Math.max(2, Math.round(spec.chain.length / 4.5));
  const pitch = spec.chain.length / nLinks;                       // 一節的長度（質點間距）
  const jump = 2.6;                                               // 小扣環：最後一節到孔中心
  const metal = new THREE.MeshPhysicalMaterial({ color: 0xd9d6d0, metalness: 1, roughness: 0.22, envMapIntensity: 1.3 });

  const com = polygonCentroid(spec.outline);
  const lowest = Math.min(...spec.outline.map(p => p[1]));
  const hangLen = 2 * ringR + spec.chain.length + jump + (hole.y - lowest);
  const hookY = hangLen + 18;                                     // 掛點高度：壓克力底下離桌面約 18mm
  const root = new THREE.Group();

  // ---- 圓環（運動學物體：跟著手）----
  const ring = new THREE.Group();
  const ringMesh = new THREE.Mesh(new THREE.TubeGeometry(new HelixCurve(ringR, 2, spec.ring.wire * 1.05), 200, spec.ring.wire / 2, 10, false), metal);
  ringMesh.position.y = -ringR;
  ringMesh.castShadow = true;
  ring.add(ringMesh);
  ring.position.y = hookY;
  root.add(ring);

  // ---- 鏈節 ----
  const linkGeo = new THREE.TubeGeometry(new LinkCurve(pitch / 2 + wire * 0.55, linkW / 2 - wire / 2), 48, wire / 2, 8, true);
  const links = Array.from({ length: nLinks }, () => {
    const m = new THREE.Mesh(linkGeo, metal); m.castShadow = true; root.add(m); return m;
  });
  const jumpMesh = new THREE.Mesh(new THREE.TorusGeometry(jump * 0.62, 0.45, 8, 32), metal);
  jumpMesh.castShadow = true;
  root.add(jumpMesh);

  // ---- 壓克力（區域座標原點 = 孔中心）----
  const acr = new THREE.Group();
  acr.matrixAutoUpdate = false;
  const inner = new THREE.Group();
  inner.position.set(-hole.x, -hole.y, 0);
  acr.add(inner);
  root.add(acr);
  const nLayers = spec.layers ?? 2, lt = t / nLayers;
  const mats = acrylicMats(env, lt);
  for (let i = 0; i < nLayers; i++) {
    const layer = slab(spec.outline, lt, mats, BEVEL, [hole]);
    layer.position.z = -t / 2 + lt * (i + 0.5);
    inner.add(layer);
  }
  const tex = await loadTexture(dir + spec.print, renderer);
  const print = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide, alphaTest: 0.5 }));
  print.position.set(w / 2, h / 2, 0);
  print.castShadow = true;
  print.customDepthMaterial = new THREE.MeshDepthMaterial({ map: tex, alphaTest: 0.5, depthPacking: THREE.RGBADepthPacking });
  inner.add(print);

  // ---- 物理 ----
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  // 壓克力剛體：孔 H + 左右兩個質點 L、R（質量分散在兩側，轉動慣量才接近真的板子；
  // 兩點離得遠，算姿態時約束的微小誤差不會被放大成抖動）
  const massA = com.area * t * 0.00119;                          // 壓克力密度 1.19 g/cm³ → g
  const mH = massA * 0.1, mS = massA * 0.45;                    // 孔 10%、左右各 45%
  const Cl = V(com.x - hole.x, com.y - hole.y, 0);              // 重心（區域座標，孔為原點）
  const Ml = Cl.clone().multiplyScalar(1 / 0.9);                 // L、R 的中點：讓三點合起來的重心剛好在 Cl
  const half = Math.max(6, w * 0.32);
  const Ll = Ml.clone().add(V(-half, 0, 0)), Rl = Ml.clone().add(V(half, 0, 0));
  const P = [];                                                  // { x, prev, inv }
  const add = (p, inv) => { P.push({ x: p.clone(), prev: p.clone(), inv }); return P.length - 1; };
  const anchorY = hookY - 2 * ringR;
  add(V(0, anchorY, 0), 0);                                      // 0：圓環底（跟著手）
  // 鏈節質量比實際（約 0.1g）重一點：太輕的鏈條吊重壓克力時約束解不乾淨，靜止時會一直抖
  for (let i = 1; i <= nLinks; i++) add(V(0, anchorY - pitch * i, 0), 1 / 0.8);
  const iLast = nLinks;
  const iH = add(V(0, anchorY - spec.chain.length - jump, 0), 1 / mH);
  const Hy = P[iH].x.y;
  const iL = add(V(Ll.x, Hy + Ll.y, 0), 1 / mS);
  const iR = add(V(Rl.x, Hy + Rl.y, 0), 1 / mS);
  const rigid = [[iH, iL, Ll.length()], [iH, iR, Rl.length()], [iL, iR, 2 * half]];

  const hand = new THREE.Quaternion(), hookV = V(0, hookY, 0);
  const handFrom = new THREE.Quaternion(), handTarget = new THREE.Quaternion();
  let handYaw = 0, handFromYaw = 0, handTargetYaw = 0;
  // TWIST：鏈條傳扭力很弱（太硬會被甩成水平）；TWIST_DAMP：扭轉的摩擦，讓來回轉幾下後自然停住
  const G = -9810, AIR = 1.6, TWIST = 0.004, TWIST_DAMP = 0.02, ITER = 20;
  const STEP = 1 / 600;                                           // 固定步長（Verlet 步長一變就會產生假速度）
  let acc = 0, lastHandYaw = 0;
  const yawOf = (a, b) => Math.atan2(-(b.z - a.z), b.x - a.x);   // 水平面上 a→b 的方位角
  const wrap = (x) => Math.atan2(Math.sin(x), Math.cos(x));
  const tmp = V(0, 0, 0), tmp2 = V(0, 0, 0);

  function rope(i, j, len, rigidMode) {
    const a = P[i], b = P[j];
    tmp.subVectors(b.x, a.x);
    const d = tmp.length();
    if (d < 1e-6 || (!rigidMode && d <= len)) return;            // 鏈條只防拉長、可以鬆
    const wsum = a.inv + b.inv;
    if (!wsum) return;
    tmp.multiplyScalar((d - len) / d / wsum);
    a.x.addScaledVector(tmp, a.inv);
    b.x.addScaledVector(tmp, -b.inv);
  }

  function substep(dt) {
    // 圓環底的掛點跟著手（掛點繞頂端旋轉）
    P[0].prev.copy(P[0].x);
    P[0].x.set(0, -2 * ringR, 0).applyQuaternion(hand).add(hookV);
    const damp = Math.exp(-AIR * dt);
    for (const p of P) {
      if (!p.inv) continue;
      tmp.subVectors(p.x, p.prev).multiplyScalar(damp);
      p.prev.copy(p.x);
      p.x.add(tmp).y += G * dt * dt;
    }
    // 每一輪交替由上往下、由下往上解，重物吊在鏈條下時收斂快很多
    for (let k = 0; k < ITER; k++) {
      if (k % 2 === 0) {
        for (let i = 0; i < nLinks; i++) rope(i, i + 1, pitch, false);
        rope(iLast, iH, jump, false);
        for (const [i, j, len] of rigid) rope(i, j, len, true);
      } else {
        for (const [i, j, len] of rigid) rope(i, j, len, true);
        rope(iLast, iH, jump, false);
        for (let i = nLinks - 1; i >= 0; i--) rope(i, i + 1, pitch, false);
      }
    }
    // 扭轉：L、R 一起繞「孔 → LR 中點」的軸轉（成對施力 = 純旋轉，不會把整塊推歪）
    //   彈力：往圓環朝向拉回；阻尼：抵消「壓克力相對圓環」的轉速
    const H = P[iH], L = P[iL], R = P[iR];
    const yawNow = yawOf(L.x, R.x), yawPrev = yawOf(L.prev, R.prev);
    const relVel = wrap(yawNow - yawPrev) - wrap(handYaw - lastHandYaw);
    lastHandYaw = handYaw;
    const ang = wrap(handYaw - yawNow) * TWIST - relVel * TWIST_DAMP;
    tmp2.addVectors(L.x, R.x).multiplyScalar(0.5);               // LR 中點
    const axis = tmp.subVectors(H.x, tmp2).normalize();           // 往上的軸：正角度 = 方位角增加
    for (const p of [L, R]) {
      const r = p.x.clone().sub(H.x).applyAxisAngle(axis, ang);
      p.x.copy(H.x).add(r);
    }
  }

  const mX = V(0, 0, 0), mY = V(0, 0, 0), mZ = V(0, 0, 0), lBasis = new THREE.Matrix4(), wBasis = new THREE.Matrix4();
  {
    const lx = Rl.clone().sub(Ll).normalize();                    // 區域座標：L → R 為 +x
    const ly = Ml.clone().negate(); ly.addScaledVector(lx, -ly.dot(lx)).normalize();   // 中點 → 孔 為 +y
    lBasis.makeBasis(lx, ly, V(0, 0, 0).crossVectors(lx, ly));
  }
  const lBasisInv = lBasis.clone().transpose();
  const up = V(0, 1, 0), q = new THREE.Quaternion(), qt = new THREE.Quaternion(), dirV = V(0, 0, 0);
  let acrYaw = 0;

  function sync() {
    ring.quaternion.copy(hand);
    // 壓克力：由三個質點算出姿態
    const H = P[iH].x, Lx = P[iL].x, Rx = P[iR].x;
    mX.subVectors(Rx, Lx).normalize();
    mY.addVectors(Lx, Rx).multiplyScalar(-0.5).add(H); mY.addScaledVector(mX, -mY.dot(mX)).normalize();
    mZ.crossVectors(mX, mY);
    wBasis.makeBasis(mX, mY, mZ).multiply(lBasisInv);
    acr.matrix.copy(wBasis).setPosition(H);
    acrYaw = Math.atan2(-mX.z, mX.x);
    // 鏈節：沿相鄰兩質點擺放，一節一節交錯 90°，扭轉角從圓環朝向漸變到壓克力朝向
    for (let i = 0; i < nLinks; i++) {
      const a = P[i].x, b = P[i + 1].x;
      dirV.subVectors(a, b).normalize();
      let dy = acrYaw - handYaw; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
      const tw = handYaw + dy * (i / nLinks) + (i % 2 ? 0 : Math.PI / 2);   // 第一節穿過圓環 → 和圓環垂直
      q.setFromUnitVectors(up, dirV);
      qt.setFromAxisAngle(up, tw);
      links[i].quaternion.copy(q).multiply(qt);
      links[i].position.addVectors(a, b).multiplyScalar(0.5);
    }
    // 小扣環：穿過孔，平面垂直於壓克力
    const last = P[iLast].x;
    dirV.subVectors(last, H).normalize();
    mZ.crossVectors(mZ.clone(), dirV).normalize();                // 扣環軸 ≈ 壓克力的左右方向
    const nx = V(0, 0, 0).crossVectors(dirV, mZ);
    jumpMesh.matrixAutoUpdate = false;
    jumpMesh.matrix.makeBasis(nx, dirV, mZ).setPosition(V(0, 0, 0).addVectors(last, H).multiplyScalar(0.5));
  }

  // 先模擬一段時間讓它靜止下來，載入時不會突然晃
  for (let i = 0; i < 1800; i++) substep(STEP);
  for (const p of P) p.prev.copy(p.x);
  sync();

  return {
    root, textures: [tex],
    size: hookY * 1.08, center: hookY * 0.5, top: hookY,   // 留邊：圓環在方形畫面裡也不會被切到
    foot: [w * 1.4, w * 0.9],
    hold: {
      // 手的新姿勢先記下來，step() 裡在每個物理小步之間平滑內插過去
      // （一畫格才跳一次的話，掛點每畫格突然位移一下，壓克力就會跟著一頓一頓地抖）
      setHand(yaw, pitch, roll) {
        handTargetYaw = yaw;
        handTarget.setFromEuler(new THREE.Euler(pitch, yaw, roll, 'YXZ'));
      },
      // 偵錯用：目前各質點的最大速度（mm/s）
      speeds() { return P.map(p => +(p.x.distanceTo(p.prev) / STEP).toFixed(1)); },
      positions() { return P.map(p => p.x.toArray().map(v => +v.toFixed(2))); },
      maxSpeed() { let m = 0; for (const p of P) if (p.inv) m = Math.max(m, p.x.distanceTo(p.prev)); return m / STEP; },
      step(dt) {
        acc = Math.min(acc + dt, 0.05);                           // 分頁切走回來時不要一次補太多步
        const n = Math.floor(acc / STEP);
        for (let k = 1; k <= n; k++) {
          hand.slerpQuaternions(handFrom, handTarget, k / n);
          handYaw = handFromYaw + (handTargetYaw - handFromYaw) * (k / n);
          substep(STEP);
        }
        acc -= n * STEP;
        if (n) { handFrom.copy(handTarget); handFromYaw = handTargetYaw; }
        sync();
      }
    }
  };
}

const BUILDERS = { acrylic: buildAcrylic, badge: buildBadge, keychain: buildKeychain };

// ---------- 檢視器 ----------

export async function createProductViewer(container, { src, background = 0xf1eee8, autoRotate = true } = {}) {
  const dir = src.slice(0, src.lastIndexOf('/') + 1);
  const spec = await (await fetch(src)).json();

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;   // 實際的模糊由 installSoftShadows 的 PCSS 接手
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = backdrop(background);
  const pm = new THREE.PMREMGenerator(renderer);
  const env = pm.fromScene(new RoomEnvironment(), 0.03).texture;
  pm.dispose();
  scene.environment = env;

  const build = BUILDERS[spec.type ?? 'acrylic'];
  if (!build) throw new Error(`不支援的商品類型：${spec.type}`);
  const item = await build(spec, { env, renderer, dir });
  scene.add(item.root);

  // ---- 燈光與地面 ----
  scene.add(new THREE.HemisphereLight(0xffffff, 0xe8e2d8, 0.25));
  const key = new THREE.DirectionalLight(0xffffff, 0.9);
  key.position.set(-60, 140, 90);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.bias = -0.0005;
  const sc = item.size * 1.3;
  const near = 10, far = 400;
  Object.assign(key.shadow.camera, { left: -sc, right: sc, top: sc, bottom: -sc, near, far });
  scene.add(key);
  installSoftShadows({ depthRange: far - near, uvPerMm: 1 / (2 * sc), maxDist: item.size });

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.ShadowMaterial({ opacity: 0.22 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // 底下一圈淡淡的接觸陰影（ShadowMaterial 不夠柔時補一點）
  const blobTex = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, 'rgba(0,0,0,0.35)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  })();
  const blob = new THREE.Mesh(new THREE.PlaneGeometry(...item.foot),
    new THREE.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false }));
  blob.rotation.x = -Math.PI / 2;
  blob.position.y = 0.05;
  scene.add(blob);

  // ---- 控制 ----
  const camera = new THREE.PerspectiveCamera(28, 1, 1, 2000);
  const dist = item.size * 2.3;
  const hold = item.hold;                         // 鑰匙圈：拖曳是轉商品本身（鏈條才會甩），鏡頭固定在正面
  if (hold) camera.position.set(0, item.center + item.size * 0.12, dist);
  else camera.position.setFromSpherical(new THREE.Spherical(dist, 1.32, 0)).add(new THREE.Vector3(0, item.center, 0));   // 和「正面」按鈕同一個角度
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, item.center, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;
  controls.enablePan = false;
  controls.minDistance = dist * 0.45;
  controls.maxDistance = dist * 1.8;
  controls.minPolarAngle = 0.25;
  controls.maxPolarAngle = Math.PI / 2 - 0.02;   // 不鑽到桌面底下
  controls.autoRotate = false;                    // 先停在正面，INTRO_HOLD 後才開始轉
  controls.autoRotateSpeed = 2.2;
  controls.enableRotate = !hold;
  controls.update();

  // ---- 手持模式（hold）：拖曳左右 = 轉動、上下 = 前後傾；放手後轉動帶慣性、傾斜彈回 ----
  // yawGoal / pitchGoal 是滑鼠指到的角度，手的實際角度平滑追上去（真實的手不會一瞬間轉半圈）
  const hs = { yaw: 0, yawGoal: 0, yawVel: 0, pitch: 0, pitchGoal: 0, pitchVel: 0, roll: 0, drag: false, lastX: 0, lastY: 0, idleAt: performance.now() - IDLE_RESUME + INTRO_HOLD };   // 手持模式：一樣停 INTRO_HOLD 後才自動轉
  const HAND_LAG = 0.07;
  let holdTween = null;
  if (hold) {
    const el = renderer.domElement;
    el.addEventListener('pointerdown', e => {
      hs.drag = true; hs.lastX = e.clientX; hs.lastY = e.clientY;
      if (!hs.catchUp) { hs.yawGoal = hs.yaw; hs.pitchGoal = hs.pitch; }
      holdTween = null; el.setPointerCapture(e.pointerId);
    });
    el.addEventListener('pointermove', e => {
      if (!hs.drag) return;
      hs.yawGoal += (e.clientX - hs.lastX) * 0.012;
      hs.pitchGoal = THREE.MathUtils.clamp(hs.pitchGoal + (e.clientY - hs.lastY) * 0.006, -0.6, 0.6);
      hs.lastX = e.clientX; hs.lastY = e.clientY;
    });
    // 放手時手還沒追上滑鼠的話，先追完再進入慣性（快速一甩也不會少轉）
    const up = () => { hs.drag = false; hs.catchUp = true; hs.idleAt = performance.now(); };
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
  }
  function stepHold(dt) {
    if (holdTween) {
      const k = Math.min(1, (performance.now() - holdTween.t0) / holdTween.dur), e = 1 - Math.pow(1 - k, 3);
      const y = holdTween.from + (holdTween.to - holdTween.from) * e;
      hs.yawVel = (y - hs.yaw) / dt; hs.yaw = y;
      if (k >= 1) { holdTween = null; hs.idleAt = performance.now(); }
    } else if (hs.drag || hs.catchUp) {
      // 臨界阻尼彈簧追隨：速度和加速度都連續，起步、停下都不會突然一頓
      const w = 1 / HAND_LAG;
      hs.yawVel += (w * w * (hs.yawGoal - hs.yaw) - 2 * w * hs.yawVel) * dt;
      hs.yawVel = THREE.MathUtils.clamp(hs.yawVel, -4, 4);          // 放手後用這個速度繼續轉（慣性）
      hs.yaw += hs.yawVel * dt;
      hs.pitchVel += (w * w * (hs.pitchGoal - hs.pitch) - 2 * w * hs.pitchVel) * dt;
      hs.pitch += hs.pitchVel * dt;
      if (!hs.drag && Math.abs(hs.yawGoal - hs.yaw) < 0.02 && Math.abs(hs.pitchGoal - hs.pitch) < 0.02) hs.catchUp = false;
    } else {
      hs.yaw += hs.yawVel * dt;
      const idle = performance.now() - hs.idleAt > IDLE_RESUME;
      const targetVel = wantAuto && idle ? 0.6 : 0;          // 自動旋轉：慢慢轉
      hs.yawVel += (targetVel - hs.yawVel) * (1 - Math.exp(-(idle ? 1.2 : 2.2) * dt));
      // 傾斜像被手放開：彈回直立
      hs.pitchVel += (-60 * hs.pitch - 9 * hs.pitchVel) * dt;
      hs.pitch += hs.pitchVel * dt;
    }
    // 快速轉動時手會帶一點側傾 → 鏈條左右甩
    const rollTarget = THREE.MathUtils.clamp(-hs.yawVel * 0.025, -0.18, 0.18);
    hs.roll += (rollTarget - hs.roll) * (1 - Math.exp(-4 * dt));
    hold.setHand(hs.yaw, hs.pitch, hs.roll);
    hold.step(dt);
  }

  let wantAuto = autoRotate, idleTimer = 0, tween = null;
  if (!hold && wantAuto) idleTimer = setTimeout(() => (controls.autoRotate = wantAuto), INTRO_HOLD);
  controls.addEventListener('start', () => { controls.autoRotate = false; clearTimeout(idleTimer); tween = null; });
  controls.addEventListener('end', () => {
    clearTimeout(idleTimer);
    if (wantAuto) idleTimer = setTimeout(() => (controls.autoRotate = true), IDLE_RESUME);
  });

  // 視角切換：繞 target 補間到指定方位角
  function view(name) {
    if (hold) {                                    // 手持模式：轉商品，不轉鏡頭
      const az = { front: 0, side: -Math.PI / 2, back: Math.PI, threeQuarter: -Math.PI / 5 }[name] ?? 0;
      let d = az - hs.yaw; d = Math.atan2(Math.sin(d), Math.cos(d));
      hs.catchUp = false;
      holdTween = { from: hs.yaw, to: hs.yaw + d, t0: performance.now(), dur: 900 };
      return;
    }
    const az = { front: 0, side: Math.PI / 2, back: Math.PI, threeQuarter: Math.PI / 5 }[name] ?? 0;
    const offset = camera.position.clone().sub(controls.target);
    const sph = new THREE.Spherical().setFromVector3(offset);
    let d = az - sph.theta;
    d = Math.atan2(Math.sin(d), Math.cos(d));      // 走最短的方向
    tween = { from: sph.theta, to: sph.theta + d, phi0: sph.phi, phi1: 1.32, r: sph.radius, t0: performance.now(), dur: 700 };
    controls.autoRotate = false;
    clearTimeout(idleTimer);
    if (wantAuto) idleTimer = setTimeout(() => (controls.autoRotate = true), IDLE_RESUME + 700);
  }

  function resize() {
    const { clientWidth: cw, clientHeight: ch } = container;
    renderer.setSize(cw, ch, false);
    camera.aspect = cw / ch;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  let raf = 0, lastNow = performance.now();
  (function loop(now) {
    raf = requestAnimationFrame(loop);
    const dt = Math.min(0.05, Math.max(0.001, (now - lastNow) / 1000)); lastNow = now;
    if (hold) stepHold(dt);
    if (tween) {
      const k = Math.min(1, (now - tween.t0) / tween.dur), e = 1 - Math.pow(1 - k, 3);
      const sph = new THREE.Spherical(tween.r, tween.phi0 + (tween.phi1 - tween.phi0) * e, tween.from + (tween.to - tween.from) * e);
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph));
      if (k >= 1) tween = null;
    }
    controls.update();
    renderer.render(scene, camera);
  })(performance.now());

  return {
    view,
    debugSpeed: () => item.hold?.maxSpeed(),
    debugHold: () => item.hold,
    // 偵錯用：目前看到的方位角（0 = 正面）
    debugAzimuth: () => hold ? hs.yaw : new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target)).theta,
    setAutoRotate(on) { wantAuto = on; controls.autoRotate = on && !hold; clearTimeout(idleTimer); hs.idleAt = 0; },
    dispose() {
      cancelAnimationFrame(raf); ro.disconnect(); controls.dispose();
      scene.traverse(o => { o.geometry?.dispose(); [].concat(o.material || []).forEach(m => m.dispose()); });
      item.textures.forEach(t => t.dispose());
      blobTex.dispose(); scene.background.dispose(); env.dispose(); renderer.dispose(); renderer.domElement.remove();
      THREE.ShaderChunk.shadowmap_pars_fragment = ORIGINAL_SHADOW_CHUNK;
    }
  };
}
