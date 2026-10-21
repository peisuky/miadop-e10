// Mi'adop 巡獵部落 E10 — 網站互動
// 資料來源：
//   data/products.json  商品、創作者文字（中英）
//   data/media.json     照片、影片清單（tools/build_assets.py 產生）
//   data/site.json      試算表 ID、GA、備份價格
//   Google 試算表        價格、販售狀態、公告、活動狀態（每 refreshSeconds 秒重新讀取）

const STR = {
  zh: {
    'nav.skip': '跳到商品', 'nav.creators': '創作者', 'nav.goods': '商品', 'nav.howto': '購買須知', 'nav.location': '攤位位置',
    'brand.tribe': '巡獵部落', 'hero.h1': "Mi'adop 巡獵部落・攤位 E10・2026 Infurnity 獸無限",
    'info.when': '開放時間', 'info.whenVal': '11/01（日）11:00–16:00', 'info.where': '地點', 'info.whereVal': '台中麗寶福容大飯店 LF 展演A廳',
    'cta.goods': '看商品', 'cta.map': '攤位位置',
    'intro.title': '荒土上的交易營地',
    'intro.body': "文明崩落之後，荒土上長出了新的森林。Mi'adop 巡獵部落在這裡生火、編織、交換物資——11 月 1 日，部落的營地就設在 E10。帶上你的故事，來換一件行囊吧。",
    'creators.title': '部落的成員', 'goods.title': '營地物資', 'goods.sub': '點商品可以看大圖；標示 3D 的商品可以拖曳旋轉。',
    'howto.title': '購買須知', 'howto.cash': '只收現金', 'howto.cashSub': '請準備零錢，感謝配合',
    'howto.one': '五位創作者一起結帳', 'howto.oneSub': '不同創作者的商品可以一次買單',
    'howto.limit': '不限購', 'howto.limitSub': '數量有限，售完為止',
    'howto.date': '僅 11/01（日）出攤', 'howto.dateSub': '11:00–16:00，其他天數不在場喔',
    'howto.gift': '消費送 Kenku 認親卡', 'howto.giftSub': '購買攤位上任一商品（不限創作者）就送一張，送完為止',
    'loc.title': '攤位位置', 'loc.sub': '展演A廳最上方的 E 排，左邊數來第 10 號。', 'loc.here': 'E10 在這裡', 'loc.full': '看完整會場地圖',
    'foot.copy': '所有作品著作權屬於各創作者：阿爾西、Kulas、Kenku、Peisuky、香酥雞白狗。', 'foot.ga': '本站使用 Google Analytics 統計瀏覽量。',
    roles: '巡獵部落的五種職分', rolesSub: '五款服裝，五種在荒土上活下去的方式',
    dealBadge: '套組優惠', age18: '🔞 限 18 歲以上購買',
    pick: '選擇款式', pickCount: n => `共 ${n} 款，點圖切換`,
    see: '看這位的商品 →', tba: '價格待公布', from: '起', variants: n => `${n} 款`,
    on: '販售中', sold: '完售', soon: '即將公開', partial: '部分完售', soonCard: '即將公開',
    hint3d: '拖曳旋轉・雙指縮放', hintHold: '拖曳甩甩看・上下拖可以前後晃', loading: '載入中…', close: '關閉',
    live: t => `價格與庫存即時同步（${t} 更新）`, offline: '暫時讀不到即時庫存，顯示的是備份資料',
    stateOn: '🔥 攤位營業中！歡迎來 E10 逛逛', stateEnd: '感謝光臨，我們下次見！',
    by: '創作者', new: 'NEW', gift: '贈品', giftBadge: '消費贈品'
  },
  en: {
    'nav.skip': 'Skip to goods', 'nav.creators': 'Creators', 'nav.goods': 'Goods', 'nav.howto': 'How to buy', 'nav.location': 'Location',
    'brand.tribe': 'HUNTING TRIBE', 'hero.h1': "Mi'adop Hunting Tribe · Booth E10 · Infurnity 2026",
    'info.when': 'OPEN', 'info.whenVal': 'Sun, Nov 1 · 11:00–16:00', 'info.where': 'VENUE', 'info.whereVal': 'Fullon Hotel Lihpao Taichung · LF Exhibition Hall A',
    'cta.goods': 'Browse goods', 'cta.map': 'Find the booth',
    'intro.title': 'A Trading Camp in the Wasteland',
    'intro.body': "After civilization fell, new forests grew over the wasteland. The Mi'adop Hunting Tribe lights its fires, weaves and trades here — on November 1st, the camp is pitched at booth E10. Bring your story and trade it for something to carry on the road.",
    'creators.title': 'Members of the Tribe', 'goods.title': 'Camp Supplies', 'goods.sub': 'Tap an item for photos. Items marked 3D can be rotated by dragging.',
    'howto.title': 'How to Buy', 'howto.cash': 'Cash only', 'howto.cashSub': 'Small bills and coins appreciated',
    'howto.one': 'One checkout for all five creators', 'howto.oneSub': 'Mix items from different creators in a single purchase',
    'howto.limit': 'No purchase limit', 'howto.limitSub': 'While stocks last',
    'howto.date': 'Open on Sun, Nov 1 only', 'howto.dateSub': '11:00–16:00 — we are not there on the other days',
    'howto.gift': 'Free Kenku meeting card', 'howto.giftSub': 'Buy anything at the booth (any creator) and get one, while supplies last',
    'loc.title': 'Booth Location', 'loc.sub': 'Top row E in Exhibition Hall A, 10th booth from the left.', 'loc.here': 'E10 is here', 'loc.full': 'Show the full floor map',
    'foot.copy': 'All artwork © their creators: Harcy, Kulas, Kenku, Peisuky and Whitedog.', 'foot.ga': 'This site uses Google Analytics to count visits.',
    roles: 'Five Roles of the Tribe', rolesSub: 'Five outfits, five ways to survive the wasteland',
    dealBadge: 'Bundle deal', age18: '🔞 18+ only — adults may purchase',
    pick: 'Choose a style', pickCount: n => `${n} styles — tap to switch`,
    see: 'See their goods →', tba: 'Price TBA', from: '+', variants: n => `${n} styles`,
    on: 'Available', sold: 'Sold out', soon: 'Coming soon', partial: 'Some sold out', soonCard: 'Coming soon',
    hint3d: 'Drag to rotate · pinch to zoom', hintHold: 'Drag to swing it · drag up/down to tilt', loading: 'Loading…', close: 'Close',
    live: t => `Prices & stock synced live (updated ${t})`, offline: 'Live stock unavailable — showing backup data',
    stateOn: '🔥 We are open! Come visit booth E10', stateEnd: 'Thanks for visiting — see you next time!',
    by: 'Creator', new: 'NEW', gift: 'Free gift', giftBadge: 'Free with purchase'
  }
};

