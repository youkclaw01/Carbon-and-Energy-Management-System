'use strict';
// 배출권 시세(KAU26): 상단 작은 박스 + 클릭 시 상세 차트·AI 분석 패널.
// 데이터 출처: KRX 배출권시장 정보플랫폼(ets.krx.co.kr) 2026-10-28 조회 시 공개된 최근 5거래일 종가표. 일 1회 마감 값이며 실시간이 아닙니다.
// 5거래일 이전 구간은 상세 차트용 모의 보강(실제 아님)이며 화면에서 점선·표식으로 구분합니다.
// 실시간 연결 시 MKT.feed 어댑터(아래 setLive)만 교체하면 됩니다. "모의 실시간"은 화면 동작 확인용 시뮬레이션입니다.
(function () {
  const REAL = [ // 날짜, 종가(원/톤), 대비, 등락률(%), 거래량(톤)
    ['2026/10/22', 30250, 100, 0.33, 153337], ['2026/10/23', 29800, -450, -1.49, 254200], ['2026/10/26', 29950, 150, 0.50, 50000],
    ['2026/10/27', 30250, 300, 1.00, 98200], ['2026/10/28', 30250, 0, 0.00, 70100]];
  const isEn = () => window.I18N && I18N.lang === 'en';
  const L = (ko, en) => isEn() ? en : ko;
  const n0 = v => Math.round(v).toLocaleString('en-US'), n1 = v => (+v).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }), n2 = v => (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const sum = a => a.reduce((s, v) => s + v, 0), avg = a => a.length ? sum(a) / a.length : 0;
  const sign = v => v > 0 ? '+' : v < 0 ? '−' : '';
  const dirCls = v => v > 0 ? 'up' : v < 0 ? 'dn' : 'eq', arrow = v => v > 0 ? '▲' : v < 0 ? '▼' : '–';

  // ── 데이터 구성 ────────────────────────────────────────────
  function mulberry(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function build() {
    const rnd = mulberry(20261028), gauss = () => { let u = 0; for (let i = 0; i < 6; i++) u += rnd(); return (u - 3) / .7071; };
    const hist = []; let d = new Date(Date.UTC(2026, 9, 21)), p = 30150;
    for (let k = 0; k < 90; k++) {
      while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d = new Date(d.getTime() - 864e5);
      const ds = d.getUTCFullYear() + '/' + String(d.getUTCMonth() + 1).padStart(2, '0') + '/' + String(d.getUTCDate()).padStart(2, '0');
      hist.push({ d: ds, c: Math.round(p / 50) * 50, v: Math.round(70000 + rnd() * 150000), real: false });
      const ret = gauss() * .0115 + (p > 33000 ? .004 : p < 26500 ? -.004 : 0); p = Math.min(35500, Math.max(25000, p / (1 + ret))); d = new Date(d.getTime() - 864e5);
    }
    hist.reverse();
    const all = hist.concat(REAL.map(r => ({ d: r[0], c: r[1], chg: r[2], rate: r[3], v: r[4], real: true })));
    for (let i = 0; i < all.length; i++) { if (all[i].chg == null) { const pr = i ? all[i - 1].c : all[i].c; all[i].chg = all[i].c - pr; all[i].rate = pr ? (all[i].c / pr - 1) * 100 : 0; } }
    const ma = n => all.map((_, i) => i + 1 < n ? null : avg(all.slice(i + 1 - n, i + 1).map(x => x.c)));
    all.forEach((x, i) => { x.m5 = ma(5)[i]; x.m20 = ma(20)[i]; });
    return all;
  }
  const SER = build();
  const MKT = window.MKT = { series: SER, live: false, tick: 0, base: SER[SER.length - 1], timer: null };
  const cur = () => {
    const last = MKT.base, prev = SER[SER.length - 2];
    if (!MKT.live) return { c: last.c, chg: last.chg, rate: last.rate, v: last.v, d: last.d, live: false };
    const c = MKT.price; return { c, chg: c - prev.c, rate: (c / prev.c - 1) * 100, v: last.v + MKT.tickVol, d: last.d, live: true };
  };

  // ── 작은 그래프(스파크라인) ───────────────────────────────
  function spark(vals, w, h0, cls) {
    const mn = Math.min(...vals), mx = Math.max(...vals), pad = 3, X = i => pad + i * (w - 2 * pad) / Math.max(1, vals.length - 1), Y = v => mx === mn ? h0 / 2 : pad + (1 - (v - mn) / (mx - mn)) * (h0 - 2 * pad);
    const pts = vals.map((v, i) => X(i).toFixed(1) + ',' + Y(v).toFixed(1)), up = vals[vals.length - 1] >= vals[0];
    const svg = sv('svg', { viewBox: `0 0 ${w} ${h0}`, class: 'mk-spark ' + (cls || '') + (up ? ' up' : ' dn'), preserveAspectRatio: 'none', 'aria-hidden': 'true' });
    svg.append(sv('polygon', { points: `${X(0)},${h0} ${pts.join(' ')} ${X(vals.length - 1)},${h0}`, class: 'sp-area' }), sv('polyline', { points: pts.join(' '), class: 'sp-line' }));
    svg.append(sv('circle', { cx: X(vals.length - 1), cy: Y(vals[vals.length - 1]), r: 3, class: 'sp-dot' }));
    return svg;
  }

  // ── 상단 박스 ─────────────────────────────────────────────
  function tile() {
    const x = cur(), last5 = SER.slice(-5);
    const priceEl = h('span', { class: 'num mk-px ' + dirCls(x.chg) }, n0(x.c)), chgEl = h('span', { class: 'mk-chg ' + dirCls(x.chg) }, `${arrow(x.chg)} ${n0(Math.abs(x.chg))} (${sign(x.rate)}${Math.abs(x.rate).toFixed(2)}%)`);
    const stEl = h('span', { class: 'mk-st' + (x.live ? ' live' : '') }, h('i', { class: 'mk-dot' }), x.live ? L('모의 실시간 · 시뮬레이션', 'Simulated live · demo') : L('종가 · 일 1회 · 실시간 아님', 'Daily close · not real-time'));
    const sel = S.kpi === 'mk', c = h('div', { class: 'card kx tn-mk mktile' + (sel ? ' sel' : ''), tabindex: 0, role: 'button', 'aria-pressed': sel, 'aria-label': L('배출권 시세 상세 열기', 'Open emission allowance price detail'), 'data-mk': 1 },
      h('div', { class: 's' }, h('span', { class: 'ic', html: (window.ico ? ico('&#128200;') : '') }), L('배출권 시세', 'Allowance price'), ' ', h('span', { class: 'tag' }, 'KAU26'), h('span', { class: 'chev' + (sel ? ' open' : ''), 'aria-hidden': 'true' })),
      h('div', { class: 'v' }, priceEl, h('span', { class: 'u' }, ' ' + L('원/톤', 'KRW/t'))), h('div', { class: 's sub' }, chgEl, ' ', stEl),
      h('div', { class: 'mk-sp' }, spark(last5.map(r => r.c), 120, 34), h('span', { class: 'mut small' }, L('최근 5거래일', 'Last 5 sessions'))),
      h('div', { class: 'gt mut' }, L('KRX 배출권시장 · ' + x.d.slice(5) + ' · 누르면 상세 차트·AI 분석', 'KRX ETS · ' + x.d.slice(5) + ' · click for chart & AI analysis')));
    const open = () => { S.kpi = S.kpi === 'mk' ? null : 'mk'; S.plSel = false; S.rv = null; S.fc = null; rerender(); }; c.addEventListener('click', open); c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    c._upd = () => { const y = cur(); const prevTxt = priceEl.textContent; priceEl.textContent = n0(y.c); priceEl.className = 'num mk-px ' + dirCls(y.chg); chgEl.className = 'mk-chg ' + dirCls(y.chg); chgEl.textContent = `${arrow(y.chg)} ${n0(Math.abs(y.chg))} (${sign(y.rate)}${Math.abs(y.rate).toFixed(2)}%)`; stEl.className = 'mk-st' + (y.live ? ' live' : ''); stEl.lastChild.textContent = y.live ? L('모의 실시간 · 시뮬레이션', 'Simulated live · demo') : L('종가 · 일 1회 · 실시간 아님', 'Daily close · not real-time'); if (prevTxt !== priceEl.textContent) flash(priceEl, y.chg); };
    return c;
  }
  function flash(el, chg) { el.classList.remove('flash-up', 'flash-dn'); void el.offsetWidth; el.classList.add(chg >= 0 ? 'flash-up' : 'flash-dn'); }

  // ── 상세 패널 ─────────────────────────────────────────────
  const RANGES = [['5d', 5, '5일', '5D'], ['1m', 22, '1개월', '1M'], ['3m', 66, '3개월', '3M']];
  let panel = null, range = '1m';
  function chart(data, hover) {
    const W = 760, H = 360, L0 = 54, R0 = 14, PT = 14, PB = 252, VT = 272, VB = 328, n = data.length;
    const vals = data.flatMap(r => [r.c, r.m5, r.m20].filter(v => v != null)), mn0 = Math.min(...vals), mx0 = Math.max(...vals), pad = (mx0 - mn0) * .12 || 200, mn = Math.floor((mn0 - pad) / 100) * 100, mx = Math.ceil((mx0 + pad) / 100) * 100;
    const X = i => L0 + (n === 1 ? 0 : i * (W - L0 - R0) / (n - 1)), Y = v => PT + (1 - (v - mn) / (mx - mn)) * (PB - PT), vmx = Math.max(...data.map(r => r.v)) || 1, bw = Math.max(2, Math.min(18, (W - L0 - R0) / n * .62));
    const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, class: 'mk-chart', role: 'img', 'aria-label': L('배출권 KAU26 종가 추이 차트', 'KAU26 closing price chart') });
    const defs = sv('defs', {}, sv('linearGradient', { id: 'mkg', x1: 0, y1: 0, x2: 0, y2: 1 }, sv('stop', { offset: '0', 'stop-color': 'var(--cy)', 'stop-opacity': '.28' }), sv('stop', { offset: '1', 'stop-color': 'var(--cy)', 'stop-opacity': '0' }))); svg.append(defs);
    const step = (() => { const raw = (mx - mn) / 5, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; })();
    for (let v = Math.ceil(mn / step) * step; v <= mx; v += step) svg.append(sv('line', { x1: L0, x2: W - R0, y1: Y(v), y2: Y(v), class: 'mk-grid' }), sv('text', { x: L0 - 8, y: Y(v) + 4, class: 'mk-ax', 'text-anchor': 'end' }, n0(v)));
    // 실제/모의 구분 배경
    const fr = data.findIndex(r => r.real); if (fr > 0) svg.append(sv('rect', { x: L0, y: PT, width: X(fr) - L0 - ((W - L0 - R0) / Math.max(1, n - 1)) / 2, height: PB - PT, class: 'mk-mock-bg' }), sv('text', { x: L0 + 8, y: PT + 14, class: 'mk-ax mk-mocklbl' }, L('모의 보강 구간(실제 아님)', 'Simulated history (not real)')));
    const line = (key, cls) => { const pts = data.map((r, i) => r[key] == null ? null : [X(i), Y(r[key])]); const segs = []; let curp = []; pts.forEach(q => { if (q) curp.push(q); else if (curp.length) { segs.push(curp); curp = []; } }); if (curp.length) segs.push(curp); segs.forEach(sg => svg.append(sv('polyline', { points: sg.map(q => q[0].toFixed(1) + ',' + q[1].toFixed(1)).join(' '), class: cls }))); };
    const areaPts = data.map((r, i) => X(i).toFixed(1) + ',' + Y(r.c).toFixed(1)).join(' ');
    svg.append(sv('polygon', { points: `${X(0)},${PB} ${areaPts} ${X(n - 1)},${PB}`, fill: 'url(#mkg)' }));
    line('m20', 'mk-ma20'); line('m5', 'mk-ma5');
    // 종가선: 모의 구간은 점선, 실제 구간은 실선
    const mockIdx = data.map((r, i) => r.real ? -1 : i).filter(i => i >= 0), realStart = fr < 0 ? n : fr;
    if (realStart > 0) { const e = Math.min(n - 1, realStart); svg.append(sv('polyline', { points: data.slice(0, e + 1).map((r, i) => X(i).toFixed(1) + ',' + Y(r.c).toFixed(1)).join(' '), class: 'mk-px-mock' })); }
    if (realStart < n) { const s = Math.max(0, realStart); svg.append(sv('polyline', { points: data.slice(s).map((r, i) => X(s + i).toFixed(1) + ',' + Y(r.c).toFixed(1)).join(' '), class: 'mk-px-real' })); data.forEach((r, i) => { if (r.real) svg.append(sv('circle', { cx: X(i), cy: Y(r.c), r: 3.6, class: 'mk-pt-real' })); }); }
    // 거래량
    svg.append(sv('line', { x1: L0, x2: W - R0, y1: VB, y2: VB, class: 'mk-grid' }), sv('text', { x: L0 - 8, y: VT + 10, class: 'mk-ax', 'text-anchor': 'end' }, L('거래량', 'Vol')));
    data.forEach((r, i) => { const bh = Math.max(1, (VB - VT) * r.v / vmx), up = r.chg >= 0; svg.append(sv('rect', { x: X(i) - bw / 2, y: VB - bh, width: bw, height: bh, rx: 1.5, class: 'mk-vol ' + (r.real ? '' : 'mock ') + (up ? 'up' : 'dn') })); });
    // x축 라벨
    const lab = Math.max(1, Math.ceil(n / 6)); data.forEach((r, i) => { if (i % lab === 0 || i === n - 1) { if (i === n - 1 && i % lab !== 0 && (n - 1 - (i - i % lab)) < lab * .6) return; svg.append(sv('text', { x: X(i), y: VB + 16, class: 'mk-ax', 'text-anchor': i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle' }, r.d.slice(5))); } });
    // 호버 십자선
    const cross = sv('g', { class: 'mk-cross', style: 'display:none' }, sv('line', { y1: PT, y2: VB, class: 'mk-cl' }), sv('circle', { r: 4.5, class: 'mk-cd' })); svg.append(cross);
    const hit = sv('rect', { x: L0, y: PT, width: W - L0 - R0, height: VB - PT, fill: 'transparent', style: 'cursor:crosshair' }); svg.append(hit);
    const move = ev => { const r = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left, vx = px / r.width * W, i = Math.max(0, Math.min(n - 1, Math.round((vx - L0) / ((W - L0 - R0) / Math.max(1, n - 1))))); cross.style.display = ''; cross.querySelector('line').setAttribute('x1', X(i)); cross.querySelector('line').setAttribute('x2', X(i)); const cd = cross.querySelector('circle'); cd.setAttribute('cx', X(i)); cd.setAttribute('cy', Y(data[i].c)); hover(data[i], X(i) / W, Y(data[i].c) / H); };
    hit.addEventListener('mousemove', move); hit.addEventListener('touchmove', move, { passive: true }); hit.addEventListener('touchstart', move, { passive: true }); hit.addEventListener('mouseleave', () => { cross.style.display = 'none'; hover(null); });
    return svg;
  }

  // ── 영향 계산·AI 분석(모의 대본: 화면 값에서 규칙으로 생성) ───────────
  const synth = () => SER.some(r => r.real === false);
  function impact() {
    let kr = 0; try { kr = sum(D.P.filter(p => p.c === '한국').map(p => D.em(p.id, 0, D.TODAY))); } catch (e) { kr = 21647.9; }
    const px = cur().c, cost = kr * px / 1e8; return { kr, px, cost, d10: cost * .1 };
  }
  function analysis(data) {
    const x = cur(), last = SER[SER.length - 1], r5 = SER.slice(-5), hi5 = Math.max(...r5.map(r => r.c)), lo5 = Math.min(...r5.map(r => r.c)), spread = (hi5 - lo5) / lo5 * 100;
    const m5 = last.m5, m20 = last.m20, vAvg = avg(r5.map(r => r.v)), vr = last.v / vAvg * 100, upDays = r5.filter(r => r.chg > 0).length, dnDays = r5.filter(r => r.chg < 0).length, im = impact();
    const pos5 = x.c >= m5 ? L('5일 평균(' + n0(m5) + '원) 이상', 'at/above the 5-day average (' + n0(m5) + ')') : L('5일 평균(' + n0(m5) + '원) 아래', 'below the 5-day average (' + n0(m5) + ')');
    const bullets = [
      [L('가격 위치', 'Price position'), L(`현재가 ${n0(x.c)}원은 ${pos5}이며, 20일 평균(${n0(m20)}원${synth() ? ', 모의 보강 포함' : ''}) 대비 ${sign(x.c - m20)}${Math.abs((x.c / m20 - 1) * 100).toFixed(1)}%입니다.`, `Current ${n0(x.c)} KRW is ${pos5}; ${sign(x.c - m20)}${Math.abs((x.c / m20 - 1) * 100).toFixed(1)}% vs the 20-day average (${n0(m20)}${synth() ? ', includes simulated history' : ''}).`)],
      [L('최근 5거래일(KRX 실제)', 'Last 5 sessions (KRX actual)'), L(`${n0(lo5)}~${n0(hi5)}원, 변동폭 ${spread.toFixed(1)}%로 좁은 구간입니다. 상승 ${upDays}일 · 하락 ${dnDays}일 · 보합 ${5 - upDays - dnDays}일입니다.`, `Range ${n0(lo5)}–${n0(hi5)} KRW (${spread.toFixed(1)}% spread): ${upDays} up, ${dnDays} down, ${5 - upDays - dnDays} flat.`)],
      [L('거래량', 'Volume'), L(`${last.d.slice(5)} 거래량 ${n0(last.v)}톤은 5일 평균(${n0(vAvg)}톤)의 ${vr.toFixed(0)}% 수준입니다. ${vr < 70 ? '거래가 한산해 가격 신뢰도가 낮을 수 있습니다.' : '거래는 평소 수준입니다.'}`, `${last.d.slice(5)} volume ${n0(last.v)} t is ${vr.toFixed(0)}% of the 5-day average (${n0(vAvg)} t). ${vr < 70 ? 'Thin trading may weaken price reliability.' : 'Trading is at a normal level.'}`)],
      [L('우리 사업장 영향(추정)', 'Impact on our sites (estimate)'), L(`한국 사업장 올해 누적 배출 ${n1(im.kr)} tCO₂를 현재가로 환산하면 약 ${n2(im.cost)}억 원이며, 가격이 ±10% 움직이면 ±${n2(im.d10)}억 원 변동합니다. 무상할당·이월 등 실제 부족분은 반영하지 않은 상한 환산입니다.`, `At the current price, Korean-site YTD emissions of ${n1(im.kr)} tCO₂ equal about KRW ${n2(im.cost)} 100M; a ±10% price move changes this by ±${n2(im.d10)} 100M. Upper-bound conversion: free allocation and carry-over are not reflected.`)]
    ];
    return { bullets, im, spread, vr };
  }
  const QA = () => {
    const im = impact(), a = analysis();
    return [
      [L('가격이 오르면 비용 영향은?', 'What if the price rises?'), L(`가격이 10% 오르면 한국 사업장 기준 환산 비용이 약 ${n2(im.d10)}억 원 늘어납니다(${n0(im.px)}→${n0(im.px * 1.1)}원). 25% 오르면 ${n2(im.cost * .25)}억 원입니다. 실제 영향은 보유·할당 물량에 따라 달라 확인이 필요합니다.`, `A 10% rise adds about KRW ${n2(im.d10)} 100M for Korean sites (${n0(im.px)}→${n0(im.px * 1.1)}); 25% adds ${n2(im.cost * .25)}. Actual impact depends on holdings and allocation.`)],
      [L('지금 구매 검토해도 될까?', 'Should we consider buying now?'), L(`투자 판단이 아니라 조달 검토 관점의 모의 답변입니다. 변동폭 ${a.spread.toFixed(1)}%로 안정적이지만 거래량이 평균의 ${a.vr.toFixed(0)}% 수준입니다. 대량 구매 전에는 분할 구매, 경매(월 1회) 일정, 승인 한도를 함께 확인하세요. 구매 요청은 "조달·승인"에서 올립니다.`, `A mock answer from a procurement perspective, not investment advice. The spread is stable at ${a.spread.toFixed(1)}%, but volume is ${a.vr.toFixed(0)}% of average. Before large buys, check staged purchasing, the monthly auction schedule and approval limits. Requests go through "Procurement & Approval".`)],
      [L('해외(EU·중국) 시세와 비교하면?', 'How does it compare with EU/China?'), L('이 시안은 해외 시세 값을 가져오지 않습니다. KRX 사이트는 유럽(CKZ26)과 중국(CCN) 시세 링크만 제공하므로 값을 직접 확인하세요. 제도와 통화가 달라 단순 비교는 권장하지 않습니다.', 'This mock does not fetch overseas prices. KRX only links to Europe (CKZ26) and China (CCN) quotes, so check them directly. Schemes and currencies differ, so direct comparison is discouraged.')]
    ];
  };

  // ── 아래 영역(다른 메뉴와 같은 방식: 박스를 누르면 KPI 줄 아래에 창이 열림) ─────────
  function intent(q) {
    const t = q.toLowerCase().replace(/\s+/g, ''), has = (...k) => k.some(x => t.includes(x));
    const im = impact(), a = analysis(), r5 = SER.slice(-5), last = SER[SER.length - 1], x = cur();
    if (has('오르', '상승', '올라', '비용', '영향', 'rise', 'cost', 'impact')) return L(`가격이 10% 오르면 한국 사업장 기준 환산 비용이 약 ${n2(im.d10)}억 원 늘고(${n0(im.px)}→${n0(im.px * 1.1)}원), 25% 오르면 ${n2(im.cost * .25)}억 원 늘어납니다. 오른쪽 아래 "가격 시나리오" 표에서 −10%~+50%를 볼 수 있습니다. 실제 영향은 보유·할당 물량에 따라 달라집니다.`, `A 10% rise adds about KRW ${n2(im.d10)} 100M for Korean sites (${n0(im.px)}→${n0(im.px * 1.1)}); 25% adds ${n2(im.cost * .25)}. See the scenario table (−10% to +50%). Actual impact depends on holdings and allocation.`);
    if (has('구매', '살', '매수', '조달', 'buy', 'purchase', 'procure')) return L(`투자 판단이 아닌 조달 검토 관점의 모의 답변입니다. 최근 5거래일 변동폭 ${a.spread.toFixed(1)}%로 안정적이지만 거래량은 평균의 ${a.vr.toFixed(0)}% 수준입니다. 대량 구매 전에는 ① 분할 구매 ② 월 1회 경매 일정 ③ 승인 한도를 확인하세요. 구매 요청은 "조달·승인" 메뉴에서 올립니다.`, `A mock answer from a procurement view, not investment advice. The 5-session spread is ${a.spread.toFixed(1)}% but volume is ${a.vr.toFixed(0)}% of average. Before large buys check ① staged purchasing ② the monthly auction ③ approval limits. File requests under "Procurement & Approval".`);
    if (has('해외', '유럽', '중국', 'eu', 'china', 'overseas')) return L('이 시안은 해외 시세 값을 가져오지 않습니다. KRX 사이트가 유럽(CKZ26)·중국(CCN) 시세 링크만 제공하므로 값은 직접 확인하세요. 제도와 통화가 달라 단순 비교는 권장하지 않습니다.', 'This mock does not fetch overseas prices. KRX only links to Europe (CKZ26) and China (CCN) quotes, so check them directly. Schemes and currencies differ, so avoid direct comparison.');
    if (has('추세', '전망', '예측', '방향', 'trend', 'forecast', 'outlook')) return L(`이동평균 기준 설명입니다(예측 아님). 현재가 ${n0(x.c)}원은 5일 평균 ${n0(last.m5)}원 ${x.c >= last.m5 ? '이상' : '아래'}, 20일 평균 ${n0(last.m20)}원 ${x.c >= last.m20 ? '이상' : '아래'}입니다. 최근 5거래일은 ${n0(Math.min(...r5.map(r => r.c)))}~${n0(Math.max(...r5.map(r => r.c)))}원의 좁은 구간입니다. 20일 평균에는 모의 보강 구간이 포함됩니다.`, `Moving-average view only (not a forecast). ${n0(x.c)} is ${x.c >= last.m5 ? 'at/above' : 'below'} the 5-day average (${n0(last.m5)}) and ${x.c >= last.m20 ? 'at/above' : 'below'} the 20-day average (${n0(last.m20)}). The last 5 sessions stayed within ${n0(Math.min(...r5.map(r => r.c)))}–${n0(Math.max(...r5.map(r => r.c)))}. The 20-day average includes simulated history.`);
    if (has('거래량', '유동', 'volume', 'liquid')) return L(`${last.d.slice(5)} 거래량은 ${n0(last.v)}톤으로 5일 평균(${n0(avg(r5.map(r => r.v)))}톤)의 ${a.vr.toFixed(0)}%입니다. 가장 많았던 날은 ${r5.slice().sort((p, q) => q.v - p.v)[0].d.slice(5)}(${n0(Math.max(...r5.map(r => r.v)))}톤)입니다.`, `${last.d.slice(5)} volume ${n0(last.v)} t is ${a.vr.toFixed(0)}% of the 5-day average (${n0(avg(r5.map(r => r.v)))} t). The busiest day was ${r5.slice().sort((p, q) => q.v - p.v)[0].d.slice(5)} (${n0(Math.max(...r5.map(r => r.v)))} t).`);
    if (has('고가', '저가', '평균', '최고', '최저', 'high', 'low', 'average')) return L(`최근 5거래일(KRX 실제) 최고 ${n0(Math.max(...r5.map(r => r.c)))}원, 최저 ${n0(Math.min(...r5.map(r => r.c)))}원, 평균 ${n0(avg(r5.map(r => r.c)))}원입니다. 더 긴 기간 수치는 모의 보강을 포함하니 차트 위 요약 칸을 참고하되 실제 값으로 쓰지 마세요.`, `Over the last 5 sessions (KRX actual): high ${n0(Math.max(...r5.map(r => r.c)))}, low ${n0(Math.min(...r5.map(r => r.c)))}, average ${n0(avg(r5.map(r => r.c)))}. Longer-range figures include simulated history; do not treat them as actual.`);
    if (has('일본', '싱가포르', 'japan', 'singapore')) return L('이 시세는 한국 배출권거래제(K-ETS) KAU26 기준이라 일본·싱가포르 사업장에는 그대로 적용되지 않습니다. 두 국가의 제도·가격은 "산정 결과 → 국가 기준·보고서"의 참고 가격(외부 자료, 대조 전)을 확인하세요.', 'This is the Korea ETS KAU26 price, so it does not apply directly to Japan or Singapore sites. See the reference prices (external data, not yet reconciled) in "Calculation → Country rules & report".');
    if (has('출처', '실시간', '신뢰', 'source', 'real-time', 'realtime', 'live')) return L('출처는 KRX 배출권시장 정보플랫폼(ets.krx.co.kr)의 공개 종가표이며 일 1회 마감 값입니다. 실시간 시세가 아닙니다. 위 "모의 실시간 재생"은 화면 동작 확인용 시뮬레이션입니다.', 'Source: public close table on the KRX ETS Market Information Platform (ets.krx.co.kr), a daily closing value, not real-time. "Play simulated live" above is only a simulation to preview behavior.');
    return L('질문을 이해하지 못했습니다. 다음처럼 물어보세요: "가격이 오르면 비용은?", "지금 구매 검토해도 돼?", "추세가 어때?", "거래량은?", "고가·저가는?", "해외 시세와 비교하면?", "일본·싱가포르는?", "출처가 어디야?"', 'I did not catch that. Try: "What if the price rises?", "Should we buy now?", "What is the trend?", "How is volume?", "High and low?", "Compare with overseas?", "What about Japan/Singapore?", "What is the source?"');
  }

  // ── 풍부한 응답: 시세 통계를 계산해 여러 줄 설명 + 이어서 물을 질문을 만듭니다(규칙 기반 모의 응답) ──
  function mstat() {
    const n = SER.length, last = SER[n - 1], c = SER.map(r => r.c), at = k => c[Math.max(0, n - 1 - k)], chg = k => (last.c / at(k) - 1) * 100;
    const rets = c.slice(1).map((v, i) => Math.log(v / c[i])), w = rets.slice(-60), mu = avg(w), sd = Math.sqrt(avg(w.map(x => (x - mu) ** 2))), y = SER.slice(-250), hi = Math.max(...y.map(r => r.h || r.c)), lo = Math.min(...y.map(r => r.l || r.c));
    const r63 = c.slice(-63); let pk = r63[0], mdd = 0; r63.forEach(v => { pk = Math.max(pk, v); mdd = Math.min(mdd, v / pk - 1); });
    const m60 = avg(c.slice(-60)), v20 = avg(SER.slice(-20).map(r => r.v || 0)), big = SER.slice(-60).reduce((b, r) => Math.abs(r.rate || 0) > Math.abs(b.rate || 0) ? r : b, SER[n - 1]);
    return { last, n, c1w: chg(5), c1m: chg(21), c3m: chg(63), vol: sd * Math.sqrt(252) * 100, hi, lo, pos: hi > lo ? (last.c - lo) / (hi - lo) * 100 : 50, m5: last.m5, m20: last.m20, m60, v20, vr: v20 ? (last.v || 0) / v20 * 100 : 0, mdd: mdd * 100, big, asof: last.d, days: Math.min(n, 250) };
  }
  const pc = v => sign(v) + Math.abs(v).toFixed(1) + '%';
  const FUEN = { '지금 구매 검토해도 될까': 'Should we consider buying now?', '가격이 오르면 비용은': 'What if the price rises?', '변동성은 어때': 'How volatile is it?', '추세가 어때': 'What is the trend?', '요약해줘': 'Summarise today', '50,000톤 사면 얼마야': 'How much for 50,000 t?' };
  function reply(q) {
    const t = q.toLowerCase().replace(/\s+/g, ''), has = (...k) => k.some(x => t.includes(x)), m = mstat(), im = impact(), px = im.px, a = analysis();
    const ev = L('근거: KRX 일별 종가 ' + m.days + '거래일, 기준일 ' + m.asof + (synth() ? ' (일부 모의 보강 포함)' : ''), 'Basis: KRX daily closes, ' + m.days + ' sessions, as of ' + m.asof + (synth() ? ' (partly simulated)' : ''));
    const lim = (() => { try { const b = window.AMA_AGENTS.state().agents.find(x => x.id === 'BA03'); return b && b.limits; } catch (e) { return null; } })();
    const num = (() => { const r = /(\d[\d,.]*)\s*(만|천)?\s*(톤|t\b|ton)/i.exec(q); if (!r) return null; let v = parseFloat(r[1].replace(/,/g, '')); if (r[2] === '만') v *= 1e4; if (r[2] === '천') v *= 1e3; return v; })();
    let text, fu;
    if (num) { const cost = num * px / 1e8; text = [L(`📌 ${n0(num)}톤을 현재가(${n0(px)}원/톤)로 사면`, `📌 Buying ${n0(num)} t at the current ${n0(px)} KRW/t`), L(`· 금액: 약 ${n2(cost)}억 원 (${n0(num * px)}원)`, `· Amount: about KRW ${n2(cost)} 100M`), L(`· 가격이 ±5% 움직이면 ${n2(cost * .05)}억 원, ±10%면 ${n2(cost * .1)}억 원 차이`, `· A ±5% move is KRW ${n2(cost * .05)} 100M; ±10% is ${n2(cost * .1)}`), L(`· 20일 평균(${n0(m.m20)}원) 기준으로 사면 ${n2(num * m.m20 / 1e8)}억 원 → 현재가와 ${n2(Math.abs(cost - num * m.m20 / 1e8))}억 원 차이`, `· At the 20-day average (${n0(m.m20)}) it would be KRW ${n2(num * m.m20 / 1e8)} 100M`), lim ? L(`· 조달 한도(조달 포지셔닝 Agent): 1회 ${n0(lim.perTrade)}톤, 승인 필요 ${n0(lim.approveAbove)}톤 초과 → ${num > lim.approveAbove ? '승인 요청이 필요한 규모' : '한도 안의 규모'}`, `· Procurement limits: ${n0(lim.perTrade)} t per trade, approval above ${n0(lim.approveAbove)} t → ${num > lim.approveAbove ? 'needs approval' : 'within limits'}`) : '', ev].filter(Boolean).join('\n'); fu = ['지금 구매 검토해도 될까', '가격이 오르면 비용은', '변동성은 어때'];
    } else if (has('요약', '브리핑', '오늘', '한눈', 'summary', 'brief', 'today')) {
      text = [L(`📌 시세 요약 (기준 ${m.asof})`, `📌 Price summary (as of ${m.asof})`), L(`· 현재가 ${n0(m.last.c)}원, 전일 대비 ${m.last.chg > 0 ? '+' : m.last.chg < 0 ? '−' : ''}${n0(Math.abs(m.last.chg || 0))}원 (${pc(m.last.rate || 0)})`, `· Close ${n0(m.last.c)} KRW (${pc(m.last.rate || 0)} d/d)`), L(`· 1주 ${pc(m.c1w)} · 1개월 ${pc(m.c1m)} · 3개월 ${pc(m.c3m)}`, `· 1w ${pc(m.c1w)} · 1m ${pc(m.c1m)} · 3m ${pc(m.c3m)}`), L(`· 52주 범위 ${n0(m.lo)}~${n0(m.hi)}원 중 하위 ${m.pos.toFixed(0)}% 지점`, `· 52-week range ${n0(m.lo)}–${n0(m.hi)}: at the ${m.pos.toFixed(0)}th percentile`), L(`· 연환산 변동성 ${m.vol.toFixed(1)}% · 거래량은 20일 평균의 ${m.vr.toFixed(0)}%`, `· Annualised volatility ${m.vol.toFixed(1)}% · volume ${m.vr.toFixed(0)}% of 20-day avg`), L(`· 한국 사업장 올해 배출량 환산 약 ${n2(im.cost)}억 원 (±10% 변동 시 ±${n2(im.d10)}억 원)`, `· Korean-site YTD emissions ≈ KRW ${n2(im.cost)} 100M (±${n2(im.d10)} for ±10%)`), L(`→ 판단: 가격 위치는 ${m.pos < 33 ? '연중 낮은 편' : m.pos > 66 ? '연중 높은 편' : '중간'}이고 ${m.vol > 25 ? '변동이 큰' : '변동이 비교적 작은'} 구간입니다. 조달 검토는 분할 접근이 무난합니다(투자 판단 아님).`, `→ Read: price sits ${m.pos < 33 ? 'low' : m.pos > 66 ? 'high' : 'mid-range'} for the year with ${m.vol > 25 ? 'higher' : 'moderate'} volatility; staged procurement is a reasonable approach (not investment advice).`), ev].join('\n'); fu = ['추세가 어때', '지금 구매 검토해도 될까', '변동성은 어때'];
    } else if (has('변동', '위험', '리스크', '불안', 'volatil', 'risk')) {
      text = [L('📌 변동성·위험', '📌 Volatility & risk'), L(`· 연환산 변동성(최근 60거래일) ${m.vol.toFixed(1)}%`, `· Annualised volatility (60 sessions) ${m.vol.toFixed(1)}%`), L(`· 최근 3개월 최대 낙폭 ${m.mdd.toFixed(1)}%`, `· Max drawdown, last 3 months ${m.mdd.toFixed(1)}%`), L(`· 최근 60거래일 가장 크게 움직인 날 ${m.big.d.slice(5)} (${pc(m.big.rate || 0)})`, `· Largest 60-session move ${m.big.d.slice(5)} (${pc(m.big.rate || 0)})`), L(`· 거래량 ${m.vr.toFixed(0)}% 수준(20일 평균 대비) — ${m.vr < 60 ? '거래가 얇아 가격이 한 번의 주문에 흔들릴 수 있습니다' : '거래는 평소 수준입니다'}`, `· Volume ${m.vr.toFixed(0)}% of the 20-day average — ${m.vr < 60 ? 'thin trading can let single orders move the price' : 'trading is normal'}`), L(`→ 금액으로 보면 한국 사업장 환산 비용이 한 달에 ±${n2(im.cost * m.vol / 100 / Math.sqrt(12))}억 원 정도 움직일 수 있는 수준입니다(1표준편차 추정).`, `→ In money terms the Korean-site exposure can move about ±KRW ${n2(im.cost * m.vol / 100 / Math.sqrt(12))} 100M a month (1-sigma estimate).`), ev].join('\n'); fu = ['가격이 오르면 비용은', '지금 구매 검토해도 될까', '요약해줘'];
    } else if (has('추세', '전망', '예측', '방향', '지지', '저항', 'trend', 'forecast', 'outlook', 'support', 'resist')) {
      const l20 = Math.min(...SER.slice(-20).map(r => r.c)), h20 = Math.max(...SER.slice(-20).map(r => r.c));
      text = [L('📌 추세 (이동평균 기준 · 예측 아님)', '📌 Trend (moving averages · not a forecast)'), L(`· 현재 ${n0(m.last.c)}원 — 5일 평균(${n0(m.m5)}) ${m.last.c >= m.m5 ? '위' : '아래'} · 20일 평균(${n0(m.m20)}) ${m.last.c >= m.m20 ? '위' : '아래'} · 60일 평균(${n0(m.m60)}) ${m.last.c >= m.m60 ? '위' : '아래'}`, `· ${n0(m.last.c)} is ${m.last.c >= m.m5 ? 'above' : 'below'} the 5d (${n0(m.m5)}), ${m.last.c >= m.m20 ? 'above' : 'below'} the 20d (${n0(m.m20)}) and ${m.last.c >= m.m60 ? 'above' : 'below'} the 60d (${n0(m.m60)}) averages`), L(`· 최근 20거래일 범위 ${n0(l20)}~${n0(h20)}원 → 아래쪽 ${n0(l20)}원 부근이 지지선, 위쪽 ${n0(h20)}원 부근이 저항선 역할을 해 왔습니다`, `· 20-session range ${n0(l20)}–${n0(h20)}: ${n0(l20)} acted as support, ${n0(h20)} as resistance`), L(`· 1주 ${pc(m.c1w)} · 1개월 ${pc(m.c1m)} · 3개월 ${pc(m.c3m)}`, `· 1w ${pc(m.c1w)} · 1m ${pc(m.c1m)} · 3m ${pc(m.c3m)}`), L(`→ ${m.last.c >= m.m20 && m.last.c >= m.m60 ? '중기 평균 위에 있어 완만한 상승 흐름' : m.last.c < m.m20 && m.last.c < m.m60 ? '중기 평균 아래라 약세 흐름' : '평균선 사이에서 방향을 탐색하는 구간'}입니다. 이동평균은 과거 흐름의 요약일 뿐 미래를 보장하지 않습니다.`, `→ ${m.last.c >= m.m20 && m.last.c >= m.m60 ? 'above mid-term averages: a gentle uptrend' : m.last.c < m.m20 && m.last.c < m.m60 ? 'below mid-term averages: a soft trend' : 'between the averages: looking for direction'}. Averages summarise the past and guarantee nothing.`), ev].join('\n'); fu = ['변동성은 어때', '지금 구매 검토해도 될까', '요약해줘'];
    } else if (has('구매', '살', '매수', '조달', '분할', 'buy', 'purchase', 'procure')) {
      const tr = 3, step = Math.ceil((lim ? Math.min(lim.perTrade, lim.approveAbove) : 30000) / 1000) * 1000;
      text = [L('📌 조달 검토 (투자 판단이 아닌 절차 관점)', '📌 Procurement view (process, not investment advice)'), L(`· 가격 위치: 52주 범위의 하위 ${m.pos.toFixed(0)}% · 변동성 ${m.vol.toFixed(1)}% · 거래량 ${m.vr.toFixed(0)}%`, `· Price at the ${m.pos.toFixed(0)}th percentile of the 52-week range · volatility ${m.vol.toFixed(1)}% · volume ${m.vr.toFixed(0)}%`), L(`· 분할 예시: ${tr}회로 나누어 회당 ${n0(step)}톤씩 → 회당 약 ${n2(step * px / 1e8)}억 원, 합계 ${n2(step * tr * px / 1e8)}억 원`, `· Staging example: ${tr} tranches of ${n0(step)} t → KRW ${n2(step * px / 1e8)} 100M each, ${n2(step * tr * px / 1e8)} total`), L('· 확인할 것 ① 월 1회 경매 일정 ② 승인 한도(조달 포지셔닝 Agent) ③ 무상할당·이월로 실제 부족분이 얼마인지', '· Check ① the monthly auction calendar ② approval limits ③ the actual shortfall after free allocation and carry-over'), lim ? L(`· 현재 설정된 한도: 1회 ${n0(lim.perTrade)}톤 · 일 ${n0(lim.perDay)}톤 · ${n0(lim.approveAbove)}톤 초과 시 승인`, `· Configured limits: ${n0(lim.perTrade)} t per trade · ${n0(lim.perDay)} t per day · approval above ${n0(lim.approveAbove)} t`) : '', L('→ 구매 요청은 \"조달·승인\" 메뉴에서 올립니다. 이 화면은 실행하지 않습니다.', '→ File requests under \"Procurement & Approval\"; this screen does not execute trades.'), ev].filter(Boolean).join('\n'); fu = ['50,000톤 사면 얼마야', '가격이 오르면 비용은', '변동성은 어때'];
    } else if (has('오르', '상승', '올라', '비용', '영향', '예산', 'rise', 'cost', 'impact', 'budget')) {
      text = [L('📌 가격 변동이 비용에 미치는 영향 (한국 사업장 올해 누적 ' + n1(im.kr) + ' tCO₂ 기준)', '📌 Cost impact of price moves (Korean sites YTD ' + n1(im.kr) + ' tCO₂)'), ...[[-.1, '−10%'], [.1, '+10%'], [.25, '+25%'], [.5, '+50%']].map(([p, lb]) => L(`· ${lb}: ${n0(px * (1 + p))}원/톤 → 환산 ${n2(im.cost * (1 + p))}억 원 (${p > 0 ? '+' : '−'}${n2(Math.abs(im.cost * p))}억)`, `· ${lb}: ${n0(px * (1 + p))} KRW/t → KRW ${n2(im.cost * (1 + p))} 100M`)), L('· 상한 환산입니다. 무상할당·이월을 반영하면 실제 부담은 더 작습니다.', '· Upper-bound conversion; free allocation and carry-over would lower the real burden.'), ev].join('\n'); fu = ['50,000톤 사면 얼마야', '지금 구매 검토해도 될까', '변동성은 어때'];
    } else if (has('거래량', '유동', 'volume', 'liquid')) {
      const r5 = SER.slice(-5);
      text = [L('📌 거래량', '📌 Volume'), L(`· ${m.last.d.slice(5)} ${n0(m.last.v || 0)}톤 — 20일 평균(${n0(m.v20)}톤)의 ${m.vr.toFixed(0)}%`, `· ${m.last.d.slice(5)} ${n0(m.last.v || 0)} t — ${m.vr.toFixed(0)}% of the 20-day average (${n0(m.v20)} t)`), L(`· 최근 5거래일: ${r5.map(r => r.d.slice(5) + ' ' + n0(r.v || 0)).join(' · ')}`, `· Last 5 sessions: ${r5.map(r => r.d.slice(5) + ' ' + n0(r.v || 0)).join(' · ')}`), L(`→ ${m.vr < 60 ? '거래가 한산해 가격 신뢰도가 낮을 수 있습니다. 큰 물량은 나누어 접근하세요.' : '거래는 평소 수준이라 가격 신뢰도는 무난합니다.'}`, `→ ${m.vr < 60 ? 'Thin trading may weaken price reliability; split large orders.' : 'Normal trading; the price is reasonably reliable.'}`), ev].join('\n'); fu = ['변동성은 어때', '지금 구매 검토해도 될까', '요약해줘'];
    } else if (has('해외', '유럽', '중국', 'eu', 'china', 'overseas')) { text = L('이 화면은 해외 시세를 가져오지 않습니다. KRX는 유럽(CKZ26)·중국(CCN) 시세 링크만 제공하므로 값은 직접 확인하세요. 제도·통화가 달라 단순 비교는 권장하지 않습니다.', 'This screen does not fetch overseas prices. KRX only links to Europe (CKZ26) and China (CCN); check them directly. Schemes and currencies differ, so avoid direct comparison.'); fu = ['요약해줘', '추세가 어때'];
    } else if (has('일본', '싱가포르', 'japan', 'singapore')) { text = L('이 시세는 한국 배출권거래제(K-ETS) KAU26 기준이라 일본·싱가포르 사업장에는 그대로 적용되지 않습니다. 두 국가의 제도·가격은 \"산정 결과 → 국가 기준·보고서\"의 참고 가격(외부 자료, 대조 전)을 확인하세요.', 'This is the Korea ETS KAU26 price and does not apply directly to Japan or Singapore. See the reference prices in \"Calculation → Country rules & report\".'); fu = ['요약해줘', '가격이 오르면 비용은'];
    } else if (has('출처', '실시간', '신뢰', 'source', 'real-time', 'realtime', 'live')) { text = L('출처는 KRX 데이터 마켓플레이스 OPEN API(배출권 일별매매정보)이며 일 1회 갱신되는 종가입니다. 실시간 시세가 아닙니다. \"모의 실시간 재생\"은 화면 동작 확인용 시뮬레이션입니다.', 'Source: KRX Data Marketplace OPEN API (daily ETS trading data), refreshed once a day. Not real-time. \"Play simulated live\" is only a UI simulation.'); fu = ['요약해줘', '추세가 어때'];
    } else { text = L('질문을 정확히 이해하지 못했습니다. 이렇게 물어보세요:\n· 오늘 시세 요약해줘\n· 추세가 어때? / 지지선·저항선은?\n· 변동성·위험은?\n· 가격이 오르면 비용은?\n· 50,000톤 사면 얼마야?\n· 지금 구매 검토해도 될까?\n· 거래량은?', 'I did not catch that. Try:\n· Summarise today\n· What is the trend? / support and resistance?\n· Volatility and risk?\n· What if the price rises?\n· How much for 50,000 t?\n· Should we consider buying now?\n· Volume?'); fu = ['요약해줘', '추세가 어때', '변동성은 어때']; }
    return { text, fu };
  }
  function section() {
    const hdrPx = h('span', { class: 'mk-big num' }), hdrChg = h('span', { class: 'mk-chg' }), hdrSt = h('span', { class: 'mk-st' }, h('i', { class: 'mk-dot' }), h('span'));
    const tip = h('div', { class: 'mk-tip', style: 'display:none' }), chartBox = h('div', { class: 'mk-chartbox' }, tip);
    const stats = h('div', { class: 'mk-stats' }), tbl = h('div', { class: 'tscroll' }), sc = h('div', { class: 'tscroll' }), ai = h('div', { class: 'mk-ai' });
    const rangeSeg = h('div', { class: 'seg mk-seg', role: 'group' }, RANGES.map(r => { const b = h('button', { type: 'button', 'data-own': 1, 'data-r': r[0], class: r[0] === range ? 'on' : '' }, L(r[2], r[3])); b.addEventListener('click', () => { range = r[0]; rangeSeg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); draw(); }); return b; }));
    const liveBtn = h('button', { type: 'button', class: 'mk-live', 'data-own': 1, 'aria-pressed': 'false', title: L('화면 동작 확인용 시뮬레이션입니다. 실제 시세가 아닙니다.', 'Simulation to preview live behavior. Not actual prices.') }, h('i', { class: 'mk-dot' }), h('span', {}, L('모의 실시간 재생', 'Play simulated live')));
    liveBtn.addEventListener('click', () => { MKT.live ? stopLive() : startLive(); syncLive(); });
    const closeB = h('button', { type: 'button', class: 'mk-x', 'data-own': 1, 'aria-label': L('닫기', 'Close'), html: '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 3l8 8M11 3l-8 8"/></svg>' });
    closeB.addEventListener('click', () => { S.kpi = null; rerender(); });
    const head = h('div', { class: 'mk-head' }, h('div', { class: 'mk-title' }, h('b', {}, L('배출권 시세 · KAU26', 'Allowance price · KAU26')), h('span', { class: 'mut small' }, L(' 한국 배출권거래제(K-ETS) · 2026년분 · 원/톤', ' Korea ETS · 2026 vintage · KRW/t'))), h('div', { class: 'mk-px-row' }, hdrPx, hdrChg, hdrSt), h('div', { class: 'mk-ctl' }, rangeSeg, liveBtn, closeB));
    const note = h('div', { class: 'mk-note mut small' }, synth() ? L('출처: KRX 배출권시장 정보플랫폼(ets.krx.co.kr) 2026-10-28 공개 종가표 · 일 1회 마감 값이며 실시간이 아닙니다. 실선·● = 실제 종가, 점선·연한 막대 = 모의 보강(실제 아님). ', 'Source: KRX ETS Market Information Platform (ets.krx.co.kr), public close table as of 2026-10-28. Daily closing values, not real-time. Solid line/● = actual close; dashed/faded bars = simulated history (not real). ') : L('출처: KRX 데이터 마켓플레이스 OPEN API · 배출권 일별매매정보 · 기준일 ' + (SER[SER.length - 1].d || '') + ' · 일 1회 갱신이며 실시간이 아닙니다. 모든 구간이 실제 자료입니다.' + (MKT.ui && MKT.ui.state === 'snapshot' ? ' (서버의 자동 갱신 연결 대기 중이라 마지막 수집분 기준입니다.) ' : ' '), 'Source: KRX Data Marketplace OPEN API · daily ETS trading data · as of ' + (SER[SER.length - 1].d || '') + ' · updated once a day, not real-time. All ranges are actual data.' + (MKT.ui && MKT.ui.state === 'snapshot' ? ' (Server refresh is pending; showing the last collected data.) ' : ' ')), h('a', { href: 'https://ets.krx.co.kr/contents/ETS/03/03010000/ETS03010000.jsp', target: '_blank', rel: 'noopener noreferrer' }, L('KRX 시세조회 열기 ↗', 'Open KRX quotes ↗')));
    const left = h('div', { class: 'mk-left' }, chartBox, h('div', { class: 'mk-legend small' }, h('span', {}, h('i', { class: 'lg px' }), L('종가', 'Close')), h('span', {}, h('i', { class: 'lg m5' }), L('5일 평균', '5-day avg')), h('span', {}, h('i', { class: 'lg m20' }), L('20일 평균', '20-day avg')), h('span', {}, h('i', { class: 'lg vol' }), L('거래량', 'Volume'))), stats, h('div', { class: 'mk-sec', style: 'margin-top:10px' }, h('div', { class: 'mk-h' }, L('최근 5거래일 (KRX 실제 값)', 'Last 5 sessions (KRX actual)')), tbl), note);
    // 채팅
    const list = h('div', { class: 'chat mk-chat', role: 'log', 'aria-live': 'polite' }), hist = MKT.hist = MKT.hist || [];
    const fuBox = () => list.querySelectorAll('.qfu').forEach(e => e.remove());
    const addMsg = (m, keep) => { if (!keep) hist.push(m); fuBox(); list.append(h('div', { class: 'msg ' + m.who }, h('div', { class: 'ml' }, m.who === 'ai' ? L('AI 도우미', 'AI assistant') : L('나', 'Me')), h('div', { class: 'bub' }, m.text.split('\n').map(ln => h('div', {}, ln))))); if (m.who === 'ai' && m.fu && m.fu.length) { const f = h('div', { class: 'qfu' }, h('span', { class: 'mut small' }, L('이어서 물어보기', 'Ask next')), m.fu.map(q => { const lab = isEn() ? (FUEN[q] || q) : q, b = h('button', { type: 'button', class: 'chip', 'data-own': 1 }, lab); b.addEventListener('click', () => send(lab)); return b; })); list.append(f); } list.scrollTop = list.scrollHeight; };
    const send = q => { q = (q || '').trim(); if (!q) return; addMsg({ who: 'me', text: q }); const st = document.documentElement.classList.contains('static'), ty = h('div', { class: 'msg ai typing' }, h('div', { class: 'bub' }, L('분석 중…', 'Analysing…'))); if (!st) { list.append(ty); list.scrollTop = list.scrollHeight; } setTimeout(() => { ty.remove(); const r = reply(q); addMsg({ who: 'ai', text: r.text, fu: r.fu }); }, st ? 0 : 700); };
    const inp = h('input', { type: 'text', placeholder: L('질문을 입력하세요 (예: 가격이 오르면 비용은?)', 'Ask a question (e.g. What if the price rises?)'), 'aria-label': L('질문 입력', 'Question'), 'data-own': 1 }), sb = h('button', { type: 'button', 'data-own': 1 }, L('보내기', 'Send'));
    sb.addEventListener('click', () => { send(inp.value); inp.value = ''; }); inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { send(inp.value); inp.value = ''; } });
    const chips = h('div', { class: 'qchips' }, [[L('가격이 오르면 비용은?', 'If price rises?'), '가격이 오르면 비용 영향은'], [L('지금 구매 검토?', 'Buy now?'), '지금 구매 검토해도 될까'], [L('추세가 어때?', 'Trend?'), '추세가 어때'], [L('거래량은?', 'Volume?'), '거래량은'], [L('해외 시세와 비교', 'Overseas'), '해외 시세와 비교하면']].map(([t, q]) => { const b = h('button', { type: 'button', class: 'chip', 'data-own': 1 }, t); b.addEventListener('click', () => send(L(q, t))); return b; }));
    const bigB = h('button', { type: 'button', class: 'mk-aib', 'data-own': 1, title: L('크게 보기', 'Expand'), 'aria-label': L('AI 분석 크게 보기', 'Expand AI panel'), html: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2.5h4v4M6.5 13.5h-4v-4M13.5 2.5l-4.5 4.5M2.5 13.5L7 9"/></svg>' }), newB = h('button', { type: 'button', class: 'mk-aib', 'data-own': 1, title: L('새 대화', 'New chat'), 'aria-label': L('새 대화', 'New chat'), html: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M13.5 8a5.5 5.5 0 1 1-1.8-4.1M13.5 2.5v3h-3"/></svg>' }), aiBtns = [bigB, newB];
    const right = h('div', { class: 'mk-right' }, h('div', { class: 'mk-sec' }, h('div', { class: 'mk-h' }, h('span', { class: 'mk-spark-ic', html: '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l1.7 4.6L14.5 7l-4.8 1.4L8 13l-1.7-4.6L1.5 7l4.8-1.4z"/></svg>' }), L('AI 분석', 'AI analysis'), h('span', { class: 'tag' }, L('모의 응답', 'Mock')), h('span', { class: 'mk-aia' }, aiBtns)), ai, list, chips, h('div', { class: 'cin' }, inp, sb), h('div', { class: 'mut small', style: 'margin-top:6px' }, L('AI 응답은 시안용 모의 대본이며 화면의 값으로 규칙에 따라 만든 설명입니다. 투자 권유가 아닙니다.', 'AI replies are mock scripts built by rules from on-screen values. Not investment advice.'))), h('div', { class: 'mk-sec' }, h('div', { class: 'mk-h' }, L('가격 시나리오별 환산 비용 (한국 사업장 올해 누적 배출 기준)', 'Cost by price scenario (Korean-site YTD emissions)')), sc));
    const box = h('div', { class: 'card mkcard', id: 'mkcard' }, head, h('div', { class: 'mk-body' }, left, right));
    const syncLive = () => { liveBtn.setAttribute('aria-pressed', MKT.live); liveBtn.classList.toggle('on', MKT.live); liveBtn.lastChild.textContent = MKT.live ? L('모의 실시간 중지', 'Stop simulated live') : L('모의 실시간 재생', 'Play simulated live'); drawHead(); };
    function drawHead() { const x = cur(); hdrPx.textContent = n0(x.c); hdrPx.className = 'mk-big num ' + dirCls(x.chg); hdrChg.className = 'mk-chg ' + dirCls(x.chg); hdrChg.textContent = `${arrow(x.chg)} ${n0(Math.abs(x.chg))} (${sign(x.rate)}${Math.abs(x.rate).toFixed(2)}%)`; hdrSt.className = 'mk-st' + (x.live ? ' live' : ''); hdrSt.lastChild.textContent = x.live ? L('모의 실시간 · 시뮬레이션(실제 시세 아님)', 'Simulated live (not actual prices)') : L('종가 · 일 1회 · 실시간 아님', 'Daily close · not real-time'); }
    function draw() {
      const n = RANGES.find(r => r[0] === range)[1], data = SER.slice(-n).map(r => ({ ...r }));
      if (MKT.live) { const li = data.length - 1; data[li].c = cur().c; data[li].v = cur().v; }
      chartBox.querySelectorAll('svg').forEach(s => s.remove());
      const svgc = chart(data, (r, fx, fy) => { if (!r) { tip.style.display = 'none'; return; } tip.style.display = ''; tip.style.left = Math.min(Math.max(fx * 100, 14), 84) + '%'; tip.style.top = Math.max(fy * 100 - 4, 2) + '%'; tip.replaceChildren(h('b', {}, r.d), h('div', {}, L('종가 ', 'Close '), h('b', { class: dirCls(r.chg) }, n0(r.c))), h('div', { class: dirCls(r.chg) }, `${arrow(r.chg)} ${n0(Math.abs(r.chg))} (${sign(r.rate)}${Math.abs(r.rate).toFixed(2)}%)`), h('div', { class: 'mut' }, L('거래량 ', 'Vol ') + n0(r.v) + ' t'), h('div', { class: 'tg ' + (r.real ? 'r' : 'm') }, r.real ? L('KRX 실제 종가', 'KRX actual close') : L('모의 보강(실제 아님)', 'Simulated (not real)'))); });
      chartBox.prepend(svgc);
      const cs = data.map(r => r.c), hi = Math.max(...cs), lo = Math.min(...cs), av = avg(data.map(r => r.v)), chgp = (cs[cs.length - 1] / cs[0] - 1) * 100;
      stats.replaceChildren(...[[L('기간 고가', 'Period high'), n0(hi)], [L('기간 저가', 'Period low'), n0(lo)], [L('기간 등락', 'Period change'), sign(chgp) + Math.abs(chgp).toFixed(2) + '%', dirCls(chgp)], [L('평균 거래량', 'Avg volume'), n0(av) + ' t']].map(([k, v, c]) => h('div', { class: 'mk-s' }, h('span', { class: 'mut small' }, k), h('b', { class: c || '' }, v))));
    }
    function drawSide() {
      const a = analysis();
      ai.replaceChildren(h('ul', { class: 'mk-bl' }, a.bullets.map(([k, v]) => h('li', {}, h('b', {}, k), h('span', {}, v)))));
      const im = impact(); sc.replaceChildren(h('table', { class: 'tbl mini-t mk-sc' }, h('thead', {}, h('tr', {}, [L('시나리오', 'Scenario'), L('가격(원/톤)', 'Price (KRW/t)'), L('환산 비용(억 원)', 'Cost (KRW 100M)'), L('현재 대비', 'vs now')].map((x, i) => h('th', { class: i ? 'n' : '' }, x)))), h('tbody', {}, [[-.1, '−10%'], [0, L('현재가', 'Current')], [.1, '+10%'], [.25, '+25%'], [.5, '+50%']].map(([p, lb]) => h('tr', { class: p === 0 ? 'now' : '' }, h('td', {}, lb), h('td', { class: 'n' }, n0(im.px * (1 + p))), h('td', { class: 'n' }, n2(im.cost * (1 + p))), h('td', { class: 'n ' + (p > 0 ? 'up' : p < 0 ? 'dn' : 'eq') }, p === 0 ? '—' : (p > 0 ? '+' : '−') + n2(Math.abs(im.cost * p))))))), h('div', { class: 'mut small', style: 'margin-top:6px' }, L('한국 올해 누적 배출 ' + n1(im.kr) + ' tCO₂ 전량을 구매한다고 가정한 상한 환산입니다(무상할당·이월 미반영).', 'Upper bound assuming all ' + n1(im.kr) + ' tCO₂ of Korean-site YTD emissions were bought (free allocation and carry-over not reflected).')));
      tbl.replaceChildren(h('table', { class: 'tbl mini-t mk-t' }, h('thead', {}, h('tr', {}, [L('날짜', 'Date'), L('종가', 'Close'), L('대비', 'Chg'), L('등락률(%)', 'Chg %'), L('거래량(톤)', 'Vol (t)')].map((x, i) => h('th', { class: i ? 'n' : '' }, x)))), h('tbody', {}, SER.slice(-5).map(r => [r.d, r.c, r.chg || 0, r.rate || 0, r.v || 0]).reverse().map(r => h('tr', {}, h('td', {}, r[0]), h('td', { class: 'n' }, n0(r[1])), h('td', { class: 'n ' + dirCls(r[2]) }, r[2] ? arrow(r[2]) + ' ' + n0(Math.abs(r[2])) : '0'), h('td', { class: 'n ' + dirCls(r[3]) }, r[3].toFixed(2)), h('td', { class: 'n' }, n0(r[4])))))));
      if (typeof labelCells === 'function') box.querySelectorAll('table').forEach(labelCells);
    }
    MKT._redraw = () => { if (!box.isConnected) return; drawHead(); draw(); };
    drawSide(); drawHead(); draw(); syncLive();
    const greet = () => { const r = reply('요약'); addMsg({ who: 'ai', text: L('안녕하세요. 배출권 시세를 읽어 드립니다. 아래 요약을 보고 이어서 물어보세요.\n(예: 추세·변동성·구매 검토·\"50,000톤 사면 얼마야?\")', 'Hello. I read the allowance price for you. Start from the summary below and keep asking.\n(e.g. trend, volatility, buying, \"how much for 50,000 t?\")') }, false); addMsg({ who: 'ai', text: r.text, fu: r.fu }, false); };
    if (hist.length) hist.slice().forEach(m => addMsg(m, true)); else greet();
    const setBig = on => { MKT.aiBig = on; box.classList.toggle('aifull', on); document.body.classList.toggle('mk-ai-open', on); bigB.setAttribute('aria-pressed', on); if (on) setTimeout(() => { list.scrollTop = list.scrollHeight; inp.focus(); }, 60); };
    bigB.addEventListener('click', () => setBig(!box.classList.contains('aifull'))); newB.addEventListener('click', () => { hist.length = 0; list.replaceChildren(); greet(); });
    const escAi = e => { if (e.key === 'Escape' && box.classList.contains('aifull')) setBig(false); if (!box.isConnected) document.removeEventListener('keydown', escAi); }; document.addEventListener('keydown', escAi);
    if (MKT.aiBig) { box.classList.add('aifull'); document.body.classList.add('mk-ai-open'); }
    return box;
  }

  // ── 모의 실시간(시뮬레이션) ───────────────────────────────
  function startLive() { MKT.live = true; MKT.price = MKT.base.c; MKT.tickVol = 0; const rnd = mulberry(Date.now() & 0xffff); MKT.timer = setInterval(() => { const d = Math.round((rnd() - .5) * 8) * 50; MKT.price = Math.max(20000, MKT.price + d); MKT.tickVol += Math.round(rnd() * 1800); refresh(); }, 1500); refresh(); }
  function stopLive() { MKT.live = false; if (MKT.timer) { clearInterval(MKT.timer); MKT.timer = null; } refresh(); }
  function refresh() { document.querySelectorAll('.mktile').forEach(t => t._upd && t._upd()); if (MKT._redraw) MKT._redraw(); }

  MKT.tile = tile; MKT.section = section; MKT.stop = stopLive;
  window.mktTile = tile;
  // 첫 화면이 시세 모듈보다 먼저 그려진 경우 한 번 다시 그려 시세 타일을 붙입니다.
  if (document.querySelector('#view .kxrow') && !document.querySelector('.mktile') && typeof go === 'function') go(true);
})();
