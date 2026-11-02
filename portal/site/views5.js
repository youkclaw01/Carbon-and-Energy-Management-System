'use strict';
// 화면 스킨 페이지: 계열별 스킨 카드(미리보기)와 표시 옵션
TITLES.skin = '화면 스킨';
function skinPreview(sk) {
  const v = sk.id === 'midnight' ? SKINS.vars(sk) : SKINS.vars(sk), s = sk.s, L = sk.m === 'light';
  const svg = sv('svg', { viewBox: '0 0 160 90', class: 'pv', preserveAspectRatio: 'none' });
  const R = (x, y, w, h2, f, rx = 3, st) => sv('rect', { x, y, width: w, height: h2, rx, fill: f, stroke: st || 'none', 'stroke-width': .6 });
  svg.append(R(0, 0, 160, 90, v['--bg'], 0), R(0, 0, 30, 90, v['--side1'], 0, v['--line']));
  [10, 22, 34].forEach((y, i) => svg.append(R(6, y, 18, 6, i === 0 ? v['--navon2'] : v['--row'], 3, i === 0 ? v['--navonb'] : null)));
  svg.append(R(36, 6, 60, 7, v['--txt'], 3), R(98, 6, 56, 7, v['--row'], 3));
  [[36, 18], [76, 18], [116, 18]].forEach(([x, y], i) => { svg.append(R(x, y, 38, 24, v['--card1'], 4, v['--line'])); svg.append(R(x + 4, y + 5, 14, 3, v['--mut'], 1.5), R(x + 4, y + 11, 22, 6, i === 2 ? v['--rd'] : v['--txt'], 2), R(x + 4, y + 20, 30, 2, v['--row'], 1), R(x + 4, y + 20, [20, 14, 28][i], 2, [s.ok, s.ac, s.bd][i], 1)); });
  svg.append(R(36, 48, 74, 38, v['--card1'], 4, v['--line']), R(114, 48, 40, 38, v['--card1'], 4, v['--line']));
  [10, 16, 12, 22, 18, 26, 20].forEach((hh, i) => svg.append(R(42 + i * 9.5, 82 - hh, 6, hh, i % 3 === 1 ? s.ac : mix2(s.ac, v['--card1']), 1.5)));
  svg.append(sv('circle', { cx: 134, cy: 67, r: 12, fill: 'none', stroke: v['--row'], 'stroke-width': 5 }), sv('circle', { cx: 134, cy: 67, r: 12, fill: 'none', stroke: s.ac, 'stroke-width': 5, 'stroke-dasharray': '46 76', transform: 'rotate(-90 134 67)' }));
  return svg;
}
function mix2(a, b) { const f = c => { c = c.replace('#', ''); return [0, 2, 4].map(i => parseInt(c.substr(i, 2), 16)); }, x = f(a), y = f(b); return '#' + x.map((n, i) => Math.round(n * .55 + y[i] * .45).toString(16).padStart(2, '0')).join(''); }
V.skin = () => {
  const cur = SKINS.current(), root = h('div', { class: 'view' });
  const mk = sk => { const c = h('button', { type: 'button', class: 'skc' + (sk.id === cur ? ' on' : ''), 'data-own': 1, 'data-skin': sk.id, 'aria-pressed': sk.id === cur ? 'true' : 'false' }, skinPreview(sk), h('div', { class: 'nm' }, h('span', {}, sk.n), h('span', { class: 'tg' }, sk.id === cur ? '사용 중' : '적용')), h('div', { class: 'ds' }, sk.d));
    c.addEventListener('click', () => { SKINS.apply(sk.id); syncSkinBtn(); go(); }); return c; };
  const dark = SKINS.list.filter(x => x.m === 'dark'), light = SKINS.list.filter(x => x.m === 'light');
  root.append(h('div', { class: 'card' }, h('h3', {}, '화면 스킨', h('span', { class: 'badge in' }, '선택 저장')), h('div', { class: 'mut small' }, '업무 환경과 취향에 맞는 색상 구성을 선택합니다. 선택은 이 브라우저에 저장되며 모든 화면(지도·차트·표)에 즉시 적용됩니다.')));
  root.append(card('밝은 계열 (라이트)', String(light.length) + '종', h('div', { class: 'skgrid' }, light.map(mk))));
  root.append(card('어두운 계열 (다크)', String(dark.length) + '종', h('div', { class: 'skgrid' }, dark.map(mk))));
  const rd = h('div', { class: 'og' }, h('span', { class: 'mut' }, '모서리'), h('div', { class: 'seg' }, [['sharp', '각진'], ['normal', '보통'], ['round', '둥근']].map(([k, n]) => { const b = h('button', { type: 'button', 'data-own': 1, class: (localStorage.getItem('ama-radius') || 'normal') === k ? 'on' : '' }, n); b.addEventListener('click', () => { SKINS.radius(k); go(); }); return b; })));
  const mo = h('div', { class: 'og' }, h('span', { class: 'mut' }, '애니메이션'), h('div', { class: 'seg' }, [['on', '켜기'], ['off', '끄기']].map(([k, n]) => { const b = h('button', { type: 'button', 'data-own': 1, class: (localStorage.getItem('ama-motion') || 'on') === k ? 'on' : '' }, n); b.addEventListener('click', () => { SKINS.motion(k === 'on'); go(); }); return b; })));
  root.append(card('표시 옵션', '', h('div', { class: 'skopt' }, rd, mo)));
  return root;
};
function syncSkinBtn() { const b = document.getElementById('skinBtn'); if (!b) return; const sk = SKINS.get(SKINS.current()); const n = b.querySelector('.skn'); if (n) { n.dataset.ko = sk.n; n.textContent = sk.n; } }
syncSkinBtn(); window.addEventListener('skinchange', syncSkinBtn);
if (V[(location.hash || '#overview').slice(1).split('?')[0]] && (location.hash || '#overview').slice(1).split('?')[0] !== 'overview') go();