// 語言：手動選過的優先，否則看瀏覽器語言（中文 → 繁中，其他 → 英文）
let lang = (navigator.language || '').toLowerCase().startsWith('zh') ? 'zh' : 'en';
try { const saved = localStorage.getItem('lang'); if (saved === 'zh' || saved === 'en') lang = saved; } catch {}
const t = (k, ...a) => { const v = STR[lang][k] ?? STR.zh[k] ?? k; return typeof v === 'function' ? v(...a) : v; };
const L = (o) => (o && (o[lang] ?? o.zh)) ?? '';
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v; else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
};

let DATA, MEDIA, SITE, SHEET = {}, sheetOk = false, sheetAt = null;

// ---------- 試算表 ----------
function parseCSV(text) {
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(cell); rows.push(row); row = []; cell = ''; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}
async function loadSheet() {
  if (!SITE.sheet) return;
  try {
    const url = `https://docs.google.com/spreadsheets/d/${SITE.sheet}/gviz/tq?tqx=out:csv&headers=1&t=${Date.now()}`;
    const res = await fetch(url, { cache: 'no-store' });
    const text = await res.text();
    if (!res.ok || text.trimStart().startsWith('<')) throw new Error('sheet not public');
    const rows = parseCSV(text), head = rows.shift().map(h => h.trim());
    const col = (name) => head.findIndex(h => h.startsWith(name));
    const iK = col('key'), iP = col('價格'), iS = col('狀態'), iZ = col('備註（中）'), iE = col('備註（英）');
    const next = {};
    for (const r of rows) {
      const k = (r[iK] || '').trim();
      if (!k || k.startsWith('#')) continue;
      next[k] = { price: (r[iP] || '').trim(), status: (r[iS] || '').trim(), note: { zh: (r[iZ] || '').trim(), en: (r[iE] || '').trim() } };
    }
    SHEET = next; sheetOk = true; sheetAt = new Date();
  } catch (e) {
    console.warn('試算表讀取失敗，改用備份資料：', e.message);
    if (!sheetOk) SHEET = SITE.fallback || {};
  }
}
const statusCode = (s) => s === '完售' || /^sold/i.test(s) ? 'sold' : s === '即將公開' || /^soon/i.test(s) ? 'soon' : 'on';
function info(key) {
  const r = SHEET[key] || (SITE.fallback || {})[key] || {};
  const n = parseInt(String(r.price || '').replace(/[^\d]/g, ''), 10);
  return { price: Number.isFinite(n) ? n : null, status: statusCode(r.status || ''), note: r.note || {} };
}
const keysOf = (p) => p.variants ? p.variants.map(v => `${p.id}/${v.id}`) : [p.sheetKey || p.id];   // sheetKey：試算表 key 和商品編號不同時用
function summary(p) {
  const all = keysOf(p).map(info), sts = all.map(i => i.status), prices = all.map(i => i.price).filter(x => x != null);
  const status = sts.every(s => s === 'sold') ? 'sold' : sts.every(s => s === 'soon') ? 'soon' : sts.some(s => s === 'sold') ? 'partial' : 'on';
  const min = prices.length ? Math.min(...prices) : null, varies = new Set(prices).size > 1;
  return { status, price: min, varies };
}
const giftText = () => el('span', { class: 'price gift' }, t('gift'));
const priceText = (n, varies) => n == null ? el('span', { class: 'price tba' }, t('tba')) : el('span', { class: 'price' }, `NT$ ${n}${varies ? ' ' + t('from') : ''}`);
const mediaOf = (p, v) => (v && MEDIA[`${p.id}/${v.id}`]) || MEDIA[p.id] || {};
const threeOf = (p, v) => (v && v.three) || p.three || null;

