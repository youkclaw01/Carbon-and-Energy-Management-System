'use strict';
// 관제 공장 에너지 흐름 트윈: 전체(국가별 묶음) → 국가 → 개별 공장 순서로 내려가며 전력 흐름·재생 비중·실시간 탄소·RE100·감축 수단을 보여 줍니다.
// 모든 수치는 시안용 가상 값(공장 일별 자료에서 파생한 예시)이며 실제 설비 연결이 아닙니다.
(function () {
  const T = (ko, en) => (window.I18N && I18N.lang === 'en') ? en : ko;
  const CN = { 한국: 'Korea', 일본: 'Japan', 싱가포르: 'Singapore' }, cn = c => T(c, CN[c] || c);
  // 감축 수단: cut=공장 배출 감축 비율, re=재생 비중 증가(%p), save=연 비용 절감(억 원, 평균 0.8MW 공장 기준)
  const LEV = [
    { k: 'pv', ko: '자가 태양광', en: 'On-site solar', cut: .06, re: 8, save: .55, eff: ['설비 1.0 MWp · 이용률 17%', '1.0 MWp · 17% load factor'] },
    { k: 'ppa', ko: '재생 PPA·REC', en: 'Renewable PPA·REC', cut: .14, re: 24, save: .30, eff: ['계약 전력의 24% 재생 전환', '24% of load on renewable'] },
    { k: 'batt', ko: '배터리 저장', en: 'Battery storage', cut: .03, re: 3, save: .50, eff: ['피크 15% 이동 · 효율 88%', '15% peak shift · 88% RTE'] },
    { k: 'eff', ko: '고효율 설비', en: 'High-efficiency motors', cut: .05, re: 0, save: .80, eff: ['모터·인버터 교체 · 전력 -6%', 'Motors & drives · -6% power'] },
    { k: 'fuel', ko: '연료 전환', en: 'Fuel switching', cut: .08, re: 0, save: .40, eff: ['LNG → 전기·수소 혼소 30%', 'LNG → electric / H₂ blend 30%'] },
    { k: 'heat', ko: '폐열 회수', en: 'Waste-heat recovery', cut: .04, re: 0, save: .70, eff: ['공정 폐열 회수율 38%', '38% process-heat recovery'] },
    { k: 'ai', ko: 'AI 가동 최적화', en: 'AI scheduling', cut: .03, re: 0, save: .60, eff: ['가동 스케줄·설정값 자동 조정', 'Auto-tuned schedules & setpoints'] }
  ];
  const DEF = [['pv', 'eff', 'ai'], ['ppa', 'eff'], ['pv', 'heat', 'batt'], ['ppa', 'fuel'], ['eff', 'ai']];
  const BASE_RE = { 한국: .22, 일본: .27, 싱가포르: .10 }, GOAL = .60;
  const ST_ = { lvl: 'all', c: null, on: {} };
  const fmt = (v, d = 1) => v.toLocaleString(T('ko-KR', 'en-US'), { minimumFractionDigits: d, maximumFractionDigits: d });
  const onSet = id => ST_.on[id] || (ST_.on[id] = new Set(DEF[D.P.findIndex(p => p.id === id) % 5]));
  function M(id) {
    const p = D.plant(id), i = D.P.indexOf(p), on = onSet(id), s0 = BASE_RE[p.c] + (((i * 37) % 9) - 4) / 100;
    let cut = 0, re = 0, save = 0; LEV.forEach(l => { if (on.has(l.k)) { cut += l.cut; re += l.re; save += l.save * p.mw / .8; } });
    cut = Math.min(.6, cut); const eh = D.day(id, 'em', D.TODAY) / 24, reS = Math.min(.98, s0 + re / 100);
    return { seed: i * 1.7, fr: k => on.has(k) ? 1 : 0, n: 1, p, id, on, s0, reS, fos: 1 - reS, eh, carbon: eh * (1 - cut), cut, saveT: eh * 8760 * cut, saveW: save, mw: D.day(id, 'pw', D.TODAY) / 24, st: stat(id) };
  }
  const agg2 = ids => { const ms = ids.map(M), mw = ms.reduce((s, m) => s + m.mw, 0); return { n: ms.length, ms, mw, re: ms.reduce((s, m) => s + m.reS * m.mw, 0) / mw, carbon: ms.reduce((s, m) => s + m.carbon, 0), base: ms.reduce((s, m) => s + m.eh, 0), saveT: ms.reduce((s, m) => s + m.saveT, 0), saveW: ms.reduce((s, m) => s + m.saveW, 0), lev: ms.reduce((s, m) => s + m.on.size, 0) }; };

  const stat_ = (k, v, u, cls, live) => `<div class="tw-st ${cls || ''}"><span>${k}</span><b${live ? ` class="tw-live" data-v="${live}"` : ''}>${v}</b>${u ? `<em>${u}</em>` : ''}</div>`;
  // ───────────────────────────────────────────────────────────────────────────
  // 프리미엄 에너지 흐름 무대: 에너지원(좌) → 공장(중앙) → 사용처·배출(우)
  // 선 굵기 = 실시간 전력(MW)에 비례(Sankey), 빛 알갱이 = 흐름 방향, 숫자는 1초마다 갱신되는 시안용 가상 실시간 값
  // ───────────────────────────────────────────────────────────────────────────
  const COL = { fos: '#c9783f', re: '#2e9e7c', sol: '#d9a02e', bat: '#4f88d6', proc: '#7e8ca0', heat: '#e0644f', co2: '#7d8794' };
  const PRICE = { 한국: 145, 일본: 170, 싱가포르: 210 };
  const lfac = h => .78 + .24 * Math.exp(-((h - 11) ** 2) / 16) + .16 * Math.exp(-((h - 19.5) ** 2) / 8) - .10 * Math.exp(-((h - 3) ** 2) / 10);
  const sday = h => Math.max(0, Math.sin(Math.PI * (h - 6) / 12));
  const nowH = () => { const d = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' })); return { h: d.getHours() + d.getMinutes() / 60 + d.getSeconds() / 3600, d }; };
  function flowAt(m, h, t) {
    const fr = k => m.fr(k), load = m.mw * lfac(h) * (1 + .018 * Math.sin(t / 2.7 + m.seed) + .01 * Math.sin(t / .9 + m.seed));
    const solar = Math.min(load * .45, fr('pv') * (m.mw / .8) * sday(h) * (.93 + .05 * Math.sin(t / 4.1 + m.seed)));
    const bt = fr('batt') * (((h >= 10 && h < 12.5) || (h >= 18 && h < 21)) ? .12 * load : (h >= 1 && h < 5) ? -.10 * load : 0), grid = Math.max(0, load - solar - Math.max(0, bt)) + Math.max(0, -bt);
    const reG = Math.min(.98, m.s0 + fr('ppa') * .24), gRE = grid * reG, gF = grid - gRE, re = Math.min(1, (solar + gRE + Math.max(0, bt) * reG) / Math.max(load, .001));
    const proc = [.46, .34, .20].map((p, i) => load * p * (1 + .02 * Math.sin(t / (1.7 + i) + i + m.seed))), heat = fr('heat') * .06 * load;
    const k = Math.min(1.8, Math.max(.3, .55 * load / m.mw + .45 * gF / Math.max(.001, m.mw * (1 - m.reS)))), carbon = m.carbon * k;
    const pm = (h >= 14 && h < 17) ? 1.35 : (h >= 23 || h < 7) ? .75 : 1, costH = load * 1000 * (PRICE[m.p.c] || 160) * pm / 1e4;
    return { h, load, solar, bt, grid, gRE, gF, re, proc, heat, carbon, inten: carbon / Math.max(load, .001) * 1000, costH, pm };
  }
  const hist = {};                                                    // 공장별 최근 60초 기록(수동 갱신으로 무대를 다시 그려도 유지)
  const sparkP = (a, w, h, pad = 2) => { const mn = Math.min(...a), mx = Math.max(...a), X = i => pad + (w - 2 * pad) * i / (a.length - 1), Y = v => h - pad - (h - 2 * pad) * (v - mn) / ((mx - mn) || 1); return a.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(''); };
  function ribbon(id, d, col, w, dur, n, rev) {
    const parts = Array.from({ length: n }, (_, i) => `<circle r="${(2 + (i % 3) * .5).toFixed(1)}" fill="${col}" filter="url(#tw-glow)" opacity=".95"><animateMotion dur="${dur}s" begin="-${(i * dur / n).toFixed(2)}s" repeatCount="indefinite" path="${d}"${rev ? ' keyPoints="1;0" keyTimes="0;1" calcMode="linear"' : ''}/></circle>`).join('');
    return `<g class="tw-rbg"><path class="tw-rb" data-rb="${id}" d="${d}" stroke="url(#tw-g-${id})" stroke-width="${w.toFixed(1)}"/><path class="tw-rc" d="${d}" stroke="${col}"/>${REDUCED ? '' : parts}</g>`;
  }
  const REDUCED = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const grad = (id, col) => `<linearGradient id="tw-g-${id}" x1="0" x2="1"><stop offset="0" stop-color="${col}" stop-opacity=".12"/><stop offset=".55" stop-color="${col}" stop-opacity=".42"/><stop offset="1" stop-color="${col}" stop-opacity=".16"/></linearGradient>`;
  function srcCard(x, y, col, label, id, sub) { return `<g class="tw-sc" transform="translate(${x} ${y})"><rect width="214" height="74" rx="14"/><circle cx="16" cy="19" r="4" fill="${col}"/><text class="lb" x="28" y="23">${label}</text><text class="vl" x="16" y="56" data-k="${id}">0.00</text><text class="un" x="${id === 'co2' ? 150 : 86}" y="56">${id === 'co2' ? 'tCO₂/h' : 'MW'}</text><text class="pc" x="198" y="23" text-anchor="end" data-k="${id}p"></text><path class="sp" data-sp="${id}" d="" stroke="${col}" transform="translate(${id === 'co2' ? 140 : 116} 30)"/><text class="sb" x="16" y="70" opacity="0">${sub || ''}</text></g>`; }
  const YL = [70, 160, 250, 340], YR = [70, 160, 250, 340];
  const defsG = () => `<defs><filter id="tw-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <linearGradient id="tw-fac1" x1="0" x2="1" y1="0" y2="1"><stop offset="0" style="stop-color:color-mix(in srgb,var(--txt) 22%,var(--card1))"/><stop offset="1" style="stop-color:color-mix(in srgb,var(--txt) 12%,var(--card1))"/></linearGradient><linearGradient id="tw-fac2" x1="0" x2="1"><stop offset="0" style="stop-color:color-mix(in srgb,var(--txt) 15%,var(--card1))"/><stop offset="1" style="stop-color:color-mix(in srgb,var(--txt) 8%,var(--card1))"/></linearGradient><linearGradient id="tw-fac3" x1="0" x2="1"><stop offset="0" style="stop-color:color-mix(in srgb,var(--txt) 30%,var(--card1))"/><stop offset="1" style="stop-color:color-mix(in srgb,var(--txt) 20%,var(--card1))"/></linearGradient>
      <radialGradient id="tw-ground" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#2e9e7c" stop-opacity=".28"/><stop offset="1" stop-color="#2e9e7c" stop-opacity="0"/></radialGradient>
      ${grad('fos', COL.fos)}${grad('re', COL.re)}${grad('sol', COL.sol)}${grad('bat', COL.bat)}${grad('p0', COL.proc)}${grad('p1', COL.proc)}${grad('p2', COL.proc)}${grad('ht', COL.heat)}${grad('co2', COL.co2)}</defs>`;
  const facG = tr => `<g class="tw-fac" transform="${tr}">
        <path d="M-96 -6L0 -42L0 40L-96 76Z" fill="url(#tw-fac2)" stroke="#5a7390" stroke-width="1"/><path d="M0 -42L96 -6L96 76L0 40Z" fill="url(#tw-fac1)" stroke="#6b86a3" stroke-width="1"/><path d="M-96 -6L0 -42L96 -6L0 30Z" fill="url(#tw-fac3)" stroke="#8aa3be" stroke-width="1"/>
        <path d="M-70 -14L-42 -25L-42 -43L-14 -32L-14 -50L14 -39" fill="none" stroke="#9db4cc" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M56 -22L56 -86L72 -80L72 -16Z" fill="#26364a" stroke="#6b86a3" stroke-width="1"/><ellipse cx="64" cy="-84" rx="8" ry="3" fill="#33475f" stroke="#7b93ad"/>
        <g class="win">${[-78, -56, -34, -12].map((x, i) => `<path d="M${x} ${14 + i * 5}L${x + 14} ${8 + i * 5}L${x + 14} ${20 + i * 5}L${x} ${26 + i * 5}Z" style="animation-delay:${i * .6}s"/>`).join('')}${[14, 36, 58, 78].map((x, i) => `<path d="M${x} ${14 - i * 4 + 14}L${x + 14} ${20 - i * 4 + 14}L${x + 14} ${32 - i * 4 + 14}L${x} ${26 - i * 4 + 14}Z" style="animation-delay:${i * .5 + .3}s"/>`).join('')}</g>
        <ellipse class="tw-core twa" cx="0" cy="78" rx="62" ry="16" fill="none" stroke="${COL.re}" stroke-width="2" data-k="core"/>
      </g>`;
  function stageSvg(m) {
    const f = flowAt(m, nowH().h, 0), ex = [238, 252, 266, 280], lp = i => `M238 ${YL[i] + 37}C330 ${YL[i] + 37},330 ${ex[i]},408 ${ex[i]}`, rp = i => `M592 ${[238, 252, 266, 280][i]}C680 ${[238, 252, 266, 280][i]},680 ${YR[i] + 37},762 ${YR[i] + 37}`;
    const src = [['fos', COL.fos, 'gF'], ['re', COL.re, 'gRE'], ['sol', COL.sol, 'solar'], ['bat', COL.bat, 'bt']], snk = [['p0', COL.proc], ['p1', COL.proc], ['p2', COL.proc], ['ht', COL.heat]];
    const dur = i => (2.6 + i * .35).toFixed(2), on = { sol: m.fr('pv') > 0, bat: m.fr('batt') > 0, ht: m.fr('heat') > 0 };
    return `<svg class="tw-svg" viewBox="0 0 1000 424" role="img" aria-label="${T('에너지 흐름도', 'Energy flow diagram')}">
      ${defsG()}
      <ellipse cx="500" cy="318" rx="190" ry="42" fill="url(#tw-ground)"/><ellipse class="tw-ring2 twa" cx="500" cy="318" rx="150" ry="30" fill="none" stroke="${COL.re}" stroke-width="1.2" stroke-dasharray="3 7" opacity=".55"/>
      ${src.map(([k, c], i) => ribbon(k, lp(i), c, 6, dur(i), 6, false)).join('')}${snk.map(([k, c], i) => ribbon(k, rp(i), c, 6, dur(i + 2), 6, false)).join('')}${ribbon('co2', 'M564 144C564 116,562 92,562 62', COL.co2, 6, 3.4, 5, false)}
      ${facG('translate(500 230)')}
      ${REDUCED ? '' : Array.from({ length: Math.max(3, Math.min(8, Math.round(f.carbon * 1.2))) }, (_, i) => `<circle class="tw-puff twa" cx="${564 + (i % 3) * 4}" cy="146" r="${5 + (i % 3) * 2}" style="animation-delay:${(i * .8).toFixed(1)}s;animation-duration:${(3.6 + i * .3).toFixed(1)}s"/>`).join('')}
      ${srcCard(24, YL[0], COL.fos, T('외부 계통 · 화석', 'GRID · FOSSIL'), 'fos', '')}${srcCard(24, YL[1], COL.re, T('재생 전력 · PPA·REC', 'RENEWABLE · PPA·REC'), 're', '')}${srcCard(24, YL[2], COL.sol, T('자가 태양광', 'ON-SITE SOLAR'), 'sol', '')}${srcCard(24, YL[3], COL.bat, T('배터리 저장', 'BATTERY'), 'bat', '')}
      ${srcCard(762, YR[0], COL.proc, T('압출 라인', 'EXTRUSION'), 'p0', '')}${srcCard(762, YR[1], COL.proc, T('성형 라인', 'FORMING'), 'p1', '')}${srcCard(762, YR[2], COL.proc, T('후처리·유틸리티', 'FINISHING · UTILITIES'), 'p2', '')}${srcCard(762, YR[3], COL.heat, T('폐열 회수', 'HEAT RECOVERY'), 'ht', '')}
      <g class="tw-sc co2" transform="translate(448 6)"><rect width="216" height="60" rx="14"/><circle cx="16" cy="14" r="4" fill="${COL.co2}"/><text class="lb" x="28" y="18">${T('실시간 탄소 배출', 'LIVE CARBON')}</text><text class="vl" x="16" y="50" data-k="co2">0.00</text><text class="un" x="92" y="50">tCO₂/h</text><text class="pc" x="200" y="18" text-anchor="end" data-k="co2p"></text></g>
      <text class="tw-ttl" x="500" y="396" text-anchor="middle">${m.title || (m.id + ' · ' + m.p.site)}</text>
      ${[['sol', on.sol], ['bat', on.bat], ['ht', on.ht]].filter(([, o]) => !o).map(([k]) => `<text class="tw-off" x="${k === 'ht' ? 780 : 40}" y="${k === 'sol' ? 336 : k === 'bat' ? 426 : 430}" opacity="0"></text>`).join('')}
    </svg>`;
  }
  function chart24(m) {
    const P = []; for (let i = 0; i <= 48; i++) { const h = i / 2, f = flowAt(m, h, 0); P.push({ h, fos: f.gF, re: f.gRE, sol: f.solar, ld: f.load, bt: Math.max(0, f.bt) }); }
    const W = 1000, H = 118, mx = Math.max(...P.map(p => p.fos + p.re + p.sol + p.bt)) * 1.12, X = h => 14 + (W - 28) * h / 24, Y = v => H - 18 - (H - 30) * v / mx;
    const band = (lo, hi) => P.map((p, i) => (i ? 'L' : 'M') + X(p.h).toFixed(1) + ' ' + Y(hi(p)).toFixed(1)).join('') + P.slice().reverse().map(p => 'L' + X(p.h).toFixed(1) + ' ' + Y(lo(p)).toFixed(1)).join('') + 'Z';
    const L1 = band(p => 0, p => p.fos), L2 = band(p => p.fos, p => p.fos + p.re), L3 = band(p => p.fos + p.re, p => p.fos + p.re + p.sol + p.bt);
    const ld = P.map((p, i) => (i ? 'L' : 'M') + X(p.h).toFixed(1) + ' ' + Y(p.ld).toFixed(1)).join('');
    return `<svg class="tw-c24" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="${T('24시간 전력 구성', '24-hour power mix')}"><defs><linearGradient id="tw-a1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${COL.fos}" stop-opacity=".75"/><stop offset="1" stop-color="${COL.fos}" stop-opacity=".25"/></linearGradient><linearGradient id="tw-a2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${COL.re}" stop-opacity=".75"/><stop offset="1" stop-color="${COL.re}" stop-opacity=".22"/></linearGradient><linearGradient id="tw-a3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${COL.sol}" stop-opacity=".85"/><stop offset="1" stop-color="${COL.sol}" stop-opacity=".25"/></linearGradient></defs>
      ${[0, 6, 12, 18, 24].map(h => `<line x1="${X(h)}" x2="${X(h)}" y1="6" y2="${H - 16}" class="gl"/><text x="${X(h)}" y="${H - 3}" class="gt" text-anchor="${h === 0 ? 'start' : h === 24 ? 'end' : 'middle'}">${String(h).padStart(2, '0')}:00</text>`).join('')}
      <path d="${L1}" fill="url(#tw-a1)"/><path d="${L2}" fill="url(#tw-a2)"/><path d="${L3}" fill="url(#tw-a3)"/><path d="${ld}" fill="none" stroke="#e9eef5" stroke-width="1.4" stroke-dasharray="4 4" vector-effect="non-scaling-stroke" opacity=".8"/>
      <line class="now" data-k="now" x1="0" x2="0" y1="4" y2="${H - 16}"/><circle class="nowd" data-k="nowd" r="3.5" cx="0" cy="0"/></svg>`;
  }
  function stageHTML(m, full) {
    return `<div class="tw-stage${full ? ' full' : ''}"><div class="tw-hd"><div class="tw-bt"><b>${m.title || (m.id + ' · ' + m.p.site)}</b><span>${T('에너지 흐름 · 선 굵기 = 실시간 전력(MW)', 'Energy flow · line width = live power (MW)')}</span></div><div class="tw-lv"><i></i>LIVE<time data-k="clock">--:--:--</time><em>${T('1초 갱신 · 시안(가상 값)', '1 s refresh · sample data')}</em></div></div>
      ${stageSvg(m)}
      <div class="tw-kpis"><div class="tk re"><span>${T('재생 비중', 'Renewable share')}</span><div class="rg"><svg viewBox="0 0 44 44"><circle cx="22" cy="22" r="18" class="bg"/><circle cx="22" cy="22" r="18" class="fg" data-k="ring" stroke-dasharray="0 200" transform="rotate(-90 22 22)"/></svg><b data-k="re%">0%</b></div><em>${T('목표(예시) 60% · RE100 100%', 'goal 60% (sample) · RE100 100%')}</em></div>
        <div class="tk"><span>${T('탄소 집약도', 'Carbon intensity')}</span><b><u data-k="inten">0</u><small>gCO₂/kWh</small></b><em data-k="intenc"></em></div>
        <div class="tk"><span>${T('현재 부하', 'Load now')}</span><b><u data-k="load">0.00</u><small>MW</small></b><svg class="mini" viewBox="0 0 120 26" preserveAspectRatio="none"><path data-sp="load" d="" stroke="#e9eef5"/></svg></div>
        <div class="tk"><span>${T('전력비(현재 단가)', 'Power cost (live tariff)')}</span><b><u data-k="cost">0</u><small>${T('만원/h', 'KRW 10k/h')}</small></b><em data-k="tariff"></em></div>
        <div class="tk"><span>${T('오늘 누적', 'Today so far')}</span><b><u data-k="cum">0</u><small>MWh</small></b><em data-k="cumc"></em></div></div>
      ${full ? `<div class="tw-ch"><div class="tw-chh"><b>${T('오늘 24시간 전력 구성', 'Power mix over 24 h')}</b><span><i style="background:${COL.fos}"></i>${T('화석 계통', 'Fossil grid')}<i style="background:${COL.re}"></i>${T('재생 전력', 'Renewable')}<i style="background:${COL.sol}"></i>${T('태양광·배터리', 'Solar · battery')}<i class="ds"></i>${T('총 부하', 'Total load')}</span></div>${chart24(m)}</div>` : ''}</div>`;
  }
  function bindStage(box, m) {
    const q = k => box.querySelector(`[data-k="${k}"]`), sp = k => box.querySelector(`[data-sp="${k}"]`), rb = k => box.querySelector(`[data-rb="${k}"]`), H = hist[m.id] || (hist[m.id] = {}), keys = ['fos', 're', 'sol', 'bat', 'p0', 'p1', 'p2', 'ht', 'co2', 'load'];
    let t0 = Math.floor(Date.now() / 1000), cum = null;
    const val = f => ({ fos: f.gF, re: f.gRE, sol: f.solar, bat: Math.abs(f.bt), p0: f.proc[0], p1: f.proc[1], p2: f.proc[2], ht: f.heat, co2: f.carbon, load: f.load });
    if (!H.load) { keys.forEach(k => H[k] = []); for (let s = -59; s <= 0; s++) { const v = val(flowAt(m, nowH().h + s / 3600, t0 + s)); keys.forEach(k => H[k].push(v[k])); } }
    const maxW = Math.max(.001, m.mw * 1.15), wk = box.querySelector('.tw-svg.cp') ? .5 : 1, wOf = v => (3 + 30 * Math.min(1, v / maxW)) * wk;
    const set = (k, v) => { const e = q(k); if (e) e.textContent = v; };
    const fmt2 = v => v.toFixed(2);
    const today = nowH(); let cumv = 0; for (let h = 0; h < today.h; h += .25) cumv += flowAt(m, h, 0).load * .25; cum = cumv;
    let timer = null;
    function tick(first) {
      if (!first && !box.isConnected) { clearInterval(timer); return; }
      const t = Math.floor(Date.now() / 1000), nh = nowH(), f = flowAt(m, nh.h, t), v = val(f); cum += f.load / 3600;
      keys.forEach(k => { H[k].push(v[k]); if (H[k].length > 60) H[k].shift(); });
      ['fos', 're', 'sol', 'bat', 'p0', 'p1', 'p2', 'ht'].forEach(k => { set(k, fmt2(v[k])); const r = rb(k); if (r) r.setAttribute('stroke-width', wOf(v[k]).toFixed(1)); const p = sp(k); if (p) p.setAttribute('d', sparkP(H[k], 70, 26)); });
      set('co2', fmt2(f.carbon)); set('fosp', Math.round(f.gF / f.load * 100) + '%'); set('rep', Math.round((f.gRE) / f.load * 100) + '%'); set('solp', Math.round(f.solar / f.load * 100) + '%'); set('batp', f.bt >= 0 ? T('방전', 'DISCH') : T('충전', 'CHARGE')); set('p0p', '46%'); set('p1p', '34%'); set('p2p', '20%'); set('htp', m.fr('heat') ? T('재사용', 'REUSED') : T('꺼짐', 'OFF')); set('co2p', f.intenc || '');
      const cr = rb('co2'); if (cr) cr.setAttribute('stroke-width', (wk * 3 + 14 * wk * Math.min(1, f.carbon / Math.max(.001, m.eh * 1.2))).toFixed(1));
      const cp = sp('co2'); if (cp) cp.setAttribute('d', sparkP(H.co2, 56, 26));
      set('re%', Math.round(f.re * 100) + '%'); const rbr = q('rebar'); if (rbr) rbr.style.width = (f.re * 100).toFixed(1) + '%'; const rg = q('ring'); if (rg) rg.setAttribute('stroke-dasharray', (f.re * 113.1).toFixed(1) + ' 200');
      set('inten', Math.round(f.inten)); set('intenc', f.inten < 220 ? T('낮음 · 청정 구간', 'low · clean window') : f.inten < 330 ? T('보통', 'moderate') : T('높음 · 화석 비중 큼', 'high · fossil-heavy')); set('load', fmt2(f.load)); const lp = sp('load'); if (lp) lp.setAttribute('d', sparkP(H.load, 120, 26));
      set('cost', fmt2(f.costH).replace(/\.00$/, '')); set('tariff', f.pm > 1 ? T('피크 단가 ×1.35 (14~17시)', 'peak tariff ×1.35 (14–17h)') : f.pm < 1 ? T('심야 단가 ×0.75', 'night tariff ×0.75') : T('기본 단가', 'standard tariff'));
      set('cum', fmt2(cum)); set('cumc', T('탄소 약 ', '≈ ') + fmt2(cum * f.carbon / Math.max(f.load, .001)) + ' tCO₂'); set('clock', nh.d.toLocaleTimeString('en-GB'));
      const core = q('core'); if (core) { core.setAttribute('stroke-dasharray', `${Math.round(f.load / maxW * 300)} 400`); core.setAttribute('stroke', f.re > .5 ? COL.re : COL.sol); }
      const now = q('now'), nd = q('nowd'), c24 = box.querySelector('.tw-c24'); if (now && c24) { const x = 14 + 972 * nh.h / 24; now.setAttribute('x1', x); now.setAttribute('x2', x); const ldv = f.load, mxv = Math.max(...Array.from({ length: 49 }, (_, i) => { const a = flowAt(m, i / 2, 0); return a.gF + a.gRE + a.solar + Math.max(0, a.bt); })) * 1.12; nd.setAttribute('cx', x); nd.setAttribute('cy', 118 - 18 - 88 * ldv / mxv); }
    }
    tick(true); timer = setInterval(() => tick(false), 1000); return () => clearInterval(timer);
  }
  let stop = null;
  function mountStage(host, m, full) { if (stop) stop(); host.innerHTML = stageHTML(m, full); stop = bindStage(host, m); }


  // ── 한 칸을 한국·일본·싱가포르 3열로 나눈 압축 무대 ──
  const cpCard = (x, y, col, label, id) => `<g class="tw-sc cp" transform="translate(${x} ${y})"><rect width="96" height="46" rx="10"/><circle cx="10" cy="11" r="3" fill="${col}"/><text class="lb" x="18" y="14">${label}</text><text class="vl" x="10" y="39" data-k="${id}">0.00</text><text class="un" x="54" y="39">MW</text></g>`;
  function colSvg(m) {
    const ys = [50, 104, 158, 212], ex = [200, 210, 220, 230], f = flowAt(m, nowH().h, 0);
    const lp = i => `M96 ${ys[i] + 22}C124 ${ys[i] + 22},118 ${ex[i]},150 ${ex[i]}`, rp = i => `M230 ${ex[i]}C262 ${ex[i]},256 ${ys[i] + 22},284 ${ys[i] + 22}`, dur = i => (2.6 + i * .35).toFixed(2);
    const src = [['fos', COL.fos, T('외부 계통', 'GRID')], ['re', COL.re, T('재생 전력', 'RENEWABLE')], ['sol', COL.sol, T('태양광', 'SOLAR')], ['bat', COL.bat, T('배터리', 'BATTERY')]], snk = [['p0', COL.proc, T('압출', 'EXTRUSION')], ['p1', COL.proc, T('성형', 'FORMING')], ['p2', COL.proc, T('후처리', 'FINISH')], ['ht', COL.heat, T('폐열 회수', 'HEAT RECOV.')]];
    return `<svg class="tw-svg cp nofit" viewBox="0 0 380 266" role="img" aria-label="${T('에너지 흐름도', 'Energy flow diagram')}">${defsG()}
      <ellipse cx="190" cy="236" rx="92" ry="20" fill="url(#tw-ground)"/>
      ${src.map(([k, c], i) => ribbon(k, lp(i), c, 3, dur(i), 4, false)).join('')}${snk.map(([k, c], i) => ribbon(k, rp(i), c, 3, dur(i + 2), 4, false)).join('')}${ribbon('co2', 'M217 166C217 110,216 80,216 42', COL.co2, 3, 3.4, 3, false)}
      ${facG('translate(190 204) scale(.42)')}
      ${REDUCED ? '' : [0, 1, 2].map(i => `<circle class="tw-puff twa" cx="${217 + i * 2}" cy="170" r="${3 + i}" style="animation-delay:${(i * .9).toFixed(1)}s"/>`).join('')}
      ${src.map(([k, c, l], i) => cpCard(0, ys[i], c, l, k)).join('')}${snk.map(([k, c, l], i) => cpCard(284, ys[i], c, l, k)).join('')}
      <g class="tw-sc cp co2" transform="translate(120 0)"><rect width="140" height="42" rx="10"/><circle cx="10" cy="11" r="3" fill="${COL.co2}"/><text class="lb" x="18" y="14">${T('실시간 탄소', 'LIVE CARBON')}</text><text class="vl" x="10" y="37" data-k="co2">0.00</text><text class="un" x="62" y="37">tCO₂/h</text></g>
    </svg>`;
  }
  function colHTML(m, c, nPl, drill) {
    const k = (lab, key, unit) => `<div><span>${lab}</span><b><u data-k="${key}">0</u><small>${unit}</small></b></div>`;
    return `<div class="tw-col"><button type="button" class="tw-cb" data-c="${c}" data-own="1"><b>${cn(c)}</b><span>${nPl} ${T('개 공장', 'plants')}${drill ? T(' · 자세히 ›', ' · details ›') : ''}</span></button>
      <div class="tw-re100"><svg viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="18" class="bg"/><circle cx="22" cy="22" r="18" class="fg" data-k="ring" stroke-dasharray="0 200" transform="rotate(-90 22 22)"/></svg><div class="rt"><span>${T('RE100 달성률', 'RE100 progress')}</span><b data-k="re%">0%</b><div class="rbar"><i data-k="rebar"></i><u></u></div><em>${T('목표(예시) 60% · RE100 100%', 'goal 60% (sample) · RE100 100%')}</em></div></div>
      ${colSvg(m)}
      <div class="tw-ckp">${k(T('탄소 집약도', 'Carbon intensity'), 'inten', 'gCO₂/kWh')}${k(T('현재 부하', 'Load now'), 'load', 'MW')}${k(T('전력비', 'Power cost'), 'cost', T('만원/h', 'KRW 10k/h'))}${k(T('오늘 누적', 'Today so far'), 'cum', 'MWh')}</div></div>`;
  }

  function paintPlant(box, id) {
    const m = M(id), set = onSet(id);
    box.innerHTML = `<div class="tw-host"></div>
      <div class="tw-levs">${LEV.map(l => { const on = set.has(l.k), sv = l.save * m.p.mw / .8; return `<button type="button" class="tw-lev${on ? ' on' : ''}" data-k="${l.k}" aria-pressed="${on}" data-own="1"><b>${T(l.ko, l.en)}</b><i class="sw"></i><span>${T('감축', 'Cut')} -${Math.round(l.cut * 100)}%${l.re ? ' · RE +' + l.re + '%p' : ''}</span><em>${T(l.eff[0], l.eff[1])}</em><u>${T('절감', 'Saves')} ${fmt(sv, 2)} ${T('억/년', 'KRW100M/yr')}</u></button>`; }).join('')}</div>
      <p class="mnote">${T('연간 탄소 절감 ', 'Annual carbon saved ')}<b>${fmt(m.saveT, 0)}</b> tCO₂ · ${T('연간 비용 절감 ', 'annual cost saved ')}<b>${fmt(m.saveW, 2)}</b>${T('억 원', ' KRW 100M')} — ${T('수치는 모두 시안용 가상 값입니다. 수단을 누르면 흐름·재생 비중·탄소·비용이 바로 바뀝니다.', 'All values are sample data. Toggle a lever to update flows, renewable share, carbon and cost.')}</p>`;
    mountStage(box.querySelector('.tw-host'), m, true);
    box.querySelectorAll('.tw-lev').forEach(b => b.addEventListener('click', () => { const k = b.dataset.k; set.has(k) ? set.delete(k) : set.add(k); paintPlant(box, id); }));
  }

  // ── 전체·국가: 국가별 큰 무대 3개(공장 이름만 나열) ──
  function cmet(c, ids) {
    const a = agg2(ids), on = new Set(), cnt = {}; a.ms.forEach(m => m.on.forEach(k => { on.add(k); cnt[k] = (cnt[k] || 0) + 1; }));
    return Object.assign(a, { id: c, title: cn(c) + ' · ' + a.n + T('개 공장', ' plants'), p: { site: '', c }, s0: a.ms.reduce((s, m) => s + m.s0 * m.mw, 0) / a.mw, reS: a.re, fos: 1 - a.re, eh: a.base, cut: a.base ? 1 - a.carbon / a.base : 0, on, fr: k => (cnt[k] || 0) / a.n, seed: c.length });
  }
  function paintGroups(box) {
    const cs = ['한국', '일본', '싱가포르'].filter(c => (ST_.c ? c === ST_.c : true) && PL().some(p => p.c === c)), all = agg2(PL().filter(p => !ST_.c || p.c === ST_.c).map(p => p.id));
    const sum = `<div class="tw-sum">${stat_(T('RE100 달성률', 'RE100 progress'), Math.round(all.re * 100) + '%', T('목표(예시) 60% · RE100 100%', 'goal 60% (sample) · RE100 100%'), 're100')}${stat_(T('실시간 탄소 발생', 'Live carbon rate'), fmt(all.carbon, 1), 'tCO₂/h', 'big', all.carbon)}${stat_(T('감축 수단 가동', 'Levers active'), all.lev, T('/ ' + all.n * 7 + '개', '/ ' + all.n * 7))}${stat_(T('연간 탄소 절감', 'Annual carbon saved'), fmt(all.saveT, 0), 'tCO₂/yr')}${stat_(T('연간 비용 절감', 'Annual cost saved'), fmt(all.saveW, 1), T('억 원/yr', 'KRW 100M/yr'))}</div>`;
    const lv = `<div class="tw-lv"><i></i>LIVE<time data-k="clock">--:--:--</time><em>${T('1초 갱신 · 시안(가상 값) · 선 굵기 = 실시간 전력(MW)', '1 s refresh · sample data · line width = live power (MW)')}</em></div>`;
    if (ST_.c) {
      box.innerHTML = sum + cs.map(c => `<section class="tw-grp" data-c="${c}"><div class="tw-host"></div></section>`).join('') + `<p class="mnote">${T('위의 공장 이름을 누르면 해당 공장의 상황을 자세히 봅니다. 수치는 시안용 가상 값입니다.', 'Click a plant name above for its details. Values are sample data.')}</p>`;
      stops.forEach(f => f()); stops = [];
      box.querySelectorAll('.tw-grp').forEach(g => { const c = g.dataset.c, m = cmet(c, PL().filter(p => p.c === c).map(p => p.id)); const host = g.querySelector('.tw-host'); host.innerHTML = stageHTML(m, false); stops.push(bindStage(host, m)); });
      return;
    }
    box.innerHTML = sum + `<div class="tw-cols">${cs.map(c => `<section class="tw-colw" data-c="${c}"></section>`).join('')}</div>` + `<p class="mnote">${T('한 칸을 한국·일본·싱가포르로 나눈 화면입니다. 국가 이름을 누르면 국가별로, 위의 공장 이름을 누르면 공장별로 자세히 봅니다. 수치는 시안용 가상 값입니다.', 'One panel split into Korea, Japan and Singapore. Click a country for details or a plant name above. Values are sample data.')}</p>`;
    stops.forEach(f => f()); stops = [];
    box.querySelectorAll('.tw-colw').forEach((el, i) => { const c = el.dataset.c, ids = PL().filter(p => p.c === c).map(p => p.id), m = cmet(c, ids); el.innerHTML = colHTML(m, c, ids.length, true); if (i === 0) el.insertAdjacentHTML('afterbegin', lv); stops.push(bindStage(el, m)); });
    box.querySelectorAll('.tw-cb').forEach(b => b.addEventListener('click', () => { ST_.lvl = 'country'; ST_.c = b.dataset.c; rerender(); }));
  }
  let stops = [];
  function pick(id) { S.plant = id; S.plSel = true; ST_.lvl = 'plant'; ST_.c = D.plant(id).c; rerender(); }

  function section() {
    if (stop) { stop(); stop = null; } stops.forEach(f => f()); stops = [];
    const box = h('div', { class: 'tw-body' });
    const tabs = h('div', { class: 'tw-tabs', role: 'tablist', 'aria-label': T('공장 선택', 'Select plant') });
    const mk = (cls, on, fn, ...kids) => { const b = h('button', { type: 'button', class: cls + (on ? ' on' : ''), role: 'tab', 'aria-selected': on ? 'true' : 'false', 'data-own': 1 }, ...kids); b.addEventListener('click', fn); return b; };
    tabs.append(mk('tw-tab all', ST_.lvl === 'all', () => { ST_.lvl = 'all'; ST_.c = null; S.plSel = false; rerender(); }, T('전체', 'All')));
    ['한국', '일본', '싱가포르'].forEach(c => { const ids = PL().filter(p => p.c === c); if (!ids.length) return;
      tabs.append(h('div', { class: 'tw-tg' }, mk('tw-tc', ST_.lvl === 'country' && ST_.c === c, () => { ST_.lvl = 'country'; ST_.c = c; S.plSel = false; rerender(); }, cn(c)),
        ...ids.map(p => mk('tw-tab', ST_.lvl === 'plant' && S.plant === p.id, () => pick(p.id), h('i', { class: 'tw-dot st-' + M(p.id).st.level }), h('b', {}, p.id), h('span', {}, p.site))))); });
    const c = card(T('관제 공장 · 에너지 흐름 트윈', 'Monitored plants · energy-flow twin'), T('예시', 'Sample'), tabs, box); c.classList.add('twc');
    if (ST_.lvl === 'plant') paintPlant(box, S.plant); else paintGroups(box);
    if (window.__twT) clearInterval(window.__twT);
    window.__twT = setInterval(() => { if (!c.isConnected) { clearInterval(window.__twT); if (stop) stop(); stops.forEach(f => f()); stops = []; return; } c.querySelectorAll('.tw-live').forEach(e => { const v = +e.dataset.v; if (v) e.textContent = fmt(v * (1 + (Math.random() - .5) * .04), v > 20 ? 1 : 2); }); }, 1200);
    return c;
  }
  window.TWIN = { section, lvl: () => ST_.lvl, reset: () => { ST_.lvl = 'all'; ST_.c = null; } };
})();
