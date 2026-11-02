const TT = s => (window.I18N && I18N.lang === 'en' && window.tr) ? tr(String(s)) : String(s);
'use strict';
// 다양한 그래프 유형(차트 선택 가이드 기반): 가로 막대·도넛·트리맵·폭포·누적 영역·버블·방사형·히스토그램·불릿·토네이도·MACC. 값은 호출하는 화면이 모의 데이터에서 계산해 넘깁니다.
const PAL = ['var(--cy)', 'var(--gr)', 'var(--yl)', 'var(--pu)', 'var(--rd)', 'var(--c6)', 'var(--c7)', 'var(--c8)'];
const CC = { 한국: 'var(--cy)', 일본: 'var(--pu)', 싱가포르: 'var(--yl)' };
const gbox = (W, H) => sv('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart' });
const tt = (el, t) => { el.append(sv('title', {}, t)); return el; };
const gnum = (v, d = 0) => v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
function smoothD(pts) { // Catmull-Rom → 베지어
  if (pts.length < 3) return 'M' + pts.map(p => p.join(' ')).join('L');
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) { const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2; d += `C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)} ${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)} ${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`; }
  return d;
}
function gridY(svg, L, W, R, Y, mx, fmtv, T, B, H) {
  const nz = nice(mx, 4); for (let v = 0; v <= nz.max + 1e-9; v += nz.step) svg.append(sv('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }), sv('text', { x: L - 6, y: Y(v) + 3.5, class: 'ax', 'text-anchor': 'end' }, fmtv(v))); return nz;
}
// 1) 가로 막대(여러 항목 비교). marks=[{v,c,label}] 기준선
function hbarChart(o) {
  const n = o.items.length, W = isMob() ? 380 : (o.W || 560), L = o.L || 86, R = 58, mk = (o.marks || []).slice().sort((p, q) => p.v - q.v), mrow = (() => { const rows = [], last = [-1e9, -1e9]; mk.forEach(m => { const w = estW(TT(m.label || ''), 10); let r = 0; const x0 = ((o.L || 86) + ((isMob() ? 380 : 560) - (o.L || 86) - 58) * m.v / (o.max || Math.max(...o.items.map(i => i.v), ...(o.marks || []).map(q => q.v)) * 1.1)); if (x0 - w / 2 < last[0] + 4) r = 1; if (r === 1 && x0 - w / 2 < last[1] + 4) r = 0; last[r] = x0 + w / 2; rows.push(r); }); return rows; })(), T = mk.length ? (mrow.some(r => r === 1) ? 38 : 24) : 8, rh = o.rh || 26, H = T + n * rh + 24, fv = o.fmt || (v => gnum(v));
  const mx = o.max || Math.max(...o.items.map(i => i.v), ...(o.marks || []).map(m => m.v)) * 1.1, X = v => L + (W - L - R) * v / mx, svg = gbox(W, H), nz = nice(mx, 4);
  for (let v = 0; v <= mx + 1e-9; v += nz.step) svg.append(sv('line', { x1: X(v), x2: X(v), y1: T, y2: H - 20, stroke: 'var(--grid)' }), sv('text', { x: X(v), y: H - 6, class: 'ax', 'text-anchor': 'middle' }, fv(v)));
  o.items.forEach((it, i) => { const y = T + i * rh + 4, w = Math.max(2, X(it.v) - L), g = sv('g', { class: 'hb' }); g.append(sv('rect', { x: L, y, width: w, height: rh - 9, rx: 5, fill: it.c || 'var(--cy)', opacity: .9 }), sv('text', { x: L - 6, y: y + rh / 2 - 1, class: 'ax', 'text-anchor': 'end' }, it.label), (() => { const txt = it.txt || fv(it.v), tw = estW(txt, 11) + 4; let x = L + w + 5, hit = false; mk.forEach(m => { const mx = X(m.v); if (mx > x - 3 && mx < x + tw) hit = true; }); if (hit && w > tw + 16) return sv('text', { x: L + w - 7, y: y + rh / 2 - 1, class: 'ax big2 dc', style: 'fill:#fff', 'text-anchor': 'end' }, txt); if (hit) mk.forEach(m => { const mx = X(m.v); if (mx > x - 3 && mx < x + tw) x = mx + 5; }); return sv('text', { x, y: y + rh / 2 - 1, class: 'ax big2' }, txt); })()); tt(g, it.tip || `${it.label} ${it.txt || fv(it.v)}`); svg.append(g); });
  mk.forEach((m, k) => svg.append(sv('line', { x1: X(m.v), x2: X(m.v), y1: mrow[k] ? 29 : 17, y2: H - 20, stroke: m.c, 'stroke-width': 1.4, 'stroke-dasharray': '5 3' }), sv('text', { x: X(m.v), y: mrow[k] ? 24 : 12, class: 'ax', fill: m.c, 'text-anchor': 'middle' }, m.label || '')));
  return h('div', {}, o.legend ? legend(o.legend) : '', svg);
}
// 2) 도넛(구성 비율)
function donutChart(o) {
  const tot = sumA(o.parts.map(p => p.v)), svg = sv('svg', { viewBox: '0 0 140 140', class: 'donut', width: o.size || 150 }); let a0 = -Math.PI / 2; const f = (r, a) => `${70 + r * Math.cos(a)} ${70 + r * Math.sin(a)}`;
  o.parts.forEach(p => { const a1 = a0 + 2 * Math.PI * p.v / tot - (o.parts.length > 1 ? .03 : 0), big = a1 - a0 > Math.PI ? 1 : 0; svg.append(tt(sv('path', { d: `M${f(62, a0)} A62 62 0 ${big} 1 ${f(62, a1)} L${f(40, a1)} A40 40 0 ${big} 0 ${f(40, a0)}Z`, fill: p.c, class: 'dseg' }), `${p.n} ${gnum(p.v, 1)} (${(p.v / tot * 100).toFixed(1)}%)`)); a0 += 2 * Math.PI * p.v / tot; });
  svg.append(sv('text', { x: 70, y: 68, fill: 'var(--txt)', 'font-size': 15, 'text-anchor': 'middle', 'font-weight': 700 }, o.center || gnum(tot, 1)), sv('text', { x: 70, y: 83, fill: 'var(--mut)', 'font-size': 8.5, 'text-anchor': 'middle' }, o.sub || ''));
  return h('div', { class: 'donutw' }, svg, h('div', { class: 'dleg' }, o.parts.map(p => h('div', { html: `<i class="dot" style="background:${p.c}"></i>${p.n} <b>${(p.v / tot * 100).toFixed(1)}%</b> <span class="mut">${gnum(p.v, 1)}</span>` }))));
}
// 3) 트리맵(전체 대비 비중)
function treemap(o) {
  const W = o.w || 560, H = o.h || 230, its = o.items.slice().sort((a, b) => b.v - a.v), mx = its[0].v, rects = [];
  (function lay(a, x, y, w, hh) { if (!a.length) return; if (a.length === 1) { rects.push({ ...a[0], x, y, w, h: hh }); return; } const t = sumA(a.map(i => i.v)); let acc = 0, k = 0; while (k < a.length - 1 && acc + a[k].v <= t / 2) { acc += a[k].v; k++; } if (k === 0) { acc = a[0].v; k = 1; } const fa = acc / t; if (w >= hh) { lay(a.slice(0, k), x, y, w * fa, hh); lay(a.slice(k), x + w * fa, y, w * (1 - fa), hh); } else { lay(a.slice(0, k), x, y, w, hh * fa); lay(a.slice(k), x, y + hh * fa, w, hh * (1 - fa)); } })(its, 0, 0, W, H);
  const svg = gbox(W, H), tot = sumA(its.map(i => i.v));
  rects.forEach(r => { const g = sv('g', { class: 'tm' }); g.append(sv('rect', { x: r.x + 1.5, y: r.y + 1.5, width: Math.max(0, r.w - 3), height: Math.max(0, r.h - 3), rx: 8, fill: r.c, opacity: .35 + .55 * r.v / mx })); if (r.w > 56 && r.h > 34) g.append(sv('text', { x: r.x + 10, y: r.y + 20, fill: '#fff', 'font-size': 13, 'font-weight': 700 }, r.n), sv('text', { x: r.x + 10, y: r.y + 36, fill: '#fff', 'font-size': 11, opacity: .9 }, `${(r.v / tot * 100).toFixed(1)}%`)); tt(g, `${r.n} ${gnum(r.v, 1)} (${(r.v / tot * 100).toFixed(1)}%)`); svg.append(g); });
  return svg;
}
// 4) 폭포(증감 기여). steps=[{n,v,total?}]
// 라벨 폭 추정(한글 10px, 영문 5.4px, 대문자·숫자 6.2px @10px) 후 슬롯에 맞게 2줄로 나누거나 말줄임
function estW(s, fs) { let w = 0; for (const ch of s) w += /[가-힣ㄱ-ㅎ]/.test(ch) ? 1.02 : /[mwMW]/.test(ch) ? .9 : /[A-Z0-9%]/.test(ch) ? .68 : /[ilj.,:'|! ]/.test(ch) ? .32 : .58; return w * (fs || 10); }
function fitLines(s, maxW, fs) {
  s = String(s); if (estW(s, fs) <= maxW) return [s];
  const cut = (t, w) => { if (estW(t, fs) <= w) return t; let o = ''; for (const ch of t) { if (estW(o + ch + '…', fs) > w) break; o += ch; } return o + '…'; };
  const sp = [...s.matchAll(/ /g)].map(m => m.index); let best = -1, bd = 1e9; sp.forEach(i => { const d = Math.abs(i - s.length / 2); if (d < bd) { bd = d; best = i; } });
  if (best < 0) return [cut(s, maxW)];
  return [cut(s.slice(0, best).trim(), maxW), cut(s.slice(best).trim(), maxW)];
}
function waterfallChart(o) {
  const n = o.steps.length, W = isMob() ? 380 : 560, H = o.h || 230, L = 50, R = 10, T = 16, fv = o.fmt || (v => gnum(v, 1)), slotW = ((isMob() ? 380 : 560) - 60) / o.steps.length, LB = o.steps.map(s => fitLines(TT(s.n), slotW - 5, 10)), B = LB.some(l => l.length > 1) || o.steps.some(s => s.sub) ? 58 : 38; let run = 0; const bars = o.steps.map(s => { if (s.total) { run = s.v; return { ...s, y0: 0, y1: s.v }; } const y0 = run; run += s.v; return { ...s, y0, y1: run }; });
  const vv = bars.flatMap(b => b.total ? [b.y1] : [b.y0, b.y1]), lo = Math.min(...vv) * (o.zero ? 0 : .985), hi = Math.max(...vv) * 1.04, base = o.zero ? 0 : lo, Y = v => T + (H - T - B) * (hi - v) / (hi - base), svg = gbox(W, H), bw = (W - L - R) / n;
  const nz = nice(hi - base, 4); for (let v = base; v <= hi + 1e-9; v += nz.step) svg.append(sv('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }), sv('text', { x: L - 6, y: Y(v) + 3.5, class: 'ax', 'text-anchor': 'end' }, fv(v)));
  bars.forEach((b, i) => { const x = L + i * bw + bw * .16, w = bw * .68, yb0 = Math.max(b.y0, base), top = Math.min(Y(yb0), Y(b.y1)), hh = Math.max(2, Math.abs(Y(yb0) - Y(b.y1))), col = b.total ? 'var(--cy)' : b.v >= 0 ? 'var(--rd)' : 'var(--gr)', g = sv('g', { class: 'hb' });
    g.append(sv('rect', { x, y: top, width: w, height: hh, rx: 4, fill: col, opacity: .88 }), sv('text', { x: x + w / 2, y: top - 4, class: 'ax', 'text-anchor': 'middle' }, (b.total ? '' : b.v > 0 ? '+' : '') + fv(b.v)), ...LB[i].map((ln, k) => sv('text', { x: x + w / 2, y: H - B + 14 + k * 13, class: 'ax', 'text-anchor': 'middle' }, ln)), b.sub ? sv('text', { x: x + w / 2, y: H - B + 14 + LB[i].length * 13, class: 'ax sub', 'text-anchor': 'middle' }, b.sub) : ''); tt(g, `${b.n} ${(b.total ? '' : b.v > 0 ? '+' : '') + fv(b.v)}`); svg.append(g);
    if (i < n - 1) svg.append(sv('line', { x1: x + w, x2: x + bw * 1.0 + bw * .16, y1: Y(b.y1), y2: Y(b.y1), stroke: 'var(--mut)', 'stroke-dasharray': '2 3', opacity: .6 })); });
  return svg;
}
// 5) 누적 영역(구성의 시간 변화). x=라벨, series=[{n,c,d}]
function stackedArea(o) {
  const n = o.x.length, W = isMob() ? 380 : 620, H = o.h || 230, L = 52, R = 14, T = 12, B = 26, tot = Array.from({ length: n }, (_, i) => sumA(o.series.map(s => s.d[i]))), nz = nice(Math.max(...tot) * 1.05, 4), mx = nz.max, X = i => L + (W - L - R) * i / (n - 1), Y = v => H - B - (H - T - B) * v / mx, svg = gbox(W, H);
  gridY(svg, L, W, R, Y, mx, v => gnum(v), T, B, H); o.x.forEach((l, i) => svg.append(sv('text', { x: X(i), y: H - 7, class: 'ax', 'text-anchor': 'middle' }, l)));
  const acc = Array(n).fill(0), layers = o.series.map(s => { const lo = acc.slice(); s.d.forEach((v, i) => acc[i] += v); return { s, lo, hi: acc.slice() }; });
  layers.forEach(({ s, lo, hi }) => { const up = hi.map((v, i) => [X(i), Y(v)]), dn = lo.map((v, i) => [X(i), Y(v)]).reverse(), d = smoothD(up) + 'L' + smoothD(dn).slice(1) + 'Z', gid = 'sa' + (++_gid); svg.append(sv('defs', {}, sv('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, sv('stop', { offset: '0%', 'stop-color': s.c, 'stop-opacity': .85 }), sv('stop', { offset: '100%', 'stop-color': s.c, 'stop-opacity': .35 }))), sv('path', { d, fill: `url(#${gid})` }), sv('path', { d: smoothD(up), fill: 'none', stroke: s.c, 'stroke-width': 1.6 })); });
  o.x.forEach((l, i) => { const r = sv('rect', { x: X(i) - (W - L - R) / (n - 1) / 2, y: T, width: (W - L - R) / (n - 1), height: H - T - B, fill: 'transparent' }); tt(r, `${l} · ` + o.series.map(s => `${s.n} ${gnum(s.d[i], 1)}`).join(' / ') + ` · 합계 ${gnum(tot[i], 1)}`); svg.append(r); });
  return h('div', {}, legend(o.series.map(s => ({ n: s.n, c: s.c }))), svg);
}
// 6) 버블 산점도(관계). pts=[{id,x,y,r,c,tip}]
function bubbleChart(o) {
  const W = isMob() ? 380 : 560, H = o.h || 250, L = 52, R = 16, T = 14, B = 34, xs = o.pts.map(p => p.x), ys = o.pts.map(p => p.y), x0 = Math.min(...xs) - (Math.max(...xs) - Math.min(...xs)) * .15 - .001, x1 = Math.max(...xs) + (Math.max(...xs) - Math.min(...xs)) * .15 + .001, y0 = Math.min(...ys) - (Math.max(...ys) - Math.min(...ys)) * .2 - .001, y1 = Math.max(...ys) + (Math.max(...ys) - Math.min(...ys)) * .2 + .001, rm = Math.max(...o.pts.map(p => p.r));
  const X = v => L + (W - L - R) * (v - x0) / (x1 - x0), Y = v => H - B - (H - T - B) * (v - y0) / (y1 - y0), svg = gbox(W, H);
  for (let i = 0; i <= 4; i++) { const yv = y0 + (y1 - y0) * i / 4, xv = x0 + (x1 - x0) * i / 4; svg.append(sv('line', { x1: L, x2: W - R, y1: Y(yv), y2: Y(yv), stroke: 'var(--grid)' }), sv('text', { x: L - 6, y: Y(yv) + 3.5, class: 'ax', 'text-anchor': 'end' }, (o.fy || (v => v.toFixed(2)))(yv)), sv('text', { x: X(xv), y: H - 18, class: 'ax', 'text-anchor': 'middle' }, (o.fx || (v => v.toFixed(1)))(xv))); }
  svg.append(sv('text', { x: (L + W - R) / 2, y: H - 4, class: 'ax', 'text-anchor': 'middle' }, o.xl), sv('text', { x: L, y: 9, class: 'ax', 'text-anchor': 'start' }, o.yl));
  o.pts.forEach(p => { const g = sv('g', { class: 'hb' }); g.append(sv('circle', { cx: X(p.x), cy: Y(p.y), r: 6 + 16 * Math.sqrt(p.r / rm), fill: p.c, opacity: .55, stroke: p.c, 'stroke-width': 1.4 }), sv('text', { x: X(p.x), y: Y(p.y) + 3, class: 'ax dc', fill: '#fff', 'text-anchor': 'middle', 'font-size': 9 }, p.id.slice(3))); tt(g, p.tip || p.id); svg.append(g); });
  return svg;
}
// 7) 방사형(순환 데이터). axes=라벨, series=[{n,c,d}]
function radarChart(o) {
  const n = o.axes.length, S0 = 130, cx = S0 + 20, cy = S0 + 10, svg = sv('svg', { viewBox: `0 0 ${2 * cx} ${2 * cy}`, class: 'chart radar' }), mx = o.max || Math.max(...o.series.flatMap(s => s.d)) * 1.1, pt = (i, v) => [cx + S0 * .86 * v / mx * Math.sin(2 * Math.PI * i / n), cy - S0 * .86 * v / mx * Math.cos(2 * Math.PI * i / n)];
  [.25, .5, .75, 1].forEach(k => svg.append(sv('polygon', { points: o.axes.map((_, i) => pt(i, mx * k).join(',')).join(' '), fill: 'none', stroke: 'var(--grid)' })));
  o.axes.forEach((a, i) => { const e = pt(i, mx * 1.0), l = pt(i, mx * 1.14); svg.append(sv('line', { x1: cx, y1: cy, x2: e[0], y2: e[1], stroke: 'var(--grid)' }), sv('text', { x: l[0], y: l[1] + 3, class: 'ax', 'text-anchor': 'middle', 'font-size': 10 }, a)); });
  o.series.forEach(s => { const pts = s.d.map((v, i) => pt(i, v)); svg.append(tt(sv('polygon', { points: pts.map(p => p.join(',')).join(' '), fill: s.c, 'fill-opacity': .2, stroke: s.c, 'stroke-width': 2, 'stroke-linejoin': 'round' }), s.n), ...pts.map((p, i) => tt(sv('circle', { cx: p[0], cy: p[1], r: 3, fill: s.c }), `${s.n} ${o.axes[i]} ${gnum(s.d[i], 1)}`))); });
  return h('div', {}, legend(o.series.map(s => ({ n: s.n, c: s.c }))), svg);
}
// 8) 히스토그램(분포). vals, bins
function histogram(o) {
  const W = isMob() ? 380 : 560, H = o.h || 210, L = 40, R = 12, T = 18, B = 32, nb = o.bins || 10, mn = Math.min(...o.vals), mxv = Math.max(...o.vals), bw0 = (mxv - mn) / nb || 1, cnt = Array(nb).fill(0); o.vals.forEach(v => cnt[Math.min(nb - 1, Math.floor((v - mn) / bw0))]++);
  const my = Math.max(...cnt) * 1.15, X = v => L + (W - L - R) * (v - mn) / (mxv - mn || 1), Y = c => H - B - (H - T - B) * c / my, svg = gbox(W, H), bw = (W - L - R) / nb;
  const nz = nice(my, 4); for (let v = 0; v <= my + 1e-9; v += nz.step) svg.append(sv('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }), sv('text', { x: L - 6, y: Y(v) + 3.5, class: 'ax', 'text-anchor': 'end' }, gnum(v)));
  const mean = sumA(o.vals) / o.vals.length, sd = Math.sqrt(sumA(o.vals.map(v => (v - mean) ** 2)) / o.vals.length);
  cnt.forEach((c, i) => { const lo = mn + i * bw0, hi = lo + bw0, out = (lo + hi) / 2 > mean + 2 * sd || (lo + hi) / 2 < mean - 2 * sd; svg.append(tt(sv('rect', { x: L + i * bw + 2, y: Y(c), width: bw - 4, height: Math.max(0, H - B - Y(c)), rx: 4, fill: out ? 'var(--rd)' : 'var(--cy)', opacity: .85, class: 'bar' }), `${gnum(lo, 1)}~${gnum(hi, 1)} : ${c}일`)); if (i % 2 === 0 || nb <= 8) svg.append(sv('text', { x: L + i * bw + bw / 2, y: H - 17, class: 'ax', 'text-anchor': 'middle', 'font-size': 9.5 }, gnum(lo, o.dec || 0))); });
  svg.append(sv('line', { x1: X(mean), x2: X(mean), y1: T - 4, y2: H - B, stroke: 'var(--yl)', 'stroke-dasharray': '4 3', 'stroke-width': 1.4 }), sv('text', { x: X(mean) + 4, y: T + 4, class: 'ax', fill: 'var(--yl)' }, '평균 ' + gnum(mean, o.dec || 0)), sv('text', { x: (L + W - R) / 2, y: H - 3, class: 'ax', 'text-anchor': 'middle' }, o.xl || ''));
  return svg;
}
// 9) 불릿 게이지(목표 대비 사용률): 70/90% 눈금
function bulletGauge(u, label) {
  const p = Math.min(130, u * 100), c = u >= .9 ? 'var(--rd)' : u >= .7 ? 'var(--yl)' : 'var(--gr)';
  return h('div', { class: 'bullet' }, label ? h('div', { class: 'bl' }, label) : '', h('div', { class: 'btrack' }, h('i', { class: 'z1', style: 'width:53.8%' }), h('i', { class: 'z2', style: 'left:53.8%;width:15.4%' }), h('i', { class: 'z3', style: 'left:69.2%;width:30.8%' }), h('b', { style: `width:${p / 1.3}%;background:${c}` }), h('s', { style: `left:${p / 1.3}%` })), h('div', { class: 'bt2' }, h('span', {}, '0'), h('span', { style: 'left:53.8%' }, '70%'), h('span', { style: 'left:69.2%' }, '90%'), h('em', { style: `color:${c}` }, (u * 100).toFixed(0) + '%')));
}
// 10) 토네이도(민감도). rows=[{n,lo,hi,loL,hiL}], base
function tornadoChart(o) {
  const rows = o.rows.slice().sort((a, b) => Math.abs(b.hi - b.lo) - Math.abs(a.hi - a.lo)), n = rows.length, W = isMob() ? 380 : 560, L = 150, R = 70, T = 10, rh = 28, H = T + n * rh + 24, span = Math.max(...rows.flatMap(r => [Math.abs(r.lo - o.base), Math.abs(r.hi - o.base)])) * 1.15 || 1, X = v => L + 50 + (W - L - 50 - R) / 2 * (1 + (v - o.base) / span), svg = gbox(W, H), fv = o.fmt || (v => gnum(v, 2));
  svg.append(sv('line', { x1: X(o.base), x2: X(o.base), y1: T, y2: H - 20, stroke: 'var(--txt)', opacity: .6 }), sv('text', { x: X(o.base), y: H - 6, class: 'ax', 'text-anchor': 'middle' }, '기준 ' + fv(o.base)));
  rows.forEach((r, i) => { const y = T + i * rh + 4, g = sv('g', { class: 'hb' }), a = Math.min(r.lo, r.hi), b = Math.max(r.lo, r.hi);
    g.append(sv('text', { x: L - 8, y: y + 13, class: 'ax', 'text-anchor': 'end' }, r.n)); if (a < o.base) g.append(sv('rect', { x: X(a), y, width: X(o.base) - X(a), height: rh - 10, rx: 4, fill: 'var(--gr)', opacity: .85 })); if (b > o.base) g.append(sv('rect', { x: X(o.base), y, width: X(b) - X(o.base), height: rh - 10, rx: 4, fill: 'var(--rd)', opacity: .85 })); g.append(sv('text', { x: X(Math.min(a, o.base)) - 5, y: y + 13, class: 'ax', 'text-anchor': 'end', 'font-size': 10 }, fv(a)), sv('text', { x: X(Math.max(b, o.base)) + 4, y: y + 13, class: 'ax', 'font-size': 10 }, fv(b))); tt(g, `${r.n}: ${r.loL || ''} → ${fv(r.lo)} / ${r.hiL || ''} → ${fv(r.hi)}`); svg.append(g); });
  return svg;
}
// 11) MACC(감축 비용 곡선): 폭=감축량, 높이=톤당 비용, 기준선=탄소가격
function maccChart(o) {
  const its = o.items.slice().sort((a, b) => a.c - b.c), W = isMob() ? 380 : 980, H = o.h || 300, L = 50, R = 12, T = 18, B = 32, tot = sumA(its.map(i => i.a)), cmin = Math.min(0, ...its.map(i => i.c)), cmax = Math.max(o.price, ...its.map(i => i.c)) * 1.12, Y = v => T + (H - T - B) * (cmax - v) / (cmax - cmin), X = v => L + (W - L - R) * v / tot, svg = gbox(W, H);
  const nz = nice(cmax - cmin, 4); for (let v = Math.ceil(cmin / nz.step) * nz.step; v <= cmax + 1e-9; v += nz.step) svg.append(sv('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: v === 0 ? 'var(--mut)' : 'var(--grid)' }), sv('text', { x: L - 6, y: Y(v) + 3.5, class: 'ax', 'text-anchor': 'end' }, (v === 0 ? '0' : gnum(v))));
  let acc = 0; its.forEach((it, i) => { const x = X(acc), w = Math.max(2, X(it.a) - L), y = Math.min(Y(it.c), Y(0)), hh = Math.max(2, Math.abs(Y(it.c) - Y(0))), col = it.c <= 0 ? 'var(--gr)' : it.c <= o.price ? 'var(--cy)' : 'var(--yl)', g = sv('g', { class: 'hb' });
    g.append(sv('rect', { x: x + 1, y, width: w - 2, height: hh, rx: 3, fill: col, opacity: .85 })); if (w > 70) g.append(sv('text', { x: x + w / 2, y: it.c <= 0 ? y + hh + 12 : y - 4, class: 'ax', 'text-anchor': 'middle', 'font-size': 9.5 }, it.n)); tt(g, `${it.n} · 감축 ${gnum(it.a)} tCO₂/년 · ${gnum(it.c)} US$/t`); svg.append(g); acc += it.a; });
  svg.append(sv('line', { x1: L, x2: W - R, y1: Y(o.price), y2: Y(o.price), stroke: 'var(--rd)', 'stroke-width': 1.6, 'stroke-dasharray': '7 4' }), sv('text', { x: L + 6, y: Y(o.price) - 5, class: 'ax', fill: 'var(--rd)', 'text-anchor': 'start' }, `탄소가격 ${o.price} US$/t`), sv('text', { x: (L + W - R) / 2, y: H - 5, class: 'ax', 'text-anchor': 'middle' }, '누적 연간 감축량 (tCO₂) →  폭 = 감축량 · 높이 = 톤당 비용 (US$/tCO₂)'));
  return svg;
}