// ---------- 畫面 ----------
function applyStatic() {
  document.documentElement.lang = lang === 'zh' ? 'zh-Hant' : 'en';
  document.querySelectorAll('[data-i18n]').forEach(n => { n.textContent = t(n.dataset.i18n); });
  $('#mClose').setAttribute('aria-label', t('close'));
}

// Anton 沒有中文字，中文名字會退回細的 Noto Sans TC：改用 Noto Sans TC 的 900 粗體，和英文名字一樣粗
const cjkClass = (s) => /[㐀-鿿]/.test(s) ? 'cjk' : '';

function renderCreators() {
  const box = $('#creatorList'); box.replaceChildren();
  for (const b of DATA.brands) {
    const names = b.members.map(m => L(m.name)).join(' × ');
    const links = b.members.flatMap(m => m.links || []);
    box.append(el('a', { class: 'creator', href: `#brand-${b.id}` },
      el('div', { class: 'avatars' }, b.members.map(m => el('img', { src: m.avatar, alt: L(m.name), loading: 'lazy', width: 140, height: 150 }))),
      el('h3', { class: cjkClass(L(b.name)) }, b.logo ? el('img', { src: b.logo, alt: '' }) : null, L(b.name)),
      el('p', { class: 'tl' }, L(b.tagline)),
      b.members.length > 1 ? el('div', { class: 'who' }, names) : null,
      el('p', {}, L(b.blurb)),
      links.length ? el('div', { class: 'links' }, links.map(l => el('a', { href: l.url, target: '_blank', rel: 'noopener', onclick: e => e.stopPropagation() }, l.label))) : null,
      el('span', { class: 'go' }, t('see'))));
  }
}

