'use strict';
// 배출권 시세 상세(주식 차트 방식): KRX 일별 자료(/api/krx)를 받아 일·주·월 봉, 기간 설정, 차트 종류, 보조 지표를 제공합니다.
// 서버 API가 없으면(로컬·정적 시안) 기존 모의 보강 자료로 동작하며 화면에 그대로 표시합니다. 시장 자료는 영업일 종가 기준이며 실시간이 아닙니다.
(function () {
  const MKT = window.MKT; if (!MKT) return;
  const SER = MKT.series, isEn = () => window.I18N && I18N.lang === 'en', L = (ko, en) => isEn() ? en : ko;
  const n0 = v => Math.round(v).toLocaleString('en-US'), sg = v => v > 0 ? '+' : v < 0 ? '\u2212' : '';
  const avg = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0;
  const ST = MKT.ui = { itv: 'D', rng: '3M', type: 'candle', ind: { ma5: true, ma20: true, ma60: false, bb: false, vol: true }, from: '', to: '', code: 'KAU26', zoom: null, api: 'loading', asof: null, products: [] };
  const fmtD = s => s.replace(/\//g, '-');

  // ── 1) 자료 적재: 서버 API → SER 교체(제자리) ─────────────────────────────
  function ma(rows, n) { return rows.map((_, i) => i + 1 < n ? null : avg(rows.slice(i + 1 - n, i + 1).map(r => r.c))); }
  function adopt(rows) {
    const pos = x => x != null && x > 0 ? x : null;
    rows = rows.filter(r => r.c != null && r.c > 0).map(r => ({ ...r, o: pos(r.o) || r.c, h: pos(r.h) || Math.max(pos(r.o) || 0, r.c), l: pos(r.l) || Math.min(pos(r.o) || r.c, r.c) })); // 거래가 없던 날(시가·고가·저가 0)은 종가로 평평하게
    const out = rows.map((r, i, a) => ({ d: r.d.slice(0, 4) + '/' + r.d.slice(4, 6) + '/' + r.d.slice(6, 8), o: r.o, h: r.h, l: r.l, c: r.c, v: r.v || 0, chg: r.chg != null ? r.chg : (i ? r.c - a[i - 1].c : 0), rate: r.rt != null ? r.rt : (i && a[i - 1].c ? (r.c / a[i - 1].c - 1) * 100 : 0), real: true }));
    if (out.length < 5) return false;
    const m5 = ma(out, 5), m20 = ma(out, 20); out.forEach((x, i) => { x.m5 = m5[i]; x.m20 = m20[i]; });
    SER.length = 0; out.forEach(x => SER.push(x)); MKT.base = SER[SER.length - 1]; return true;
  }
  function load(code) {
    ST.api = 'loading';
    const d0 = new Date(Date.now() - 430 * 864e5), from = d0.getFullYear() + String(d0.getMonth() + 1).padStart(2, '0') + String(d0.getDate()).padStart(2, '0');
    return fetch('/api/krx/series?code=' + encodeURIComponent(code) + '&from=' + from, { cache: 'no-cache' }).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(j => {
      if (j.rows && adopt(j.rows)) { ST.api = 'live'; ST.state = j.state; ST.asof = j.asof; ST.code = code; ST.zoom = null; } else ST.api = 'none';
      afterLoad();
    }).catch(() => { ST.api = 'none'; afterLoad(); });
  }
  function afterLoad() { try { document.querySelectorAll('.mktile').forEach(t => t._upd && t._upd()); if (typeof rerender === 'function' && document.querySelector('#view .kxrow')) rerender(); } catch (e) { } }
  fetch('/api/krx/products', { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).then(j => { if (j && j.products) { ST.products = j.products; if (ST._render) ST._render(); } }).catch(() => { });
  load('KAU26');

  // ── 2) 집계(일→주→월), 기간, 지표 ────────────────────────────────────────
  const toDate = s => { const p = s.split('/'); return new Date(+p[0], +p[1] - 1, +p[2]); };
  const mondayKey = d => { const x = new Date(d); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x.getFullYear() + '/' + String(x.getMonth() + 1).padStart(2, '0') + '/' + String(x.getDate()).padStart(2, '0'); };
  function synth(rows) { // 시가·고가·저가가 없는 모의 구간은 종가에서 결정적으로 만든다
    return rows.map((r, i) => { if (r.o != null && r.h != null) return r; const p = i ? rows[i - 1].c : r.c, o = p, hi = Math.max(o, r.c) + 50 * ((i * 7) % 3), lo = Math.min(o, r.c) - 50 * ((i * 5) % 3); return { ...r, o, h: hi, l: lo }; });
  }
  function aggregate(rows, itv) {
    if (itv === 'D') return rows;
    const g = new Map();
    rows.forEach(r => { const k = itv === 'W' ? mondayKey(toDate(r.d)) : r.d.slice(0, 7) + '/01'; if (!g.has(k)) g.set(k, []); g.get(k).push(r); });
    const out = []; g.forEach((a, k) => { const c = a[a.length - 1].c, prev = out.length ? out[out.length - 1].c : a[0].o;
      out.push({ d: k, e: a[a.length - 1].d, o: a[0].o, h: Math.max(...a.map(x => x.h)), l: Math.min(...a.map(x => x.l)), c, v: a.reduce((s, x) => s + x.v, 0), chg: c - prev, rate: prev ? (c / prev - 1) * 100 : 0, real: a.every(x => x.real), n: a.length }); });
    return out;
  }
  const RNG = { '1W': 7, '1M': 31, '3M': 92, '6M': 183, '1Y': 366, ALL: 99999 };
  function pick() {
    let rows = synth(SER.map(r => ({ ...r }))); const last = toDate(rows[rows.length - 1].d);
    let from = ST.from ? new Date(ST.from) : (ST.rng === 'ALL' ? new Date(0) : new Date(last.getTime() - RNG[ST.rng] * 864e5)), to = ST.to ? new Date(ST.to + 'T23:59:59') : new Date(8e15);
    const full = aggregate(rows, ST.itv); // 지표는 전체 이력으로 계산한 뒤 보이는 구간만 자른다
    const m = n => { const a = full.map(r => r.c); return a.map((_, i) => i + 1 < n ? null : avg(a.slice(i + 1 - n, i + 1))); };
    const m5 = m(5), m20 = m(20), m60 = m(60), bu = [], bl = [];
    full.forEach((_, i) => { if (i < 19) { bu.push(null); bl.push(null); return; } const w = full.slice(i - 19, i + 1).map(r => r.c), mu = avg(w), sd = Math.sqrt(avg(w.map(x => (x - mu) ** 2))); bu.push(mu + 2 * sd); bl.push(mu - 2 * sd); });
    full.forEach((r, i) => { r.m5 = m5[i]; r.m20 = m20[i]; r.m60 = m60[i]; r.bu = bu[i]; r.bl = bl[i]; });
    let vis = full.filter(r => { const t = toDate(r.d); return t >= from && t <= to; }); if (vis.length < 2) vis = full.slice(-Math.min(full.length, 30));
    return { vis, all: full };
  }

  // ── 3) 차트 그리기 ─────────────────────────────────────────────────────────
  const E = (t, a, ...c) => { const e = document.createElementNS('http://www.w3.org/2000/svg', t); for (const k in a) e.setAttribute(k, a[k]); c.forEach(x => e.append(x)); return e; };
  function draw(box, tip, st) {
    const { vis } = pick(); let data = vis; if (ST.zoom) { const [a, b] = ST.zoom; data = vis.slice(Math.max(0, a), Math.min(vis.length, b)); if (data.length < 3) data = vis; }
    box.querySelectorAll('svg').forEach(s => s.remove());
    const W = Math.max(320, box.clientWidth), H = Math.max(260, box.clientHeight), n = data.length, L0 = 58, R0 = 16, PT = 12, vh = ST.ind.vol ? Math.round(H * .2) : 0, PB = H - 28 - vh - (vh ? 12 : 0), VT = PB + 14, VB = H - 24;
    const svg = E('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: 'mk-chart2', role: 'img', 'aria-label': L('배출권 시세 차트', 'Allowance price chart') });
    const keys = ['h', 'l']; let vals = data.flatMap(r => [r.h, r.l]); if (ST.ind.ma5) vals = vals.concat(data.map(r => r.m5)); if (ST.ind.ma20) vals = vals.concat(data.map(r => r.m20)); if (ST.ind.ma60) vals = vals.concat(data.map(r => r.m60)); if (ST.ind.bb) vals = vals.concat(data.map(r => r.bu), data.map(r => r.bl));
    vals = vals.filter(v => v != null); const mn0 = Math.min(...vals), mx0 = Math.max(...vals), pad = (mx0 - mn0) * .08 || 100, mn = mn0 - pad, mx = mx0 + pad;
    const X = i => L0 + (n === 1 ? 0 : (i + .5) * (W - L0 - R0) / n), Y = v => PT + (1 - (v - mn) / (mx - mn)) * (PB - PT), bw = Math.max(2, Math.min(18, (W - L0 - R0) / n * .62));
    const raw = (mx - mn) / 5, pw = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / pw, step = (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * pw;
    for (let v = Math.ceil(mn / step) * step; v <= mx; v += step) svg.append(E('line', { x1: L0, x2: W - R0, y1: Y(v), y2: Y(v), class: 'mk-grid' }), Object.assign(E('text', { x: L0 - 8, y: Y(v) + 4, class: 'mk-ax', 'text-anchor': 'end' }), { textContent: n0(v) }));
    const mock = data.findIndex(r => !r.real); const lastMock = data.map(r => r.real).lastIndexOf(false);
    if (lastMock >= 0) { svg.append(E('rect', { x: L0, y: PT, width: Math.max(0, X(lastMock) + (W - L0 - R0) / n / 2 - L0), height: PB - PT, class: 'mk-mock-bg' }), Object.assign(E('text', { x: L0 + 8, y: PT + 14, class: 'mk-ax mk-mocklbl' }), { textContent: L('모의 보강 구간(실제 아님)', 'Simulated filler (not actual)') })); }
    const path = (key, cls) => { const seg = []; let cur = []; data.forEach((r, i) => { if (r[key] == null) { if (cur.length) { seg.push(cur); cur = []; } } else cur.push(X(i).toFixed(1) + ',' + Y(r[key]).toFixed(1)); }); if (cur.length) seg.push(cur); seg.forEach(s => svg.append(E('polyline', { points: s.join(' '), class: cls }))); };
    if (ST.ind.bb) { const up = data.map((r, i) => r.bu == null ? null : X(i).toFixed(1) + ',' + Y(r.bu).toFixed(1)).filter(Boolean), lo = data.map((r, i) => r.bl == null ? null : X(i).toFixed(1) + ',' + Y(r.bl).toFixed(1)).filter(Boolean); if (up.length > 1) svg.append(E('polygon', { points: up.join(' ') + ' ' + lo.slice().reverse().join(' '), class: 'mk-bbfill' })); path('bu', 'mk-bb'); path('bl', 'mk-bb'); }
    if (ST.type === 'area') { const pts = data.map((r, i) => X(i).toFixed(1) + ',' + Y(r.c).toFixed(1)).join(' '); svg.append(E('polygon', { points: `${X(0)},${PB} ${pts} ${X(n - 1)},${PB}`, class: 'mk-area' })); }
    if (ST.type === 'candle') data.forEach((r, i) => { const up = r.c >= r.o, x = X(i); svg.append(E('line', { x1: x, x2: x, y1: Y(r.h), y2: Y(r.l), class: 'mk-wick ' + (up ? 'up' : 'dn') }), E('rect', { x: x - bw / 2, y: Math.min(Y(r.o), Y(r.c)), width: bw, height: Math.max(1.2, Math.abs(Y(r.o) - Y(r.c))), class: 'mk-body ' + (up ? 'up' : 'dn') + (r.real ? '' : ' mock'), rx: 1 })); });
    else path('c', 'mk-px2');
    if (ST.ind.ma60) path('m60', 'mk-ma60'); if (ST.ind.ma20) path('m20', 'mk-ma20'); if (ST.ind.ma5) path('m5', 'mk-ma5');
    if (vh) { const vmx = Math.max(...data.map(r => r.v)) || 1; svg.append(Object.assign(E('text', { x: L0 - 8, y: VT + 10, class: 'mk-ax', 'text-anchor': 'end' }), { textContent: L('거래량', 'Vol') }), E('line', { x1: L0, x2: W - R0, y1: VB, y2: VB, class: 'mk-grid' })); data.forEach((r, i) => { const bh = Math.max(1, (VB - VT) * r.v / vmx); svg.append(E('rect', { x: X(i) - bw / 2, y: VB - bh, width: bw, height: bh, rx: 1.5, class: 'mk-vol ' + (r.c >= r.o ? 'up' : 'dn') + (r.real ? '' : ' mock') })); }); }
    const lab = Math.max(1, Math.ceil(n / Math.max(3, Math.floor((W - L0) / 90))));
    data.forEach((r, i) => { if (i % lab === 0) svg.append(Object.assign(E('text', { x: X(i), y: H - 8, class: 'mk-ax', 'text-anchor': 'middle' }), { textContent: ST.itv === 'M' ? r.d.slice(2, 7).replace('/', '.') : r.d.slice(5).replace('/', '/') })); });
    const cross = E('g', { class: 'mk-cross', style: 'display:none' }, E('line', { y1: PT, y2: H - 24, class: 'mk-cl' }), E('line', { x1: L0, x2: W - R0, class: 'mk-cl mk-ch' })); svg.append(cross);
    const hit = E('rect', { x: L0, y: PT, width: W - L0 - R0, height: H - 24 - PT, fill: 'transparent', style: 'cursor:crosshair' }); svg.append(hit);
    const move = ev => { const rc = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - rc.left, py = (ev.touches ? ev.touches[0].clientY : ev.clientY) - rc.top, i = Math.max(0, Math.min(n - 1, Math.floor((px / rc.width * W - L0) / ((W - L0 - R0) / n)))), r = data[i];
      cross.style.display = ''; const x = X(i); cross.children[0].setAttribute('x1', x); cross.children[0].setAttribute('x2', x); cross.children[1].setAttribute('y1', py / rc.height * H); cross.children[1].setAttribute('y2', py / rc.height * H);
      tip.style.display = ''; const up = r.c >= r.o; tip.innerHTML = `<b>${fmtD(r.d)}${ST.itv !== 'D' ? ' ~ ' + fmtD(r.e || r.d).slice(5) : ''}</b><div>${L('시가', 'O')} ${n0(r.o)} · ${L('고가', 'H')} ${n0(r.h)}</div><div>${L('저가', 'L')} ${n0(r.l)} · <span class="${up ? 'tu' : 'td'}">${L('종가', 'C')} ${n0(r.c)}</span></div><div>${L('대비', 'Chg')} ${sg(r.chg)}${n0(Math.abs(r.chg))} (${sg(r.rate)}${Math.abs(r.rate).toFixed(2)}%)</div><div>${L('거래량', 'Vol')} ${n0(r.v)}</div>${r.m5 ? `<div class="mu">MA5 ${n0(r.m5)}${r.m20 ? ' · MA20 ' + n0(r.m20) : ''}</div>` : ''}${r.real ? '' : '<div class="mu">' + L('모의 보강(실제 아님)', 'Simulated') + '</div>'}`;
      tip.style.left = Math.min(Math.max(x / W * 100, 16), 82) + '%'; tip.style.top = '8px'; };
    hit.addEventListener('mousemove', move); hit.addEventListener('touchmove', move, { passive: true }); hit.addEventListener('mouseleave', () => { cross.style.display = 'none'; tip.style.display = 'none'; });
    hit.addEventListener('wheel', ev => { ev.preventDefault(); const base = vis.length, cur = ST.zoom || [0, base], span = cur[1] - cur[0], ns = Math.max(8, Math.min(base, Math.round(span * (ev.deltaY > 0 ? 1.2 : .83)))), rc = svg.getBoundingClientRect(), ratio = Math.min(1, Math.max(0, (ev.clientX - rc.left) / rc.width)), a = Math.max(0, Math.min(base - ns, Math.round(cur[0] + (span - ns) * ratio))); ST.zoom = ns >= base ? null : [a, a + ns]; st(); }, { passive: false });
    let drag = null; hit.addEventListener('mousedown', ev => { drag = { x: ev.clientX, z: ST.zoom || [0, vis.length] }; }); window.addEventListener('mouseup', () => { drag = null; });
    hit.addEventListener('mousemove', ev => { if (!drag || !ST.zoom) return; const rc = svg.getBoundingClientRect(), per = rc.width / (drag.z[1] - drag.z[0]), dx = Math.round((drag.x - ev.clientX) / per), a = Math.max(0, Math.min(vis.length - (drag.z[1] - drag.z[0]), drag.z[0] + dx)); ST.zoom = [a, a + (drag.z[1] - drag.z[0])]; st(true); });
    box.prepend(svg); return data;
  }

  // ── 4) 화면(컨트롤 + 차트 + 요약) ────────────────────────────────────────
  function ui() {
    const root = document.createElement('div'); root.className = 'mk2ui';
    const bar = document.createElement('div'); bar.className = 'mk2bar';
    const grp = (label, items, cur, on) => { const g = document.createElement('div'); g.className = 'mk2g'; const l = document.createElement('span'); l.className = 'mk2l'; l.textContent = label; g.append(l); const s = document.createElement('div'); s.className = 'seg mk2seg'; items.forEach(([k, t]) => { const b = document.createElement('button'); b.type = 'button'; b.dataset.own = 1; b.textContent = t; if (k === cur) b.classList.add('on'); b.addEventListener('click', () => on(k)); s.append(b); }); g.append(s); return g; };
    const box = document.createElement('div'); box.className = 'mk2chart'; const tip = document.createElement('div'); tip.className = 'mk-tip'; tip.style.display = 'none'; box.append(tip);
    const stats = document.createElement('div'); stats.className = 'mk2stats'; const foot = document.createElement('div'); foot.className = 'mk2foot';
    let ro = null;
    function render(light) {
      bar.replaceChildren();
      bar.append(grp(L('봉 단위', 'Interval'), [['D', L('일', 'Day')], ['W', L('주', 'Week')], ['M', L('월', 'Month')]], ST.itv, k => { ST.itv = k; ST.zoom = null; render(); }));
      bar.append(grp(L('기간', 'Range'), Object.keys(RNG).map(k => [k, k === 'ALL' ? L('전체', 'All') : k.replace('W', L('주', 'W')).replace('M', L('개월', 'M')).replace('Y', L('년', 'Y'))]), ST.from || ST.to ? '' : ST.rng, k => { ST.rng = k; ST.from = ST.to = ''; ST.zoom = null; render(); }));
      const dg = document.createElement('div'); dg.className = 'mk2g'; const dl = document.createElement('span'); dl.className = 'mk2l'; dl.textContent = L('직접 설정', 'Custom'); const di = (v, cb) => { const i = document.createElement('input'); i.type = 'date'; i.value = v; i.dataset.own = 1; i.addEventListener('change', () => { cb(i.value); ST.zoom = null; render(); }); return i; };
      const mid = document.createElement('span'); mid.textContent = '~'; dg.append(dl, di(ST.from, v => ST.from = v), mid, di(ST.to, v => ST.to = v)); bar.append(dg);
      bar.append(grp(L('차트', 'Chart'), [['candle', L('캔들', 'Candle')], ['line', L('선', 'Line')], ['area', L('면', 'Area')]], ST.type, k => { ST.type = k; render(); }));
      const ig = document.createElement('div'); ig.className = 'mk2g'; const il = document.createElement('span'); il.className = 'mk2l'; il.textContent = L('지표', 'Indicators'); ig.append(il);
      [['ma5', L('5일', 'MA5')], ['ma20', L('20일', 'MA20')], ['ma60', L('60일', 'MA60')], ['bb', L('볼린저', 'Bollinger')], ['vol', L('거래량', 'Volume')]].forEach(([k, t]) => { const b = document.createElement('button'); b.type = 'button'; b.dataset.own = 1; b.className = 'mk2chip' + (ST.ind[k] ? ' on' : ''); b.textContent = t; b.setAttribute('aria-pressed', !!ST.ind[k]); b.addEventListener('click', () => { ST.ind[k] = !ST.ind[k]; render(); }); ig.append(b); }); bar.append(ig);
      if (ST.products.length > 1) { const pg = document.createElement('div'); pg.className = 'mk2g'; const pl = document.createElement('span'); pl.className = 'mk2l'; pl.textContent = L('종목', 'Product'); const sel = document.createElement('select'); sel.dataset.own = 1; ST.products.slice(0, 19).forEach(p => { const o = document.createElement('option'); o.value = p.code; o.textContent = p.code; if (p.code === ST.code) o.selected = true; sel.append(o); }); sel.addEventListener('change', () => load(sel.value).then(() => { if (typeof rerender === 'function') rerender(); })); pg.append(pl, sel); bar.append(pg); }
      const rs = document.createElement('button'); rs.type = 'button'; rs.dataset.own = 1; rs.className = 'mk2reset'; rs.textContent = L('초기화', 'Reset'); rs.addEventListener('click', () => { Object.assign(ST, { itv: 'D', rng: '3M', type: 'candle', from: '', to: '', zoom: null, ind: { ma5: true, ma20: true, ma60: false, bb: false, vol: true } }); render(); }); bar.append(rs);
      paint();
    }
    function paint() {
      const data = draw(box, tip, (keep) => { if (keep) paint(); else render(); }); if (!data || !data.length) return;
      const hi = Math.max(...data.map(r => r.h)), lo = Math.min(...data.map(r => r.l)), first = data[0], last = data[data.length - 1], chgp = (last.c / first.o - 1) * 100, vsum = data.reduce((s, r) => s + r.v, 0);
      stats.replaceChildren(...[[L('기간 고가', 'High'), n0(hi)], [L('기간 저가', 'Low'), n0(lo)], [L('기간 등락', 'Change'), sg(chgp) + Math.abs(chgp).toFixed(2) + '%'], [L('평균 거래량', 'Avg vol'), n0(vsum / data.length)], [L('봉 수', 'Bars'), data.length + (ST.itv === 'D' ? L('일', 'd') : ST.itv === 'W' ? L('주', 'w') : L('개월', 'm'))]].map(([k, v]) => { const d = document.createElement('div'); d.className = 'mk2s'; d.innerHTML = '<span></span><b></b>'; d.firstChild.textContent = k; d.lastChild.textContent = v; return d; }));
      const real = ST.api === 'live';
      foot.textContent = real ? L('출처: KRX Data Marketplace OPEN API · 배출권 시장 일별매매정보(' + ST.code + ') · 기준일 ' + (ST.asof || '').replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3') + ' · 영업일 다음 날 오후 갱신, 실시간 아님 · 마우스 휠로 확대·축소, 끌어서 이동', 'Source: KRX Data Marketplace OPEN API (ETS daily trading, ' + ST.code + ') as of ' + (ST.asof || '') + ' · updated next business day afternoon, not real-time · wheel to zoom, drag to pan')
        : ST.api === 'loading' ? L('KRX 자료를 불러오는 중…', 'Loading KRX data…') : L('서버 연결이 없어 기존 시안 자료(최근 5거래일 실제 + 모의 보강)로 표시합니다.', 'No server connection: showing the draft data (last 5 sessions actual + simulated filler).');
    }
    ST._render = () => { if (root.isConnected) render(); };
    root.append(bar, box, stats, foot);
    ro = new ResizeObserver(() => { if (root.isConnected) paint(); }); ro.observe(box);
    render(); return root;
  }
  const origSection = MKT.section;
  MKT.section = function () { const box = origSection(); const left = box.querySelector('.mk-left'); if (left) { left.replaceChildren(ui()); box.classList.add('mk2'); } return box; };

  // ── 5) 한 화면에 맞춤(스크롤 없음) ────────────────────────────────────────
  function fit() {
    const c = document.querySelector('.mkcard.mk2'); if (!c) return;
    const top = c.getBoundingClientRect().top + window.scrollY, h = Math.max(520, window.innerHeight - top - 18);
    c.style.height = h + 'px';
  }
  const prevAfter = window.afterGo; window.afterGo = function (k) { if (prevAfter) prevAfter.apply(this, arguments); fit(); requestAnimationFrame(fit); setTimeout(fit, 200); };
  window.addEventListener('resize', fit);
})();
