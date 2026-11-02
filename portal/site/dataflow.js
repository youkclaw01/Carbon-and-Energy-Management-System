'use strict';
// 데이터 흐름: 전기(설비) → 공장 VM → 중앙 수신 → 메달리온(Bronze·Silver·Gold) → 전력·탄소 그래프·AI 분석을 애니메이션으로 보여 줍니다.
// 한국 KR-01은 실제 수신 중인 값(중앙 수신 앱·gold 요약)과 실제 이벤트로 움직입니다. 일본·싱가포르는 자료 경계상 값을 읽지 않고 구조만 모의 속도로 보여 줍니다.
// AI 분석 단계는 /api/ai/insights(신규 Foundry gpt-6.1-sol)를 호출합니다. 모델이 실패하면 실패를 그대로 보여 주며 규칙 기반 문구로 대체하지 않습니다. 모든 자료는 합성입니다.
(function () {
  const BASE = { 'KR-01': '/api/plant/v1/', 'JP-01': '/api/plant-jp/v1/', 'SG-01': '/api/plant-sg/v1/' };
  const n0 = v => v == null || isNaN(v) ? '–' : Math.round(v).toLocaleString('ko-KR'), n1 = v => v == null || isNaN(v) ? '–' : (Math.round(v * 10) / 10).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const TC = { 'meter.reading': 'var(--cy)', 'energy.flow': 'var(--yl)', 'process.state': 'var(--gr)', 'production.counter': 'var(--pu)', 'production.workorder': 'var(--pu)', 'shipment.dispatched': 'var(--pu)', 'alarm.event': 'var(--rd)', heartbeat: 'var(--dl)' };
  const TL = { 'meter.reading': '전력 계량', 'energy.flow': '에너지 수지', 'process.state': '설비 상태', 'production.counter': '생산', 'production.workorder': '작업지시', 'shipment.dispatched': '출하', 'alarm.event': '알람', heartbeat: '하트비트' };
  const SITES = { 'KR-01': { n: '포항(한국)', live: true, st: 'stamaprdkrcbronze01 (koreacentral)' }, 'KR-02': { n: '광양(한국)', live: true, st: 'stamaprdkrcbronze01 (koreacentral)' }, 'KR-03': { n: '울산(한국)', live: true, st: 'stamaprdkrcbronze01 (koreacentral)' }, 'KR-04': { n: '당진(한국)', live: true, st: 'stamaprdkrcbronze01 (koreacentral)' }, 'KR-05': { n: '광주(한국)', live: true, st: 'stamaprdkrcbronze01 (koreacentral)' }, 'JP-01': { n: '기타큐슈(일본)', live: true, st: 'stamaprdjpelake01 (japaneast)' }, 'JP-02': { n: '구라시키(일본)', live: true, st: 'stamaprdjpelake01 (japaneast)' }, 'JP-03': { n: '지바(일본)', live: true, st: 'stamaprdjpelake01 (japaneast)' }, 'JP-04': { n: '나고야(일본)', live: true, st: 'stamaprdjpelake01 (japaneast)' }, 'SG-01': { n: '주롱(싱가포르)', live: true, st: 'stamaprdsealake01 (southeastasia)' }, 'SG-02': { n: '투아스(싱가포르)', live: true, st: 'stamaprdsealake01 (southeastasia)' }, 'SG-03': { n: '우드랜즈(싱가포르)', live: true, st: 'stamaprdsealake01 (southeastasia)' } };
  const STEPS = [
    { k: 'power', t: '① 전기가 들어와 설비를 돌립니다', b: '외부 계통·재생 PPA·태양광·배터리에서 들어온 전기가 압출·성형·후처리·유틸리티 설비로 흘러갑니다. 설비마다 계량기(M-코드)가 있어 5초마다 전력(kW)과 누적 전력량(kWh)을 읽습니다.' },
    { k: 'vm', t: '② 공장 VM이 읽고, 묶고, 서명합니다', b: '공장 VM의 앱이 계량·설비 상태·생산·알람을 이벤트로 만들어 먼저 자기 디스크(outbox)에 저장하고, 80건 단위로 묶어 HMAC 서명을 붙여 보냅니다. 연결이 끊겨도 쌓아 두었다가 이어서 보냅니다.' },
    { k: 'ingest', t: '③ 중앙 수신이 검사하고 받습니다', b: '해당 리전의 중앙 수신 앱이 서명·시각·형식·event_id를 검사합니다. 같은 이벤트가 다시 오면 중복으로 버리고, 위조·형식 오류는 거절합니다. 통과한 이벤트만 저장소로 넘어갑니다.' },
    { k: 'medal', t: '④ 메달리온으로 적재·정제합니다', b: 'Bronze는 받은 원본을 그대로(추가 전용), Silver는 5분마다 검증·형 변환·중복 제거한 Parquet, Gold는 시간별 전력·탄소·가동률·생산 집계입니다. 모두 같은 리전 저장소 안에서만 처리됩니다.' },
    { k: 'use', t: '⑤ Gold가 그래프와 AI 분석이 됩니다', b: '전력 데이터는 전력 그래프, 배출 데이터는 탄소 그래프로 가고, 둘을 함께 읽는 AI 분석 단계가 피크·재생 비중·가동 이상 같은 인사이트와 조치를 제안합니다(현재는 규칙 기반 시안).' }];
  function mini(t, series, h) {
    if (!t || t.length < 2) return '<div class="df-empty">자료 수집 중…</div>'; const W = 440, H = h || 150, L = 38, R = 8, T = 8, B = 20, all = series.flatMap(s => s.d), mx = Math.max(...all, 1) * 1.1, x = i => L + i / (t.length - 1) * (W - L - R), y = v => T + (1 - v / mx) * (H - T - B); let s = '';
    for (let k = 0; k <= 3; k++) { const v = mx * k / 3; s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-width=".6"/><text x="${L - 5}" y="${y(v) + 3}" text-anchor="end">${n0(v)}</text>`; }
    [0, .5, 1].forEach(k => { const i = Math.round((t.length - 1) * k); s += `<text x="${x(i)}" y="${H - 5}" text-anchor="${k == 0 ? 'start' : k == 1 ? 'middle' : 'end'}">${esc(t[i])}</text>`; });
    series.forEach(q => { const pts = q.d.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' '); if (q.fill) s += `<polygon points="${pts} ${x(t.length - 1)},${y(0)} ${x(0)},${y(0)}" fill="${q.c}" opacity=".16"/>`; s += `<polyline points="${pts}" fill="none" stroke="${q.c}" stroke-width="1.8" stroke-linejoin="round"/>`; });
    return `<svg viewBox="0 0 ${W} ${H}" class="df-svg" style="height:${H}px">${s}</svg><div class="df-leg">${series.map(q => `<span><i style="background:${q.c}"></i>${q.n}</span>`).join('')}</div>`;
  }
  const node = (id, x, y, w, h, title, sub) => `<g class="df-n" id="n-${id}" data-step="${id}" tabindex="0"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14"/><text class="df-nt" x="${x + 14}" y="${y + 26}">${title}</text><text class="df-ns" x="${x + 14}" y="${y + 44}">${sub}</text></g>`;
  V.flow = () => {
    let site = 'KR-01'; const get = p => fetch((BASE[site] || BASE[site.slice(0, 2) + '-01']) + p, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
    const root = h('div', { class: 'view dfview' }); let step = 0, auto = true, lastClick = 0, cursor = 0, pend = [], timers = [], raf = 0, S = { sum: null, gd: null, sites: null };
    const RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    root.innerHTML = `<div class="card df-top"><div><b>데이터 흐름</b> <span class="tag">합성 자료</span><p>전기가 설비에서 쓰이는 순간부터 공장 VM, 중앙 수신, 메달리온 적재, 그래프와 AI 분석까지 한 번에 따라갑니다. 점 하나는 실제로 전송된 이벤트 하나입니다(속도는 알아보기 쉽게 느리게 표시).</p></div><div class="df-tabs" id="dfTabs"></div></div>
    <div class="card df-stage"><svg id="dfSvg" viewBox="0 0 1200 430" class="df-flow" role="img" aria-label="데이터 흐름 도식">
      <defs><marker id="dfa" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8z" fill="var(--mut)"/></marker></defs>
      <g class="df-links"><path d="M200 215 H250" marker-end="url(#dfa)"/><path d="M430 215 H480" marker-end="url(#dfa)"/><path d="M660 215 H710" marker-end="url(#dfa)"/><path class="df-vl" d="M820 168 V190"/><path class="df-vl" d="M820 268 V290"/>
        <path class="df-out" d="M930 330 C960 330 960 100 990 100" /><path class="df-out" d="M930 330 C960 330 960 215 990 215"/><path class="df-out" d="M930 330 C960 330 960 335 990 335"/></g>
      ${node('power', 20, 80, 180, 270, '전기 · 설비', '계통·PPA·태양광·배터리')}${node('vm', 250, 130, 180, 170, '공장 VM', '읽기 · 묶기 · 서명')}${node('ingest', 480, 130, 180, 170, '중앙 수신', '검증 · 중복 제거')}
      <g class="df-n" id="n-medal" data-step="medal" tabindex="0"><rect x="710" y="60" width="220" height="330" rx="14"/><text class="df-nt" x="724" y="86">메달리온 (지역 저장소)</text><text class="df-ns" x="724" y="104">같은 리전 안에서만 처리</text>
        <g class="df-m" id="m-bronze"><rect x="724" y="116" width="192" height="52" rx="9"/><text x="738" y="138" class="df-mt">Bronze</text><text x="738" y="156" class="df-ms" id="t-bronze">원본 · 추가 전용</text></g>
        <g class="df-m" id="m-silver"><rect x="724" y="216" width="192" height="52" rx="9"/><text x="738" y="238" class="df-mt">Silver</text><text x="738" y="256" class="df-ms" id="t-silver">검증·정제 Parquet</text></g>
        <g class="df-m" id="m-gold"><rect x="724" y="316" width="192" height="52" rx="9"/><text x="738" y="338" class="df-mt">Gold</text><text x="738" y="356" class="df-ms" id="t-gold">시간별 집계</text></g></g>
      <g class="df-n df-o" id="n-use" data-step="use" tabindex="0"><rect x="990" y="60" width="190" height="80" rx="12"/><text class="df-nt" x="1004" y="88">전력 그래프</text><text class="df-ns" x="1004" y="108">수요·계통·태양광</text></g>
      <g class="df-n df-o" data-step="use"><rect x="990" y="175" width="190" height="80" rx="12"/><text class="df-nt" x="1004" y="203">탄소 측정 그래프</text><text class="df-ns" x="1004" y="223">직접·전력 CO₂</text></g>
      <g class="df-n df-o df-ai" data-step="use"><rect x="990" y="295" width="190" height="80" rx="12"/><text class="df-nt" x="1004" y="323">AI 분석</text><text class="df-ns" x="1004" y="343">피크·재생·이상 인사이트</text></g>
      <g id="dfLive"></g><g id="dfSrc"></g><g id="dfPk"></g><rect id="dfBatch" x="0" y="0" width="56" height="20" rx="6" class="df-batch" opacity="0"/><text id="dfBatchT" class="df-bt" opacity="0">정제</text></svg>
      <div class="df-cap" id="dfCap"></div></div>
    <div class="df-cols"><div class="card"><h4>전력 그래프 <small>Gold · 시간별</small></h4><div id="dfPow"></div></div><div class="card"><h4>탄소 측정 그래프 <small>Gold · 시간별 kgCO₂</small></h4><div id="dfCo2"></div></div></div>
    <div class="card"><h4>AI 분석 <small id="dfAiMeta">Gold 값을 근거로 모델이 작성한 인사이트</small></h4><div class="df-ins" id="dfIns"></div></div>`;
    const $ = s => root.querySelector(s);
    function tabs() { $('#dfTabs').innerHTML = Object.entries(SITES).map(([k, v]) => `<button type="button" data-own="1" data-s="${k}" class="${k === site ? 'on' : ''}">${k} ${v.n}${v.live ? ' · 실시간' : ' · 구조 보기'}</button>`).join(''); $('#dfTabs').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { site = b.dataset.s; cursor = 0; pend = []; S = { sum: null, gd: null }; tabs(); caption(); paintLive(); loadAll(); })); }
    function caption() { const s = STEPS[step]; $('#dfCap').innerHTML = `<b>${s.t}</b><p>${s.b}</p>` + `<p class="df-note">${site === 'KR-01' ? '' : `${site}의 자료는 해당 리전 저장소(${SITES[site].st})에 쌓이고, 한국 포털은 허브 연결을 통해 읽기 전용으로 가져와 보여 줍니다.`}</p>`; root.querySelectorAll('.df-n').forEach(g => g.classList.toggle('on', g.dataset.step === s.k)); }
    function paintLive() {
      const sm = S.sum, live = SITES[site].live, g = $('#dfLive'); const b = sm && sm.brief, en = sm && sm.energy || {}, eq = sm && sm.equipment || [];
      const run = eq.filter(e => e.state === 'RUN').length, L = (x, y, t, c) => `<text x="${x}" y="${y}" class="df-l ${c || ''}">${t}</text>`;
      let s = '';
      if (live && sm) {
        s += L(34, 336, `수요 ${n0(en.demand)} kW`, 'b') + L(34, 318, `가동 설비 ${run}/${eq.length}`);
        s += L(264, 262, `수신 속도 ${b ? b.per_s : '–'} 건/초`, 'b') + L(264, 244, `대기(outbox) ${b && b.hb ? b.hb.outbox_pending : '–'}건`) + L(264, 280, `이벤트 8종 · 80건 묶음`);
        s += L(494, 262, `누계 ${n0(b && b.count)} 건`, 'b') + L(494, 244, `중복 ${b ? b.dup : '–'} · 거절 ${b ? b.rejected : '–'}`) + L(494, 280, `전파 지연 ${b && b.lag_ms != null ? (b.lag_ms >= 1000 ? (b.lag_ms / 1000).toFixed(1) + ' 초' : n0(b.lag_ms) + ' ms') : '–'}`);
      } else s += L(34, 336, '구조 보기(값 비공개)', 'm') + L(264, 262, '서명 · outbox · 재전송', 'm') + L(494, 262, '지역 수신 앱', 'm');
      g.innerHTML = s;
      $('#t-bronze').textContent = live && b ? `원본 ${n0(b.count)}건 · 추가 전용` : '원본 · 추가 전용';
      $('#t-silver').textContent = live && S.gd && !S.gd.error ? `5분마다 정제 · Parquet` : '검증·정제 Parquet'; $('#t-gold').textContent = live && S.gd && !S.gd.error ? `최근 ${String(S.gd.generated).slice(11, 19)}Z 집계` : '시간별 집계';
      const src = [['계통', en.grid, 'var(--dl)'], ['PPA', en.ppa, 'var(--gr)'], ['태양광', en.solar, 'var(--yl)'], ['배터리', Math.abs(en.batt || 0), 'var(--pu)']];
      $('#dfSrc').innerHTML = live && sm ? src.map((q, i) => `<g><rect x="32" y="${116 + i * 46}" width="156" height="36" rx="9" class="df-chip"/><rect x="32" y="${116 + i * 46}" width="5" height="36" rx="2" fill="${q[2]}"/><text x="46" y="${130 + i * 46}" class="df-l">${q[0]}</text><text x="46" y="${145 + i * 46}" class="df-l b">${n0(q[1])} kW</text></g>`).join('') : src.map((q, i) => `<g><rect x="32" y="${116 + i * 46}" width="156" height="36" rx="9" class="df-chip"/><rect x="32" y="${116 + i * 46}" width="5" height="36" rx="2" fill="${q[2]}"/><text x="46" y="${139 + i * 46}" class="df-l">${q[0]}</text></g>`).join('');
    }
    function paintGold() {
      const gd = S.gd, live = SITES[site].live;
      if (!live) { $('#dfPow').innerHTML = $('#dfCo2').innerHTML = '<div class="df-empty">리전 경계: 값을 읽지 않습니다.</div>'; $('#dfIns').innerHTML = '<div class="df-empty">해당 리전 안에서만 분석됩니다.</div>'; return; }
      if (!gd || gd.error) { const m = gd && gd.error === 'gold not ready' ? '첫 정제 실행을 기다리는 중입니다.' : '메달리온 조회 중…'; $('#dfPow').innerHTML = $('#dfCo2').innerHTML = `<div class="df-empty">${m}</div>`; $('#dfIns').innerHTML = `<div class="df-empty">${m}</div>`; return; }
      const en = gd.energy_hourly, t = en.map(r => String(r.hour).padStart(2, '0') + ':00');
      $('#dfPow').innerHTML = mini(t, [{ n: '수요 kW', c: 'var(--cy)', d: en.map(r => r.avg_demand_kw), fill: 1 }, { n: '계통 kWh/시', c: 'var(--dl)', d: en.map(r => r.grid_kwh) }, { n: '태양광 kWh/시', c: 'var(--yl)', d: en.map(r => r.solar_kwh) }]);
      $('#dfCo2').innerHTML = mini(t, [{ n: 'CO₂ kg/시', c: 'var(--rd)', d: en.map(r => r.co2_kg), fill: 1 }, { n: '직접(가스)', c: 'var(--or,#e8a020)', d: en.map(r => r.scope1_kg) }, { n: '전력', c: 'var(--pu)', d: en.map(r => r.scope2_kg) }]);
      loadAI();
    }
    let ai = {};   // site -> {t, v|err}
    async function loadAI() {
      const st = site, c = ai[st]; if (c && Date.now() - c.t < 300000 && !c.err) return showAI(c);
      if (c && c.busy) return; ai[st] = { t: Date.now(), busy: 1 }; $('#dfIns').innerHTML = '<div class="df-empty">AI가 Gold 집계를 분석하는 중입니다… (수십 초 걸릴 수 있습니다)</div>';
      try { const v = await fetch('/api/ai/insights?site=' + st, { cache: 'no-store' }).then(async r => { const j = await r.json(); if (!r.ok) throw new Error((j.error || 'HTTP ' + r.status) + (j.detail ? ': ' + j.detail : '')); return j; }); ai[st] = { t: Date.now(), v }; }
      catch (e) { ai[st] = { t: Date.now() - 270000, err: String(e.message || e) }; }
      if (st === site) showAI(ai[st]);
    }
    function showAI(c) {
      if (c.err) { $('#dfAiMeta').textContent = 'AI 분석 실패'; $('#dfIns').innerHTML = `<div class="df-empty">AI 분석을 가져오지 못했습니다(대체 문구 없음): ${esc(c.err)}</div>`; return; }
      const v = c.v; $('#dfAiMeta').textContent = `배포 ${v.deployment} · 응답 모델 ${v.response_model || '–'} · ${String(v.generated).slice(11, 19)}Z · ${n0(v.latency_ms / 1000)}초 · 신규 Foundry(한국) · 숫자는 Gold 값 대조 통과`;
      $('#dfIns').innerHTML = (v.insights || []).map(x => `<div class="df-in"><b>${esc(x.title)}</b><span>${esc(x.body)}</span></div>`).join('') || '<div class="df-empty">인사이트가 없습니다.</div>';
    }
    async function loadAll() {
      if (!SITES[site].live) { paintLive(); paintGold(); return; }
      try { S.sum = await get('sites/' + site + '/summary'); } catch (e) { S.sum = null; } paintLive();
      try { S.gd = await get('sites/' + site + '/gold'); } catch (e) { S.gd = { error: '조회 실패' }; } paintGold(); paintLive();
    }
    async function pollFeed() {
      if (!root.isConnected) { stop(); return; }
      if (SITES[site].live) { try { const d = await get('sites/' + site + '/feed?after=' + cursor + '&limit=40'); if (d.events.length) { cursor = d.last_rid; if (cursor && !pend._init) { pend._init = 1; d.events = d.events.slice(-8); } d.events.forEach(e => pend.push({ type: e.type, ref: e.ref })); } } catch (e) { } }
      else for (let i = 0; i < 3; i++) pend.push({ type: ['meter.reading', 'meter.reading', 'energy.flow', 'process.state', 'production.counter'][Math.floor(Math.random() * 5)], ref: 'SIM' });
    }
    // ---- 이벤트 점 애니메이션 ----
    const PTS = [[110, 215], [340, 215], [570, 215], [820, 142]]; const SEG = [2.2, .7, 2.2, .7, 2.0];     // 구간 이동 / 체류 시간(초)
    const TOT = SEG.reduce((a, b) => a + b, 0); let packets = [], lastSpawn = 0, batch = null, lastBatch = 0;
    function posAt(a) {
      let t = a; const s = SEG;
      if (t < s[0]) return lerp(PTS[0], PTS[1], t / s[0]); t -= s[0];
      if (t < s[1]) return PTS[1]; t -= s[1];
      if (t < s[2]) return lerp(PTS[1], PTS[2], t / s[2]); t -= s[2];
      if (t < s[3]) return PTS[2]; t -= s[3];
      return lerp(PTS[2], PTS[3], Math.min(1, t / s[4]));
    }
    const lerp = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k + (Math.sin(k * 6.28) * 0)];
    function loop(ts) {
      if (!root.isConnected) return; const pk = $('#dfPk'), now = ts / 1000;
      if (!RM) {
        if (pend.length && now - lastSpawn > .35) { const e = pend.shift(); if (pend.length > 30) pend.splice(0, pend.length - 30); packets.push({ t0: now, e, dy: (Math.random() - .5) * 70 }); lastSpawn = now; }
        packets = packets.filter(p => now - p.t0 < TOT);
        pk.innerHTML = packets.map(p => { const age = now - p.t0, q = posAt(age), dwell = (age > SEG[0] && age < SEG[0] + SEG[1]) || (age > SEG[0] + SEG[1] + SEG[2] && age < SEG[0] + SEG[1] + SEG[2] + SEG[3]); return `<circle cx="${q[0].toFixed(1)}" cy="${Math.max(40, Math.min(390, q[1] + (q[0] < 700 ? p.dy * .55 : 0))).toFixed(1)}" r="${dwell ? 6 : 4.5}" fill="${TC[p.e.type] || 'var(--cy)'}" opacity=".92"/>`; }).join('');
        if (!batch && now - lastBatch > 9) { batch = { t0: now }; lastBatch = now; }
        const bt = $('#dfBatch'), btt = $('#dfBatchT');
        if (batch) { const a = now - batch.t0; let y; const Y = [142, 242, 342]; if (a < 2.6) y = Y[0] + (Y[1] - Y[0]) * a / 2.6; else if (a < 3.2) y = Y[1]; else if (a < 5.8) y = Y[1] + (Y[2] - Y[1]) * (a - 3.2) / 2.6; else y = null; if (y == null) { batch = null; bt.setAttribute('opacity', 0); btt.setAttribute('opacity', 0); } else { bt.setAttribute('x', 862); bt.setAttribute('y', y - 10); bt.setAttribute('opacity', .9); btt.setAttribute('x', 890); btt.setAttribute('y', y + 4); btt.setAttribute('opacity', 1); btt.textContent = '정제 ▸'; } }
      }
      raf = requestAnimationFrame(loop);
    }
    function stop() { timers.forEach(clearInterval); cancelAnimationFrame(raf); }
    // ---- 단계 안내 ----
    root.addEventListener('click', e => { const g = e.target.closest('[data-step]'); if (!g) return; const i = STEPS.findIndex(s => s.k === g.dataset.step); if (i >= 0) { step = i; lastClick = Date.now(); caption(); } });
    root.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { const g = e.target.closest('[data-step]'); if (g) { e.preventDefault(); g.dispatchEvent(new MouseEvent('click', { bubbles: true })); } } });
    tabs(); caption(); paintLive(); paintGold(); loadAll();
    timers.push(setInterval(pollFeed, 1000), setInterval(() => { if (!root.isConnected) return stop(); if (SITES[site].live) loadAll(); }, 5000), setInterval(() => { if (!root.isConnected) return stop(); if (auto && Date.now() - lastClick > 20000) { step = (step + 1) % STEPS.length; caption(); } }, 6000));
    if (!RM) raf = requestAnimationFrame(loop);
    return root;
  };
})();
