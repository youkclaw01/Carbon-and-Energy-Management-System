'use strict';
// 상태·필터·종합 관제 화면. 모든 수치는 data.js의 모의 원천에서 계산합니다(저장하지 않음).
const ST = { ok: ['정상', 'ok'], wn: ['주의', 'wn'], er: ['경고', 'er'], dl: ['자료 지연', 'dl'], over: ['초과 예상', 'er'] };
const SC = { ok: 'var(--gr)', wn: 'var(--yl)', er: 'var(--rd)', dl: 'var(--dl)', over: 'var(--rd)' };
const S = { region: '전체 지역', pk: 'ytd', a: 0, b: D.TODAY, kpi: null, plant: 'KR-01', fc: null, fk: 'em', metric: 'em', rv: null, rvPlant: null, sort: { em: ['risk', -1], cost: ['risk', -1] }, contrib: 'share', role: null, pm: 'em', chat: {} };
const PL = () => D.P.filter(p => S.region === '전체 지역' || p.c === S.region);
const dlabel = i => D.ymd(i).slice(5).replace('-', '.');
const periodLabel = () => ((D.PRESETS.find(p => p[0] === S.pk) || [0, '사용자 지정'])[1]) + ' · ' + dlabel(S.a) + '~' + dlabel(S.b);
const hasToday = () => S.b === D.TODAY;
const stat = (id, kind) => D.status(id, S.a, S.b, kind);
const agg = (ids, a = S.a, b = S.b) => ({ em: sumA(ids.map(i => D.em(i, a, b))), s1: sumA(ids.map(i => D.sum(i, 's1', a, b))), s2: sumA(ids.map(i => D.sum(i, 's2', a, b))), co: sumA(ids.map(i => D.sum(i, 'co', a, b))), pw: sumA(ids.map(i => D.sum(i, 'pw', a, b))), pr: sumA(ids.map(i => D.sum(i, 'pr', a, b))), hr: sumA(ids.map(i => D.sum(i, 'hr', a, b))) });
const tgt = (ids, kind) => sumA(ids.map(i => D.target(i, S.a, S.b, kind)));
const E8 = v => v / 1e8, pct = (v, d = 0) => (v * 100).toFixed(d) + '%';
const rerender = () => go(true);
const stB = k => h('span', { class: 'b st-' + k }, ST[k][0]);
const openRV = () => D.RV.filter(r => r.st !== 'resolved' && (S.region === '전체 지역' || D.plant(r.plant).c === S.region));
const sevOrd = { er: 0, wn: 1, dl: 2, ok: 3 };
const MK = (k, x, y, r = 6) => k === 'wn' ? sv('path', { d: `M${x} ${y - r}l${r * 1.1} ${r * 1.9}h${-r * 2.2}z`, fill: 'var(--yl)' }) : k === 'dl' ? sv('rect', { x: x - r * .85, y: y - r * .85, width: r * 1.7, height: r * 1.7, rx: 2, fill: 'var(--dl)' }) : k === 'er' ? sv('path', { d: `M${x} ${y - r * 1.1}l${r * 1.1} ${r * 1.1}l${-r * 1.1} ${r * 1.1}l${-r * 1.1} ${-r * 1.1}z`, fill: 'var(--rd)' }) : sv('circle', { cx: x, cy: y, r, fill: 'var(--gr)' });
const ubar = (u, big) => h('div', { class: 'ubar' + (big ? ' big' : '') }, h('i', { style: `width:${Math.min(100, u * 100)}%;background:${SC[D.lvl(u)]}` }), h('s', { style: 'left:70%' }), h('s', { style: 'left:90%' }));
const scrollTo = () => {};   // 화면 위치 유지(요청: 클릭 시 아래로 이동하지 않음)
const seg = (items, cur, fn) => h('div', { class: 'seg', role: 'tablist' }, items.map(([k, t]) => { const b = h('button', { type: 'button', role: 'tab', class: k === cur ? 'on' : '', 'data-own': 1, 'aria-selected': k === cur }, t); b.addEventListener('click', () => fn(k)); return b; }));
const buckets = () => { const a = S.a, b = S.b, n = b - a + 1, out = []; if (n <= 31) for (let i = a; i <= b; i++) out.push({ a: i, b: i, label: dlabel(i), full: true }); else if (n <= 120) for (let i = a; i <= b; i += 7) { const e = Math.min(b, i + 6); out.push({ a: i, b: e, label: dlabel(i), full: e - i === 6 }); } else { let i = a; while (i <= b) { const m = D.mon(i), me = D.mfirst(i) + D.dim(m) - 1, e = Math.min(b, me); out.push({ a: i, b: e, label: (m + 1) + '월', full: e === me && i === D.mfirst(i) }); i = e + 1; } } return out; };
const METRIC = { em: ['배출', 'tCO₂', 'var(--gr)', (id, a, b) => D.em(id, a, b), v => fmt(v, 1)], co: ['비용', '억 원', 'var(--yl)', (id, a, b) => E8(D.sum(id, 'co', a, b)), v => fmt(v, 2)], pr: ['생산량', 't', 'var(--cy)', (id, a, b) => D.sum(id, 'pr', a, b), v => fmt(v, 0)], pw: ['전력', 'MWh', 'var(--pu)', (id, a, b) => D.sum(id, 'pw', a, b), v => fmt(v, 0)] };

// ---- KPI 카드(단일 선택·선택 시 색 채움)
function kx(o) {
  const c = h('div', { class: 'card kx tn-' + o.tone + (S.kpi === o.key ? ' sel' : ''), tabindex: 0, role: 'button', 'aria-pressed': S.kpi === o.key, 'data-key': o.key },
    h('div', { class: 's' }, h('span', { class: 'ic', html: ico(o.icon) }), o.label, ' ', h('span', { class: 'tag' }, o.tag || '예시'), h('span', { class: 'chev' + (S.kpi === o.key ? ' open' : ''), 'aria-hidden': 'true' })),
    h('div', { class: 'v' }, h('span', { class: 'num' }, o.value), h('span', { class: 'u' }, o.unit ? ' ' + o.unit : '')), h('div', { class: 's sub' }, o.sub), o.extra || '');
  const go2 = () => { S.kpi = S.kpi === o.key ? null : o.key; if (S.kpi !== 'pl') S.plSel = false; else if (window.TWIN) { TWIN.reset(); S.plSel = false; } if (o.key === 'em') S.fk = 'em'; if (o.key === 'co') S.fk = 'cost'; if (S.kpi !== 'rv') S.rv = null; if (S.kpi !== 'em' && S.kpi !== 'co') S.fc = null; rerender(); if (S.kpi) scrollTo('sec'); };
  c.addEventListener('click', go2); c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go2(); } });
  return c;
}
const gauge = (u, txt, extra) => h('div', { class: 'gauge' }, ubar(u), h('div', { class: 'gt' }, txt), extra ? h('div', { class: 'gt mut' }, extra) : '');

