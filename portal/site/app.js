'use strict';
// AMA 웹 초안(디자인 시안 기반). 모든 자료는 모의 자료이며 실제 운영과 연결되어 있지 않습니다.
const MENUS = [['overview','종합 관제','&#8962;'],['plants','공장 운영','&#127981;'],['calc','산정 결과','&#128202;'],['sim','시뮬레이션','&#128200;'],['proc','조달·승인','&#128196;'],['cust','고객 탄소정보','&#128101;'],['audit','증빙·감사','&#128737;'],['know','지식 검색','&#128211;'],['agents','에이전트 관리','&#129302;'],['factory','공장 VM 현장','&#128225;'],['flow','데이터 흐름','&#9889;']];
const TITLES = {overview:'Asia Plant Control Center',plants:'공장 운영',calc:'산정 결과',sim:'시뮬레이션',proc:'조달·승인',cust:'고객 탄소정보',audit:'증빙·감사',know:'지식 검색',agents:'에이전트 관리',factory:'공장 VM 현장',flow:'데이터 흐름'};
const MON = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월'];
const EM = [105,121,146,150,182,195,225,280,238,231], CO = [38,48,55,60,88,92,110,142,108,106];
const $ = (s, r = document) => r.querySelector(s);
const h = (t, a = {}, ...c) => { const e = document.createElement(t); for (const k in a) { if (a[k] == null || a[k] === false) continue; k === 'html' ? e.innerHTML = a[k] : e.setAttribute(k, a[k]); } c.flat().forEach(x => e.append(x)); return e; };
const NS = 'http://www.w3.org/2000/svg';
const sv = (t, a = {}, ...c) => { const e = document.createElementNS(NS, t); const vs = []; for (const k in a) { const v = a[k]; if (v == null) continue; (typeof v === 'string' && v.startsWith('var(') && (k === 'fill' || k === 'stroke')) ? vs.push([k, v]) : e.setAttribute(k, v); } vs.forEach(([k, v]) => e.style[k] = v); c.flat().forEach(x => e.append(x)); return e; };
const card = (title, tag, ...body) => h('div', { class: 'card' }, h('h3', {}, h('span', { html: title }), tag ? h('span', { class: 'tag' }, tag) : ''), ...body);
function kpi(icon, label, value, unit, sub, cls = '', tagText = '예시') {
  const v = h('div', { class: 'v' }, h('span', { class: 'num' }, value), h('span', { class: 'u' }, unit ? ' ' + unit : ''));
  const kc = h('div', { class: 'card kpi ' + cls }, h('div', { class: 's' }, h('span', { class: 'ic tn-' + tone(icon), html: ico(icon) }), label, ' ', tagText ? h('span', { class: 'tag' }, tagText) : ''), v, h('div', { class: 's' }, sub)); kc.setAttribute('tabindex', '0'); kc.setAttribute('role', 'button'); kc.setAttribute('aria-pressed', 'false'); const tg = () => { kc.classList.toggle('sel'); kc.setAttribute('aria-pressed', kc.classList.contains('sel')); }; kc.addEventListener('click', tg); kc.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tg(); } }); return kc;
}
function countUp(root) {
  if (document.documentElement.classList.contains('static')) return;
  root.querySelectorAll('.num').forEach(n => {
    const raw = n.textContent, m = raw.replace(/,/g, '').match(/^-?\d+(\.\d+)?$/); if (!m) return;
    const to = parseFloat(m[0]), dec = (m[1] || '').length - (m[1] ? 1 : 0), t0 = performance.now();
    const step = t => { const p = Math.min(1, (t - t0) / 700); const v = to * (1 - Math.pow(1 - p, 3)); n.textContent = v.toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec }); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}
function line(series, opts = {}) {
  const W = 520, H = opts.h || 190, L = 36, R = 36, T = 14, B = 24, n = series[0].d.length;
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%' });
  [0, 1, 2, 3].forEach(i => { const y = T + (H - T - B) * i / 3; svg.append(sv('line', { x1: L, x2: W - R, y1: y, y2: y, stroke: 'var(--grid)' })); });
  const X = i => L + (W - L - R) * i / (n - 1);
  series.forEach((s, k) => {
    const mx = Math.max(...s.d) * 1.15, Y = v => H - B - (H - T - B) * v / mx;
    svg.append(sv('path', { d: s.d.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(' '), fill: 'none', stroke: s.c, 'stroke-width': 2.2, class: 'draw' }));
    s.d.forEach((v, i) => { if (n <= 12) svg.append(sv('circle', { cx: X(i), cy: Y(v), r: 2.8, fill: s.c })); });
    svg.append(sv('text', { x: k ? W - R + 4 : 2, y: T + 4, fill: s.c, 'font-size': 10 }, s.n));
  });
  (opts.labels || MON).forEach((l, i) => { if (n <= 12 || i % 4 === 0) svg.append(sv('text', { x: X(i), y: H - 6, fill: 'var(--mut)', 'font-size': 10, 'text-anchor': 'middle' }, l)); });
  return svg;
}
function bars(vals, labels, colors, opts = {}) {
  const W = 520, H = opts.h || 170, L = 30, B = 22, T = 8, n = vals.length, mx = Math.max(...vals) * 1.12, bw = (W - L) / n;
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%' });
  vals.forEach((v, i) => { const bh = (H - B - T) * v / mx, x = L + i * bw + bw * 0.18;
    svg.append(sv('rect', { x, y: H - B - bh, width: bw * 0.64, height: bh, rx: 3, fill: colors[i % colors.length], class: 'bar', style: `animation-delay:${i * 60}ms` }));
    svg.append(sv('text', { x: x + bw * 0.32, y: H - 8, fill: 'var(--mut)', 'font-size': 9, 'text-anchor': 'middle' }, labels[i])); });
  return svg;
}
function donut(parts) {
  const svg = sv('svg', { viewBox: '0 0 120 120', width: 150 }); let a0 = -Math.PI / 2; const tot = parts.reduce((s, p) => s + p.v, 0);
  parts.forEach(p => { const a1 = a0 + 2 * Math.PI * p.v / tot, large = a1 - a0 > Math.PI ? 1 : 0, f = (r, a) => `${60 + r * Math.cos(a)} ${60 + r * Math.sin(a)}`;
    svg.append(sv('path', { d: `M${f(50, a0)} A50 50 0 ${large} 1 ${f(50, a1)} L${f(30, a1)} A30 30 0 ${large} 0 ${f(30, a0)}Z`, fill: p.c })); a0 = a1; });
  svg.append(sv('text', { x: 60, y: 64, fill: 'var(--txt)', 'font-size': 14, 'text-anchor': 'middle', 'font-weight': 700 }, '286.4')); return svg;
}
const badge = (t, c) => h('span', { class: 'b ' + c }, t);
function table(head, rows, num = []) {
  return h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, head.map((x, i) => h('th', { class: num.includes(i) ? 'n' : '' }, x)))), h('tbody', {}, rows.map(r => h('tr', {}, r.map((c, i) => h('td', { class: num.includes(i) ? 'n' : '' }, c))))));
}
const V = {};
V.calc = () => {
  const root = h('div', { class: 'view' });
  root.append(h('div', { class: 'row r4' }, kpi('&#128293;', '직접 배출 (Scope 1)', '86.4', 'tCO₂', '12.1%'), kpi('&#9889;', '간접 배출 (Scope 2)', '200.0', 'tCO₂', '지역 기반'), kpi('&#8721;', '선택 기준 합계', '286.4', 'tCO₂', '시장 기반 병행'), kpi('&#128221;', '산정 상태', '초안', '', '계수 버전 EF-2026.1', 'warn')));
  root.append(h('div', { class: 'row r2' }, card('월별 배출 추이 (KR-01)', '예시', bars(EM.map(v => v * .24), MON, ['var(--cy)', 'var(--gr)'])), card('배출 구성', '예시', h('div', { style: 'display:flex;gap:14px;align-items:center;flex-wrap:wrap' }, donut([{ v: 86.4, c: 'var(--yl)' }, { v: 200, c: 'var(--cy)' }]), h('div', { class: 'list' }, h('span', { html: '<i class="dot" style="background:var(--yl)"></i>직접 30.2%' }), h('span', { html: '<i class="dot" style="background:var(--cy)"></i>간접 69.8%' }))))));
  root.append(card('배출 결과 (KR-01)', '예시 · 초안', table(['구분', '활동량', '단위', '계수', '계수 버전', '배출량(tCO₂)'], [['고정 연소', '12,400', 'GJ', '0.0561', 'EF-2026.1', '69.6'], ['이동 연소', '240', 'kL', '2.31', 'EF-2026.1', '16.8'], ['구입 전력', '412,000', 'kWh', '0.4781', 'EF-2026.1', '197.0'], ['구입 열', '3,100', 'GJ', '0.0642', 'EF-2026.1', '3.0']], [1, 3, 5])));
  return root;
};
V.sim = () => {
  const root = h('div', { class: 'view' }), st = { g: 10, p: 15, f: 5 };
  const out = h('div', {});
  const calc = () => { const em = 261 * (1 - st.g / 100 * .4 - st.f / 100 * .3), cs = 1.82 * (1 + st.p / 100 * .2 - st.g / 100 * .1);
    out.replaceChildren(h('div', { class: 'row r3' }, kpi('&#127807;', '예상 배출', em.toFixed(1), 'tCO₂', '가정 기반 · 미검증'), kpi('&#128178;', '예상 에너지 비용', cs.toFixed(2), '억 원', '가정 기반'), kpi('&#128190;', '대안 상태', '검토 요청 전', '', '저장·검토 요청만 가능 (실행 불가)', 'warn')),
      h('div', { style: 'margin-top:10px' }, bars([261, +em.toFixed(1), +(261 * .97).toFixed(1), +(261 * .93).toFixed(1)], ['기준', '현재 가정', '피크 10%↓', '전환 20%'], ['var(--dl)', 'var(--cy)', 'var(--yl)', 'var(--pu)']))); };
  const sl = (k, lb, mn, mx) => { const o = h('span', {}, st[k] + '%'); const i = h('input', { type: 'range', min: mn, max: mx, value: st[k] }); i.addEventListener('input', () => { st[k] = +i.value; o.textContent = st[k] + '%'; calc(); }); return h('div', { class: 'slider' }, h('span', {}, lb), i, o); };
  root.append(h('div', { class: 'row r2' }, card('시나리오 가정 (예시)', '미검증', sl('g', '재생에너지 비중', 0, 40), sl('p', '피크 시간 사용', 0, 30), sl('f', '연료 전환', 0, 30), h('div', { style: 'display:flex;gap:8px;margin-top:8px' }, h('button', {}, '시나리오 저장'), h('button', {}, '검토 요청'), h('button', { disabled: 'disabled' }, '실행 (비활성)'))), card('시나리오 결과', '가정 · 예상 · 미검증', out)));
  calc(); return root;
};
V.proc = () => {
  const root = h('div', { class: 'view' });
  root.append(h('div', { class: 'row r4' }, kpi('&#128202;', '조달 필요 (예시 합계)', '480,000', 'kWh', '월 기준'), kpi('&#9989;', '확정 커버리지', '71.4', '%', '확정 계약 기준'), kpi('&#128176;', '예상 비용', '6.84', '억 원', '모의'), kpi('&#9203;', '승인 대기', '3', '건', '직무 분리 적용', 'warn')));
  root.append(h('div', { class: 'row r2' }, card('월별 조달 커버리지 (예시)', '예시', bars([62, 66, 70, 72, 68, 74, 71, 78, 73, 71], MON, ['var(--cy)', 'var(--gr)'])),
    card('승인 요청 목록', '예시', table(['요청', '내용', '금액', '상태'], [['REQ-021', 'REC 구매 10,000', '₩ 38M', badge('검토 중', 'wn')], ['REQ-022', '전력 PPA 연장', '₩ 120M', badge('승인 대기', 'dr')], ['REQ-023', '탄소배출권', '₩ 54M', badge('요청 생성', 'in')]], [2]), h('div', { style: 'margin-top:10px;display:flex;gap:8px;align-items:center' }, h('button', { disabled: 'disabled' }, '제한 실행 (비활성)'), h('span', { class: 'tag' }, '거래 시스템 미연결 · 승인 후에도 이 화면에서는 실행되지 않습니다')))));
  return root;
};
V.cust = () => {
  const root = h('div', { class: 'view' });
  root.append(h('div', { class: 'row r4' }, kpi('&#128230;', '제품 수', '12', '종', '선언 단위 1 kg'), kpi('&#129534;', '공개 승인', '3', '건', '초안 → 승인 대기'), kpi('&#128226;', '고객 전송', '0', '건', '비활성 (시안)', 'warn'), kpi('&#128337;', '다음 마감', '5', '일', '2026.11.05')));
  root.append(h('div', { class: 'row r2' }, card('제품 목록', '예시', table(['제품 ID', '제품명', '선언 단위', '탄소발자국(kgCO₂e)', '상태'], [['P-101', '냉연 강판', '1 kg', '1.92', badge('초안', 'dr')], ['P-102', '도금 강판', '1 kg', '2.31', badge('초안', 'dr')], ['P-104', '고강도 강판', '1 kg', '2.84', badge('검토', 'wn')], ['P-110', '화학 소재 A', '1 kg', '1.14', badge('승인 대기', 'in')]], [3])),
    card('선택 제품 · P-104 고강도 강판', '예시', h('div', { class: 'kv' }, h('span', {}, '탄소발자국'), h('span', {}, '2.84 kgCO₂e / kg'), h('span', {}, '산정 경계'), h('span', {}, '요람~공장 문'), h('span', {}, '배분 방법'), h('span', {}, '질량 배분'), h('span', {}, '공개 승인'), h('span', {}, '승인 후 열람 가능')), h('div', { class: 'steps', style: 'margin-top:10px' }, ['초안', '검토', '공개 승인', '전송'].map((s, i) => h('div', { class: 'st' + (i < 2 ? ' on' : '') }, (i + 1) + '. ' + s))))));
  return root;
};
V.audit = () => {
  const root = h('div', { class: 'view' });
  root.append(h('div', { class: 'row r4' }, kpi('&#128193;', '증빙 문서', '248', '건', ''), kpi('&#9989;', '검증 완료율', '75.0', '%', ''), kpi('&#9203;', '무결성 검토 대기', '18', '건', '', 'warn'), kpi('&#128221;', '감사 기록', '20', '건', '추가 기록형 (개념 표기)')));
  root.append(h('div', { class: 'row r2' }, card('증빙 목록', '예시', table(['문서', '버전', '국가', '상태', '체크섬'], [['CALC-026 근거', 'v3', '한국', badge('검증', 'ok'), 'a1f3…9c'], ['전력 청구서 10월', 'v1', '한국', badge('검토', 'wn'), '7be0…21'], ['공장 계량 기록', 'v2', '일본', badge('검증', 'ok'), 'c92d…ff'], ['배출계수 표', 'v1', '공통', badge('초안', 'dr'), '03aa…5e']])),
    card('근거 흐름 · CALC-026', '예시', h('div', { class: 'steps' }, ['측정 자료', '변환·검증', '산정', '승인'].map((s, i) => h('div', { class: 'st on' }, h('div', {}, (i + 1)), s))), h('div', { style: 'margin-top:10px' }, table(['시각', '행위', '대상'], [['10-28 09:12', '증빙 추가', 'CALC-026'], ['10-28 09:40', '검토 요청', 'CALC-026'], ['10-28 10:05', '승인', 'CALC-026']])))));
  return root;
};
function go(keep) {
  const K = keep === true, key = (location.hash || '#overview').slice(1).split('?')[0]; const k = V[key] ? key : 'overview', y = window.scrollY;
  $('#title').textContent = TITLES[k]; document.title = 'AMA · ' + TITLES[k] + ' (디자인 시안)';
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.k === k));
  const v = $('#view'); document.documentElement.classList.toggle('nofx', K); if (K) v.style.minHeight = v.offsetHeight + 'px'; v.replaceChildren(window.AUTHZ && !window.AUTHZ(k) ? window.DENIED(k) : V[k]()); if (!K) countUp(v); window.scrollTo(0, K ? y : 0); if (K) requestAnimationFrame(() => { v.style.minHeight = ''; }); if (window.afterGo) window.afterGo(k);
}
MENUS.forEach(([k, t, i]) => $('#nav').append(h('a', { href: '#' + k, 'data-k': k, html: `<span class="ni">${ico(i)}</span><span>${t}</span>` })));
window.addEventListener('hashchange', () => go());