function card(p) {
  const s = summary(p), v0 = p.variants?.[0], m = mediaOf(p, v0), cover = MEDIA[p.id]?.cover || m.photos?.[0];   // 有指定封面就用封面
  const has3d = p.three || p.variants?.some(v => v.three), hasVid = MEDIA[p.id]?.videos?.length;
  const badges = el('div', { class: 'badges' },
    p.isNew ? el('span', { class: 'badge new' }, t('new')) : null,
    p.age === '18' || p.variants?.some(v => v.age === '18') ? el('span', { class: 'badge r18' }, 'R-18') : null,   // 有任一款 18 禁就標
    p.deal ? el('span', { class: 'badge deal' }, t('dealBadge')) : null,
    p.gift ? el('span', { class: 'badge deal' }, t('gift')) : null,
    has3d ? el('span', { class: 'badge d3' }, '3D') : null,
    hasVid ? el('span', { class: 'badge vid' }, '▶ VIDEO') : null);
  const ph = cover
    ? el('div', { class: 'ph' }, el('img', { src: cover.thumb, alt: L(p.name), loading: 'lazy', width: 520, height: 650 }), badges)
    : el('div', { class: 'ph soon' }, el('span', {}, t('soonCard')), badges);
  if (s.status === 'sold') ph.append(el('div', { class: 'stamp' }, el('b', {}, t('sold'))));
  return el('button', { class: 'card', type: 'button', onclick: () => openProduct(p.id) },
    ph,
    el('h4', {}, L(p.name)),
    p.sub ? el('p', { class: 'sub' }, L(p.sub)) : null,
    el('div', { class: 'meta' },
      s.status === 'soon' ? el('span', { class: 'status soon' }, t('soon')) : p.gift ? giftText() : priceText(s.price, s.varies),
      s.status === 'partial' ? el('span', { class: 'status partial' }, t('partial')) : p.variants ? el('span', { class: 'count' }, t('variants', p.variants.length)) : null));
}

function renderGoods() {
  const box = $('#goodsList'); box.replaceChildren();
  for (const b of DATA.brands) {
    const items = DATA.products.filter(p => p.brand === b.id);
    const block = el('div', { class: 'brand-block', id: `brand-${b.id}` },
      el('div', { class: 'brand-head' },
        el('div', { class: 'bh-avatars' }, b.members.map(m => el('img', { src: m.avatar, alt: '', loading: 'lazy' }))),
        el('div', {}, el('h3', { class: cjkClass(L(b.name)) }, L(b.name)), el('p', {}, L(b.tagline)))));
    const outfits = items.filter(p => p.kind === 'outfit'), rest = items.filter(p => p.kind !== 'outfit');
    if (outfits.length) {
      block.append(el('div', { class: 'roles-head' }, el('h4', {}, t('roles')), el('span', {}, t('rolesSub'))),
        el('div', { class: 'grid' }, outfits.map(card)));
      if (rest.length) block.append(el('div', { style: 'height:18px' }));
    }
    if (rest.length) block.append(el('div', { class: 'grid' }, rest.map(card)));
    box.append(block);
  }
}