// ---- 공장 표(배출/비용) → 행 선택 시 예측
function factoryTable(kind) {
  const ids = PL(), rows = ids.map(p => { const s = stat(p.id, kind), f = hasToday() ? D.forecast(p.id, kind) : null, dc = kind === 'cost' ? D.costDecomp(p.id, S.a, S.b) : null; return { p, s, f, dc, cur: kind === 'cost' ? E8(s.act) : s.act, risk: f ? f.ratio : s.usage, est: f ? (kind === 'cost' ? E8(f.est) : f.est) : -1 }; });
  const [sk, dir] = S.sort[kind]; const keyf = { id: r => r.p.id, cur: r => r.cur, use: r => r.s.usage, est: r => r.est, mom: r => r.s.mom == null ? -9 : r.s.mom, risk: r => r.risk, price: r => r.dc ? r.dc.price + r.dc.fx : 0 }[sk]; rows.sort((x, y) => { const a = keyf(x), b = keyf(y); return (a > b ? 1 : a < b ? -1 : 0) * dir; });
  const u = kind === 'cost' ? '억 원' : 'tCO₂', f2 = kind === 'cost' ? v => fmt(v, 2) : v => fmt(v, 1);
  const hasPrev = !!D.pm(S.a, S.b), cols = [['id', '공장'], ['cur', `현재(${u})`], ['use', kind === 'cost' ? '예산 대비' : '목표 대비'], ['est', `이번 달 예상(${u})`], ...(hasPrev ? [['mom', '직전 대비']] : []), ...(kind === 'cost' && hasPrev ? [['price', '단가·환율 영향']] : []), ['risk', '예측 상태']];
  const th = cols.map(([k, t]) => { const x = h('th', { class: (k ? 'sortable' + (k === sk ? ' on' : '') : '') + (k === 'id' || k === 'risk' ? '' : ' n'), 'data-own': 1 }, t + (k === sk ? (dir > 0 ? ' ▲' : ' ▼') : '')); if (k) x.addEventListener('click', () => { S.sort[kind] = [k, S.sort[kind][0] === k ? -S.sort[kind][1] : -1]; rerender(); }); return x; });
  const body = rows.map(r => { const lv = r.f ? r.f.level : r.s.level, mom = r.s.mom, tr = h('tr', { class: 'pick' + (S.fc === r.p.id ? ' on' : ''), tabindex: 0, 'data-own': 1 },
    h('td', {}, h('b', {}, r.p.id), ' ', h('span', { class: 'mut' }, r.p.site)), h('td', { class: 'n' }, f2(r.cur)), h('td', { class: 'n' }, ubar(r.s.usage), pct(r.s.usage), h('span', { class: 'mut' }, r.s.usage >= 1 ? ' · 초과 ' + pct(r.s.usage - 1) : ' · 여유 ' + pct(1 - r.s.usage))),     h('td', { class: 'n' }, r.f ? f2(r.est) + ' ' : '—', r.f ? h('span', { class: 'mut' }, '(' + pct(r.f.ratio) + ')') : ''), ...(hasPrev ? [h('td', { class: 'n ' + (mom != null && mom >= .1 ? 'up' : '') }, mom == null ? '—' : (mom >= 0 ? '+' : '') + (mom * 100).toFixed(1) + '%')] : []),
    ...(kind === 'cost' && hasPrev ? [h('td', { class: 'n' }, r.dc ? (r.dc.price + r.dc.fx >= 0 ? '+' : '') + fmt(E8(r.dc.price + r.dc.fx), 3) + '억' : '—')] : []), h('td', {}, r.f ? stB(lv) : h('span', { class: 'mut' }, '실적만'))); const pick = () => { S.fc = r.p.id; S.fk = kind; S.plant = r.p.id; rerender(); scrollTo('fcard'); }; tr.addEventListener('click', pick); tr.addEventListener('keydown', e => { if (e.key === 'Enter') pick(); }); return tr; });
  const note = hasPrev ? '' : h('p', { class: 'mnote' }, '올해 누적은 비교할 직전 동일 기간이 없어 "직전 대비" 열을 숨겼습니다. 증감은 기간을 "이번 달/최근 1개월/최근 3개월"로 바꾸면 표시됩니다.'), note0 = hasToday() ? '' : h('p', { class: 'mnote' }, `선택한 기간(${periodLabel()})이 이번 달을 포함하지 않아 예측 열은 비우고 실적만 표시합니다. 예측은 기간을 "이번 달/최근 1개월/최근 3개월/올해 누적"으로 두면 표시됩니다.`);
  return card(kind === 'cost' ? '에너지 비용 · 공장별 현황' : '배출 추정 · 공장별 현황', '예측·추정 · 모의', h('div', { class: 'tscroll' }, h('table', { class: 'tbl cmp', 'data-nomodal': 1 }, h('thead', {}, h('tr', {}, th)), h('tbody', {}, body))), note, note0, h('p', { class: 'mnote' }, '행을 누르면 아래에 해당 공장의 이번 달 예측이 열립니다. 열 제목을 누르면 정렬됩니다. 상태 기준: 70% 주의 · 90% 경고 · 100% 초과.'));
}

