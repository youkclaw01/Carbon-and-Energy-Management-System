'use strict';
// 산정 결과 화면의 "실산정" 카드: calc-api(S02)가 DB02에 기록한 산정 run을 보여 주고 최근 1시간 산정을 요청합니다.
// 입력은 합성 자료(SIMULATED)이며 계수는 모의입니다. 후보 수치는 잠정이고 certified 발행은 승인(S07)·권한 출처 확정 전까지 차단됩니다.
(function () {
  if (typeof V === 'undefined' || !V.calc) return; const orig = V.calc, API = '/api/calc/v1/';
  const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])), kst = s => new Date(s).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  const fmt = (v, d = 1) => v == null ? '–' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: d });
  const ST = { accepted: ['접수', 'var(--dl)'], awaiting_candidate: ['후보 생성 중', 'var(--yl)'], candidate_ready: ['후보 완료', 'var(--yl)'], validating: ['독립 검증 중', 'var(--yl)'], ready: ['검증 통과', 'var(--gr)'], dq_failed: ['검증 실패', 'var(--rd)'] };
  const chip = (t, c) => `<span class="fx-chip" style="--c:${c}"><i></i>${esc(t)}</span>`, val = (r, m) => { const x = (r.values || []).find(v => v.metric === m); return x ? fmt(x.value, 1) : '–'; };
  V.calc = () => {
    const root = orig(), box = document.createElement('div'); box.className = 'card fx-q'; let sel = null, timer = null;
    box.innerHTML = '<h4>실산정 · KR-01 <small>calc-api(S02) · DB02 기록 · 합성 입력 · 모의 계수</small></h4><div id="cvBody"><p class="fx-tip">불러오는 중…</p></div>';
    root.prepend(box);
    async function load() {
      if (!root.isConnected) { clearInterval(timer); return; } const b = box.querySelector('#cvBody');
      try {
        const d = await fetch(API + 'calc-runs?plantId=KR-01&limit=6', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject(r.status)); const rs = d.items || [], busy = rs.some(r => ['accepted', 'awaiting_candidate', 'candidate_ready', 'validating'].includes(r.businessState));
        let det = ''; if (sel) { try { const r = await fetch(API + 'calc-runs/' + sel, { cache: 'no-store' }).then(x => x.json()); det = `<div class="fx-tip"><b>${esc(r.screenLabel)}</b> · 방법론 ${esc(r.versionSet.methodology.id)} v${esc(r.versionSet.methodology.version)} · 계수 ${Object.entries(r.versionSet.factors).map(([k, v]) => esc(k) + ' v' + esc(v.version)).join(', ')} · 반올림 ${esc(r.versionSet.rounding)} · DQ 정책 v${esc(r.versionSet.dqPolicy)}<br>${(r.validation ? r.validation.checks : []).map(c => `${c.status === 'PASS' ? '✓' : '✗'} ${esc(c.checkId)} (관측 ${esc(c.observed)} / 기대 ${esc(c.expected)} ${esc(c.unit)})`).join('<br>')}</div>`; } catch (e) { } }
        b.innerHTML = `<p class="fx-tip">후보 수치는 <b>잠정(모의)</b>입니다. certified 발행은 분리 승인(S07)·권한 출처 확정 전까지 차단되며(입력도 SIMULATED), 누락 표본은 0이나 추정값으로 채우지 않습니다.</p><p><button type="button" class="cv-btn" id="cvRun">최근 1시간 산정 요청</button> <span id="cvMsg" class="fx-tip"></span></p>` + (rs.length ? `<table><tr><th>기간(KST)</th><th>상태</th><th>Scope 2 kgCO₂e</th><th>Scope 1 kgCO₂e</th><th>전력 kWh</th><th>표본 커버리지</th><th>검증</th><th></th></tr>${rs.map(r => { const s = ST[r.businessState] || [r.businessState, 'var(--dl)']; return `<tr><td>${kst(r.periodStart)}–${kst(r.periodEnd).slice(-5)}</td><td>${chip(s[0], s[1])}</td><td>${val(r, 'scope2_location_based')}</td><td>${val(r, 'scope1_stationary_fuel')}</td><td>${val(r, 'grid_energy')}</td><td>${r.dq ? (Number(r.dq.coverage) * 100).toFixed(1) + '% (' + fmt(r.dq.samples, 0) + '/' + fmt(r.dq.expectedSamples, 0) + ')' : '–'}</td><td>${r.validation ? esc(r.validation.verdict) : '–'}</td><td><button type="button" class="cv-btn" data-r="${r.runId}">${sel === r.runId ? '닫기' : '근거'}</button></td></tr>`; }).join('')}</table>` : '<p class="fx-tip">아직 산정 기록이 없습니다.</p>') + det;
        b.querySelector('#cvRun').addEventListener('click', run); b.querySelectorAll('[data-r]').forEach(x => x.addEventListener('click', () => { sel = sel === x.dataset.r ? null : x.dataset.r; load(); }));
        if (busy && !timer) timer = setInterval(load, 3000); if (!busy && timer) { clearInterval(timer); timer = null; }
      } catch (e) { b.innerHTML = '<p class="fx-tip">산정 이력 조회에 실패했습니다(calc-api 확인 필요). 수치를 대신 만들어 보이지 않습니다.</p>'; }
    }
    async function run() {
      const m = box.querySelector('#cvMsg'), end = new Date(); end.setUTCMinutes(0, 0, 0); const st = new Date(end.getTime() - 3600000), z = d => d.toISOString().slice(0, 19) + 'Z'; m.textContent = '요청 중…';
      try { const r = await fetch(API + 'calc-runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID(), 'X-Actor': 'portal-demo' }, body: JSON.stringify({ plantId: 'KR-01', periodStart: z(st), periodEnd: z(end) }) }); const d = await r.json(); m.textContent = r.status === 202 ? '접수됨 · 산정 중' : r.status === 200 ? '같은 기간·버전의 기존 산정입니다' : '거절: ' + (d.code || r.status) + ' ' + (d.message || ''); sel = d.runId || sel; if (timer) { clearInterval(timer); timer = null; } load(); } catch (e) { m.textContent = '요청 실패'; }
    }
    load(); return root;
  };
})();