function renderMeta() {
  const ev = (SHEET['@活動狀態'] || {}).status || '';
  const st = $('#eventState');
  st.hidden = !/活動中|活動結束/.test(ev);
  st.textContent = ev.includes('活動中') ? t('stateOn') : ev.includes('活動結束') ? t('stateEnd') : '';
  const n = SHEET['@公告']?.note || {}, msg = n[lang] || n.zh || '';
  const notice = $('#notice'); notice.hidden = !msg; notice.textContent = msg;
  const fmt = (d) => `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  $('#sync').textContent = sheetOk ? t('live', fmt(sheetAt)) : t('offline');
}

function renderAll() { applyStatic(); renderCreators(); renderGoods(); renderMeta(); if (cur) fillInfo(); }

// ---------- 商品視窗 ----------
const modal = $('#modal');
let cur = null;        // { p, v, items, idx }
let viewer = null, viewerSeq = 0;
let pushedModal = false;   // 這次打開視窗時有沒有新增一筆瀏覽紀錄（直接開商品網址時沒有，關閉時就不能按「上一頁」）

function disposeViewer() { viewerSeq++; if (viewer) { viewer.dispose(); viewer = null; } }
// 停掉展示區裡的影片：dialog 關閉只是隱藏，影片不會自己停，聲音會繼續播
function stopMedia() {
  const stage = $('#mStage');
  stage.querySelectorAll('video').forEach(v => { v.pause(); v.removeAttribute('src'); v.load(); });
  stage.replaceChildren();
}

function openProduct(id, push = true) {
  const [pid, vid] = id.split('/');
  const p = DATA.products.find(x => x.id === pid); if (!p) return;
  const v = p.variants ? (p.variants.find(x => x.id === vid) || p.variants[0]) : null;
  cur = { p, v, idx: 0 };
  fillModal();
  if (!modal.open) modal.showModal();
  const hash = `#p=${p.id}${v ? '/' + v.id : ''}`;
  if (push && !modal.open) { history.pushState({ modal: true }, '', hash); pushedModal = true; }
  else history.replaceState(history.state, '', hash);
  gtagEvent('view_item', { item_id: p.id + (v ? '/' + v.id : '') });
}

// 換商品／換款式：媒體（3D、影片、照片）和文字都重畫
function fillModal() {
  const { p, v } = cur, m = mediaOf(p, v), three = threeOf(p, v);
  cur.items = [
    ...(three ? [{ type: '3d', src: three }] : []),
    ...((m.videos || []).map(x => ({ type: 'video', ...x }))),
    ...((m.photos || []).map(x => ({ type: 'img', ...x })))
  ];
  if (cur.idx >= cur.items.length) cur.idx = 0;
  fillInfo();
  renderThumbs(); showItem(cur.idx);
}