function fcExplain(id, kind, f, st) {
  const u = kind === 'cost' ? '억 원' : ' tCO₂', fv = kind === 'cost' ? (v => fmt(E8(v), 2)) : (v => fmt(v, 1)), lv = f.level, mom = st.mom;
  const sentences = [];
  if (lv === 'over' || lv === 'er') sentences.push(`이 추세면 월말 ${fv(f.est)}${u}${kind === 'cost' ? '으로' : '로'} ${kind === 'cost' ? '예산' : '한도'} ${fv(f.tgt)}${u}의 ${pct(f.ratio)}입니다.` + (f.crossMid ? ` ${new Date(Date.UTC(2026, 0, 1) + f.crossMid * 864e5).getUTCDate()}일경 ${kind === 'cost' ? '예산을' : '한도를'} 넘을 가능성이 있어 이번 달 문제가 예상됩니다.` : f.crossHi ? ` 중앙 예상은 한도 안이지만 상한 기준으로는 ${new Date(Date.UTC(2026, 0, 1) + f.crossHi * 864e5).getUTCDate()}일경 넘을 수 있어 주의가 필요합니다.` : ' 한도에 근접해 이번 달 문제가 예상됩니다.'));
  else if (lv === 'wn') sentences.push(`월말 예상은 ${fv(f.est)}${u}${kind === 'cost' ? '으로' : '로'} ${kind === 'cost' ? '예산' : '한도'}의 ${pct(f.ratio)}입니다. 한도 안이지만 70%를 넘어 여유가 ${pct(1 - f.ratio)}로 줄어 있어 추이를 지켜볼 필요가 있습니다.`);
  else sentences.push(`이번 달은 문제가 없을 것으로 예상됩니다. 월말 예상 ${fv(f.est)}${u}${kind === 'cost' ? '으로' : '로'} ${kind === 'cost' ? '예산' : '한도'}의 ${pct(f.ratio)}이며 여유가 ${pct(1 - f.ratio)}입니다.`);
  const concl = h('div', { class: 'concl lv-' + lv }, h('b', {}, lv === 'ok' ? '결론: 문제 없음' : lv === 'wn' ? '결론: 주의' : '결론: 이번 달 문제 예상'), h('p', {}, sentences.join(' ')));
  const basis = [`최근 14일 요일 보정 평균을 남은 ${f.daysLeft}일에 적용했습니다(최근 8주 요일 패턴 사용).`, `음영은 최근 28일 변동폭으로 계산한 80% 예상 범위입니다.`, `직전 동일 기간 대비 ${mom == null ? '—' : (mom >= 0 ? '+' : '') + (mom * 100).toFixed(1) + '%'}${mom != null && mom >= D.RULE.surge ? '로 급증 조건(+10%)에 해당합니다.' : '입니다.'}`, '단순 추세 기반 모의 예측이며 확정값이 아닙니다. 실제 예측 모델은 별도 설계 대상입니다.'];
  const dec = kind === 'cost' ? D.costDecomp(id, D.mfirst(D.TODAY), D.TODAY) : null;
  const decEl = dec ? h('div', { class: 'decomp' }, h('b', {}, `비용 변화 요인 (직전 동일 기간 대비 ${dec.delta >= 0 ? '+' : ''}${fmt(E8(dec.delta), 2)}억)`), [['사용량 변화', dec.usage], ['환율 영향', dec.fx], ['단가·시간대(피크) 영향', dec.price]].map(([n, v]) => h('div', { class: 'dr' }, h('span', {}, n), h('div', { class: 'db' }, h('i', { style: `width:${Math.min(100, Math.abs(v) / (Math.abs(dec.usage) + Math.abs(dec.fx) + Math.abs(dec.price) + 1) * 100)}%;background:${v >= 0 ? 'var(--yl)' : 'var(--gr)'}` })), h('b', {}, (v >= 0 ? '+' : '') + fmt(E8(v), 3) + '억')))) : '';
  const two = (h('div', { class: 'two' }, h('div', {}, h('b', {}, '예측 근거'), h('ul', { class: 'bl' }, basis.map(t => h('li', {}, t)))), decEl || h('div', {}, h('b', {}, '확인할 곳'), h('ul', { class: 'bl' }, ['공장 운영 → 시간대별 전력(피크)과 공정 부하', '설비 수신 상태(지연 설비가 있으면 추정이 부정확)', '확인 필요 목록의 관련 항목'].map(t => h('li', {}, t))))));
  return [concl, two];
}
// ---- 공장 예측 페이지(이번 달 문제 여부 예측)
function forecastCard(id, kind, inline, compact) {
  const p = D.plant(id), u = kind === 'cost' ? '억 원' : ' tCO₂', fv = kind === 'cost' ? (v => fmt(E8(v), 2)) : (v => fmt(v, 1)), root = h('div', { class: 'card' + (compact ? ' compact' : ''), id: 'fcard' });
  root.append(h('h3', {}, h('span', {}, `${id} · ${p.c} ${p.site} · 이번 달 ${kind === 'cost' ? '비용' : '배출'} 예측`), h('span', { class: 'tag' }, '예측·추정 · 모의')));
  root.append(seg([['em', '배출'], ['cost', '비용']], kind, k => { S.fk = k; rerender(); scrollTo('fcard'); }));
  if (!hasToday()) { root.append(h('p', { class: 'mnote' }, `선택한 기간(${periodLabel()})에는 이번 달이 포함되지 않아 예측 대신 실적 비교를 표시합니다.`)); return root; }
  const f = D.forecast(id, kind), st = D.status(id, D.mfirst(D.TODAY), D.TODAY, kind), lv = f.level, mom = st.mom;
  root.append(h('div', { class: 'row r4 mini' },
    h('div', { class: 'card mk' }, h('div', { class: 's' }, '현재 누적(이번 달)'), h('div', { class: 'v' }, fv(f.mtd), h('span', { class: 'u' }, u)), h('div', { class: 's sub' }, `기준일 10.20 · ${D.TODAY - f.a0 + 1}일 경과`)),
    h('div', { class: 'card mk' }, h('div', { class: 's' }, '현재 상태'), h('div', { class: 'v' }, stB(st.level)), h('div', { class: 's sub' }, st.why.slice(0, 2).join(' · '))),
    h('div', { class: 'card mk' }, h('div', { class: 's' }, '월말 예상'), h('div', { class: 'v' }, fv(f.est), h('span', { class: 'u' }, u)), h('div', { class: 's sub' }, `범위 ${fv(f.estLo)}~${fv(f.estHi)}${u}`)),
    h('div', { class: 'card mk' }, h('div', { class: 's' }, kind === 'cost' ? '예산 대비 예상' : '한도 대비 예상'), h('div', { class: 'v ' + (lv === 'ok' ? '' : 'warnv') }, pct(f.ratio)), ubar(f.ratio), h('div', { class: 's sub' }, `이달 ${kind === 'cost' ? '예산' : '한도'} ${fv(f.tgt)}${u}`))));
  root.append(forecastChart(f, kind === 'cost' ? '억' : 't', fv, compact ? (isMob() || window.innerWidth <= 1000 ? 160 : 200) : undefined, !!compact));
  if (compact) { const [cc, two] = fcExplain(id, kind, f, st); root.append(cc, h('details', { class: 'fdet' }, h('summary', {}, '근거·요인 보기'), two)); } else root.append(...fcExplain(id, kind, f, st));
  root.append(h('div', { class: 'acts' }, !inline ? btn('공장 운영에서 보기', () => { S.plant = id; location.hash = '#plants'; }) : '', btn('이 공장 확인 필요 보기', () => { S.kpi = 'rv'; S.rvPlant = id; const it = D.RV.find(r => r.plant === id && r.st !== 'resolved'); S.rv = it ? it.id : null; if (inline) location.hash = '#overview'; rerender(); scrollTo('sec'); })));
  return root;
}
const btn = (t, fn, cls = '') => { const b = h('button', { type: 'button', class: cls, 'data-own': 1 }, t); b.addEventListener('click', fn); return b; };

