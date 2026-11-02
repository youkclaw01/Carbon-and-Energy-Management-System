'use strict';
// 차트 모음(축·범례·툴팁이 있는 SVG). 범례는 HTML로 그려 잘리지 않게 합니다.
const isMob = () => window.matchMedia('(max-width:720px)').matches;
const nice = (mx, n = 4) => { const raw = mx / n, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p, s = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10, st = s * p; return { step: st, max: Math.ceil(mx / st) * st }; };
const legend = items => h('div', { class: 'lg' }, items.map(i => h('span', { html: `<i class="${i.dash ? 'ln' : 'dot'}" style="${i.dash ? 'border-top:2px dashed ' + i.c : 'background:' + i.c}"></i>${i.n}` })));
let _gid = 0;
// 그래픽 스타일: 둥근 플롯 배경, 막대 그라데이션, 선 글로우
function beautify(svg, g) {
  const id = 'gx' + (++_gid), defs = sv('defs');
  defs.append(sv('filter', { id: id + 'b', x: '-20%', y: '-20%', width: '140%', height: '140%' }, sv('feGaussianBlur', { stdDeviation: 3.5 })));
  svg.insertBefore(defs, svg.firstChild);
  svg.insertBefore(sv('rect', { x: g.L, y: g.T, width: g.W - g.L - g.R, height: g.H - g.T - g.B, rx: 10, fill: 'rgba(120,200,255,.045)', stroke: 'rgba(120,200,255,.12)' }), defs.nextSibling);
  const made = {};
  svg.querySelectorAll('rect.bar').forEach(r => { const col = r.getAttribute('fill') || r.style.fill; if (!col || col.startsWith('url(')) return; r.style.fill = ''; const gid = id + col.replace(/[^a-z0-9]/gi, ''); if (!made[gid]) { made[gid] = 1; defs.append(sv('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, sv('stop', { offset: '0%', 'stop-color': col, 'stop-opacity': 1 }), sv('stop', { offset: '100%', 'stop-color': col, 'stop-opacity': .55 }))); } r.setAttribute('fill', `url(#${gid})`); r.setAttribute('rx', 4); });
  svg.querySelectorAll('path[fill="none"]').forEach(p => { p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round'); const gl = p.cloneNode(); gl.setAttribute('stroke-width', (+p.getAttribute('stroke-width') || 2) * 3.2); gl.setAttribute('opacity', .22); gl.setAttribute('filter', `url(#${id}b)`); gl.removeAttribute('class'); gl.setAttribute('pointer-events', 'none'); p.parentNode.insertBefore(gl, p); });
}
function areaGrad(svg, color, op) { const gid = 'ag' + (++_gid); svg.append(sv('defs', {}, sv('linearGradient', { id: gid, x1: 0, y1: 0, x2: 0, y2: 1 }, sv('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': op }), sv('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': 0 })))); return `url(#${gid})`; }
function tipBox(wrap) { const t = h('div', { class: 'ctip' }); wrap.append(t); return t; }
function attachHover(wrap, svg, W, H, L, R, n, xOf, render, extra) {
  const tip = tipBox(wrap), cur = sv('line', { y1: 0, y2: H, stroke: 'var(--mut)', 'stroke-width': 1, 'stroke-dasharray': '3 3', opacity: 0 }); svg.append(cur);
  const mv = e => { const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W; let bi = 0, bd = 1e9; for (let i = 0; i < n; i++) { const d = Math.abs(xOf(i) - x); if (d < bd) { bd = d; bi = i; } } cur.setAttribute('x1', xOf(bi)); cur.setAttribute('x2', xOf(bi)); cur.setAttribute('opacity', 1); tip.innerHTML = render(bi); tip.style.display = 'block'; const px = xOf(bi) / W * r.width; tip.style.left = Math.min(Math.max(px + 12, 4), r.width - tip.offsetWidth - 4) + 'px'; tip.style.top = '6px'; if (extra) extra(bi); };
  const lv = () => { cur.setAttribute('opacity', 0); tip.style.display = 'none'; };
  svg.addEventListener('pointermove', mv); svg.addEventListener('pointerdown', mv); svg.addEventListener('pointerleave', lv);
}
// 이중 축 선 차트: series[{n,c,d,axis:'l'|'r',u,dash}], x: 라벨 배열, hl: 가로선[{v,label,c,axis}]
function lineChart(o) {
  const W = isMob() ? 380 : 640, H = o.h || 220, L = isMob() ? 44 : 52, R = o.dual ? (isMob() ? 44 : 56) : 14, T = 12, B = 26, n = o.x.length, wrap = h('div', { class: 'cwrap' });
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart' });
  const ax = { l: o.series.filter(s => (s.axis || 'l') === 'l'), r: o.series.filter(s => s.axis === 'r') };
  const rng = k => { const ds = ax[k].flatMap(s => s.d.filter(v => v != null)).concat((o.hl || []).filter(x => (x.axis || 'l') === k).map(x => x.v)); const mn = o.zero === false ? Math.min(...ds) : 0, nz = nice(Math.max(...ds) * 1.08 - mn, 4); return { mn, mx: mn + nz.max, st: nz.step }; };
  const A = { l: rng('l'), r: ax.r.length ? rng('r') : null };
  const Y = (v, k) => H - B - (H - T - B) * (v - A[k].mn) / (A[k].mx - A[k].mn), X = i => L + (W - L - R) * (n === 1 ? .5 : i / (n - 1));
  for (let v = A.l.mn; v <= A.l.mx + 1e-9; v += A.l.st) { const y = Y(v, 'l'); svg.append(sv('line', { x1: L, x2: W - R, y1: y, y2: y, stroke: 'var(--grid)' }), sv('text', { x: L - 6, y: y + 3.5, class: 'ax', 'text-anchor': 'end' }, (o.fl || fmt)(v))); }
  if (A.r) for (let v = A.r.mn; v <= A.r.mx + 1e-9; v += A.r.st) svg.append(sv('text', { x: W - R + 6, y: Y(v, 'r') + 3.5, class: 'ax', 'text-anchor': 'start' }, (o.fr || fmt)(v)));
  const step = Math.max(1, Math.ceil(n / (isMob() ? 5 : 8))); o.x.forEach((l, i) => { if (i % step === 0 || i === n - 1) svg.append(sv('text', { x: X(i), y: H - 7, class: 'ax', 'text-anchor': 'middle' }, l)); });
  (o.hl || []).forEach(x => { const k = x.axis || 'l', y = Y(x.v, k); svg.append(sv('line', { x1: L, x2: W - R, y1: y, y2: y, stroke: x.c, 'stroke-width': 1.4, 'stroke-dasharray': '6 4' }), sv('text', { x: W - R - 4, y: y - 5, class: 'ax', fill: x.c, 'text-anchor': 'end' }, x.label)); });
  o.series.forEach(s => { const k = s.axis || 'l', pts = s.d.map((v, i) => v == null ? null : [X(i), Y(v, k)]).filter(Boolean); if (s.area) svg.append(sv('path', { d: 'M' + pts.map(p => p.join(' ')).join('L') + `L${pts[pts.length - 1][0]} ${H - B}L${pts[0][0]} ${H - B}Z`, fill: areaGrad(svg, s.c, .34) }));
    svg.append(sv('path', { d: pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(''), fill: 'none', stroke: s.c, 'stroke-width': 2.2, 'stroke-dasharray': s.dash ? '6 4' : null, class: s.dash ? '' : 'draw' }));
    if (n <= 14) s.d.forEach((v, i) => { if (v != null) svg.append(sv('circle', { cx: X(i), cy: Y(v, k), r: o.partial && i === n - 1 ? 3.6 : 2.8, fill: o.partial && i === n - 1 ? 'var(--bg)' : s.c, stroke: s.c, 'stroke-width': 1.6 })); }); });
  beautify(svg, { W, H, L, R, T, B }); wrap.append(svg); attachHover(wrap, svg, W, H, L, R, n, X, i => `<b>${o.x[i]}${o.partial && i === n - 1 ? ' (일부 기간)' : ''}</b>` + o.series.map(s => s.d[i] == null ? '' : `<div><i class="dot" style="background:${s.c}"></i>${s.n} <b>${(s.f || fmt)(s.d[i])}${s.u || ''}</b></div>`).join(''));
  return h('div', {}, legend(o.series.map(s => ({ n: s.n, c: s.c, dash: s.dash })).concat((o.hl || []).map(x => ({ n: x.label, c: x.c, dash: true })))), wrap);
}
// 막대: 누적/발산 지원. items[{label, parts:[{v,c,n}]}], diverge=true이면 0 기준 ±
function barChart(o) {
  const W = isMob() ? 380 : 640, H = o.h || 220, L = isMob() ? 40 : 46, R = 10, T = 14, B = 34, n = o.items.length, wrap = h('div', { class: 'cwrap' }), svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart' });
  const tot = it => sumA(it.parts.map(p => p.v)), pos = o.diverge ? Math.max(1, ...o.items.map(tot)) : Math.max(...o.items.map(tot)), neg = o.diverge ? Math.min(0, ...o.items.map(tot)) : 0;
  const nz = nice(Math.max(pos, Math.abs(neg)) * 1.1, 4), mx = nz.max, mn = o.diverge ? -nz.max : 0, Y = v => T + (H - T - B) * (mx - v) / (mx - mn);
  for (let v = mn; v <= mx + 1e-9; v += nz.step) svg.append(sv('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: v === 0 ? 'var(--mut)' : 'var(--grid)', 'stroke-width': v === 0 ? 1.2 : 1 }), sv('text', { x: L - 6, y: Y(v) + 3.5, class: 'ax', 'text-anchor': 'end' }, fmt(v)));
  const bw = (W - L - R) / n; o.items.forEach((it, i) => { let y0 = o.diverge ? 0 : 0; const x = L + i * bw + bw * .2, w = bw * .6;
    if (o.diverge) { const v = tot(it); svg.append(sv('rect', { x, y: Math.min(Y(0), Y(v)), width: w, height: Math.abs(Y(v) - Y(0)), rx: 2, fill: o.col ? o.col(it) : it.parts[0].c, class: 'bar', style: `animation-delay:${i * 40}ms` })); svg.append(sv('text', { x: x + w / 2, y: v >= 0 ? Y(v) - 4 : Y(v) + 11, class: 'ax', 'text-anchor': 'middle' }, (v > 0 ? '+' : '') + fmt(v))); }
    else { let acc = 0; it.parts.forEach(p => { const y1 = Y(acc + p.v), y2 = Y(acc); svg.append(sv('rect', { x, y: y1, width: w, height: Math.max(0, y2 - y1), fill: p.c, class: 'bar', style: `animation-delay:${i * 40}ms`, rx: 1 })); acc += p.v; }); if (o.total) svg.append(sv('text', { x: x + w / 2, y: Y(acc) - 4, class: 'ax', 'text-anchor': 'middle' }, o.total(it))); }
    svg.append(sv('text', { x: x + w / 2, y: H - 20, class: 'ax', 'text-anchor': 'middle' }, it.label), it.sub ? sv('text', { x: x + w / 2, y: H - 8, class: 'ax sub', 'text-anchor': 'middle' }, it.sub) : ''); });
  beautify(svg, { W, H, L, R, T, B }); wrap.append(svg); attachHover(wrap, svg, W, H, L, R, n, i => L + i * bw + bw * .5, i => `<b>${o.items[i].label}</b>` + (o.tipx ? o.tipx(o.items[i]) : o.items[i].parts.map(p => `<div><i class="dot" style="background:${p.c}"></i>${p.n} <b>${fmt(p.v, 1)}</b></div>`).join('')));
  return h('div', {}, o.legend ? legend(o.legend) : '', wrap);
}
// 예측 차트(주식/Azure 비용 예측 형태): 실선=지금까지, 점선=예상, 음영=80% 예상 범위, 가로선=목표/예산
function forecastChart(f, unit, fmtv, hOv, wide) {
  const W = hOv ? (wide || hOv < 200 ? 620 : 430) : isMob() ? 400 : 760, H = hOv || (isMob() ? 280 : 300), L = isMob() ? 44 : 58, R = 18, T = 14, B = 30, n = f.days.length, wrap = h('div', { class: 'cwrap' }), svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart' });
  const vals = f.act.concat(f.proj, f.hi).filter(v => v != null).concat([f.tgt]), nz = nice(Math.max(...vals) * 1.06, 5), mx = nz.max, X = i => L + (W - L - R) * i / (n - 1), Y = v => H - B - (H - T - B) * v / mx;
  for (let v = 0; v <= mx + 1e-9; v += nz.step) svg.append(sv('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }), sv('text', { x: L - 6, y: Y(v) + 3.5, class: 'ax', 'text-anchor': 'end' }, fmtv(v)));
  const dl = i => new Date(Date.UTC(2026, 0, 1) + f.days[i] * 864e5).getUTCDate() + '일';
  for (let i = 0; i < n; i += Math.ceil(n / (isMob() ? 6 : 11))) svg.append(sv('text', { x: X(i), y: H - 8, class: 'ax', 'text-anchor': 'middle' }, dl(i)));
  const ti = f.days.indexOf(D.TODAY), idx = f.days.map((_, i) => i), up = idx.filter(i => f.hi[i] != null), lw = idx.filter(i => f.lo[i] != null);
  if (up.length > 1) svg.append(sv('path', { d: 'M' + up.map(i => X(i) + ' ' + Y(f.hi[i])).join('L') + 'L' + lw.slice().reverse().map(i => X(i) + ' ' + Y(f.lo[i])).join('L') + 'Z', fill: 'var(--cy)', opacity: .16 }));
  svg.append(sv('line', { x1: L, x2: W - R, y1: Y(f.tgt), y2: Y(f.tgt), stroke: 'var(--rd)', 'stroke-width': 1.6, 'stroke-dasharray': '7 4' }), sv('text', { x: L + 6, y: Y(f.tgt) - 6, class: 'ax', fill: 'var(--rd)', 'text-anchor': 'start' }, (f.kind === 'cost' ? '이달 예산 ' : '이달 한도 ') + fmtv(f.tgt) + unit));
  svg.append(sv('line', { x1: X(0), y1: Y(0), x2: X(n - 1), y2: Y(f.tgt), stroke: 'var(--mut)', 'stroke-width': 1, 'stroke-dasharray': '2 4', opacity: .8 }));
  svg.append(sv('line', { x1: X(ti), x2: X(ti), y1: T, y2: H - B, stroke: 'var(--yl)', 'stroke-width': 1.2, 'stroke-dasharray': '3 3' }), sv('text', { x: X(ti) + 4, y: H - B - 6, class: 'ax', fill: 'var(--yl)' }, '기준일 20일'));
  const ap = idx.filter(i => f.act[i] != null), pp = idx.filter(i => f.proj[i] != null);
  svg.append(sv('path', { d: 'M' + ap.map(i => X(i).toFixed(1) + ' ' + Y(f.act[i]).toFixed(1)).join('L') + `L${X(ap[ap.length - 1]).toFixed(1)} ${H - B}L${X(ap[0]).toFixed(1)} ${H - B}Z`, fill: areaGrad(svg, 'var(--cy)', .38) }));
  svg.append(sv('path', { d: 'M' + ap.map(i => X(i).toFixed(1) + ' ' + Y(f.act[i]).toFixed(1)).join('L'), fill: 'none', stroke: 'var(--cy)', 'stroke-width': 2.6, class: 'draw' }));
  svg.append(sv('path', { d: 'M' + pp.map(i => X(i).toFixed(1) + ' ' + Y(f.proj[i]).toFixed(1)).join('L'), fill: 'none', stroke: 'var(--cy)', 'stroke-width': 2.4, 'stroke-dasharray': '7 5' }));
  { const lc = f.level === 'ok' ? 'var(--gr)' : f.level === 'wn' ? 'var(--yl)' : 'var(--rd)'; svg.append(sv('circle', { cx: X(ti), cy: Y(f.act[ti]), r: 10, fill: 'var(--cy)', opacity: .22 }), sv('circle', { cx: X(n - 1), cy: Y(f.est), r: 10, fill: lc, opacity: .22 })); }
  svg.append(sv('circle', { cx: X(ti), cy: Y(f.act[ti]), r: 4.5, fill: 'var(--cy)', stroke: 'var(--bg)', 'stroke-width': 2 }), sv('circle', { cx: X(n - 1), cy: Y(f.est), r: 4.5, fill: f.level === 'ok' ? 'var(--gr)' : f.level === 'wn' ? 'var(--yl)' : 'var(--rd)', stroke: 'var(--bg)', 'stroke-width': 2 }));
  svg.append(sv('text', { x: X(n - 1) - 8, y: Math.max(T + 10, Math.min(Y(f.est), Y(f.tgt)) - 9), class: 'ax big', 'text-anchor': 'end' }, '월말 예상 ' + fmtv(f.est) + unit));
  beautify(svg, { W, H, L, R, T, B }); wrap.append(svg); attachHover(wrap, svg, W, H, L, R, n, X, i => `<b>${new Date(Date.UTC(2026, 0, 1) + f.days[i] * 864e5).toISOString().slice(5, 10)}</b>` + (f.act[i] != null ? `<div><i class="dot" style="background:var(--cy)"></i>누적 실적 <b>${fmtv(f.act[i])}${unit}</b></div>` : `<div><i class="dot" style="background:var(--cy)"></i>예상 누적 <b>${fmtv(f.proj[i])}${unit}</b></div><div class="mut">범위 ${fmtv(f.lo[i])}~${fmtv(f.hi[i])}${unit}</div>`) + `<div class="mut">계획선 ${fmtv(f.tgt * i / (n - 1))}${unit}</div>`);
  return h('div', {}, legend([{ n: '지금까지(실적)', c: 'var(--cy)' }, { n: '예상', c: 'var(--cy)', dash: true }, { n: '80% 예상 범위', c: 'var(--cy)' }, { n: f.kind === 'cost' ? '이달 예산' : '이달 한도', c: 'var(--rd)', dash: true }, { n: '기준일', c: 'var(--yl)', dash: true }]), wrap);
}
function spark(vals, c) { const W = 90, H = 26, mn = Math.min(...vals), mx = Math.max(...vals), X = i => 2 + (W - 4) * i / (vals.length - 1), Y = v => H - 3 - (H - 6) * (v - mn) / ((mx - mn) || 1); return sv('svg', { viewBox: `0 0 ${W} ${H}`, class: 'spark' }, sv('path', { d: vals.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(''), fill: 'none', stroke: c, 'stroke-width': 1.8 }), sv('circle', { cx: X(vals.length - 1), cy: Y(vals[vals.length - 1]), r: 2.4, fill: c })); }
function heatmap(rows) { const t = h('div', { class: 'heat' }); t.append(h('span'), ...Array.from({ length: 12 }, (_, i) => h('span', { class: 'hh' }, i * 2 + '시'))); rows.forEach(r => { t.append(h('span', { class: 'hl' }, r.n)); for (let c = 0; c < 12; c++) { const v = Math.round((r.v[c * 2] + r.v[c * 2 + 1]) / 2); t.append(h('span', { class: 'hc', style: `background:color-mix(in srgb,var(--cy) ${Math.round(v * .85)}%,transparent)`, title: r.n + ' ' + c * 2 + '시 ' + v + '%' }, v)); } }); return t; }