// 只更新文字（價格、狀態、語言）：試算表定時更新或切換語言時用，不打斷正在轉的 3D
function fillInfo() {
  const { p, v } = cur, b = DATA.brands.find(x => x.id === p.brand), key = v ? `${p.id}/${v.id}` : p.sheetKey || p.id, i = info(key);
  $('#mBrand').textContent = `${t('by')} ・ ${L(b.name)}`;
  $('#mName').textContent = L(p.name);
  $('#mSub').textContent = [L(p.sub), v ? L(v.name) : ''].filter(Boolean).join(' ・ ');
  // 款式選擇：標題寫明「選擇款式・共 N 款」，每款一張有縮圖的卡，選中的有紅框和勾勾
  const vb = $('#mVariants'); vb.replaceChildren();
  if (p.variants?.length) {
    const k = p.variants.indexOf(v) + 1;
    vb.append(el('p', { class: 'v-head' },
      el('b', {}, t('pick')), el('span', {}, t('pickCount', p.variants.length)), el('em', {}, `${k} / ${p.variants.length}`)));
    const row = el('div', { class: 'v-row', role: 'radiogroup', 'aria-label': t('pick') });
    for (const x of p.variants) {
      const sold = info(`${p.id}/${x.id}`).status === 'sold', ph = mediaOf(p, x).photos?.[0];
      row.append(el('button', { type: 'button', role: 'radio', 'aria-checked': String(x === v), class: 'v-card' + (sold ? ' sold' : ''),
        onclick: () => {
          if (x === cur.v) return;
          cur.v = x; cur.idx = 0; fillModal(); history.replaceState(history.state, '', `#p=${p.id}/${x.id}`);
          // 手機上款式區在畫面下方：切換後捲回上面，讓人看到換成哪一款
          if ($('#mStage').getBoundingClientRect().bottom < 80) modal.scrollTo({ top: 0, behavior: 'smooth' });
        } },
        el('span', { class: 'v-img' }, ph ? el('img', { src: ph.thumb, alt: '', loading: 'lazy' }) : null, sold ? el('i', {}, t('sold')) : null),
        el('span', { class: 'v-name' }, L(x.name))));
    }
    vb.append(row);
  }
  const pr = $('#mPrice'); pr.replaceChildren(i.status === 'soon' ? '' : p.gift ? giftText() : priceText(i.price));
  const st = $('#mStatus'); st.className = 'status ' + i.status; st.textContent = t(i.status);
  st.hidden = p.gift && i.status === 'on';   // 贈品不寫「販售中」，送完時試算表改完售才顯示
  $('#mLore').textContent = L(p.lore);
  $('#mDeal').hidden = !p.deal && !p.gift; $('#mDeal').replaceChildren(el('b', {}, t(p.gift ? 'giftBadge' : 'dealBadge')), L(p.gift || p.deal));
  $('#mAge').hidden = (v?.age || p.age) !== '18'; $('#mAge').textContent = t('age18');
  const specs = [...(L(p.specs) || []), ...(v ? L(v.specs) || [] : [])];
  $('#mSpecs').replaceChildren(...specs.map(s => el('li', {}, s)));
  const note = i.note?.[lang] || i.note?.zh || ''; $('#mNote').hidden = !note; $('#mNote').textContent = note;
  $('#mStage').querySelectorAll('[data-hint]').forEach(h => { h.textContent = t(h.dataset.hint); });
}

function renderThumbs() {
  const box = $('#mThumbs'); box.replaceChildren();
  box.hidden = cur.items.length < 2;
  cur.items.forEach((it, k) => {
    const sel = String(k === cur.idx);
    const btn = it.type === '3d' ? el('button', { type: 'button', class: 't3d', role: 'tab', 'aria-selected': sel, 'aria-label': '3D' }, '3D')
      : it.type === 'video' ? el('button', { type: 'button', class: 'tv', role: 'tab', 'aria-selected': sel, 'aria-label': 'video' }, el('img', { src: it.poster, alt: '' }))
      : el('button', { type: 'button', role: 'tab', 'aria-selected': sel, 'aria-label': `photo ${k + 1}` }, el('img', { src: it.thumb, alt: '', loading: 'lazy' }));
    btn.addEventListener('click', () => showItem(k));
    box.append(btn);
  });
}