// ---- 선택 공장 패널(지표 선택)
function selPanel() {
  const ids = PL().map(p => p.id); if (!ids.includes(S.plant)) S.plant = ids[0]; const id = S.plant, p = D.plant(id), s = stat(id), m = METRIC[S.pm], bk = buckets();
  const fk = S.pm === 'co' ? 'cost' : S.pm, canF = hasToday(), showF = S.pf && canF, cur = m[3](id, S.a, S.b); let chart, below = '';
  if (showF) {
    const f = D.forecast(id, fk), mf = m[4];
    if (fk === 'em' || fk === 'cost') { chart = forecastChart(f, fk === 'cost' ? '억' : 't', fk === 'cost' ? (v => fmt(E8(v), 2)) : (v => fmt(v, 1)), isMob() ? 260 : 230); const [cc, two] = fcExplain(id, fk, f, D.status(id, D.mfirst(D.TODAY), D.TODAY, fk)); below = h('div', {}, cc, h('details', { class: 'fdet' }, h('summary', {}, '근거·요인 보기'), two)); }
    else { chart = lineChart({ x: f.days.map(i => D.ymd(i).slice(8) + '일'), h: 200, series: [{ n: '이번 달 누적(실적)', c: m[2], d: f.act, u: ' ' + m[1], f: mf }, { n: '월말까지 예상', c: m[2], d: f.proj, dash: true, u: ' ' + m[1], f: mf }], fl: mf }); below = h('p', { class: 'mnote' }, `${m[0]}은 한도·예산이 없어 월말 예상 ${mf(f.est)} ${m[1]}(범위 ${mf(f.estLo)}~${mf(f.estHi)})만 표시합니다.`); }
  } else chart = lineChart({ x: bk.map(b => b.label), series: [{ n: m[0], c: m[2], d: bk.map(b => m[3](id, b.a, b.b)), u: ' ' + m[1], f: v => m[4](v), area: true }], h: 120, fl: v => m[4](v), partial: !bk[bk.length - 1].full });
  const fb = btn(S.pf && canF ? '실적 추이로 돌아가기' : '이번 달 예측 보기', () => { S.pf = !S.pf; rerender(); }); if (!canF) { fb.disabled = true; fb.title = '선택한 기간에 이번 달이 포함되어야 예측을 볼 수 있습니다'; }
  return card(`선택 공장 · ${id}${showF ? ' · 이번 달 예측' : ''}`, showF ? '예측·추정 · 모의' : '예시', seg([['em', '배출'], ['co', '비용'], ['pr', '생산'], ['pw', '전력']], S.pm, k => { S.pm = k; rerender(); }),
    h('div', { class: 'kv' }, h('span', {}, '지역'), h('span', {}, `${p.c} ${p.site} (가상 위치)`), h('span', {}, '상태'), h('span', {}, stB(s.level)), h('span', {}, m[0] + ' (기간)'), h('span', {}, m[4](cur) + ' ' + m[1]), h('span', {}, '목표 대비'), h('span', {}, S.pm === 'em' ? pct(s.usage) : S.pm === 'co' ? pct(stat(id, 'cost').usage) : '—')),
    h('p', { class: 'why' }, s.why.slice(0, 2).join(' · ')), chart, below, h('div', { class: 'acts' }, btn('공장 운영에서 자세히', () => { location.hash = '#plants'; }), fb));
}
const chkCard = () => { const items = openRV().sort((a, b) => sevOrd[a.sev] - sevOrd[b.sev]);
  return card(`확인 필요 (${items.length}건)`, '예시', h('div', { class: 'list' }, items.length ? items.map(r => h('div', { class: 'it' }, h('span', {}, stB(r.sev), ' ', `${r.plant} · ${r.type}`, r.st === 'mailed' ? h('em', { class: 'mut' }, ' · 메일 발송됨') : ''), btn('검토', () => { S.kpi = 'rv'; S.rv = r.id; S.rvPlant = null; rerender(); scrollTo('sec'); }))) : h('p', { class: 'mut' }, '확인이 필요한 항목이 없습니다.')), h('p', { class: 'mnote' }, '"검토"를 누르면 AI와 대화하며 원인 확인·담당자 메일 작성까지 진행할 수 있습니다.')); };

