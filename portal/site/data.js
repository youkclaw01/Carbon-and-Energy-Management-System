'use strict';
// AMA 모의 데이터 생성기. 모든 값은 시드 고정으로 생성한 가상 자료이며 실제 운영과 연결되어 있지 않습니다.
// 원천(일별 실적)만 만들고, 합계·사용률·여유·상태·예측은 아래 함수로 계산합니다(저장하지 않음).
const D = (() => {
  const START = Date.UTC(2026, 0, 1), DAY = 864e5, TODAY = 292, N = 293;            // 기준일 2026-10-20(모의), 1/1~10/20
  const ymd = i => new Date(START + i * DAY).toISOString().slice(0, 10);
  const di = s => Math.round((Date.parse(s + 'T00:00:00Z') - START) / DAY);
  const mon = i => new Date(START + i * DAY).getUTCMonth(), dow = i => new Date(START + i * DAY).getUTCDay();
  const dim = m => new Date(Date.UTC(2026, m + 1, 0)).getUTCDate();
  const mfirst = i => i - (new Date(START + i * DAY).getUTCDate() - 1);
  const rng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const sumA = a => a.reduce((s, v) => s + v, 0);
  // 공장 마스터(가상 위치). mw=평균 전력(MW), pi=전력 원단위(MWh/t), ur/cr=연간 허용량·예산 대비 누적 사용 비율(시안 시나리오 설계값)
  const P = [
    { id: 'KR-01', c: '한국', site: '포항', lat: 36.02, lon: 129.37, mw: 143.7, pi: 0.10859, k1: 40.54, ur: .84, cr: .80, owner: '김도윤', proc: ['압출', '성형', '후처리'] },
    { id: 'KR-02', c: '한국', site: '광양', lat: 34.94, lon: 127.70, mw: 98.8, pi: 0.10861, k1: 40.54, ur: .93, cr: .97, owner: '박서준', proc: ['압출', '성형', '후처리'] },
    { id: 'KR-03', c: '한국', site: '울산', lat: 35.54, lon: 129.31, mw: 67.4, pi: 0.10869, k1: 40.5, ur: .62, cr: .60, owner: '이하늘', proc: ['압출', '성형', '후처리'] },
    { id: 'KR-04', c: '한국', site: '당진', lat: 36.89, lon: 126.65, mw: 62.9, pi: 0.10861, k1: 40.54, ur: .66, cr: .64, owner: '최민재', proc: ['압출', '성형', '후처리'] },
    { id: 'KR-05', c: '한국', site: '광주', lat: 35.16, lon: 126.85, mw: 247.0, pi: 0.44148, k1: 8.06, ur: .58, cr: .57, owner: '정유진', proc: ['압출', '성형', '후처리'] },
    { id: 'JP-01', c: '일본', site: '기타큐슈', lat: 33.88, lon: 130.88, mw: 341.2, pi: 0.44153, k1: 7.86, ur: .78, cr: .76, owner: '다나카 켄', proc: ['압출', '성형', '후처리'] },
    { id: 'JP-02', c: '일본', site: '구라시키', lat: 34.60, lon: 133.77, mw: 277.2, pi: 0.44152, k1: 7.86, ur: .64, cr: .66, owner: '사토 유이', proc: ['압출', '성형', '후처리'] },
    { id: 'JP-03', c: '일본', site: '지바', lat: 35.60, lon: 140.12, mw: 264.4, pi: 0.44114, k1: 7.87, ur: .60, cr: .58, owner: '스즈키 렌', proc: ['압출', '성형', '후처리'] },
    { id: 'JP-04', c: '일본', site: '나고야', lat: 35.18, lon: 136.91, mw: 234.6, pi: 0.44128, k1: 7.87, ur: .55, cr: .56, owner: '이토 아야', proc: ['압출', '성형', '후처리'] },
    { id: 'SG-01', c: '싱가포르', site: '주롱', lat: 1.335, lon: 103.84, mw: 111.1, pi: 0.44106, k1: 8.95, ur: .68, cr: .71, owner: '탄 웨이', proc: ['압출', '성형', '후처리'] },
    { id: 'SG-02', c: '싱가포르', site: '투아스', lat: 1.335, lon: 103.705, mw: 78.4, pi: 0.44084, k1: 8.96, ur: .72, cr: .70, owner: '리 메이', proc: ['압출', '성형', '후처리'] },
    { id: 'SG-03', c: '싱가포르', site: '우드랜즈', lat: 1.425, lon: 103.80, mw: 89.8, pi: 0.44202, k1: 8.93, ur: .63, cr: .62, owner: '응 지아', proc: ['압출', '성형', '후처리'] }
  ];
  const EF = { 한국: .45, 일본: .46, 싱가포르: .41 }, PW = { 한국: 150, 일본: 190, 싱가포르: 210 }, FU = { 한국: 15000, 일본: 17000, 싱가포르: 19000 }, EFG = .0561;   // 가상 값
  const SEASON = [1.0, .98, .97, .96, 1.0, 1.06, 1.12, 1.16, 1.04, .98], DOWF = [.80, 1.02, 1.04, 1.05, 1.04, 1.02, .86], FX = [1.00, 1.01, 1.02, 1.00, .99, 1.01, 1.03, 1.05, 1.04, 1.06];
  const W = [.078, .074, .080, .081, .085, .090, .096, .100, .088, .083, .075, .070];   // 월별 목표 분포(계절 가중)
  const S = {};     // id -> 일별 배열
  P.forEach((p, k) => {
    const r = rng(1000 + k * 77), a = { pw: [], pk: [], pr: [], hr: [], ut: [], df: [], s1: [], s2: [], co: [], ps: [] };
    for (let i = 0; i < N; i++) {
      const m = mon(i); let ev = 1;
      if (p.id === 'KR-02' && m === 9) ev = 1 + Math.min(.22, .05 + (i - 273) * .013);            // 10월 사용량 증가(시안 "원인 분석 KR-02")
      if (p.id === 'KR-01' && m === 9) ev = 1.03;
      const mw = p.mw * SEASON[m] * DOWF[dow(i)] * ev * (1 + (r() - .5) * .08), pw = mw * 24;
      const ut = Math.min(.98, Math.max(.55, .80 * (DOWF[dow(i)] * .98) + (r() - .5) * .1)), pr = pw / p.pi * (1 + (r() - .5) * .06);
      const s2 = pw * EF[p.c], s1 = s2 * (p.k1 != null ? p.k1 : .43) * (1 + (r() - .5) * .08), ps = .3 + (r() - .5) * .12;
      const pk = mw * (1.45 + (r() - .5) * .22);
      const cost = pw * 1000 * PW[p.c] * FX[m] * (1 + .25 * ps) + s1 / EFG * FU[p.c] * .3 * FX[m];   // 철강 공정은 석탄·코크스 중심이라 연료 단가를 가스(FU)의 30%로 둠(모의)
      a.pw.push(pw); a.pk.push(pk); a.pr.push(pr); a.hr.push(24 * ut); a.ut.push(ut * 100); a.df.push(.5 + r() * 2.2); a.s1.push(s1); a.s2.push(s2); a.co.push(cost); a.ps.push(ps);
    }
    S[p.id] = a;
  });
  const pre = {}; Object.keys(S).forEach(id => { pre[id] = {}; Object.keys(S[id]).forEach(k => { const c = [0]; S[id][k].forEach(v => c.push(c[c.length - 1] + v)); pre[id][k] = c; }); });
  const sum = (id, k, a, b) => pre[id][k][b + 1] - pre[id][k][a];                    // 일 인덱스 a..b 합
  const em = (id, a, b) => sum(id, 's1', a, b) + sum(id, 's2', a, b);
  const day = (id, k, i) => k === 'em' ? S[id].s1[i] + S[id].s2[i] : S[id][k][i];
  // 목표(연간 허용량 C, 연간 예산 B): 설계한 사용 비율이 나오도록 실적에서 역산(결정적)
  const wd = i => W[mon(i)] / dim(mon(i));
  const T = {};
  P.forEach(p => { const sw = sumA(Array.from({ length: N }, (_, i) => wd(i))); T[p.id] = { C: em(p.id, 0, TODAY) / (p.ur * sw), B: sum(p.id, 'co', 0, TODAY) / (p.cr * sw) }; });
  const target = (id, a, b, kind) => { let s = 0; for (let i = a; i <= b; i++) s += wd(i); return T[id][kind === 'cost' ? 'B' : 'C'] * s; };
  const plant = id => P.find(p => p.id === id);
  // 설비(수신 상태): 정상/주의/없음. 기준 시각 2026-10-20 12:00
  const EQN = ['압출기 1호', '성형기 2호', '냉각탑', '컴프레서', '보일러', '수배전반'];
  const EQ = {};
  P.forEach(p => { EQ[p.id] = EQN.map((n, j) => { let st = '정상', last = 2 + j; if (p.id === 'SG-02' && (j === 3 || j === 4)) { st = '없음'; last = 14 * 60 + j * 5; } else if (p.id === 'SG-02' && j === 2) { st = '주의'; last = 45; } else if (p.id === 'KR-03' && j === 5) { st = '주의'; last = 38; } return { id: 'EQ-' + p.id.slice(3) + (j + 1), name: n, proc: p.proc[j % 3], st, lastMin: last }; }); });
  const delay = id => EQ[id].filter(e => e.st === '없음').length;
  const recv = id => Math.round(100 * EQ[id].filter(e => e.st === '정상').length / EQ[id].length);
  // 확인 필요 항목(상태 규칙 + 수동 검토). 상태: open | mailed | resolved
  const RV = [
    { id: 'RV-101', plant: 'KR-02', type: '에너지 비용 상승', sev: 'er', at: '2026-10-20 09:10', st: 'open' },
    { id: 'RV-102', plant: 'KR-01', type: '배출 목표 근접(주의)', sev: 'wn', at: '2026-10-20 08:40', st: 'open' },
    { id: 'RV-103', plant: 'JP-01', type: '산정 근거 검토', sev: 'wn', at: '2026-10-19 17:25', st: 'open' },
    { id: 'RV-104', plant: 'SG-02', type: '자료 수신 지연', sev: 'dl', at: '2026-10-20 06:05', st: 'open' }
  ];
  // 기간: 프리셋은 기준일(TODAY) 기준으로 환산
  const quarterOf = i => Math.floor(mon(i) / 3);
  const preset = k => {
    if (k === 'month') return [mfirst(TODAY), TODAY];
    if (k === 'm1') return [TODAY - 29, TODAY];
    if (k === 'm3') return [TODAY - 89, TODAY];
    if (k === 'lastq') { const q = quarterOf(TODAY) - 1, a = di('2026-' + String(q * 3 + 1).padStart(2, '0') + '-01'), b = di('2026-' + String(q * 3 + 3).padStart(2, '0') + '-' + dim(q * 3 + 2)); return [a, b]; }
    if (k === 'ytd') return [0, TODAY];
    return [0, TODAY];
  };
  const PRESETS = [['month', '이번 달'], ['m1', '최근 1개월'], ['m3', '최근 3개월'], ['lastq', '지난 분기'], ['ytd', '올해 누적']];
  // 상태 규칙(설정값). 사용률 = 기간 누적 ÷ 기간 목표, 보조 조건: 전월 동일 기간 대비 +10% 급증
  const RULE = { warn: .7, crit: .9, surge: .10, delayMin: 360 };
  const lvl = u => u >= RULE.crit ? 'er' : u >= RULE.warn ? 'wn' : 'ok';
  const up = l => l === 'ok' ? 'wn' : 'er';
  const pm = (a, b) => { const n = b - a + 1, pb = a - 1, pa = pb - n + 1; return pa >= 0 ? [pa, pb] : null; };
  const status = (id, a, b, kind = 'em') => {
    const act = kind === 'cost' ? sum(id, 'co', a, b) : em(id, a, b), tg = target(id, a, b, kind), u = act / tg, why = [];
    let l = lvl(u); why.push(`${kind === 'cost' ? '예산' : '목표'} 대비 ${Math.round(u * 100)}% 사용(기준: 70% 주의·90% 경고)`);
    let mom = null; const q = pm(a, b);
    if (q) { const prev = kind === 'cost' ? sum(id, 'co', q[0], q[1]) : em(id, q[0], q[1]); mom = act / prev - 1; if (b === TODAY) { why.push(`직전 동일 기간 대비 ${mom >= 0 ? '+' : ''}${(mom * 100).toFixed(1)}%`); if (mom >= RULE.surge) { l = up(l); why.push('급증(+10% 이상)으로 한 단계 상향'); } } }
    const rvN = RV.filter(r => r.plant === id && r.st !== 'resolved').length; if (rvN) why.push(`검토 대기 ${rvN}건`);
    const dl = delay(id); if (dl) why.push(`수신 지연 설비 ${dl}대(6시간 이상 무수신)`);
    return { level: dl ? 'dl' : l, perf: l, usage: u, act, tg, mom, why, delayed: dl };
  };
  // 이번 달 예측: 월 누적 + 요일 보정 추세. 예상 범위는 최근 28일 변동폭 기반 80% 구간(±1.28σ)
  const forecast = (id, kind = 'em') => {
    const m = mon(TODAY), a0 = mfirst(TODAY), last = a0 + dim(m) - 1, v = i => day(id, ({ em: 'em', cost: 'co', pr: 'pr', pw: 'pw' })[kind] || 'em', i);
    const base = Array.from({ length: 56 }, (_, j) => TODAY - 55 + j), mean = x => sumA(x) / x.length, all = mean(base.map(v)), f = Array(7).fill(0).map((_, d) => { const xs = base.filter(i => dow(i) === d).map(v); return mean(xs) / all; });
    const L = mean(Array.from({ length: 14 }, (_, j) => TODAY - 13 + j).map(i => v(i) / f[dow(i)]));
    const res = Array.from({ length: 28 }, (_, j) => TODAY - 27 + j).map(i => v(i) / f[dow(i)] - L), sd = Math.sqrt(mean(res.map(x => x * x)));
    const days = [], act = [], proj = [], lo = [], hi = []; let c = 0, pc = 0, k = 0;
    for (let i = a0; i <= last; i++) {
      days.push(i);
      if (i <= TODAY) { c += v(i); act.push(c); proj.push(i === TODAY ? c : null); lo.push(i === TODAY ? c : null); hi.push(i === TODAY ? c : null); pc = c; }
      else { k++; pc += L * f[dow(i)]; const w = 1.28 * sd * Math.sqrt(k) * mean(f); act.push(null); proj.push(pc); lo.push(pc - w); hi.push(pc + w); }
    }
    const tgt = (kind === 'em' || kind === 'cost') ? target(id, a0, last, kind) : null, est = proj[proj.length - 1], ratio = tgt ? est / tgt : null, mtd = act[TODAY - a0];
    const cross = arr => { const j = arr.findIndex((x, n) => x != null && days[n] > TODAY && tgt != null && x >= tgt); return j < 0 ? null : days[j]; };
    const lv = ratio == null ? 'ok' : ratio >= 1 ? 'over' : ratio >= RULE.crit ? 'er' : ratio >= RULE.warn ? 'wn' : 'ok';
    return { id, kind, days, act, proj, lo, hi, tgt, est, ratio, mtd, level: lv, crossMid: cross(proj), crossHi: cross(hi), daysLeft: last - TODAY, a0, last, estLo: lo[lo.length - 1], estHi: hi[hi.length - 1] };
  };
  // 비용 요인 분해(직전 동일 기간 대비): 사용량 / 환율 / 단가·시간대
  const costDecomp = (id, a, b) => {
    const q = pm(a, b); if (!q) return null;
    const c1 = sum(id, 'co', a, b), c0 = sum(id, 'co', q[0], q[1]), u1 = sum(id, 'pw', a, b), u0 = sum(id, 'pw', q[0], q[1]);
    const fx = (() => { let x1 = 0, x0 = 0; for (let i = a; i <= b; i++) x1 += FX[mon(i)]; for (let i = q[0]; i <= q[1]; i++) x0 += FX[mon(i)]; return (x1 / (b - a + 1)) / (x0 / (q[1] - q[0] + 1)); })();
    const usage = c0 * (u1 / u0 - 1), fxE = c0 * (u1 / u0) * (fx - 1), price = c1 - c0 * (u1 / u0) - fxE;
    return { c0, c1, delta: c1 - c0, usage, fx: fxE, price, uPct: u1 / u0 - 1 };
  };
  const hourly = (id, i) => { const p = plant(id), r = rng(5000 + i * 13 + P.indexOf(p)), shape = h => .72 + .28 * Math.sin((h - 6) / 24 * 2 * Math.PI * 1.0) + (h >= 14 && h <= 17 ? .18 : 0) - (h <= 4 ? .12 : 0), avg = S[id].pw[i] / 24;
    const raw = Array.from({ length: 24 }, (_, h) => Math.max(.2, shape(h)) * (1 + (r() - .5) * .06)), k = S[id].pw[i] / sumA(raw);
    return { act: raw.map(x => x * k), base: raw.map(x => x * k * .9), avg };
  };
  const load = (id, i) => { const r = rng(7000 + i * 7 + P.indexOf(plant(id)) * 3); return plant(id).proc.map((n, j) => ({ n, v: Array.from({ length: 24 }, (_, h) => Math.round(Math.min(100, Math.max(8, 55 + 30 * Math.sin((h - 5 + j * 2) / 24 * 2 * Math.PI) + (r() - .5) * 18)))) })); };
  const fmt = (v, d = 0) => v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
  // 정합성 검사(생성 직후 자동 실행: 합계 일치·비용 구성·상태 규칙 일치)
  const check = () => {
    const out = []; let ok = true;
    const t = (name, cond, info) => { out.push({ name, ok: !!cond, info }); if (!cond) ok = false; };
    const all = sumA(P.map(p => em(p.id, 0, TODAY))), byC = sumA(['한국', '일본', '싱가포르'].map(c => sumA(P.filter(p => p.c === c).map(p => em(p.id, 0, TODAY)))));
    t('공장합 = 국가합', Math.abs(all - byC) < 1e-6, all.toFixed(1));
    const mo = sumA(Array.from({ length: 10 }, (_, m) => { const a = di('2026-' + String(m + 1).padStart(2, '0') + '-01'), b = Math.min(TODAY, a + dim(m) - 1); return em('KR-01', a, b); }));
    t('월별 합 = 누적(KR-01)', Math.abs(mo - em('KR-01', 0, TODAY)) < 1e-6);
    t('공장 수 12(KR5·JP4·SG3)', P.length === 12 && P.filter(p => p.c === '한국').length === 5 && P.filter(p => p.c === '일본').length === 4 && P.filter(p => p.c === '싱가포르').length === 3);
    P.forEach(p => { const s = status(p.id, 0, TODAY), exp = lvl(Math.max(0, 0) + s.usage); t('상태 규칙 일치 ' + p.id, s.perf === exp || s.mom >= RULE.surge, `${(s.usage * 100).toFixed(0)}% → ${s.perf}`); });
    t('KR-01 YTD 사용률 약 84%', Math.abs(status('KR-01', 0, TODAY).usage - .84) < .005);
    t('SG-02 지연 표시', status('SG-02', 0, TODAY).level === 'dl');
    t('KR-02 이번 달 예측 한도 초과 가능', forecast('KR-02', 'em').ratio > .9, forecast('KR-02', 'em').ratio.toFixed(2));
    return { ok, out };
  };
  return { P, S, T, RV, EQ, EF, PW, TODAY, N, ymd, di, mon, dow, dim, mfirst, sum, em, day, target, plant, status, forecast, costDecomp, hourly, load, delay, recv, preset, PRESETS, RULE, lvl, sumA, fmt, check, W, FX, pm };
})();
const sumA = D.sumA, fmt = D.fmt;
