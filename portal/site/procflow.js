// 조달·승인 — "거래 진행" 탭(실데이터, 읽기 전용). 정책 평가 → 승인 신청 → 승인 → 한도 예약 → 허가(permit) → 실행(모의) → 증빙을
// 한 화면에서 보여 준다. 값은 운영 서비스(승인·실행·증빙·산정·AI 등)에서 읽으며, 이 화면에서 승인·실행을 하지 않는다.
// 실행은 모의(실거래 없음). 기존 3개 탭(조달 현황·승인 요청·계약·위험)은 코드에 적힌 시안이므로 '시안'으로 표시한다.
(function () {
  if (typeof V === 'undefined' || !V.proc) return;
  const orig = V.proc;
  if (!S.pfInit) { S.pfInit = 1; S.pt = 'flow'; }   // 처음 열면 실데이터 탭
  const KST = s => { try { return new Date(s).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch (e) { return s || '–'; } };
  const AGE = s => { const m = Math.max(0, Math.round((Date.now() - new Date(s).getTime()) / 60000)); return m < 60 ? m + '분 전' : m < 1440 ? Math.round(m / 60) + '시간 전' : Math.round(m / 1440) + '일 전'; };
  const MONEY = (v, c) => v == null ? '–' : (c === 'KRW' ? '₩ ' : (c || '') + ' ') + Number(v).toLocaleString('ko-KR');
  const STEPS = ['정책', '신청', '승인', '한도', '허가', '실행'];
  const STATE = { pending: ['승인 대기', '--yl'], approved: ['승인됨', '--gr'], rejected: ['거절', '--rd'], cancelled: ['취소', '--dl'], expired: ['만료', '--rd'] };
  const EXS = { accepted: '접수', sending: '전송 중', executed: '모의 체결 완료', unknown: '결과 불명', partial: '일부 체결', rejected: '거절', reconciling: '대사 중', 'review-required': '검토 필요' };
  const PMS = { signing: '서명 중', active: '발급됨(미사용)', claimed: '사용됨', block_pending: '차단 대기', blocked: '차단', expired: '만료' };
  // 승인자 결정 패널: 승인 권한(approve)이 있고 신청자가 본인이 아닌 "승인 대기" 건에만 승인/반려 버튼을 보인다.
  // 실제 검증(MFA 세션·신청자≠승인자·digest 재검증·버전 CAS)은 서버가 한다. 화면은 결과 코드를 그대로 보여 준다.
  const decidePanel = (c, reload, compact) => {
    const me = window.AMA_ME, can = me && (me.grants || []).includes('approve');
    if (c.state !== 'pending') return null;
    if (!me) return h('p', { class: 'mnote' }, '승인하려면 로그인해야 합니다.');
    if (!can) return h('p', { class: 'mnote' }, '이 계정(' + me.username + ')에는 승인 권한이 없습니다. 승인자 또는 관리자 계정으로 로그인하세요.');
    const adm = (me.grants || []).includes('admin');   // 관리자는 본인 신청도 결정할 수 있다(2026-11-01 사용자 결정)
    if (c.requester === me.username && !adm) return h('p', { class: 'mnote' }, '본인이 신청한 건은 본인이 승인할 수 없습니다(업무 분리). 다른 승인자 또는 관리자 계정으로 승인하세요.');
    const msg = h('p', { class: 'mnote', role: 'status' }, ''), post = async d => {
      if (!window.confirm((d === 'approve' ? '승인' : '반려') + '합니다.\n' + title(c) + ' · ' + MONEY(c.amountMinor, c.currency) + '\n신청자 ' + c.requester + '\n실행은 모의이며 실제 거래가 아닙니다. 계속할까요?')) return;
      msg.textContent = '처리 중…'; const t = sessionStorage.getItem('ama_tok');
      try {
        const g = await fetch('/api/approval/v1/approval-requests/' + c.requestId, { cache: 'no-store', headers: { Authorization: 'Bearer ' + t } }); const rq = await g.json(); if (!g.ok) throw new Error(rq.message || rq.code || ('조회 ' + g.status));
        const r = await fetch('/api/approval/v1/approval-decisions', { method: 'POST', headers: { Authorization: 'Bearer ' + t, 'Content-Type': 'application/json', 'Idempotency-Key': 'ui-' + c.requestId + '-' + d + '-' + rq.rev }, body: JSON.stringify({ requestId: c.requestId, decision: d, expectedVersion: rq.rev, reasonSeen: c.reasonUpdatedAt || null }) });
        const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error((j.message || j.code || ('오류 ' + r.status)) + (j.code ? ' [' + j.code + ']' : ''));
        msg.textContent = (d === 'approve' ? '승인' : '반려') + '했습니다. 목록을 새로 고칩니다.'; reload();
      } catch (e) { msg.textContent = '처리하지 못했습니다: ' + (e.message || e) + ' — 신청은 그대로 승인 대기입니다.'; }
    };
    const ok = h('button', { type: 'button', class: 'btn pri', 'data-own': 1 }, '승인'), no = h('button', { type: 'button', class: 'btn', 'data-own': 1 }, '반려');
    ok.addEventListener('click', () => post('approve')); no.addEventListener('click', () => post('reject'));
    if (compact) { ok.addEventListener('click', e => e.stopPropagation()); no.addEventListener('click', e => e.stopPropagation()); return h('div', { class: 'pf-dec pf-dec-c' }, h('div', { class: 'pf-decb' }, ok, no), msg); }
    return h('div', { class: 'pf-dec' }, h('p', { class: 'mnote' }, h('b', {}, '승인자 결정 '), '(' + me.username + (c.requester === me.username ? ' · 본인 신청, 관리자 예외로 감사에 남김' : '') + ') · 건별로 관리자 또는 검수자가 결정합니다. MFA로 로그인한 세션이어야 처리됩니다.'), h('div', { class: 'pf-decb' }, ok, no), msg);
  };
  const FETCH = async (u, auth) => { const o = { cache: 'no-store' }; const t = sessionStorage.getItem('ama_tok'); if (auth && t) o.headers = { Authorization: 'Bearer ' + t }; const r = await fetch(u, o); if (!r.ok) { const e = new Error('HTTP ' + r.status); e.status = r.status; throw e; } return r.json(); };

  // 건의 6단계 상태: done / cur / fail / wait / unk
  function steps(c) {
    const s = ['done', 'done', 'wait', 'wait', 'wait', 'wait'], pol = c.policy && c.policy.decision;
    if (pol === 'deny') s[0] = 'fail';
    if (c.state === 'pending') s[2] = 'cur'; else if (c.state === 'approved') s[2] = 'done'; else s[2] = 'fail';
    if (c.state === 'approved') {
      s[3] = c.reservation ? 'done' : 'cur';
      const p = c.permit; s[4] = !p ? 'cur' : (p.state === 'active' || p.state === 'claimed') ? 'done' : (p.state === 'blocked' || p.state === 'expired' || p.state === 'block_pending') ? 'fail' : 'cur';
      if (p && (p.state === 'active' || p.state === 'claimed')) {
        if (!c.executionKnown) s[5] = 'unk'; else { const e = c.execution; s[5] = !e ? 'cur' : e.executionState === 'executed' ? 'done' : ['rejected', 'review-required', 'unknown', 'partial'].includes(e.executionState) ? 'fail' : 'cur'; }
      }
    }
    return s;
  }
  function next(c, s) {
    if (c.state === 'pending') return '승인자의 승인 필요(요청자 본인은 승인 불가)';
    if (c.state !== 'approved') return '종료(' + (STATE[c.state] || [c.state])[0] + ')';
    if (!c.permit) return '허가(permit) 발급 필요';
    if (s[4] === 'fail') return 'permit ' + (PMS[c.permit.state] || c.permit.state) + ' — 확인 필요';
    if (!c.executionKnown) return '실행 서비스 상태를 알 수 없음';
    if (!c.execution) return '실행 대기(permit 사용 전)';
    if (s[5] === 'fail') return '실행 ' + (EXS[c.execution.executionState] || c.execution.executionState) + ' — 확인 필요';
    return s[5] === 'done' ? '완료(모의 체결 · 증빙 연결)' : '실행 진행 중';
  }
  const dots = s => h('span', { class: 'pf-dots', role: 'img', 'aria-label': STEPS.map((n, i) => n + ' ' + s[i]).join(', ') }, STEPS.map((n, i) => h('i', { class: s[i], title: n + ' · ' + ({ done: '완료', cur: '진행 중', fail: '막힘', wait: '대기', unk: '알 수 없음' })[s[i]] })));
  const ACT = { 'procurement.allowance.sell': '배출권 매도', 'procurement.allowance.buy': '배출권 매입', 'procurement.rec.purchase': 'REC 구매' };
  const isTest = c => /^(live-e2e|e2e-)/.test(c.requester || '');   // 종단 시험이 남긴 건(신청자 이름 규칙)
  const title = c => { const a = ACT[c.action] || c.action, i = c.intent; return i && i.quantity ? `${a} · ${Number(i.quantity).toLocaleString('ko-KR')} ${i.unit}` : a; };
  const verdict = c => { const r = c.intent && c.intent.rule; return r ? h('span', { class: 'tag pf-vd ' + (r.verdict === 'recommended' ? 'ok' : 'no'), title: '규칙 계산 기준: ' + r.reason }, r.verdict === 'recommended' ? '권고' : '비권고') : ''; };
  const chip = (t, v) => h('span', { class: 'tag', style: `color:var(${v});border-color:var(${v})` }, t);

  function stageStrip() {
    const defs = [['collect', '수집', '공장 VM 3곳'], ['calc', '산정', '탄소 산정 실행'], ['ai', 'AI 판단', 'AI 초안 실행'], ['proc', '조달 의도', '제안(초안)'], ['appr', '승인', '건별 관리자·검수자 승인'], ['permit', '허가', '서명 permit'], ['exec', '실행(모의)', '실거래 없음'], ['evid', '증빙', '서명·패키지']];
    const box = {}; const strip = h('div', { class: 'pf-strip' }, defs.map(([k, t, sub]) => { const v = h('b', {}, '…'), s = h('em', {}, sub), d = h('div', { class: 'pf-st', 'data-k': k }, h('span', {}, t), v, s); box[k] = { d, v, s, sub }; return d; }));
    const set = (k, val, text, st) => { const b = box[k]; if (!b) return; b.v.textContent = val; b.s.textContent = text || b.sub; b.d.className = 'pf-st ' + (st || 'ok'); };
    const get = (p) => FETCH(p).catch(() => null);
    (async () => {
      const [calc, agent, proc, evid, exec, appr] = await Promise.all([get('/api/calc/health'), get('/api/agent/health'), get('/api/proc/health'), get('/api/evidence/health'), get('/api/exec/health'), get('/api/approval/health')]);
      const rs = await Promise.all(['/api/plant/v1/sites', '/api/plant-jp/v1/sites', '/api/plant-sg/v1/sites'].map(u => FETCH(u).then(d => d.sites || []).catch(() => []))); const ok = rs.flat().filter(s => s.status === 'ONLINE').length;
      set('collect', ok + '/12', '공장 12곳 중 수신 중', ok === 12 ? 'ok' : ok ? 'warn' : 'bad');
      set('calc', calc ? String(calc.runs) : '–', calc ? '산정 실행(건)' : '조회 실패', calc ? 'ok' : 'bad');
      set('ai', agent ? String(agent.db.runs) : '–', agent ? 'AI 초안 실행(건) · 승인 권한 없음' : '조회 실패', agent ? 'ok' : 'bad');
      set('proc', proc ? String(proc.db.intents) : '–', proc ? '조달 의도(초안·모의)' : '조회 실패', proc ? 'ok' : 'bad');
      set('appr', appr ? String(appr.db.requests) : '–', appr ? '승인 신청(건)' : '조회 실패', appr ? 'ok' : 'bad');
      set('exec', exec ? String(exec.db.executions) : '–', exec ? '모의 실행(건) · 실거래 없음' : '조회 실패', exec ? 'ok' : 'bad');
      set('evid', evid ? String(evid.db.packages) : '–', evid ? '증빙 패키지(건)' : '조회 실패', evid ? 'ok' : 'bad');
      set('permit', '…', '서명 permit', 'ok');
    })();
    strip._set = set; return strip;
  }


  // 배출권 포지션: 포스코 공개 자료(실제) + 2026 가정(모의). 판단은 규칙 기반 초안이며 거래 권한이 없다.
  function position() {
    const D = window.POSCO_DEMO; if (!D) return null;
    const act = D.actual, as = D.assumptions, carry = act.surplus.carryOverTo2026, alloc = as.allocation2026.value, em = as.emission2026Expected.value;
    const endBal = carry + alloc - em, deficit = em - alloc, yrs = deficit > 0 ? carry / deficit : Infinity;
    const T = n => (n / 1e6).toFixed(2) + ' Mt', W = n => Math.round(n).toLocaleString('ko-KR');
    const price = { KAU26: act.market.KAU26, KAU27: act.market.KAU27, live: false }, pv = h('div', {}), jb = h('div', {});
    const yr = act.allowance.years, rows = Object.keys(yr).map(k => h('tr', {}, h('td', {}, k), h('td', { class: 'n' }, W(yr[k].freeAllocation)), h('td', { class: 'n' }, W(yr[k].emission)), h('td', { class: 'n' }, W(yr[k].over))));
    function judge() {
      const R = act.rules, N = R.carryMultiple['2026'], S = endBal, price26 = price.KAU26, val = carry * price26;
      const minSale = Math.ceil(S / (N + 1)), maxSale = Math.max(0, S - Math.max(0, deficit)), rec = Math.floor(maxSale / 10000) * 10000, ok = rec >= minSale;
      const big = 3000000, bigAfter = S - big, bigShort = Math.max(0, deficit - bigAfter), after = S - rec;
      pv.replaceChildren(h('div', { class: 'row r4' }, kpi('&#128230;', '이월 보유(2026 이월)', T(carry), 'tCO₂e', '공시·보도 기준(실제)', '', '공시'), kpi('&#128200;', 'KAU26 시세', W(price26), '원/t', price.live ? 'KRX 기준일 ' + price.asOf : '데이터셋 값(조회 실패)', '', price.live ? 'KRX' : '대체값'), kpi('&#128176;', '이월분 평가액', Math.round(val / 1e8).toLocaleString('ko-KR'), '억 원', '이월 × KAU26 시세', '', '모의'), kpi('&#9203;', '2026 말 잔여(모의)', T(S), 'tCO₂e', '이월 + 할당 − 예상 배출', '', '모의')));
      jb.replaceChildren(h('div', { class: 'pf-judge' },
        h('div', { class: 'pf-jh' }, h('b', {}, 'AI 판단 초안(규칙 기반 모의)'), chip(ok ? 'KAU26 ' + W(rec) + 't 매도 권고' : '매도 조건 불충족', ok ? '--gr' : '--yl')),
        h('p', {}, h('b', {}, '핵심 규칙 '), `잉여업체는 해당 연도 순매도량의 ${N}배까지만 다음 해로 이월할 수 있고, 한도를 넘는 잉여는 소멸합니다(4기 할당계획, 확인됨). 포스코의 2026 이월 ${W(carry)}t도 2025 순매각 추정량의 5배(3기 기준)와 일치합니다.`),
        h('p', {}, h('b', {}, '계산 '), `2026 말 잔여 ${T(S)}(모의). 전량 이월하려면 순매도 ≥ 잔여 ÷ ${N + 1} = ${W(minSale)}t. 다음 해 구조적 부족 ${T(deficit)}을 이월분으로 덮으려면 순매도 ≤ 잔여 − 부족 = ${W(maxSale)}t. 허용 구간 ${W(minSale)}~${W(maxSale)}t.`),
        h('p', {}, h('b', {}, '제안 A(권고) '), `KAU26 ${W(rec)}t 매도 ≈ ${(rec * price26 / 1e8).toFixed(0)}억 원. 이월 후 잔량 ${T(after)} ≤ 이월 한도 ${T(rec * N)}이고 다음 해 부족분을 덮습니다. 수량이 1,000~3,000,000t 범위라 협의매매 1건 또는 10:00~11:30 경쟁매매 분할이 가능하고, 이월 신청 전날까지의 순매도량이 기준입니다.`),
        h('p', {}, h('b', {}, '제안 B(비권고) '), `KAU26 ${W(big)}t 매도 ≈ ${(big * price26 / 1e8).toFixed(0)}억 원. 이월 후 잔량 ${T(bigAfter)}로 다음 해 부족분 ${T(deficit)}을 덮지 못해 약 ${T(bigShort)}를 다시 매수해야 합니다.`),
        h('p', { class: 'mut small' }, '위 숫자는 규칙으로 계산한 결과입니다. 궁금한 점은 위 "AI와 판단하기"에서 질문하세요. AI는 승인·실행 권한이 없고 실행은 관리자·검수자의 건별 승인과 모의 체결로만 진행됩니다. 실제 주문은 KRX 시장 회원 시스템으로만 제출되며 AMA는 주문표까지 만듭니다. 2026 할당·배출 예상은 가정한 모의 값입니다.')));
    }
    judge();
    fetch('/api/krx/products', { cache: 'no-store' }).then(r => r.ok ? r.json() : Promise.reject()).then(d => { const g = c => (d.products.find(p => p.code === c) || {}).last; if (g('KAU26')) { price.KAU26 = g('KAU26'); price.KAU27 = g('KAU27') || price.KAU27; price.live = true; price.asOf = d.asof; judge(); } }).catch(() => { });
    return card('포지션·규칙 근거', '포스코 공개 자료 기준 · 2026 값은 모의', pv,
      h('div', { class: 'row r2e' }, card('무상할당 vs 실제 배출(실제 공시·보도)', '실제', h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, ['연도', '무상할당(t)', '배출(t)', '초과 할당(t)'].map((t, i) => h('th', { class: i ? 'n' : '' }, t)))), h('tbody', {}, rows)), h('p', { class: 'mut small' }, '출처: 기후에너지환경부 자료(차규근 의원실, 2025-10) · 이월 11,808,259t: 이용우 의원실 자료(뉴스토마토 2026-10-15).')), card('규칙 계산 결과(AI 판단 초안)', '규칙 계산', jb)));
  }

  // 신청 사유: 왜 이 건이 올라왔는지. 소유 서비스(S04)의 규칙 계산 결과(포지션)와 신청 수량을 대조해 서술한다(브라우저는 읽기만).
  const N = v => Number(v).toLocaleString('ko-KR'), POSID = { kr: '3ab9e628-fbce-556f-877f-f2c8c7f606e2', jp: '913150a9-e09c-5394-9106-e5495397f497' };
  S.pfPos = S.pfPos || {};
  const getPos = k => S.pfPos[k] || (S.pfPos[k] = fetch('/api/proc/v1/allowance-positions/' + POSID[k]).then(r => r.ok ? r.json() : null).catch(() => null).then(d => { if (!d) delete S.pfPos[k]; return d; }));
  function reasonBox(c, reload) {
    const i = c.intent || {}, rule = i.rule, q = Number(i.quantity), kind = i.purpose === 'buy' && c.currency === 'JPY' ? 'jp' : (i.purpose === 'sell' && c.currency === 'KRW' ? 'kr' : null);
    const body = h('div', { class: 'pf-why' }, h('p', { class: 'mnote' }, kind ? '근거를 불러오는 중…' : (rule ? '규칙 판정: ' + rule.reason : '이 건의 상세 근거 정보가 아직 없습니다.') + ' 자세한 내용은 오른쪽 AI에게 물어보세요.'));
    const row = (k, v, em) => h('div', { class: em ? 'em' : '' }, h('dt', {}, k), h('dd', {}, v));
    if (kind) getPos(kind).then(d => {
      if (!d) { body.replaceChildren(h('p', { class: 'mnote' }, '규칙 계산 결과를 읽지 못했습니다. ' + (rule ? '규칙 판정: ' + rule.reason + '. ' : '') + '잠시 뒤 다시 선택해 주세요.')); return; }
      const ok = rule && rule.verdict === 'recommended', r = d.result, a = d.assumed, ac = d.actual; let why, rows, judge;
      if (kind === 'jp') {
        const lo = Math.ceil(r.shortageTon * 0.9), hi = Math.floor(r.shortageTon * 1.05), pct = Math.round(q / r.shortageTon * 1000) / 10;
        why = `일본 사업장(${d.siteId})의 2026년 예상 배출량이 가정한 무상할당량보다 ${N(r.shortageTon)}t 많아, 부족분을 시장에서 매입하려는 신청입니다. 신청 수량 ${N(q)}t은 부족분의 ${pct}%입니다.`;
        rows = [['예상 배출량(연환산)', N(a.expectedEmissionTon) + 't · 모의 이력 기반(2025 모의 배출 ' + N(a.emission2025Ton) + 't)'], ['무상할당량(가정)', N(a.allocationTon) + 't · ' + a.allocationRule], ['부족분', N(r.shortageTon) + 't = 예상 배출 − 무상할당', 1], ['신청 수량', N(q) + 't (부족분의 ' + pct + '%)', 1], ['규칙 허용 범위', '부족분의 90~105% = ' + N(lo) + '~' + N(hi) + 't'], ['가격 범위(안내)', N(ac.priceFloorJpyPerT) + '~' + N(ac.priceCapJpyPerT) + ' JPY/t → 전량 매입 시 ' + N(r.costAtFloorMillionJpy) + '~' + N(r.costAtCapMillionJpy) + '백만 JPY'], ['신청 금액', MONEY(c.amountMinor, c.currency) + (i.priceCap ? ' (신청에 지정한 상한가 ' + N(i.priceCap) + ' JPY/t × 수량)' : '')], ['보유 기한', ac.holdDeadline + ' (' + ac.law + ')'], ['목표 임계(10만 t) 초과', r.aboveTargetThreshold ? '초과 — 보유 의무 대상' : '미만']];
        judge = ok ? '신청 수량이 허용 범위 안에 있어 규칙상 권고입니다.' : '신청 수량이 허용 범위(' + N(lo) + '~' + N(hi) + 't) 밖이라 규칙상 비권고입니다.';
      } else {
        const end = r.endBalanceTon, lim = q * d.rule.carryMultiple, after = end - q, lost = Math.max(0, after - lim), carried = Math.min(after, lim), nextShort = Math.max(0, r.annualDeficitTon - carried), val = q * ac.priceKauKrw;
        why = `포스코 2026 연말 예상 잔여 배출권이 ${N(end)}t인데, 이월 한도(해당 연도 순매도량 × ${d.rule.carryMultiple})를 넘는 잉여는 소멸되고 너무 많이 팔면 다음 해 부족이 생깁니다. 이에 대해 ${N(q)}t을 매도하려는 신청입니다.`;
        rows = [['연말 예상 잔여', N(end) + 't = 이월 ' + N(ac.carryOver2026Ton) + ' + 할당(가정) ' + N(a.allocation2026Ton) + ' − 예상 배출(가정) ' + N(a.emission2026ExpectedTon)], ['연간 부족(예상)', N(r.annualDeficitTon) + 't · 이월분이 약 ' + r.carryCoverYears + '년치'], ['신청 수량', N(q) + 't', 1], ['규칙 허용 매도 구간', N(r.minSellTon) + '~' + N(r.maxSellTon) + 't (소멸 방지 최소 ~ 다음 해 부족 방지 최대)'], ['매도 후 잔여', N(after) + 't · 이월 한도 ' + N(lim) + 't'], ['소멸 예상', lost ? N(lost) + 't' : '없음'], ['다음 해 부족 예상', nextShort ? N(nextShort) + 't' : '없음'], ['예상 매각 금액', '약 ' + N(Math.round(val / 1e8)) + '억 원 (KAU26 ' + N(ac.priceKauKrw) + '원/t, 기준일 ' + ac.priceAsOf + ')']];
        judge = ok ? '신청 수량이 허용 구간 안에 있어 규칙상 권고입니다.' : (q > r.maxSellTon ? '신청 수량이 허용 구간 상한(' + N(r.maxSellTon) + 't)을 넘어 매도 후 다음 해 부족 ' + N(nextShort) + 't이 생기므로 규칙상 비권고입니다.' : '신청 수량이 허용 구간 하한(' + N(r.minSellTon) + 't)에 못 미쳐 이월 한도를 넘는 잉여 ' + N(lost) + 't이 소멸되므로 규칙상 비권고입니다.');
      }
      body.replaceChildren(h('p', { class: 'pf-why-t' }, why), h('dl', { class: 'pf-why-kv' }, rows.map(x => row(...x))), h('p', { class: 'pf-why-j ' + (ok ? 'ok' : 'no') }, h('b', {}, '규칙 판정 '), judge), h('p', { class: 'mut small' }, (kind === 'jp' ? '예상 배출·할당은 모의 이력 기반 가정이고 가격 범위·법령 기한은 공개 기준입니다. ' : '이월·시세는 공시·시장 값이고 2026 할당·예상 배출은 가정(모의)입니다. ') + '신청자가 입력한 별도 사유 문구는 이 화면에 없으며, 위 내용은 소유 서비스(S04) 규칙 계산 결과로 서술했습니다.'));
    });
    return h('section', { class: 'pf-sec' }, h('h4', { class: 'pf-h4' }, '신청 사유 — 왜 올렸나요?'), h('h5', { class: 'pf-h5' }, '신청자가 직접 입력한 사유'), ownReason(c, reload), h('h5', { class: 'pf-h5' }, '시스템 계산 근거(S04 규칙)'), body);
  }
  // 신청자가 직접 입력한 사유: 표시, 그리고 신청자 본인이 승인 대기 중일 때만 수정(서버도 같은 규칙으로 막는다)
  function ownReason(c, reload) {
    const me = window.AMA_ME, mine = !!(me && me.username === c.requester && c.state === 'pending'), view = h('div', { class: 'pf-rsn' });
    const edited = c.reasonUpdatedAt && c.createdAt && Math.abs(new Date(c.reasonUpdatedAt) - new Date(c.createdAt)) > 2000;
    const draw = editing => {
      if (editing) {
        const ta = h('textarea', { class: 'pf-in pf-rta', rows: 4, maxlength: 500, 'data-own': 1, 'aria-label': '신청 사유' }), cnt = h('span', { class: 'mut small' }, ''), msg = h('p', { class: 'mnote', role: 'status' }, ''), save = h('button', { type: 'button', class: 'btn pri', 'data-own': 1 }, '저장'), cancel = h('button', { type: 'button', class: 'btn', 'data-own': 1 }, '취소');
        ta.value = c.reason || ''; const upd = () => { cnt.textContent = ta.value.trim().length + '/500자 (10자 이상)'; }; ta.addEventListener('input', upd); upd();
        cancel.addEventListener('click', () => draw(false));
        save.addEventListener('click', async () => {
          const v = ta.value.trim(); if (v.length < 10 || v.length > 500) { msg.textContent = '신청 사유는 10~500자로 입력해 주세요.'; return; }
          save.disabled = true; msg.textContent = '저장 중…';
          try {
            const r = await fetch('/api/approval/v1/approval-requests/' + c.requestId + '/reason', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + sessionStorage.getItem('ama_tok') }, body: JSON.stringify({ reason: v }) });
            const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error((j.message || j.code || ('오류 ' + r.status)));
            c.reason = j.reason; c.reasonUpdatedAt = j.reasonUpdatedAt; draw(false); if (reload) reload();
          } catch (e) { msg.textContent = '저장하지 못했습니다: ' + (e.message || e); save.disabled = false; }
        });
        view.replaceChildren(h('p', { class: 'mut small' }, '승인 대기 중에만 수정할 수 있고, 수정하면 승인자는 사유를 다시 확인한 뒤 결정해야 합니다.'), ta, cnt, h('div', { class: 'pf-decb' }, save, cancel), msg); ta.focus(); return;
      }
      const eb = h('button', { type: 'button', class: 'btn', 'data-own': 1 }, c.reason ? '사유 수정' : '사유 입력'); eb.addEventListener('click', () => draw(true));
      view.replaceChildren(c.reason ? h('p', { class: 'pf-rsn-t' }, c.reason) : h('p', { class: 'mnote' }, '신청자가 입력한 사유가 없습니다(사유 입력 기능이 생기기 전에 만든 시험 데이터입니다).'),
        c.reason ? h('p', { class: 'mut small' }, c.requester + '님이 직접 입력 · ' + KST(c.reasonUpdatedAt) + (edited ? ' · 수정됨' : '')) : '', mine ? eb : '');
    };
    draw(false); return view;
  }

  // 새 거래 신청(모의): 조달 의도 기록(S04) → 정책 평가(S07) → 승인 신청(S07, 사유 필수). 승인은 별도 승인자가 건별로 한다. 실거래·주문 없음.
  const KINDS = { 'kr-sell': { label: '한국 KAU 배출권 매도(원화)', purpose: 'sell', ccy: 'KRW', unitName: '원/t', pos: 'kr', scen: 'POSCO-DEMO-2026-KR-SELL-WEB', priceLabel: '희망 매도 단가(원/t)' }, 'jp-buy': { label: '일본 GX 배출枠 매입(엔화)', purpose: 'buy', ccy: 'JPY', unitName: 'JPY/t', pos: 'jp', scen: 'GX-DEMO-JP01-FY2026-WEB', priceLabel: '상한 매입 단가(JPY/t)' } };
  const sha256 = async t => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(t)))].map(b => b.toString(16).padStart(2, '0')).join('');
  function applyForm(onDone, onClose) {
    const f = h('form', { class: 'pf-apply-f', novalidate: '' }), msg = h('p', { class: 'mnote', role: 'status' }, ''), prev = h('p', { class: 'pf-prev' }, '');
    const sel = h('select', { class: 'pf-in', 'data-own': 1, 'aria-label': '신청 종류' }, Object.entries(KINDS).map(([k, v]) => h('option', { value: k }, v.label)));
    const qty = h('input', { class: 'pf-in', type: 'number', min: 1, step: 1, 'data-own': 1, 'aria-label': '수량(t)' }), price = h('input', { class: 'pf-in', type: 'number', min: 1, step: 1, 'data-own': 1, 'aria-label': '단가' });
    const why = h('textarea', { class: 'pf-in pf-rta', rows: 4, maxlength: 500, 'data-own': 1, 'aria-label': '신청 사유', placeholder: '왜 이 거래를 신청하는지 구체적으로 적어 주세요. 예) 일본 4개 사업장의 2026년 예상 배출이 가정한 무상할당을 넘어 부족분 전량을 연내 매입하려 합니다. 근거: 계산 결과 부족분 1,359,247t.' });
    const cnt = h('span', { class: 'mut small' }, ''), amt = h('span', { class: 'pf-amt' }, ''), submit = h('button', { type: 'submit', class: 'btn pri', 'data-own': 1 }, '신청 접수'), close = h('button', { type: 'button', class: 'btn', 'data-own': 1 }, '닫기');
    const lab = (t, ...c) => h('label', { class: 'pf-fl' }, h('span', {}, t), ...c); let d = null, attempt = null, lastSig = '';
    const K = () => KINDS[sel.value], num = v => Math.floor(Number(v)), q = () => num(qty.value), pr = () => num(price.value);
    const ruleOf = () => { if (!d) return null; const x = q(); if (!(x > 0)) return null; if (K().pos === 'kr') { const r = d.result, ok = x >= r.minSellTon && x <= r.maxSellTon; return [ok, '허용 구간 ' + N(r.minSellTon) + '~' + N(r.maxSellTon) + 't ' + (ok ? '안' : '밖')]; } const s = d.result.shortageTon, ok = x >= s * 0.9 && x <= s * 1.05; return [ok, '예상 부족 ' + N(s) + 't의 90~105% ' + (ok ? '안' : '밖')]; };
    const refresh = () => { cnt.textContent = why.value.trim().length + '/500자 (10자 이상)'; const a = q() * pr(); amt.textContent = a > 0 ? '예상 금액 ' + (K().ccy === 'KRW' ? '₩ ' : 'JPY ') + N(a) : ''; const r = ruleOf(); prev.className = 'pf-prev' + (r ? (r[0] ? ' ok' : ' no') : ''); prev.textContent = r ? '규칙 미리보기: ' + (r[0] ? '권고' : '비권고') + ' — ' + r[1] + '. 비권고여도 신청할 수 있지만 승인자가 사유를 보고 판단합니다.' : ''; };
    const reset = async () => { d = null; refresh(); d = await getPos(K().pos); if (d) { qty.value = K().pos === 'kr' ? d.result.recommendedSellTon : d.result.shortageTon; price.value = K().pos === 'kr' ? d.actual.priceKauKrw : 3000; } refresh(); };
    sel.addEventListener('change', reset); [qty, price, why].forEach(e => e.addEventListener('input', refresh));
    close.addEventListener('click', () => onClose());
    f.addEventListener('submit', async ev => {
      ev.preventDefault(); const me = window.AMA_ME, t = sessionStorage.getItem('ama_tok'), k = K(), x = q(), p = pr(), reason = why.value.trim();
      if (!me || !t) { msg.textContent = '로그인이 필요합니다.'; return; } if (!(me.grants || []).includes('request')) { msg.textContent = '이 계정(' + me.username + ')에는 승인 신청 권한(request)이 없습니다.'; return; }
      if (!(x > 0) || x > 1e9) { msg.textContent = '수량은 1 이상의 정수(t)로 입력해 주세요.'; return; } if (!(p > 0) || p > 1e9) { msg.textContent = '단가는 1 이상의 정수로 입력해 주세요.'; return; }
      if (reason.length < 10 || reason.length > 500) { msg.textContent = '신청 사유는 필수입니다. 10~500자로 구체적으로 적어 주세요(현재 ' + reason.length + '자).'; why.focus(); return; }
      if (!window.confirm('모의 신청을 접수합니다.\n' + k.label + ' · ' + N(x) + 't · ' + (k.ccy === 'KRW' ? '₩ ' : 'JPY ') + N(x * p) + '\n실제 거래·주문은 나가지 않으며, 승인은 승인 권한이 있는 관리자 또는 검수자가 건별로 결정합니다. 계속할까요?')) return;
      const sig = JSON.stringify([sel.value, x, p, reason]); if (sig !== lastSig || !attempt) { attempt = crypto.randomUUID(); lastSig = sig; }   // 입력이 같은 재시도는 같은 키(중복 신청 방지)
      submit.disabled = true; const J = async (u, o, label) => { const r = await fetch(u, o), j = await r.json().catch(() => ({})); if (![200, 201, 202].includes(r.status)) throw new Error(label + ': ' + (j.message || j.code || ('오류 ' + r.status)) + (j.code ? ' [' + j.code + ']' : '')); return j; };
      try {
        msg.textContent = '1/3 조달 의도를 기록하는 중(S04)…'; const dd = d || await getPos(k.pos); if (!dd) throw new Error('규칙 계산 결과를 읽지 못했습니다');
        const now = new Date(), end = new Date(now.getTime() + 86400000), hash = await sha256(JSON.stringify(dd));
        const IT = await J('/api/proc/v1/procurement-intents', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': attempt + '-intent', 'X-Actor': me.username }, body: JSON.stringify({ businessRequestRef: 'WEB-' + attempt.slice(0, 13).toUpperCase(), instrumentType: 'allowance', purpose: k.purpose, quantity: { value: String(x), unit: 't' }, currency: k.ccy, priceCap: String(p), delivery: { start: now.toISOString(), end: end.toISOString() }, scenarioRef: { scenarioId: k.scen, scenarioVersion: 1, resultHash: hash }, assumption: { unitPrice: String(p), priceUnit: k.unitName, quoteCurrency: k.ccy } }) }, '조달 의도');
        msg.textContent = '2/3 정책을 평가하는 중(S07)…';
        const EV = await J('/api/approval/v1/policy-evaluations', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': attempt + '-eval', 'X-Actor': me.username }, body: JSON.stringify({ action: 'procurement.allowance.' + k.purpose, resource: 'ALLOWANCE', purpose: k.purpose.toUpperCase(), operationKey: 'KR|AMA-KR|S04|' + IT.businessOperationId, intentDigest: IT.intentDigest, canonicalizationVersion: IT.canonicalizationVersion, digestAlgorithmId: IT.digestAlgorithmId, amount: { value: String(x * p), currency: k.ccy } }) }, '정책 평가');
        msg.textContent = '3/3 승인 신청을 접수하는 중(S07)…';
        const RQ = await J('/api/approval/v1/approval-requests', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t, 'Idempotency-Key': attempt + '-req' }, body: JSON.stringify({ evaluationId: EV.evaluationId, intentRevision: IT.intentVersion, intentDigest: IT.intentDigest, intentRef: { intentId: IT.intentId, intentVersion: IT.intentVersion }, reason }) }, '승인 신청');
        msg.textContent = '접수했습니다(승인 대기). 목록에서 확인합니다.'; onDone(RQ);
      } catch (e) { msg.textContent = '접수하지 못했습니다: ' + (e.message || e) + ' — 같은 내용으로 다시 누르면 중복 없이 이어서 처리합니다.'; submit.disabled = false; }
    });
    f.append(h('p', { class: 'mnote' }, h('b', {}, '새 거래 신청(모의) '), '실제 거래·주문은 나가지 않습니다. 신청하면 승인 대기가 되고, 승인 권한이 있는 관리자 또는 검수자가 사유와 규칙 계산 결과를 보고 건별로 결정합니다.'),
      h('div', { class: 'pf-fg' }, lab('종류', sel), lab('수량(t)', qty), lab('단가', price), h('div', { class: 'pf-fl' }, h('span', {}, '예상 금액'), amt)), prev,
      lab('신청 사유(필수) — 왜 올리는지 직접 입력', why), h('div', { class: 'pf-fl-c' }, cnt), h('div', { class: 'pf-decb' }, submit, close), msg);
    why.addEventListener('input', refresh); reset(); return f;
  }

  // AI와 판단하기: 선택한 건에 대해 질문하면 AI(S11)가 S04의 규칙 계산 결과(건·규칙 판정·포지션)만 읽어 답한다. 승인·반려·실행은 하지 못한다.
  S.pfChat = S.pfChat || {};
  const QUICK = ['이 건의 규칙 판정 근거를 설명해 주세요', '승인하기 전에 확인할 점은 무엇인가요?', '수량이 허용 구간 안에 있나요?', '비권고라면 어떤 대안이 있나요?'];
  function chatBox(c) {
    const id = c.requestId, st = S.pfChat[id] || (S.pfChat[id] = { m: [], busy: false, draft: '' }), opid = String(c.operationKey || '').split('|').pop();
    const list = h('div', { class: 'pf-chat', role: 'log', 'aria-live': 'polite' }), inp = h('textarea', { class: 'pf-in', rows: 2, maxlength: 400, 'data-own': 1, 'aria-label': 'AI에게 질문', placeholder: '이 건에 대해 질문하세요(예: 왜 비권고인가요?). 승인·반려는 아래 버튼으로만 합니다.' }), send = h('button', { type: 'button', class: 'btn pri', 'data-own': 1 }, '질문 보내기');
    inp.value = st.draft || '';
    const bubble = m => h('div', { class: 'pf-msg ' + (m.role === 'u' ? 'u' : 'a') + (m.err ? ' err' : '') }, h('p', {}, m.text), m.meta ? h('p', { class: 'mut small' }, m.meta) : '');
    const draw = () => { list.replaceChildren(...(st.m.length ? st.m.map(bubble) : [h('p', { class: 'mnote' }, '아직 질문이 없습니다. 아래 예시를 누르거나 직접 입력하세요. 답변은 소유 서비스(S04)가 규칙으로 계산한 결과만 근거로 하는 초안이며, 승인·실행 권한이 없습니다.')]), ...(st.busy ? [h('p', { class: 'mnote' }, 'AI가 S04 계산 결과를 읽고 답하는 중입니다(20~60초)…')] : [])); list.scrollTop = list.scrollHeight; send.disabled = st.busy; };
    st.redraw = draw;
    async function ask(q) {
      q = String(q || '').trim(); if (!q || st.busy) return;
      const hist = []; for (let i = 0; i + 1 < st.m.length; i++) if (st.m[i].role === 'u' && st.m[i + 1].role === 'a' && !st.m[i + 1].err) hist.push({ q: st.m[i].text.slice(0, 400), a: st.m[i + 1].text.slice(0, 1500) });
      st.m.push({ role: 'u', text: q }); st.busy = true; st.draft = ''; inp.value = ''; st.redraw();
      try {
        const r = await fetch('/api/agent/agent-runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'pfq-' + (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()), 'X-Actor': (sessionStorage.getItem('ama-user') || 'portal-user') }, body: JSON.stringify({ schemaVersion: '1', role: 'AI-A03', task: 'ask_procurement_case', purpose: 'qa', plantScope: 'KR-01', contextRefs: [{ owner: 'S04', id: opid }], question: q, history: hist.slice(-4), ...(c.reason ? { requesterReason: c.reason } : {}) }) });
        const d = await r.json(); if (!r.ok) throw new Error(d.message || ('HTTP ' + r.status)); let run = null;
        for (let i = 0; i < 45; i++) { await new Promise(x => setTimeout(x, 2000)); run = await FETCH('/api/agent/agent-runs/' + d.agentRunId); if (['DRAFT', 'BLOCKED', 'FAILED'].includes(run.state)) break; }
        if (!run || !run.draft) st.m.push({ role: 'a', err: 1, text: '답변을 만들지 못했습니다: ' + ((run && run.blockedReasons && run.blockedReasons[0]) || (run && run.state) || '시간 초과') + ' (값을 보충하지 않았습니다).' });
        else { const ev = run.evaluation || {}; st.m.push({ role: 'a', text: run.draft.text, meta: `초안(DRAFT) · 모델 ${(run.usage && run.usage.model) || '–'} · 숫자 근거 검증 ${ev.numeric || '–'} · 실행 ${run.agentRunId.slice(0, 8)} · 승인·실행 권한 없음` }); }
      } catch (e) { st.m.push({ role: 'a', err: 1, text: '질문을 처리하지 못했습니다(' + (e.message || '오류') + '). 규칙 계산 결과는 위에 그대로 있습니다.' }); }
      finally { st.busy = false; st.redraw(); }
    }
    send.addEventListener('click', () => ask(inp.value)); inp.addEventListener('input', () => { st.draft = inp.value; });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(inp.value); } });
    draw();
    return h('div', { class: 'pf-chatw' }, list, h('div', { class: 'pf-qs' }, QUICK.map(t => { const b = h('button', { type: 'button', class: 'pf-q', 'data-own': 1 }, t); b.addEventListener('click', () => ask(t)); return b; })), h('div', { class: 'pf-ask' }, inp, send), h('p', { class: 'mut small' }, 'AI는 읽기 전용입니다. 승인·반려·주문은 하지 못하며, 답변은 규칙 계산 결과에 근거한 초안(모의)입니다.'));
  }
  function flow() {
    const root = h('div', { class: 'cstack' }), strip = stageStrip(), listBox = h('div', {}), detBox = h('div', {}), kpis = h('div', {});
    const applyBox = h('div', { class: 'pf-apply', hidden: '' }), applyBtn = h('button', { type: 'button', class: 'btn pri', 'data-own': 1 }, '＋ 새 거래 신청'), applyBar = h('div', { class: 'pf-bar' }, h('span', { class: 'mut small' }, '신청 사유를 직접 입력해 거래를 신청합니다(모의 · 실거래 없음)'), applyBtn);
    applyBtn.addEventListener('click', () => { if (!applyBox.hidden) { applyBox.hidden = true; applyBox.replaceChildren(); return; } applyBox.replaceChildren(applyForm(async rq => { S.pfSel = sel = rq.requestId; applyBox.hidden = true; applyBox.replaceChildren(); await load(); if (detBox.scrollIntoView) detBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, () => { applyBox.hidden = true; applyBox.replaceChildren(); })); applyBox.hidden = false; });
    root.append(card('전체 흐름 한눈에 보기', '실데이터', h('p', { class: 'mnote' }, '각 칸은 운영 서비스에서 지금 읽은 건수입니다. 승인·반려는 승인 권한이 있는 계정이 건별로 결정하고, 실행은 모의입니다(실거래 없음).'), strip), kpis, h('div', { class: 'card pf-one' }, applyBar, applyBox, listBox, detBox));
    let cases = [], vis = [], sel = S.pfSel;
    function detail() {
      const c = vis.find(x => x.requestId === sel) || vis[0]; if (!c) { detBox.replaceChildren(); return; }
      const s = steps(c), ev = [];
      ev.push([c.createdAt, '정책 평가', `${{ allow: '허용', deny: '거부', 'needs-approval': '관리자·검수자 승인 필요' }[c.policy.decision] || c.policy.decision} · 사유 ${c.policy.reasonCode} · 정책 ${c.policy.version}`, c.policy.decision === 'deny' ? 'fail' : 'done']);
      ev.push([c.createdAt, '승인 신청', `${c.requester} · ${title(c)} · ${MONEY(c.amountMinor, c.currency)}${c.intent && c.intent.rule ? ' · 규칙 판정 ' + (c.intent.rule.verdict === 'recommended' ? '권고' : '비권고') + '(' + c.intent.rule.reason + ')' : ''}`, 'done']);
      c.decisions.forEach(d => ev.push([d.decidedAt, '승인 결정', `${d.actor} · ${({ approve: '승인', reject: '거절', cancel: '취소' })[d.decision] || d.decision}${d.reasonCode ? ' · ' + d.reasonCode : ''}`, d.decision === 'approve' ? 'done' : 'fail']));
      if (c.state === 'pending') ev.push([null, '승인 대기', '승인자의 결정을 기다리는 중(만료 ' + KST(c.expiresAt) + ')', 'cur']);
      if (c.reservation) ev.push([null, '한도 예약', `${c.reservation.state} · ${MONEY(c.reservation.reservedMinor, c.currency)}`, 'done']);
      if (c.permit) ev.push([c.permit.createdAt, '허가(permit)', PMS[c.permit.state] || c.permit.state, s[4]]);
      if (c.execution) ev.push([c.execution.createdAt, '실행(모의)', `${EXS[c.execution.executionState] || c.execution.executionState} · 영수증 ${c.execution.receipts.length}건${c.execution.receipts.some(r => r.verified) ? ' · 검증됨' : ''}`, s[5]]);
      else if (c.permit && c.executionKnown === false) ev.push([null, '실행(모의)', '실행 서비스에서 상태를 읽지 못했습니다(없음이 아님)', 'unk']);
      const st0 = STATE[c.state] || [c.state, '--dl'], rule = c.intent && c.intent.rule, kr = window.POSCO_DEMO && c.currency === 'KRW';
      const kv = [['신청자', c.requester], ['금액', MONEY(c.amountMinor, c.currency)], ['신청', KST(c.createdAt) + ' (' + AGE(c.createdAt) + ')'], ['만료', c.expiresAt ? KST(c.expiresAt) : '–'], ['다음 조치', next(c, s)], ['작업 식별', c.operationKey]];
      const pos = kr ? h('details', { class: 'pf-pos', open: '' }, h('summary', {}, '포지션·규칙 근거 보기(포스코 공개 자료 기준)'), position()) : '';
      detBox.replaceChildren(card('선택한 거래 건 · 상세·AI 판단·승인', c.requestId.slice(0, 8) + ' · ' + st0[0],
        h('div', { class: 'pf-hd' }, h('b', { class: 'pf-ttl' }, title(c), verdict(c)), chip(st0[0], st0[1])),
        h('div', { class: 'pf-grid' },
          h('div', { class: 'pf-left' }, reasonBox(c, load), h('section', { class: 'pf-sec' }, h('h4', { class: 'pf-h4' }, '신청 정보'), h('dl', { class: 'pf-kv' }, kv.map(([k, v]) => h('div', { class: k === '작업 식별' ? 'wide' : '' }, h('dt', {}, k), h('dd', {}, v))))),
            h('section', { class: 'pf-sec' }, h('h4', { class: 'pf-h4' }, '진행 기록'), h('ol', { class: 'pf-tl' }, ev.map(([t, n, d, st]) => h('li', { class: st }, h('b', {}, n), h('span', {}, d), h('em', {}, t ? KST(t) : '–'))))),
            h('section', { class: 'pf-sec' }, h('h4', { class: 'pf-h4' }, '승인자 결정'), decidePanel(c, load) || h('p', { class: 'mnote' }, '이 건은 승인 대기 상태가 아니어서 결정 버튼이 없습니다(' + st0[0] + ').'))),
          h('aside', { class: 'pf-right' }, h('div', { class: 'pf-chath' }, h('b', {}, 'AI와 판단하기'), h('span', { class: 'tag' }, '초안·모의 · 읽기 전용')), chatBox(c))),
        pos));
    }
    let lastSig = '';
    function paint(force) {   // 같은 자료면 다시 그리지 않아 깜빡임을 막는다(행 선택은 강조·기록만 갱신)
      const sig = JSON.stringify([cases, !!S.pfTest]); if (!force && sig === lastSig) return; lastSig = sig;
      vis = S.pfTest ? cases : cases.filter(c => !isTest(c)); const hid = cases.length - cases.filter(c => !isTest(c)).length;
      const live = vis.filter(c => c.state === 'pending' || (c.state === 'approved' && !(c.execution && c.execution.executionState === 'executed')));
      const stuck = vis.filter(c => { const s = steps(c); return s.includes('fail') && c.state === 'approved'; });
      kpis.replaceChildren(h('div', { class: 'row r4' }, kpi('&#128221;', '전체 건', String(vis.length), '건', '최근 50건까지', '', '실데이터'), kpi('&#9203;', '승인 대기', String(vis.filter(c => c.state === 'pending').length), '건', '관리자·검수자 승인 필요', vis.some(c => c.state === 'pending') ? 'warn' : '', '실데이터'), kpi('&#9989;', '모의 체결 완료', String(vis.filter(c => c.execution && c.execution.executionState === 'executed').length), '건', '실거래 아님', '', '모의'), kpi('&#9888;', '막힘·확인 필요', String(stuck.length), '건', 'permit 차단·실행 실패 등', stuck.length ? 'warn' : '', '실데이터')));
      if (!vis.length) { listBox.replaceChildren(card('거래 건', '실데이터', h('p', { class: 'mnote' }, '아직 승인 신청이 없습니다.'))); detBox.replaceChildren(); return; }
      const tb = h('table', { class: 'tbl evt' }, h('thead', {}, h('tr', {}, ['건', '내용', '금액', '진행(정책→신청→승인→한도→허가→실행)', '상태', '신청자', '신청', '결정'].map((t, i) => h('th', { class: i === 2 ? 'n' : '' }, t)))),
        h('tbody', {}, vis.map(c => { const s = steps(c), st = STATE[c.state] || [c.state, '--dl']; const tr = h('tr', { class: 'pick' + ((sel || vis[0].requestId) === c.requestId ? ' on' : ''), tabindex: 0, 'data-own': 1 }, h('td', {}, c.requestId.slice(0, 8)), h('td', {}, h('b', { class: 'pf-ttl' }, title(c), verdict(c)), h('div', { class: 'mut small' }, next(c, s))), h('td', { class: 'n' }, MONEY(c.amountMinor, c.currency)), h('td', {}, dots(s)), h('td', {}, chip(st[0], st[1])), h('td', {}, c.requester), h('td', { class: 'mut' }, AGE(c.createdAt)), h('td', { class: 'pf-dcell' }, c.state === 'pending' ? decidePanel(c, load, true) : '–')); const go = () => { sel = S.pfSel = c.requestId; listBox.querySelectorAll('tr.pick').forEach(r => r.classList.toggle('on', r === tr)); detail(); if (detBox.scrollIntoView) detBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }; tr.addEventListener('click', go); tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); }); return tr; })));
      const tg = hid || S.pfTest ? (() => { const b = h('button', { type: 'button', class: 'pf-tg', 'data-own': 1 }, S.pfTest ? '시험 데이터 숨기기' : `시험 데이터 ${hid}건 보기(종단 시험이 남긴 건, 기본 숨김)`); b.addEventListener('click', () => { S.pfTest = !S.pfTest; paint(true); }); return b; })() : null;
      listBox.replaceChildren(card('거래 건 (행을 누르면 진행 기록)', '실데이터', tg, tb));
      detail();
    }
    async function load() {
      if (!root.isConnected) { clearInterval(tm); return; }
      try { cases = (await FETCH('/api/approval/v1/cases', true)).items || []; paint(); strip._set('permit', String(cases.filter(c => c.permit).length), 'permit 발급(건) · 서명 검증', 'ok'); strip._set('appr', String(cases.length), '승인 신청 · 대기 ' + cases.filter(c => c.state === 'pending').length + '건', 'ok'); }
      catch (e) { const msg = e.status === 401 ? '로그인이 필요합니다. 다시 로그인한 뒤 확인하세요.' : '거래 건을 불러오지 못했습니다(' + (e.message || '오류') + '). 잠시 후 다시 시도합니다. 없음이 아니라 읽기 실패입니다.'; listBox.replaceChildren(card('거래 건', '실데이터', h('p', { class: 'mnote' }, msg))); }
    }
    const tm = setInterval(load, 30000); setTimeout(load, 40); return root;
  }

  V.proc = () => {
    const tab = S.pt || 'flow';
    if (tab !== 'flow') { const v = orig(); const hd = v.querySelector('.phd'); if (hd) hd.replaceWith(header()); const note = h('p', { class: 'mnote', style: 'margin:0 0 8px' }, '이 탭은 코드에 적힌 시안(예시 값)입니다. 실제 진행 현황은 "거래 진행" 탭에서 확인합니다.'); v.insertBefore(note, v.children[1] || null); return v; }
    const root = h('div', { class: 'view' }); root.append(header(), flow()); return root;
  };
  function header() { return h('div', { class: 'phd' }, h('div', {}, h('b', {}, '조달·승인'), h('span', { class: 'mut' }, ' 직무 분리 · 건별 관리자·검수자 승인 · 실행은 모의(실거래 없음)')), h('div', { class: 'phc' }, tabsOf([['flow', '거래 진행'], ['st', '조달 현황(시안)'], ['rq', '승인 요청(시안)'], ['ct', '계약·위험(시안)']], S.pt || 'flow', 'pt'))); }
})();