// ---- 지도(아시아 전체 / 국가 확대)
function asiaBaseSvg() {
  const map = sv('svg', { viewBox: `0 0 ${MAPD.W} ${MAPD.H}`, class: 'asia', preserveAspectRatio: 'xMidYMid meet' });
  baseDefs(map); map.append(sv('rect', { x: 0, y: 0, width: MAPD.W, height: MAPD.H, fill: 'url(#sea)' }));
  const gx = lo => (lo - MAPD.lon0) * MAPD.cos * MAPD.k, gy = la => (MAPD.lat1 - la) * MAPD.k;
  for (let lo = 70; lo < 158; lo += 10) map.append(sv('line', { x1: gx(lo), x2: gx(lo), y1: 0, y2: MAPD.H, stroke: 'var(--seaGrid)' })); for (let la = 0; la < 47; la += 10) map.append(sv('line', { y1: gy(la), y2: gy(la), x1: 0, x2: MAPD.W, stroke: 'var(--seaGrid)' }));
  map.append(sv('path', { d: MAPD.land, fill: 'url(#lnd)', stroke: 'var(--lndLine)', 'stroke-width': 1, 'stroke-linejoin': 'round' }));
  ['중국', '인도', '몽골'].forEach(t => map.append(sv('text', { x: MAPD.lab[t][0], y: MAPD.lab[t][1], class: 'mlab', 'font-size': 17 }, t))); ['태평양', '인도양'].forEach(t => map.append(sv('text', { x: MAPD.lab[t][0], y: MAPD.lab[t][1], class: 'mlab sea', 'font-size': 18 }, t)));
  return map;
}
function asiaMap() {
  const map = asiaBaseSvg();
  const BW = 262, RH = 32, HD = 42, SS = window.matchMedia('(max-width:720px)').matches ? 1.3 : 1.14, rows = {};
  [['한국', 'KR'], ['일본', 'JP'], ['싱가포르', 'SG']].forEach(([name, code]) => {
    const list = D.P.filter(p => p.c === name), tot = sumA(list.map(p => D.em(p.id, S.a, S.b))), an = MAPD.anch[code], bh = HD + list.length * RH + 8, bwA = BW * SS, bhA = bh * SS;
    const bx = Math.max(8, code === 'KR' ? an[0] - bwA - 70 * SS : code === 'JP' ? Math.min(an[0] - 40, MAPD.W - bwA - 8) : an[0] - bwA - 70 * SS), by = code === 'KR' ? 12 : code === 'JP' ? an[1] + 120 * SS : MAPD.H - bhA - 44;
    const dim = S.region !== '전체 지역' && S.region !== name, cg = sv('g', { class: (dim ? 'cg dim' : 'cg') + (D.plant(S.plant).c === name ? ' selc' : '') }), tx = an[0] < bx ? bx : an[0] > bx + bwA ? bx + bwA : an[0], ty = an[1] < by ? by : an[1] > by + bhA ? by + bhA : an[1];
    cg.append(sv('line', { x1: an[0], y1: an[1], x2: tx, y2: ty, class: 'lead' }), sv('circle', { cx: an[0], cy: an[1], r: 7 * (SS > 1 ? 1.3 : 1), class: 'anc' }), sv('circle', { cx: an[0], cy: an[1], r: 13 * (SS > 1 ? 1.3 : 1), class: 'anc2' }));
    const bg = sv('g', { class: 'boxg', transform: `translate(${bx.toFixed(1)} ${by.toFixed(1)}) scale(${SS})` });
    bg.append(sv('rect', { x: 0, y: 0, width: BW, height: bh, rx: 8, class: 'cbox' }), sv('text', { x: 12, y: 26, class: 'ctitle', 'font-size': 17 }, `${name} · ${list.length}개`), sv('text', { x: BW - 12, y: 26, class: 'csum', 'font-size': 15 }, fmt(tot, 0) + ' tCO₂'));
    list.forEach((p, i) => { const y = HD + 6 + i * RH, s = stat(p.id), row = sv('rect', { x: 6, y: y - 15, width: BW - 12, height: RH - 3, rx: 6, class: 'crow' + (p.id === S.plant ? ' on' : '') });
      const g = sv('g', { class: 'pt' }, row, MK(s.level, 21, y - 1, 6), sv('text', { x: 36, y: y + 4.5, class: 'cid', 'font-size': 14.5 }, p.id), sv('text', { x: 98, y: y + 4.5, class: 'cu', 'font-size': 12, fill: SC[D.lvl(s.usage)] }, pct(s.usage)), sv('text', { x: BW - 12, y: y + 4.5, class: 'cv', 'font-size': 14 }, fmt(D.em(p.id, S.a, S.b), 0)));
      g.addEventListener('click', () => { S.plant = p.id; rerender(); }); rows[p.id] = row; bg.append(g); });
    cg.append(bg); map.append(cg); });
  return h('div', { class: 'mapbox' }, map, legendPill());
}
function baseDefs(map) { map.append(sv('defs', {}, sv('radialGradient', { id: 'sea', cx: '45%', cy: '40%', r: '75%' }, sv('stop', { offset: '0', 'stop-color': 'var(--seaA)' }), sv('stop', { offset: '1', 'stop-color': 'var(--seaB)' })), sv('linearGradient', { id: 'lnd', x1: '0', y1: '0', x2: '1', y2: '1' }, sv('stop', { offset: '0', 'stop-color': 'var(--lndA)' }), sv('stop', { offset: '1', 'stop-color': 'var(--lndB)' })))); }
const legendPill = () => h('div', { class: 'legend ov' }, ['ok', 'wn', 'er', 'dl'].map(k => h('span', { html: `<i class="dot" style="background:${SC[k]}"></i>${ST[k][0]}` })), h('span', { class: 'lgi', title: '사용률 70% 이상 주의 · 90% 이상 경고 · 전월 +10% 급증 시 한 단계 상향 · 수신 6시간 이상 끊기면 자료 지연', html: 'ⓘ 기준' }));
function zoomMap(code, compact) {
  const Z = MAPZ[code], ps = PL(), map = sv('svg', { viewBox: `0 0 ${Z.W} ${Z.H}`, class: 'asia zoom', preserveAspectRatio: 'xMidYMid meet' }); baseDefs(map);
  map.append(sv('rect', { x: 0, y: 0, width: Z.W, height: Z.H, fill: 'url(#sea)' }), sv('path', { d: Z.land, fill: 'url(#lnd)', stroke: 'var(--lndLine)', 'stroke-width': 1.2, 'stroke-linejoin': 'round' }));
  const px = p => (p.lon - Z.lon0) * Z.cos * Z.k, py = p => (Z.lat1 - p.lat) * Z.k, sc = Math.max(1, Z.W / 620) * (window.matchMedia('(max-width:720px)').matches ? 1.5 : 1), fs = 15 * sc, r = 10 * sc;
  if (code === 'KR') { const dx = (131.8667 - Z.lon0) * Z.cos * Z.k, dy = (Z.lat1 - 37.2414) * Z.k; map.append(sv('circle', { cx: dx - 1.6 * sc, cy: dy + .8 * sc, r: 3.4 * sc, class: 'dkd' }), sv('circle', { cx: dx + 1.6 * sc, cy: dy - .8 * sc, r: 2.8 * sc, class: 'dkd' })); }
  const sorted = ps.slice().sort((a, b) => py(a) - py(b)), left = new Set(); sorted.forEach((p, i) => { for (let j = 0; j < i; j++) { if (!left.has(sorted[j].id) && Math.abs(py(p) - py(sorted[j])) < 30 * sc && Math.abs(px(p) - px(sorted[j])) < 90 * sc) left.add(p.id); } });
  ps.forEach(p => { const s = stat(p.id), x = px(p), y = py(p), g = sv('g', { class: 'pt zp' + (p.id === S.plant ? ' on' : ''), 'data-dot': p.id }), L = left.has(p.id), tx = L ? x - r * 1.6 : x + r * 1.6, an = L ? 'end' : 'start';
    g.append(sv('circle', { cx: x, cy: y, r: r * 1.9, class: 'zring' }), MK(s.level, x, y, r), sv('text', { x, y: y - r * 1.7, class: 'zid', 'font-size': fs, 'text-anchor': 'middle' }, p.id), compact ? sv('text', { x, y: y + r * 1.9 + fs * .8, class: 'cv', 'font-size': fs * .82, style: 'text-anchor:middle' }, fmt(D.em(p.id, S.a, S.b), 0) + ' tCO₂ · ' + pct(s.usage)) : '');
    g.addEventListener('click', () => { S.plant = p.id; rerender(); }); map.append(g); });
  return h('div', { class: 'mapbox zoomed', style: `aspect-ratio:${Z.W}/${Z.H}` }, map, legendPill());
}