async function showItem(k) {
  cur.idx = k;
  $('#mThumbs').querySelectorAll('button').forEach((b, j) => b.setAttribute('aria-selected', String(j === k)));
  const stage = $('#mStage'), it = cur.items[k];
  disposeViewer(); stopMedia(); stage.classList.remove('three');
  if (!it) { stage.append(el('div', { class: 'soon-big' }, t('soonCard'))); return; }
  // 讀取中：展示區正中間轉圈，圖片／影片／3D 讀好就拿掉
  const spin = el('div', { class: 'spin', role: 'status' }, el('i', {}), el('span', {}, t('loading')));
  const done = () => spin.remove();
  if (it.type === 'img') {
    const img = el('img', { src: it.src, alt: L(cur.p.name), width: it.w, height: it.h });
    img.addEventListener('load', done); img.addEventListener('error', done);
    stage.append(img, spin);
    if (img.complete && img.naturalWidth) done();
  } else if (it.type === 'video') {
    const vid = el('video', { src: it.src, poster: it.poster, autoplay: true, muted: true, loop: true, playsinline: true, controls: true });
    vid.addEventListener('loadeddata', done); vid.addEventListener('error', done);
    stage.append(vid, spin);
  } else {
    stage.classList.add('three');
    stage.append(spin);
    const seq = ++viewerSeq;
    try {
      const { createProductViewer } = await import('../viewer/product3d.js?v=20261021a');
      if (seq !== viewerSeq) return;
      const vw = await createProductViewer(stage, { src: it.src, background: 0xefe3c4 });
      if (seq !== viewerSeq) { vw.dispose(); return; }
      viewer = vw; done();
      const spec = await (await fetch(it.src)).json();
      const key = spec.type === 'keychain' ? 'hintHold' : 'hint3d';
      stage.append(el('span', { class: 'hint', 'data-hint': key }, t(key)));
    } catch (e) { console.error(e); if (seq === viewerSeq) stage.replaceChildren(el('div', { class: 'soon-big' }, '3D ✕')); }
  }
  stage.querySelector('video')?.play?.().catch(() => {});
}

// 手機左右滑換下一張（3D 例外：3D 要拿來拖曳旋轉）
(function swipe() {
  const stage = $('#mStage'); let x0 = null, y0 = 0;
  stage.addEventListener('touchstart', e => { if (cur?.items[cur.idx]?.type === '3d') return; x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
  stage.addEventListener('touchend', e => {
    if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0; x0 = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) showItem((cur.idx + (dx < 0 ? 1 : cur.items.length - 1)) % cur.items.length);
  });
})();

function closeModal(fromPop = false) {
  if (!modal.open) return;
  disposeViewer(); stopMedia(); modal.close(); cur = null;
  if (!fromPop && pushedModal) history.back();
  else if (!fromPop) history.replaceState(null, '', location.pathname + location.search);
  pushedModal = false;
}
$('#mClose').addEventListener('click', () => closeModal());
modal.addEventListener('cancel', e => { e.preventDefault(); closeModal(); });
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
window.addEventListener('popstate', () => {
  const m = location.hash.match(/^#p=(.+)$/);
  if (m) openProduct(decodeURIComponent(m[1]), false); else { pushedModal = false; closeModal(true); }
});

// ---------- 語言 ----------
$('#lang').addEventListener('click', () => {
  lang = lang === 'zh' ? 'en' : 'zh';
  try { localStorage.setItem('lang', lang); } catch {}
  renderAll();
});

// ---------- GA ----------
function gtagEvent(name, params) { if (window.gtag) window.gtag('event', name, params); }
function initGA(id) {
  if (!id) return;
  $('#gaNote').hidden = false;
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag('js', new Date()); window.gtag('config', id);
  document.head.append(el('script', { async: true, src: `https://www.googletagmanager.com/gtag/js?id=${id}` }));
}

// ---------- 啟動 ----------
(async function boot() {
  const j = (u) => fetch(u, { cache: 'no-cache' }).then(r => r.json());
  [DATA, MEDIA, SITE] = await Promise.all([j('data/products.json'), j('data/media.json'), j('data/site.json')]);
  DATA.products = DATA.products.filter(p => !p.hidden);   // hidden: true = 暫時下架（資料留著，改回 false 就恢復）
  SHEET = SITE.fallback || {};
  renderAll();                                  // 先用備份資料畫出來，不等試算表
  initGA(SITE.ga);
  await loadSheet(); renderAll();
  const m = location.hash.match(/^#p=(.+)$/);
  if (m) openProduct(decodeURIComponent(m[1]), false);
  setInterval(async () => { await loadSheet(); renderGoods(); renderMeta(); if (cur) fillInfo(); }, (SITE.refreshSeconds || 120) * 1000);
})();