const dotc = k => h('i', { class: 'dot', style: `background:${SC[k]}` });
function asiaDots() {
  const map = asiaBaseSvg();
  [['한국', 'KR'], ['일본', 'JP'], ['싱가포르', 'SG']].forEach(([name, code]) => { const an = MAPD.anch[code];
    map.append(sv('g', { class: 'pt zp', 'data-dot': name }, sv('circle', { cx: an[0], cy: an[1], r: 20, class: 'anc2' }), sv('circle', { cx: an[0], cy: an[1], r: 11, class: 'anc' }), sv('text', { x: an[0] - 20, y: an[1] + 10, class: 'zid', 'font-size': 30, 'text-anchor': 'end' }, name))); });
  return h('div', { class: 'mapbox' }, map, legendPill());
}
const lbar = (label, u) => h('div', { class: 'lbar' }, h('span', { class: 'll' }, label), ubar(u), h('b', { class: 'lv ' + (u >= .9 ? 'er' : u >= .7 ? 'wn' : '') }, pct(u)));
const kvm = (k, v) => h('div', {}, h('span', {}, k), h('b', {}, v));
function countryBox(name) {
  const list = D.P.filter(p => p.c === name), tot = sumA(list.map(p => D.em(p.id, S.a, S.b)));
  return h('div', { class: 'mbox', 'data-box': name }, h('div', { class: 'mbh' }, h('b', {}, `${name} · ${list.length}개`), h('span', {}, fmt(tot, 0) + ' tCO₂')),
    h('table', { class: 'mt', 'data-nomodal': 1 }, h('thead', {}, h('tr', {}, ['공장', '배출', '목표', '비용'].map((t, i) => h('th', { class: i ? 'n' : '' }, t)))), h('tbody', {}, list.map(p => { const s = stat(p.id), tr = h('tr', { class: 'pick' + (p.id === S.plant ? ' on' : ''), 'data-own': 1 }, h('td', {}, dotc(s.level), p.id), h('td', { class: 'n' }, fmt(D.em(p.id, S.a, S.b), 0)), h('td', { class: 'n' }, pct(s.usage)), h('td', { class: 'n' }, fmt(E8(D.sum(p.id, 'co', S.a, S.b)), 2) + '억')); tr.addEventListener('click', () => { S.plant = p.id; rerender(); }); return tr; }))));
}
function plantBox(p, side) {
  const s = stat(p.id), c = stat(p.id, 'cost'), a = agg([p.id]), util = D.sum(p.id, 'ut', S.a, S.b) / (S.b - S.a + 1);
  const el = h('div', { class: 'mbox pb' + (p.id === S.plant ? ' sel' : ''), 'data-box': p.id, 'data-side': side, tabindex: 0, role: 'button', 'data-own': 1 }, h('div', { class: 'mbh' }, h('span', {}, dotc(s.level), h('b', {}, p.id), ' ' + p.site), stB(s.level)),
    h('div', { class: 'mg' }, kvm('배출', fmt(a.em, 0) + ' tCO₂'), kvm('비용', fmt(E8(a.co), 2) + '억'), kvm('생산', fmt(a.pr, 0) + ' t'), kvm('가동률', util.toFixed(0) + '%')), lbar('배출 목표 사용', s.usage), lbar('비용 예산 사용', c.usage), h('div', { class: 'lgd' }, '바 = 목표(예산) 대비 사용률 · 눈금 70% 주의 · 90% 경고'));
  const pk = () => { S.plant = p.id; rerender(); }; el.addEventListener('click', pk); el.addEventListener('keydown', e => { if (e.key === 'Enter') pk(); }); return el;
}
function drawLinks(w) {
  const svg = w.querySelector('svg.links'); if (!svg) return; svg.replaceChildren(); const r = w.getBoundingClientRect(); svg.setAttribute('viewBox', `0 0 ${r.width} ${r.height}`);
  w.querySelectorAll('[data-box]').forEach(b => { const d = w.querySelector(`[data-dot="${b.dataset.box}"]`); if (!d) return; const dr = d.getBoundingClientRect(), br = b.getBoundingClientRect(), x1 = dr.left + dr.width / 2 - r.left, y1 = dr.top + dr.height / 2 - r.top, side = b.dataset.side, x2 = (side === 'L' ? br.right : br.left) - r.left, y2 = br.top + 18 - r.top, on = b.classList.contains('sel') || b.querySelector('tr.on');
    svg.append(sv('path', { d: `M${x1.toFixed(1)} ${y1.toFixed(1)}L${(x2 + (side === 'L' ? 12 : -12)).toFixed(1)} ${y2.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}`, class: 'lk' + (on ? ' on' : '') }), sv('circle', { cx: x1, cy: y1, r: 3, class: 'lkd' + (on ? ' on' : '') })); });
}
function mapSplit() {
  const all = S.region === '전체 지역', code = { 한국: 'KR', 일본: 'JP', 싱가포르: 'SG' }[S.region];
  if (all) return asiaMap();   // 전체 지역: 지도 위 라벨 박스(이전 방식)
  if (isMob()) return zoomMap(code, true);
  if (all) { const col = h('div', { class: 'boxcol' }); ['한국', '일본', '싱가포르'].forEach(n => col.append(countryBox(n))); return h('div', { class: 'mapsplit' }, asiaDots(), col, sv('svg', { class: 'links' })); }
  const ps = PL().slice().sort((a, b) => a.lon - b.lon), nl = Math.ceil(ps.length / 2), byLat = (a, b) => b.lat - a.lat;
  const lc = h('div', { class: 'boxcol' }, ps.slice(0, nl).sort(byLat).map(p => plantBox(p, 'L'))), rc = h('div', { class: 'boxcol' }, ps.slice(nl).sort(byLat).map(p => plantBox(p, 'R')));
  return h('div', { class: 'zsplit' }, h('div', { class: 'mapsplit two' }, lc, zoomMap(code, false), rc, sv('svg', { class: 'links' })), zoomSide(S.region));
}
// 국가 확대 화면: 지도 옆 공간에 공장 비교 표 · 월별 배출 추이 · 주목 공장
function zoomSide(cn) {
  const T_ = (ko, en) => (window.I18N && I18N.lang === 'en') ? en : ko, ps = PL(), rows = ps.map(p => ({ p, s: stat(p.id, 'em'), em: D.em(p.id, S.a, S.b) })).sort((a, b) => b.s.usage - a.s.usage), tot = rows.reduce((q, r) => q + r.em, 0);
  const col = u => { try { return SC[D.lvl(u)]; } catch (e) { return 'var(--cy)'; } };
  const tb = h('table', { class: 'zs-t' }, h('thead', {}, h('tr', {}, [T_('공장', 'Plant'), T_('배출 tCO₂', 'tCO₂'), T_('배출 목표', 'Emission'), T_('비용 예산', 'Budget')].map((x, i) => h('th', { class: i ? 'n' : '' }, x)))), h('tbody', {}, rows.map(r => { const cu = stat(r.p.id, 'cost').usage, mom = Math.round(cu * 100) + '%'; return h('tr', { class: 'zs-r', 'data-own': 1, tabindex: 0 }, h('td', {}, h('i', { style: `background:${col(r.s.usage)}` }), h('b', {}, r.p.id), ' ', h('span', { class: 'mut' }, r.p.site)), h('td', { class: 'n' }, Math.round(r.em).toLocaleString('en-US')), h('td', { class: 'n' }, h('span', { class: 'zs-b' }, h('u', { style: `width:${Math.min(100, r.s.usage * 100)}%;background:${col(r.s.usage)}` })), Math.round(r.s.usage * 100) + '%'), h('td', { class: 'n' }, mom)); })));
  tb.querySelectorAll('.zs-r').forEach((tr, i) => { const go = () => { S.plant = rows[i].p.id; location.hash = '#plants'; }; tr.addEventListener('click', go); tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); }); });
  const T0 = D.TODAY, vals = []; for (let a = 0; a <= T0; a += 30) vals.push(ps.reduce((q, p) => q + D.em(p.id, a, Math.min(T0, a + 29)), 0));
  let spark = '';
  if (vals.length > 2) { const mx = Math.max(...vals) * 1.1, mn = Math.min(...vals) * .85, X = i => 4 + (i / (vals.length - 1)) * 192, Y = v => 66 - ((v - mn) / (mx - mn || 1)) * 56, pts = vals.map((v, i) => X(i).toFixed(1) + ',' + Y(v).toFixed(1)).join(' '), li = vals.length - 1;
    spark = sv('svg', { viewBox: '0 0 200 76', class: 'zs-sp', preserveAspectRatio: 'none', 'aria-label': T_('월별 배출 추이', 'Monthly emissions') }, sv('polygon', { points: `4,70 ${pts} 196,70`, class: 'a' }), sv('polyline', { points: pts, class: 'l' }), sv('circle', { cx: X(li), cy: Y(vals[li]), r: 3, class: 'd' })); }
  const watch = rows.slice(0, 2).map(r => h('button', { type: 'button', class: 'zs-w', 'data-own': 1 }, h('span', { class: 'zs-wt' }, h('i', { style: `background:${col(r.s.usage)}` }), h('b', {}, r.p.id + ' ' + r.p.site), h('em', { style: `color:${col(r.s.usage)}` }, Math.round(r.s.usage * 100) + '%')), h('span', { class: 'zs-wr' }, (r.s.why && (r.s.why[1] || r.s.why[0])) || ''))).map((b, i) => { b.addEventListener('click', () => { S.plant = rows[i].p.id; location.hash = '#plants'; }); return b; });
  const hd = (t, r) => h('div', { class: 'zs-h' }, h('b', {}, t), h('span', { class: 'mut' }, r));
  return h('aside', { class: 'zs' }, h('div', { class: 'zs-sec s1' }, hd(cn + T_(` ${rows.length}개 공장 비교`, ` · ${rows.length} plants`), T_('합계 ', 'Total ') + Math.round(tot).toLocaleString('en-US') + ' tCO₂'), tb), h('div', { class: 'zs-sec s2' }, hd(T_('월별 배출 추이', 'Monthly emissions'), T_('30일 단위 합계', '30-day sums')), spark), h('div', { class: 'zs-sec s3' }, hd(T_('주목할 공장', 'Plants to watch'), T_('목표 대비 사용률 높은 순', 'highest usage vs target')), h('div', { class: 'zs-wl' }, watch)));
}
// 국가 확대 시 공장별 상세 카드
function plantCards() {
  return h('div', { class: 'pcards' }, PL().map(p => { const s = stat(p.id), c = stat(p.id, 'cost'), a = agg([p.id]), rvn = D.RV.filter(r => r.plant === p.id && r.st !== 'resolved').length, util = a.hr ? (D.sum(p.id, 'ut', S.a, S.b) / (S.b - S.a + 1)) : 0;
    const el = h('div', { class: 'card pc' + (p.id === S.plant ? ' sel' : ''), tabindex: 0, role: 'button', 'data-own': 1 }, h('div', { class: 'pch' }, h('b', {}, p.id), h('span', { class: 'mut' }, p.site), stB(s.level)),
      h('div', { class: 'pcr' }, h('span', {}, '배출'), h('b', {}, fmt(a.em, 1) + ' tCO₂'), h('em', {}, '목표 ' + pct(s.usage))), ubar(s.usage), h('div', { class: 'pcr' }, h('span', {}, '비용'), h('b', {}, fmt(E8(a.co), 2) + ' 억'), h('em', {}, '예산 ' + pct(c.usage))), ubar(c.usage),
      h('div', { class: 'pcg' }, h('div', {}, h('span', {}, '생산량'), h('b', {}, fmt(a.pr, 0) + ' t')), h('div', {}, h('span', {}, '가동률'), h('b', {}, util.toFixed(0) + '%')), h('div', {}, h('span', {}, '전력'), h('b', {}, fmt(a.pw, 0) + ' MWh')), h('div', {}, h('span', {}, '확인 필요'), h('b', {}, rvn + '건'))), h('p', { class: 'why' }, s.why[0]));
    const pick = () => { S.plant = p.id; rerender(); }; el.addEventListener('click', pick); el.addEventListener('keydown', e => { if (e.key === 'Enter') pick(); }); return el; }));
}
// 관제 공장 선택 타일
function tiles() {
  return card('관제 공장 · 공장을 선택하세요', '예시', h('div', { class: 'tiles', style: '--cols:' + Math.min(6, PL().length) }, PL().map(p => { const s = stat(p.id), a = agg([p.id]), t = h('div', { class: 'tile st-' + s.level + (S.plSel && p.id === S.plant ? ' sel' : ''), tabindex: 0, role: 'button', 'data-own': 1 }, h('div', { class: 'th' }, h('b', {}, p.id), stB(s.level)), h('div', { class: 'mut' }, p.c + ' ' + p.site), h('div', { class: 'tr' }, h('span', {}, '생산량'), h('b', {}, fmt(a.pr, 0) + ' t')), h('div', { class: 'tr' }, h('span', {}, '목표 대비'), h('b', {}, pct(s.usage))), ubar(s.usage)); const go2 = () => { S.plant = p.id; S.plSel = true; rerender(); }; t.addEventListener('click', go2); t.addEventListener('keydown', e => { if (e.key === 'Enter') go2(); }); return t; })), h('p', { class: 'mnote' }, '공장을 누르면 아래에 그 공장의 상세 카드(생산·에너지·탄소·설비 현황)가 나타납니다.'));
}
// 추이·기여도
function trendCard() { const ids = PL().map(p => p.id), bk = buckets(), em = bk.map(b => agg(ids, b.a, b.b).em), co = bk.map(b => E8(agg(ids, b.a, b.b).co)), gran = bk.length > 1 && bk[0].a === bk[0].b ? '일별' : bk[0].b - bk[0].a === 6 ? '주별' : '월별';
  return card(`배출·비용 추이 (${gran})`, '예시', lineChart({ x: bk.map(b => b.label), dual: true, h: 230, series: [{ n: '배출량', c: 'var(--cy)', d: em, u: ' tCO₂', f: v => fmt(v, 1) }, { n: '비용', c: 'var(--yl)', d: co, axis: 'r', u: ' 억 원', f: v => fmt(v, 2) }], fl: v => fmt(v, 0), fr: v => fmt(v, 1), partial: !bk[bk.length - 1].full }), h('p', { class: 'mnote' }, `왼쪽 축: 배출량(tCO₂) · 오른쪽 축: 비용(억 원) · ${S.region === '전체 지역' ? '전체 공장' : S.region + ' 공장'} 합계${bk[bk.length - 1].full ? '' : ' · 마지막 점은 일부 기간(기준일까지)'}`)); }
function contribCard() {
  const ps = PL(), ids = ps.map(p => p.id), tot = agg(ids).em, root = card('공장별 배출 구성·증감 기여', '예시', seg([['share', '배출 비중·구성'], ['delta', '증감 기여']], S.contrib, k => { S.contrib = k; rerender(); }));
  if (S.contrib === 'share') { const items = ps.map(p => ({ label: p.id, sub: pct(D.em(p.id, S.a, S.b) / tot), parts: [{ v: D.sum(p.id, 's1', S.a, S.b), c: 'var(--yl)', n: '직접(연료)' }, { v: D.sum(p.id, 's2', S.a, S.b), c: 'var(--cy)', n: '간접(전력)' }], tot: D.em(p.id, S.a, S.b) })); root.append(barChart({ items, h: 230, legend: [{ n: '직접(연료·공정)', c: 'var(--yl)' }, { n: '간접(구입 전력)', c: 'var(--cy)' }], total: it => fmt(it.tot, 0), tipx: it => it.parts.map(p => `<div><i class="dot" style="background:${p.c}"></i>${p.n} <b>${fmt(p.v, 1)} tCO₂</b></div>`).join('') + `<div class="mut">전체의 ${it.sub}</div>` }));
    const top = items.slice().sort((a, b) => b.tot - a.tot).slice(0, 3); root.append(h('p', { class: 'mnote' }, '공장이 전체 배출에서 차지하는 비중입니다(막대 아래 %). 막대 색은 배출 구성으로, 노랑=연료·공정에서 직접 나오는 배출, 청록=구입 전력에서 나오는 간접 배출입니다. 비중이 크고 간접 비율이 높은 공장일수록 전력 절감 효과가 큽니다.'), h('p', { class: 'why' }, '상위 기여: ' + top.map(t => `${t.label} ${t.sub}`).join(' · ') + ` (3곳 합계 ${pct(sumA(top.map(t => t.tot)) / tot)})`)); }
  else { const a0 = D.mfirst(D.TODAY), n = D.TODAY - a0, pa = a0 - D.dim(D.mon(a0 - 1)), pb = pa + n, items = ps.map(p => ({ label: p.id, parts: [{ v: D.em(p.id, a0, D.TODAY) - D.em(p.id, pa, pb), c: 'var(--rd)', n: '증감' }] })), dt = sumA(items.map(i => i.parts[0].v));
    root.append(barChart({ items, h: 230, diverge: true, col: it => it.parts[0].v >= 0 ? 'var(--rd)' : 'var(--gr)', legend: [{ n: '증가(전월 대비 늘림)', c: 'var(--rd)' }, { n: '감소', c: 'var(--gr)' }], tipx: it => `<div>이번 달 누적 − 직전 달 동일 기간 <b>${it.parts[0].v >= 0 ? '+' : ''}${fmt(it.parts[0].v, 1)} tCO₂</b></div>` }));
    const up = items.filter(i => i.parts[0].v > 0).sort((a, b) => b.parts[0].v - a.parts[0].v).slice(0, 3); root.append(h('p', { class: 'mnote' }, `기준: 이번 달(${dlabel(a0)}~${dlabel(D.TODAY)}) 누적 배출과 직전 달 같은 일수의 차이입니다. 전체 ${dt >= 0 ? '+' : ''}${fmt(dt, 1)} tCO₂ 중 빨강(증가) 공장이 증가분을 만든 요인이고, 초록(감소) 공장은 상쇄한 요인입니다.`), h('p', { class: 'why' }, up.length ? '증가 상위: ' + up.map(t => `${t.label} +${fmt(t.parts[0].v, 1)}`).join(' · ') : '증가한 공장이 없습니다.')); }
  return root;
}

V.overview = () => {
  if (!PL().find(p => p.id === S.plant)) S.plant = PL()[0].id;
  const root = h('div', { class: 'view' }), ps = PL(), ids = ps.map(p => p.id), A = agg(ids), TE = tgt(ids, 'em'), TC = tgt(ids, 'cost'), uE = A.em / TE, uC = A.co / TC, levels = { ok: 0, wn: 0, er: 0, dl: 0 };
  ids.forEach(id => levels[stat(id).level]++); const F = hasToday() ? ids.map(id => D.forecast(id, 'em')) : null, FC = hasToday() ? ids.map(id => D.forecast(id, 'cost')) : null, rv = openRV(), rvc = { er: 0, wn: 0, dl: 0 }; rv.forEach(r => rvc[r.sev]++);
  const rest = (u, kind) => u >= 1 ? `초과 ${pct(u - 1)}` : `여유 ${pct(1 - u)}`;
  root.append(h('div', { class: 'row r4 kxrow' },
    kx({ key: 'em', tone: 'gr', icon: '&#127807;', label: '배출 추정', tag: '추정·검증 전', value: fmt(A.em, 1), unit: 'tCO₂', sub: periodLabel(), extra: gauge(uE, `목표(예시) ${fmt(TE, 0)} 대비 ${pct(uE)} 사용 · ${rest(uE)}`, F ? `이번 달 예상 ${fmt(sumA(F.map(f => f.est)), 0)} (한도의 ${pct(sumA(F.map(f => f.est)) / sumA(F.map(f => f.tgt)))})` : '') }),
    kx({ key: 'co', tone: 'yl', icon: '&#128178;', label: '에너지 비용', tag: '추정', value: fmt(E8(A.co), 2), unit: '억 원', sub: '환율 기준 예시 · KRW', extra: gauge(uC, `예산(예시) ${fmt(E8(TC), 1)}억 대비 ${pct(uC)} 사용 · ${rest(uC)}`, FC ? `이번 달 예상 ${fmt(E8(sumA(FC.map(f => f.est))), 2)}억 (예산의 ${pct(sumA(FC.map(f => f.est)) / sumA(FC.map(f => f.tgt)))})` : '') }),
    kx({ key: 'pl', tone: 'cy', icon: '&#127981;', label: '관제 공장', value: String(ids.length), unit: '개', sub: ['한국', '일본', '싱가포르'].filter(n => ps.some(p => p.c === n)).map(n => n + ps.filter(p => p.c === n).length).join('·'), extra: h('div', { class: 'lvs' }, ['ok', 'wn', 'er', 'dl'].map(k => h('span', { html: `<i class="dot" style="background:${SC[k]}"></i>${ST[k][0]} <b>${levels[k]}</b>` }))) }),
    kx({ key: 'rv', tone: 'or', icon: '&#9888;', label: '확인 필요', tag: '검토 대기', value: String(rv.length), unit: '건', sub: `경고 ${rvc.er} · 주의 ${rvc.wn} · 지연 ${rvc.dl}`, extra: h('div', { class: 'gt mut' }, '누르면 AI와 확인·메일 작성') }), window.mktTile ? mktTile() : ''));
  const sec = h('div', { id: 'sec' }); root.append(sec);
  if (S.kpi === 'em' || S.kpi === 'co') {
    const kd = S.kpi === 'co' ? 'cost' : 'em'; if (!S.fc || !ids.includes(S.fc)) S.fc = ids.slice().sort((x, y) => (hasToday() ? D.forecast(y, kd).ratio - D.forecast(x, kd).ratio : D.status(y, S.a, S.b, kd).usage - D.status(x, S.a, S.b, kd).usage))[0];
    sec.append(h('div', { class: 'split2' }, factoryTable(kd), forecastCard(S.fc, S.fk === 'cost' || S.fk === 'em' ? S.fk : kd, false, true)));
  }
  if (S.kpi === 'pl') { sec.append(window.TWIN ? TWIN.section() : tiles()); if (S.plSel && (!window.TWIN || TWIN.lvl() === 'plant')) { const pv = V.plants({ embed: true }); const ch = pv.querySelector('.pchips'); if (ch) ch.remove(); pv.classList.add('embed'); sec.append(pv); } }
  if (S.kpi === 'rv') sec.append(reviewWorkspace());
  if (S.kpi === 'mk' && window.MKT) sec.append(MKT.section());
  if (S.kpi !== 'rv' && S.kpi !== 'em' && S.kpi !== 'co' && S.kpi !== 'mk' && S.kpi !== 'pl') {
    const mapCard = card(S.region === '전체 지역' ? '아시아 공장 현황' : `${S.region} 공장 현황`, S.region === '전체 지역' ? '국가별 배치 · 지리 좌표 아님' : '가상 위치(지역 단위)', mapSplit());
    root.append(h('div', { class: 'row r21 main' + (S.region === '전체 지역' ? '' : ' zoomrow') }, mapCard, h('div', { class: 'col' }, selPanel(), chkCard())));
    if (S.region !== '전체 지역' && isMob()) root.append(card(`${S.region} 공장별 상세 현황`, `${periodLabel()}`, plantCards()));
  }
  return root;
};
