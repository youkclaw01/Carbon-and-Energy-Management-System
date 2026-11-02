'use strict';
// 에이전트 관리: 과제의 업무 Agent 5개(BA01~BA05)와 사용자가 만든 Agent(업무·SRE)를 한곳에서 관리합니다.
// 참고한 관리형 서비스 구조: Foundry Agent Service(모델 카탈로그·툴박스·MCP·지식), Copilot Studio(커넥터·MCP·다중 Agent),
// Azure SRE Agent(트리거=예약 작업·경고 대응 계획, 실행 모드=검토/자율, 커넥터), PagerDuty SRE Agent(런북·에스컬레이션).
// 이 화면은 시안입니다: 설정은 브라우저에만 저장되며 실제 Agent 실행·MCP 호출·모델 배포와는 아직 연결되지 않았습니다.
(function () {
  const T = (ko, en) => (window.I18N && I18N.lang === 'en') ? en : ko;
  const KEY = 'ama-agents-v2', uid = p => p + Math.random().toString(36).slice(2, 7);
  const LV = { 1: ['L1', '관찰', 'Observe'], 2: ['L2', '추천', 'Recommend'], 3: ['L3', '한도 내 실행·초과 시 승인', 'Act within limits, else approval'], 4: ['L4', '자율(감사 추적)', 'Autonomous with audit trail'] };
  const MODELS = [['gpt-6.1', 'GPT-6.1', ['최신 범용·긴 문맥 (기본)','Latest general · long context (default)']], ['gpt-6.1-mini', 'GPT-6.1 mini', ['최신 · 저비용·빠름','Latest · low cost · fast']], ['gpt-6-astra', 'GPT-6 Astra', ['심층 추론·검토','Deep reasoning · review']], ['claude-sonnet-5.5', 'Claude Sonnet 5.5', ['최신 · 긴 분석·코딩','Latest · long analysis · coding']], ['gpt-4.1', 'GPT-4.1 (이전 세대)', ['이전 세대·호환용','Previous gen · compatibility']], ['gpt-4.1-mini', 'GPT-4.1 mini (이전 세대)', ['이전 세대·호환용','Previous gen · compatibility']], ['o4-mini', 'o4-mini (이전 세대)', ['이전 세대·호환용','Previous gen · compatibility']]];
  const FEATS = [['overview', '종합 관제', 'Overview'], ['pl', '관제 공장', 'Monitored plants'], ['em', '배출 추정', 'Emission estimate'], ['co', '에너지 비용', 'Energy cost'], ['mk', '배출권 시세', 'Allowance price'], ['plants', '공장 운영', 'Plant operations'], ['calc', '산정 결과', 'Calculation results'], ['sim', '시뮬레이션', 'Simulation'], ['proc', '조달·승인', 'Procurement & approval'], ['cust', '고객 탄소정보', 'Customer carbon data'], ['audit', '증빙·감사', 'Evidence & audit']];
  const SKILLS = [['calc-engine', '배출 산정 엔진 호출', 'Call emission engine'], ['factor-lookup', '배출계수 버전 조회', 'Emission factor lookup'], ['cost-sim', '시나리오 비용 계산', 'Scenario cost calc'], ['limit-check', '한도·승인 검증', 'Limit & approval check'], ['disclosure', '공개정책 검사', 'Disclosure policy check'], ['evidence-pack', '증빙 패키지 생성', 'Evidence package builder'], ['report-draft', '보고서 초안(DOCX·XLSX)', 'Report drafting'], ['mail-draft', '담당자 메일 초안', 'Owner email draft'], ['runbook', '런북 실행', 'Runbook execution'], ['log-correlate', '로그·지표 상관 분석', 'Log & metric correlation']];
  const MCPS = [['krx', 'KRX 배출권 시세', 'KRX allowance prices', '조회 전용 · 일 1회 갱신', ['get_series', 'get_products']], ['hub', '공장 데이터 허브(IoT·이벤트)', 'Plant data hub (IoT/events)', '수신 상태·지연 조회', ['plant_status', 'ingest_lag']], ['monitor', 'Azure Monitor · Log Analytics', 'Azure Monitor · Log Analytics', '지표·로그 조회', ['query_logs', 'query_metrics']], ['notify', 'Teams·메일 알림', 'Teams · e-mail notifications', '알림 전송', ['post_message', 'send_mail']], ['itsm', '티켓·온콜(ServiceNow·PagerDuty 예시)', 'Ticket & on-call (ServiceNow · PagerDuty sample)', '티켓 생성·갱신', ['create_ticket', 'update_ticket']], ['aisearch', 'Azure AI Search (지식 검색)', 'Azure AI Search (knowledge)', '규정·방법론·정책·런북 검색 · 읽기 전용', ['search_knowledge', 'get_document']], ['trade', '거래 시스템 연계', 'Trading system bridge', '실행 차단(승인 전)', ['place_order']]];
  const METRICS = [['lag', '자료 수신 지연(분)', 'Data ingest lag (min)'], ['usage', '배출 목표 사용률(%)', 'Emission target usage (%)'], ['price', '시세 일 변동폭(%)', 'Price daily move (%)'], ['err', 'Agent 오류율(%)', 'Agent error rate (%)'], ['wait', '승인 대기 시간(시간)', 'Approval wait (h)']];
  const FREQ = [['hour', '매시간', 'Hourly'], ['day', '매일', 'Daily'], ['week', '매주 월요일', 'Weekly (Mon)'], ['month', '매월 1일', 'Monthly (1st)']];
  const mk = o => Object.assign({ status: 'active', temp: .2, budget: 50, features: [], knowledge: [], skills: [], mcp: [], schedules: [], alerts: [], log: [], limits: null, src: false, search: { idx: [], mode: 'hybrid', topK: 4, cite: true, country: '' } }, o);
  const SIDX = { BA01: ['methods', 'regulations'], BA02: ['regulations', 'policies'], BA03: ['regulations', 'policies'], BA04: ['policies', 'regulations'], BA05: ['methods', 'policies'], SRE01: ['runbooks'] };
  const ensure = a => { if (!a.search) a.search = { idx: (SIDX[a.id] || []).slice(), mode: 'hybrid', topK: 4, cite: true, country: '' }; return a; };
  const kn = (n, t, s, v) => ({ id: uid('k'), name: n, type: t, scope: s, ver: v });
  const mc = id => { const d = MCPS.find(x => x[0] === id); return { id, on: true, tools: d[4].slice() }; };
  const sch = (n, f, tm, ins, md) => ({ id: uid('s'), name: n, freq: f, time: tm, instr: ins, mode: md, on: true });
  const alr = (m, op, th, sev, ch, resp) => ({ id: uid('a'), metric: m, op, th, sev, ch, resp, on: true });
  function seed() {
    return { agents: [
      mk({ id: 'BA01', name: 'Emissions Calculation Agent', ko: '배출 산정 Agent', role: ['공장·제품별 Scope 1/2 배출량을 지속적으로 계산하고 계산 근거를 감사 추적으로 남깁니다. 계산은 결정론적 엔진이 하고 LLM은 설명과 이상 징후 해석만 맡습니다.', 'Continuously computes Scope 1/2 per plant and product and keeps an audit trail. A deterministic engine does the math; the LLM only explains and flags anomalies.'], src: true, svc: 'S02', level: 4, cap: 4, model: 'gpt-6.1-mini', features: ['overview', 'em', 'calc', 'audit'], skills: ['calc-engine', 'factor-lookup'], mcp: [mc('hub'), mc('notify')],
        knowledge: [kn('배출계수표 · 한국 2026', '문서', 'KR', 'v3'), kn('배출계수표 · 일본', '문서', 'JP', 'v2'), kn('GHG Protocol Scope 2 지침', '문서', '공통', 'v1')],
        schedules: [sch('전 공장 Scope 1/2 재계산', 'hour', '00', '모든 공장의 최신 수신분으로 Scope 1/2를 다시 계산하고 이전 버전과 차이가 큰 공장을 알려라.', 'auto')], alerts: [alr('lag', '>', 120, 'wn', 'portal', 'propose')] }),
      mk({ id: 'BA02', name: 'Cost Simulation Agent', ko: '비용 시뮬레이션 Agent', role: ['생산 계획에 맞춰 탄소·에너지 비용을 모델링하고 대안을 추천합니다. 추천만 하며 계획 변경이나 구매는 하지 않습니다.', 'Models carbon and energy cost against production plans and recommends options. It only recommends; it never changes plans or buys.'], src: true, svc: 'S03', level: 2, cap: 2, model: 'gpt-6-astra', features: ['co', 'sim', 'overview'], skills: ['cost-sim', 'report-draft'], mcp: [mc('krx')],
        knowledge: [kn('월간 생산 계획 템플릿', '데이터셋', '공통', 'v1'), kn('전력 요금표 · 한국', '문서', 'KR', 'v2')], schedules: [sch('월간 비용 계획 초안', 'month', '09', '다음 달 생산 계획 기준으로 시나리오 3개의 비용을 비교하고 추천안을 써라.', 'review')], alerts: [] }),
      mk({ id: 'BA03', name: 'Procurement Positioning Agent', ko: '조달 포지셔닝 Agent', role: ['한도 안에서 에너지·감축 수단 구매를 실행합니다. 한도를 넘으면 승인을 요청합니다. 현재는 외부 실행이 차단되어 후보·포지션 제안까지만 합니다.', 'Executes energy and abatement purchases within limits; above limits it asks for approval. External execution is currently blocked, so it only proposes candidates and positions.'], src: true, svc: 'S04', level: 3, cap: 3, model: 'gpt-6.1', features: ['proc', 'mk', 'overview'], skills: ['limit-check', 'cost-sim'], mcp: [mc('krx'), { id: 'trade', on: false, tools: ['place_order'] }],
        limits: { perTrade: 50000, perDay: 200000, approveAbove: 30000 }, knowledge: [kn('조달 한도 정책', '문서', '공통', 'v2'), kn('K-ETS 제도 요약', '문서', 'KR', 'v1')], schedules: [sch('시세 확인 후 포지션 점검', 'day', '09', '배출권 시세와 잔여 한도를 보고 필요하면 후보 거래를 제안하라(실행 금지).', 'review')], alerts: [alr('price', '>', 3, 'wn', 'portal', 'propose')] }),
      mk({ id: 'BA04', name: 'Customer Footprint Agent', ko: '고객 탄소정보 Agent', role: ['고객의 출하별 제품 탄소 요청에 공개정책 범위 안에서 답합니다. 정책 밖이거나 국가 밖으로 나가는 정보는 응답하지 않고 승인을 요청합니다.', 'Answers per-shipment product-carbon requests within the disclosure policy. Out-of-policy or cross-border data is withheld and escalated.'], src: true, svc: 'S05', level: 3, cap: 3, model: 'gpt-6.1-mini', features: ['cust', 'audit'], skills: ['disclosure', 'mail-draft'], mcp: [mc('notify')],
        knowledge: [kn('고객 공개정책', '문서', '공통', 'v2'), kn('제품별 탄소 계수', '데이터셋', '공통', 'v1')], schedules: [], alerts: [alr('wait', '>', 4, 'wn', 'mail', 'notify')] }),
      mk({ id: 'BA05', name: 'Evidence Assembly Agent', ko: '증빙 취합 Agent', role: ['검증에 바로 쓸 수 있는 계산 증빙을 계속 준비합니다. 초안은 자율로 쓰지만 외부 인증·최종 검증은 하지 않습니다.', 'Keeps verification-ready calculation evidence. Drafts autonomously; it never performs external certification or final verification.'], src: true, svc: 'S06', level: 4, cap: 4, model: 'gpt-6.1-mini', features: ['audit', 'calc'], skills: ['evidence-pack', 'report-draft'], mcp: [mc('notify')],
        knowledge: [kn('검증 방법론 체크리스트', '문서', '공통', 'v1'), kn('증빙 보존 정책', '문서', '공통', 'v1')], schedules: [sch('주간 증빙 패키지 초안', 'week', '08', '지난주 확정된 산정의 근거·계보·승인 참조를 모아 증빙 초안을 만들어라.', 'auto')], alerts: [] }),
      mk({ id: 'SRE01', name: 'Platform SRE Agent', ko: '플랫폼 SRE Agent', role: ['포털과 데이터 수신 상태를 지켜보고, 경고가 오면 원인을 조사해 조치안을 제안합니다. 예약 점검과 경고 대응을 맡는 운영 Agent의 예시입니다.', 'Watches portal and ingestion health, investigates alerts and proposes mitigations. An example operations agent that owns scheduled checks and alert response.'], kind: 'sre', svc: '운영', level: 2, cap: 3, model: 'gpt-6.1-mini', features: ['overview', 'pl'], skills: ['log-correlate', 'runbook', 'mail-draft'], mcp: [mc('monitor'), mc('notify'), mc('itsm')],
        knowledge: [kn('장애 대응 런북', '문서', '공통', 'v1'), kn('야간 중지·복구 절차', '문서', '공통', 'v1')], schedules: [sch('매시 상태 점검', 'hour', '10', '포털 응답, 게이트웨이 상태, 공장 데이터 수신 지연을 점검하고 이상이 있으면 요약하라.', 'review')], alerts: [alr('lag', '>', 60, 'er', 'teams', 'propose'), alr('err', '>', 5, 'wn', 'teams', 'notify')] })
    ].map(a => { a.log = [{ t: new Date().toISOString(), who: '시스템', msg: '기본 설정으로 생성(시안)' }]; ensure(a); if (!a.search.idx.length && SIDX[a.id]) a.search.idx = SIDX[a.id].slice(); if (a.search.idx.length && !a.mcp.some(x => x.id === 'aisearch')) a.mcp.push(mc('aisearch')); return a; }) };
  }
  function load() { try { const j = JSON.parse(localStorage.getItem(KEY)); if (j && j.agents && j.agents.length) return j; } catch (e) { } return seed(); }
  let ST = load(), sel = ST.agents[0].id, tab = 'ov', form = null;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(ST)); } catch (e) { } };
  const cur = () => ensure(ST.agents.find(a => a.id === sel) || ST.agents[0]);
  const canEdit = () => !window.S || !S.role || S.role === '관리자' || S.role === '승인자';
  const note = (a, msg) => { a.log.unshift({ t: new Date().toISOString(), who: (window.S && S.role) || '관리자', msg }); a.log = a.log.slice(0, 80); save(); };
  const R = () => go(true);
  const txt = (ko, en) => T(ko, en);
  const fm = d => { const x = new Date(d); return x.toLocaleString(T('ko-KR', 'en-US'), { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }); };

  // ── 작은 UI 부품 ──
  const sw = (on, fn, dis) => { const b = h('button', { type: 'button', class: 'ag-sw' + (on ? ' on' : ''), role: 'switch', 'aria-checked': !!on, 'data-own': 1, disabled: dis ? 'disabled' : null }); b.addEventListener('click', () => { if (!dis) fn(!on); }); return b; };
  const lab = (s, ...c) => h('label', { class: 'ag-f' }, h('span', {}, s), ...c);
  const inp = (v, fn, o = {}) => { const e = h('input', Object.assign({ value: v == null ? '' : v, 'data-own': 1 }, o)); e.addEventListener('change', () => fn(e.value)); return e; };
  const sel_ = (opts, v, fn) => { const e = h('select', { 'data-own': 1 }, ...opts.map(([k, a, b]) => h('option', Object.assign({ value: k }, k === v ? { selected: 'selected' } : {}), b === undefined ? a : T(a, b)))); e.addEventListener('change', () => fn(e.value)); return e; };
  const pill = (c, s) => h('span', { class: 'ag-pill ' + (c || '') }, s);
  const lvl = a => pill('lv' + a.level, LV[a.level][0] + ' ' + T(LV[a.level][1], LV[a.level][2]));
  const btn = (s, fn, c) => { const b = h('button', { type: 'button', class: 'ag-btn ' + (c || ''), 'data-own': 1 }, s); b.addEventListener('click', fn); return b; };
  const empty = s => h('p', { class: 'ag-empty' }, s);

  // ── 탭 내용 ──
  function tabOv(a) {
    const ed = canEdit(), box = h('div', { class: 'ag-pane' });
    box.append(h('p', { class: 'ag-role' }, T(a.role[0], a.role[1])),
      h('div', { class: 'ag-grid2' },
        lab(T('이름', 'Name'), inp(a.ko && !isEn() ? a.ko : a.name, v => { if (a.src) return; a.name = v; a.ko = v; note(a, '이름 변경: ' + v); R(); }, a.src ? { disabled: 'disabled' } : {})),
        lab(T('상태', 'Status'), sel_([['active', '운영 중', 'Active'], ['paused', '일시 중지', 'Paused']], a.status, v => { a.status = v; note(a, '상태: ' + v); R(); })),
        lab(T('모델 (Foundry 카탈로그 예시)', 'Model (Foundry catalog sample)'), sel_(MODELS.map(m => [m[0], m[1] + ' — ' + T(m[2][0], m[2][1])]), a.model, v => { a.model = v; note(a, '모델 변경: ' + v); R(); })),
        lab(T('온도(창의성) ', 'Temperature ') + a.temp, h('input', { type: 'range', min: 0, max: 1, step: .1, value: a.temp, 'data-own': 1, oninput: null }))),
      h('div', { class: 'ag-lv' }, h('span', { class: 'ag-l' }, T('자율성(실행 모드)', 'Autonomy (run mode)')),
        ...[1, 2, 3, 4].map(n => { const dis = n > a.cap, b = h('button', { type: 'button', class: 'ag-lvb' + (a.level === n ? ' on' : '') + (dis ? ' off' : ''), 'data-own': 1, title: dis ? T('원문 자율성 상한(L' + a.cap + ')을 넘기려면 승인이 필요합니다', 'Above the source cap (L' + a.cap + ') needs approval') : '' }, h('b', {}, 'L' + n), h('em', {}, T(LV[n][1], LV[n][2]))); b.addEventListener('click', () => { if (dis || !ed) return; a.level = n; note(a, '자율성 L' + n); R(); }); return b; }),
        h('p', { class: 'ag-hint' }, a.src ? T('과제 원문 기준 목표 자율성은 L' + a.cap + '입니다. 낮출 수는 있어도 승인 없이 높일 수 없습니다.', 'The source target autonomy is L' + a.cap + '. It can be lowered but not raised without approval.') : T('새 Agent는 쓰기 작업 기준 L3까지만 허용합니다. 그 이상은 승인 후 열립니다.', 'New agents are capped at L3 for write actions; more needs approval.'))));
    const rg = box.querySelector('input[type=range]'); if (rg) rg.addEventListener('change', () => { a.temp = +rg.value; note(a, '온도 ' + a.temp); R(); });
    box.append(h('div', { class: 'ag-grid2' }, lab(T('월 예산(만 원)', 'Monthly budget (KRW 10k)'), inp(a.budget, v => { a.budget = +v || 0; note(a, '월 예산 ' + a.budget); R(); }, { type: 'number', min: 0 })), lab(T('담당 서비스', 'Owner service'), h('b', { class: 'ag-b' }, a.svc || '-'))));
    const cnt = [['kn', T('지식', 'Knowledge'), a.knowledge.length + a.search.idx.length], ['sk', T('스킬', 'Skills'), a.skills.length + (a.customSkills || []).length], ['mcp', 'MCP', a.mcp.filter(x => x.on).length + (a.customMcp || []).length], ['map', T('포털 기능', 'Portal features'), a.features.length], ['sch', T('예약 작업', 'Tasks'), a.schedules.length], ['al', T('경고 규칙', 'Alert rules'), a.alerts.length]];
    box.append(h('div', { class: 'ag-cnt' }, ...cnt.map(([k, l, n]) => { const b = h('button', { type: 'button', class: 'ag-cn', 'data-own': 1 }, h('b', {}, n), h('span', {}, l)); b.addEventListener('click', () => { tab = k; R(); }); return b; })));
    if (a.limits) box.append(h('div', { class: 'ag-lim' }, h('b', {}, T('실행 한도(원문: 한도 안에서 실행, 초과 시 승인)', 'Execution limits (within limits; above them, approval)')),
      h('div', { class: 'ag-grid3' }, lab(T('1회 상한(톤)', 'Per trade (t)'), inp(a.limits.perTrade, v => { a.limits.perTrade = +v; note(a, '1회 상한 ' + v); R(); }, { type: 'number', min: 0 })), lab(T('일 상한(톤)', 'Per day (t)'), inp(a.limits.perDay, v => { a.limits.perDay = +v; note(a, '일 상한 ' + v); R(); }, { type: 'number', min: 0 })), lab(T('승인 필요 기준(톤)', 'Approval above (t)'), inp(a.limits.approveAbove, v => { a.limits.approveAbove = +v; note(a, '승인 기준 ' + v); R(); }, { type: 'number', min: 0 }))),
      h('p', { class: 'ag-hint' }, T('외부 거래 실행은 승인 방식이 원문에서 미결이라 지금은 차단되어 있습니다(MCP 탭의 거래 시스템 연계 꺼짐).', 'External trading stays blocked because the approval method is unresolved in the source (trading bridge is off in the MCP tab).'))));
    if (!a.src) box.append(h('div', { class: 'ag-danger' }, btn(T('이 Agent 삭제', 'Delete this agent'), () => { if (!ed) return; if (confirm(T('삭제할까요?', 'Delete?'))) { ST.agents = ST.agents.filter(x => x.id !== a.id); sel = ST.agents[0].id; save(); R(); } }, 'warn')));
    return box;
  }
  const isEn = () => window.I18N && I18N.lang === 'en';
  function searchSec(a, ed) {
    const K = window.AMA_KNOW, s = a.search, sec = h('div', { class: 'ag-srch' });
    if (!K) return sec;
    sec.append(h('div', { class: 'ag-sh' }, h('b', {}, T('AI Search 연결', 'AI Search connection')), pill(s.idx.length ? 'ok' : '', s.idx.length ? T(s.idx.length + '개 인덱스 연결', s.idx.length + ' indexes') : T('연결 안 됨', 'Not connected'))),
      h('p', { class: 'ag-hint' }, T('규정·방법론·정책·런북을 Azure AI Search 인덱스에서 찾아 근거로 씁니다. 연결하면 이 Agent가 검색 MCP 도구(search_knowledge)로 읽기 전용 검색을 합니다.', 'The agent grounds answers on regulations, methodology, policies and runbooks from Azure AI Search indexes via the read-only search MCP tool (search_knowledge).')));
    K.IDX.forEach(i => { const on = s.idx.includes(i.id); sec.append(h('div', { class: 'ag-row' }, sw(on, v => { if (!ed) return; s.idx = v ? s.idx.concat(i.id) : s.idx.filter(x => x !== i.id); if (v && !a.mcp.some(x => x.id === 'aisearch')) a.mcp.push({ id: 'aisearch', on: true, tools: ['search_knowledge', 'get_document'] }); note(a, 'AI Search 인덱스 ' + (v ? '연결: ' : '해제: ') + i.ko); R(); }, !ed), h('b', {}, T(i.ko, i.en)), h('em', {}, T(i.desc[0], i.desc[1])))); });
    if (s.idx.length) {
      sec.append(h('div', { class: 'ag-grid3' }, lab(T('검색 방식', 'Retrieval'), sel_([['hybrid', '하이브리드 + 시맨틱 랭커', 'Hybrid + semantic ranker'], ['keyword', '키워드(BM25)', 'Keyword (BM25)'], ['vector', '벡터(의미)', 'Vector (semantic)']], s.mode, v => { s.mode = v; note(a, '검색 방식 ' + v); R(); })), lab(T('가져올 조각 수(top-k)', 'Results (top-k)'), inp(s.topK, v => { s.topK = Math.max(1, Math.min(10, +v || 4)); note(a, 'top-k ' + s.topK); R(); }, { type: 'number', min: 1, max: 10 })), lab(T('국가 필터', 'Country filter'), sel_([['', '모든 국가', 'All'], ['KR', '한국', 'Korea'], ['JP', '일본', 'Japan'], ['SG', '싱가포르', 'Singapore']], s.country, v => { s.country = v; note(a, '국가 필터 ' + (v || '없음')); R(); }))),
        h('div', { class: 'ag-row' }, sw(s.cite, v => { s.cite = v; note(a, '출처 표시 필수 ' + (v ? '켜짐' : '꺼짐')); R(); }, !ed), h('b', {}, T('답변에 출처(문서·절·버전) 표시 필수', 'Require citations (document, section, version)')), h('em', {}, T('근거 없는 답변 방지', 'prevents ungrounded answers'))));
      const q = h('input', { placeholder: T('검색 테스트: 예) 승인 한도 · 배출계수 버전', 'Test search, e.g. approval limits · factor version'), 'data-own': 1 }), out = h('div', { class: 'ag-sres' });
      const run = () => { const r = K.search(q.value, { mode: s.mode, idx: s.idx, country: s.country, topK: s.topK }); out.replaceChildren(...(q.value.trim() ? (r.length ? r.map(x => h('div', { class: 'ag-hit' }, h('b', {}, x.doc + ' § ' + x.sec), pill('', x.ver), h('span', { class: 'ag-rel' }, h('i', { style: 'width:' + Math.round(x.rel * 100) + '%' })), h('p', { html: K.hl(x.text.slice(0, 150) + (x.text.length > 150 ? '…' : ''), x.hit) }))) : [empty(T('결과가 없습니다.', 'No results.'))]) : [])); };
      q.addEventListener('input', run); sec.append(h('div', { class: 'ag-add' }, q), out);
    }
    return sec;
  }
  function tabKnow(a) {
    const box = h('div', { class: 'ag-pane' }), ed = canEdit();
    box.append(searchSec(a, ed));
    box.append(h('p', { class: 'ag-hint' }, T('Agent가 근거로 참고하는 자료입니다. 등록한 자료는 이 Agent만 읽습니다(범위 표시 기준).', 'Reference material this agent grounds on. Registered items are readable by this agent only (per scope).')));
    a.knowledge.forEach(k => box.append(h('div', { class: 'ag-row' }, h('b', {}, k.name), pill('', k.type), pill('', k.scope), h('em', {}, k.ver), ed ? btn('×', () => { a.knowledge = a.knowledge.filter(x => x.id !== k.id); note(a, '지식 삭제: ' + k.name); R(); }, 'x') : '')));
    if (!a.knowledge.length) box.append(empty(T('등록된 지식이 없습니다.', 'No knowledge yet.')));
    if (ed) { const n = h('input', { placeholder: T('이름(예: 배출계수표 2027)', 'Name'), 'data-own': 1 }), t = sel_([['문서', '문서', 'Document'], ['URL', 'URL', 'URL'], ['데이터셋', '데이터셋', 'Dataset']], '문서', () => { }), s = sel_([['공통', '공통', 'Shared'], ['KR', '한국', 'Korea'], ['JP', '일본', 'Japan'], ['SG', '싱가포르', 'Singapore']], '공통', () => { });
      box.append(h('div', { class: 'ag-add' }, n, t, s, btn(T('＋ 지식 등록', '＋ Add'), () => { if (!n.value.trim()) return; a.knowledge.push(kn(n.value.trim(), t.value, s.value, 'v1')); note(a, '지식 등록: ' + n.value); R(); }, 'pri')), h('p', { class: 'ag-hint' }, T('시안: 실제 파일 업로드·색인은 아직 연결되지 않았고 목록만 저장됩니다.', 'Draft: no real upload/indexing yet; only the list is saved.'))); }
    return box;
  }
  function tabSkill(a) {
    const box = h('div', { class: 'ag-pane' }), ed = canEdit();
    box.append(h('p', { class: 'ag-hint' }, T('Agent가 호출할 수 있는 기능 묶음입니다. 쓰기 성격의 스킬은 자율성에 따라 실행 전 승인이 필요합니다.', 'Capabilities the agent can call. Write-type skills need approval depending on autonomy.')));
    SKILLS.forEach(([id, ko, en]) => { const on = a.skills.includes(id); box.append(h('div', { class: 'ag-row' }, sw(on, v => { if (!ed) return; a.skills = v ? a.skills.concat(id) : a.skills.filter(x => x !== id); note(a, '스킬 ' + (v ? '켜짐: ' : '꺼짐: ') + ko); R(); }, !ed), h('b', {}, T(ko, en)), h('em', {}, id))); });
    (a.customSkills || []).forEach(s => box.append(h('div', { class: 'ag-row' }, h('b', {}, s), pill('', T('직접 등록', 'Custom')), ed ? btn('×', () => { a.customSkills = a.customSkills.filter(x => x !== s); note(a, '스킬 삭제: ' + s); R(); }, 'x') : '')));
    if (ed) { const n = h('input', { placeholder: T('새 스킬 이름(예: 탄소 라벨 생성)', 'New skill name'), 'data-own': 1 }); box.append(h('div', { class: 'ag-add' }, n, btn(T('＋ 스킬 등록', '＋ Add'), () => { if (!n.value.trim()) return; (a.customSkills = a.customSkills || []).push(n.value.trim()); note(a, '스킬 등록: ' + n.value); R(); }, 'pri'))); }
    return box;
  }
  function tabMcp(a) {
    const box = h('div', { class: 'ag-pane' }), ed = canEdit();
    box.append(h('p', { class: 'ag-hint' }, T('MCP 서버(툴박스)를 연결하고 이 Agent가 쓸 도구만 골라 허용합니다. 인증은 관리 ID·Key Vault 참조로만 하며 키 값은 화면에 나오지 않습니다.', 'Connect MCP servers (toolbox) and allow only the tools this agent needs. Auth uses managed identity / Key Vault references; no secret values are shown.')));
    MCPS.forEach(([id, ko, en, desc, tools]) => { const c = a.mcp.find(x => x.id === id), on = c && c.on;
      const row = h('div', { class: 'ag-mcp' + (on ? ' on' : '') }, h('div', { class: 'ag-row' }, sw(on, v => { if (!ed) return; if (!c) a.mcp.push({ id, on: v, tools: tools.slice() }); else c.on = v; note(a, 'MCP ' + (v ? '연결: ' : '해제: ') + ko); R(); }, !ed), h('b', {}, T(ko, en)), pill(on ? 'ok' : '', on ? T('연결됨', 'Connected') : T('꺼짐', 'Off')), h('em', {}, desc)));
      if (on) row.append(h('div', { class: 'ag-tools' }, ...tools.map(t => { const al = c.tools.includes(t), b = h('button', { type: 'button', class: 'ag-chip' + (al ? ' on' : ''), 'data-own': 1 }, t); b.addEventListener('click', () => { if (!ed) return; c.tools = al ? c.tools.filter(x => x !== t) : c.tools.concat(t); note(a, `MCP 도구 ${al ? '차단' : '허용'}: ${id}.${t}`); R(); }); return b; })));
      box.append(row); });
    if (ed) { const n = h('input', { placeholder: T('새 MCP 서버 이름', 'New MCP server'), 'data-own': 1 }), u = h('input', { placeholder: 'https://…/mcp', 'data-own': 1 }); box.append(h('div', { class: 'ag-add' }, n, u, btn(T('＋ 서버 연결', '＋ Connect'), () => { if (!n.value.trim() || !/^https:\/\//.test(u.value)) { alert(T('이름과 https 주소를 입력하세요.', 'Enter a name and an https URL.')); return; } (a.customMcp = a.customMcp || []).push({ name: n.value.trim(), url: u.value.trim() }); note(a, 'MCP 서버 등록: ' + n.value); R(); }, 'pri'))); }
    (a.customMcp || []).forEach(m => box.append(h('div', { class: 'ag-row' }, h('b', {}, m.name), pill('', T('직접 등록', 'Custom')), h('em', {}, m.url.replace(/^(https:\/\/[^/]+).*/, '$1/…')), ed ? btn('×', () => { a.customMcp = a.customMcp.filter(x => x !== m); note(a, 'MCP 서버 삭제: ' + m.name); R(); }, 'x') : '')));
    return box;
  }
  function tabMap(a) {
    const box = h('div', { class: 'ag-pane' }), ed = canEdit();
    box.append(h('p', { class: 'ag-hint' }, T('이 Agent가 도와줄 포털 기능입니다. 선택한 화면 오른쪽 위에 담당 Agent가 표시되고, 그 화면에서 이 Agent를 호출할 수 있게 됩니다(시안: 표시만 연결).', 'Portal features this agent supports. The assigned agent is shown on those screens (draft: display only).')));
    box.append(h('div', { class: 'ag-featgrid' }, ...FEATS.map(([k, ko, en]) => { const on = a.features.includes(k), b = h('button', { type: 'button', class: 'ag-feat' + (on ? ' on' : ''), 'data-own': 1, 'aria-pressed': on }, T(ko, en)); b.addEventListener('click', () => { if (!ed) return; a.features = on ? a.features.filter(x => x !== k) : a.features.concat(k); note(a, '포털 기능 ' + (on ? '해제: ' : '매핑: ') + ko); R(); }); return b; })));
    return box;
  }
  function tabSched(a) {
    const box = h('div', { class: 'ag-pane' }), ed = canEdit();
    box.append(h('p', { class: 'ag-hint' }, T('정해진 시각에 Agent가 지시문대로 일하고 결과를 알림 채널에 남깁니다. 실행 모드가 \'검토\'이면 쓰기 작업은 승인 후에만 실행됩니다.', 'The agent runs the instruction on a schedule and posts results. In Review mode, write actions run only after approval.')));
    a.schedules.forEach(s => { const f = FREQ.find(x => x[0] === s.freq); box.append(h('div', { class: 'ag-card' }, h('div', { class: 'ag-row' }, sw(s.on, v => { s.on = v; note(a, '예약 작업 ' + (v ? '켜짐: ' : '꺼짐: ') + s.name); R(); }, !ed), h('b', {}, s.name), pill('', T(f[1], f[2]) + (s.freq === 'hour' ? ' :' + s.time : ' ' + s.time + ':00')), pill(s.mode === 'auto' ? 'wn' : 'ok', s.mode === 'auto' ? T('자율', 'Autonomous') : T('검토', 'Review')), ed ? btn('×', () => { a.schedules = a.schedules.filter(x => x.id !== s.id); note(a, '예약 작업 삭제: ' + s.name); R(); }, 'x') : ''), h('p', { class: 'ag-instr' }, s.instr))); });
    if (!a.schedules.length) box.append(empty(T('예약 작업이 없습니다.', 'No scheduled tasks.')));
    if (ed) { const n = h('input', { placeholder: T('작업 이름', 'Task name'), 'data-own': 1 }), f = sel_(FREQ.map(x => [x[0], x[1], x[2]]), 'day', () => { }), tm = h('input', { type: 'number', min: 0, max: 23, value: 9, 'data-own': 1, title: T('시각', 'Hour') }), md = sel_([['review', '검토', 'Review'], ['auto', '자율', 'Autonomous']], 'review', () => { }), ins = h('textarea', { placeholder: T('Agent에게 줄 지시문(자연어)', 'Instruction in natural language'), rows: 2, 'data-own': 1 });
      box.append(h('div', { class: 'ag-addcol' }, h('div', { class: 'ag-add' }, n, f, tm, md), ins, btn(T('＋ 예약 작업 만들기', '＋ Create task'), () => { if (!n.value.trim() || !ins.value.trim()) return; const mode = md.value === 'auto' && a.level < 3 ? 'review' : md.value; a.schedules.push(sch(n.value.trim(), f.value, String(tm.value).padStart(2, '0'), ins.value.trim(), mode)); note(a, '예약 작업 생성: ' + n.value + (mode !== md.value ? ' (자율성이 낮아 검토 모드로 설정)' : '')); R(); }, 'pri'))); }
    return box;
  }
  function tabAlert(a) {
    const box = h('div', { class: 'ag-pane' }), ed = canEdit();
    box.append(h('p', { class: 'ag-hint' }, T('지표가 기준을 넘으면 알림을 보내거나, Agent가 조사해 조치안을 제안하거나, (자율 모드에서만) 정해진 조치를 실행합니다. SRE 역할의 핵심 설정입니다.', 'When a metric crosses its threshold: notify, let the agent investigate and propose, or (autonomous only) run an approved action. This is the SRE core.')));
    const SEV = [['in', '정보', 'Info'], ['wn', '주의', 'Watch'], ['er', '경고', 'Alert']], CH = [['portal', '포털 알림', 'Portal'], ['teams', 'Teams', 'Teams'], ['mail', '메일', 'E-mail']], RS = [['notify', '알림만', 'Notify only'], ['propose', '조사 후 조치안 제안', 'Investigate & propose'], ['act', '자동 조치(자율)', 'Auto-remediate (autonomous)']];
    a.alerts.forEach(r => { const m = METRICS.find(x => x[0] === r.metric); box.append(h('div', { class: 'ag-card' }, h('div', { class: 'ag-row' }, sw(r.on, v => { r.on = v; note(a, '경고 규칙 ' + (v ? '켜짐' : '꺼짐') + ': ' + m[1]); R(); }, !ed), h('b', {}, T(m[1], m[2]) + ' ' + r.op + ' ' + r.th), pill(r.sev, T(SEV.find(x => x[0] === r.sev)[1], SEV.find(x => x[0] === r.sev)[2])), pill('', T(CH.find(x => x[0] === r.ch)[1], CH.find(x => x[0] === r.ch)[2])), pill('', T(RS.find(x => x[0] === r.resp)[1], RS.find(x => x[0] === r.resp)[2])), ed ? btn('×', () => { a.alerts = a.alerts.filter(x => x.id !== r.id); note(a, '경고 규칙 삭제'); R(); }, 'x') : ''))); });
    if (!a.alerts.length) box.append(empty(T('경고 규칙이 없습니다.', 'No alert rules.')));
    if (ed) { const m = sel_(METRICS.map(x => [x[0], x[1], x[2]]), 'lag', () => { }), op = sel_([['>', '>'], ['<', '<']], '>', () => { }), th = h('input', { type: 'number', value: 60, 'data-own': 1 }), sv = sel_(SEV.map(x => [x[0], x[1], x[2]]), 'wn', () => { }), ch = sel_(CH.map(x => [x[0], x[1], x[2]]), 'portal', () => { }), rs = sel_(RS.map(x => [x[0], x[1], x[2]]), 'notify', () => { });
      box.append(h('div', { class: 'ag-addcol' }, h('div', { class: 'ag-add' }, m, op, th, sv, ch, rs), btn(T('＋ 경고 규칙 추가', '＋ Add rule'), () => { const resp = rs.value === 'act' && a.level < 4 ? 'propose' : rs.value; a.alerts.push(alr(m.value, op.value, +th.value, sv.value, ch.value, resp)); note(a, '경고 규칙 추가: ' + m.value + (resp !== rs.value ? ' (자율성이 낮아 제안 모드로 설정)' : '')); R(); }, 'pri'))); }
    return box;
  }
  function tabLog(a) { const box = h('div', { class: 'ag-pane' }); box.append(h('p', { class: 'ag-hint' }, T('설정 변경은 모두 기록됩니다(누가·언제·무엇을). 시안에서는 이 브라우저에만 저장됩니다.', 'Every change is recorded (who, when, what). In this draft it stays in this browser.'))); a.log.forEach(l => box.append(h('div', { class: 'ag-log' }, h('time', {}, fm(l.t)), h('b', {}, l.who), h('span', {}, l.msg)))); return box; }
  const TABS = [['ov', '개요·모델', 'Overview · model', tabOv], ['kn', '지식', 'Knowledge', tabKnow], ['sk', '스킬', 'Skills', tabSkill], ['mcp', 'MCP', 'MCP', tabMcp], ['map', '포털 매핑', 'Portal mapping', tabMap], ['sch', '예약 작업', 'Scheduled tasks', tabSched], ['al', '경고·알람', 'Alerts', tabAlert], ['log', '변경 이력', 'History', tabLog]];

  // ── 새 Agent 만들기 ──
  const TEMPL = [['biz', '업무 Agent', 'Business agent', '포털 기능을 돕는 Agent. 쓰기 작업은 L3(한도·승인) 안에서만.', 'Helps a portal function; write actions within L3.'], ['sre', 'SRE Agent', 'SRE agent', '예약 점검과 경고 대응을 맡는 운영 Agent. 기본은 검토 모드.', 'Operations agent for scheduled checks and alert response; review mode by default.']];
  function createModal() {
    const bg = h('div', { class: 'ag-modal', role: 'dialog', 'aria-modal': 'true' }), box = h('div', { class: 'ag-mbox' });
    let kind = 'sre'; const name = h('input', { placeholder: T('예: 데이터 수신 SRE Agent', 'e.g. Ingestion SRE agent'), 'data-own': 1 }), role = h('textarea', { rows: 3, placeholder: T('이 Agent의 역할을 한두 문장으로', 'Describe the role in a sentence or two'), 'data-own': 1 }), model = sel_(MODELS.map(m => [m[0], m[1] + ' — ' + T(m[2][0], m[2][1])]), 'gpt-4.1-mini', () => { });
    const tp = h('div', { class: 'ag-templ' }); const draw = () => { tp.replaceChildren(...TEMPL.map(([k, ko, en, d1, d2]) => { const b = h('button', { type: 'button', class: 'ag-tpl' + (kind === k ? ' on' : ''), 'data-own': 1 }, h('b', {}, T(ko, en)), h('em', {}, T(d1, d2))); b.addEventListener('click', () => { kind = k; draw(); }); return b; })); }; draw();
    box.append(h('h3', {}, T('새 Agent 만들기', 'Create an agent')), tp, lab(T('이름', 'Name'), name), lab(T('역할 설명', 'Role'), role), lab(T('모델', 'Model'), model), h('p', { class: 'ag-hint' }, T('만든 뒤 지식·스킬·MCP·포털 매핑·예약 작업·경고 알람을 이어서 설정합니다. 처음에는 \'검토(L2)\'로 시작합니다.', 'Afterwards configure knowledge, skills, MCP, portal mapping, schedules and alerts. It starts in Review (L2).')),
      h('div', { class: 'ag-mact' }, btn(T('취소', 'Cancel'), () => bg.remove()), btn(T('만들기', 'Create'), () => { if (!name.value.trim()) { name.focus(); return; } const id = (kind === 'sre' ? 'SRE' : 'AG') + String(ST.agents.length + 1).padStart(2, '0'), a = mk({ id, name: name.value.trim(), ko: name.value.trim(), role: [role.value.trim() || T('역할 미입력', 'No role'), role.value.trim() || 'No role'], kind, svc: kind === 'sre' ? '운영' : '-', level: 2, cap: 3, model: model.value, skills: kind === 'sre' ? ['log-correlate', 'runbook'] : [], mcp: kind === 'sre' ? [mc('monitor'), mc('notify')] : [] }); a.log = [{ t: new Date().toISOString(), who: (window.S && S.role) || '관리자', msg: '새 Agent 생성(' + kind + ')' }]; ST.agents.push(a); sel = a.id; tab = 'ov'; save(); bg.remove(); R(); }, 'pri')));
    bg.append(box); bg.addEventListener('click', e => { if (e.target === bg) bg.remove(); }); document.body.append(bg); name.focus();
  }

  // ── 화면 ──
  V.agents = () => {
    const root = h('div', { class: 'view agview' }), ed = canEdit(), a = cur();
    const sc = ST.agents.reduce((s, x) => s + x.schedules.filter(y => y.on).length, 0), al = ST.agents.reduce((s, x) => s + x.alerts.filter(y => y.on).length, 0), mp = new Set(ST.agents.flatMap(x => x.mcp.filter(y => y.on).map(y => y.id))).size;
    root.append(h('div', { class: 'ag-sum' }, ...[[T('운영 중 Agent', 'Active agents'), ST.agents.filter(x => x.status === 'active').length + '/' + ST.agents.length], [T('예약 작업', 'Scheduled tasks'), sc], [T('활성 경고 규칙', 'Active alert rules'), al], [T('연결된 MCP', 'Connected MCP'), mp]].map(([k, v]) => h('div', { class: 'ag-stat' }, h('span', {}, k), h('b', {}, v)))), h('p', { class: 'ag-note' }, T('시안: 설정은 이 브라우저에만 저장되며 실제 Agent 실행·MCP 호출·모델 배포와는 아직 연결되지 않았습니다. 과제의 업무 Agent 5개(BA01~BA05)는 삭제할 수 없고 자율성 상한은 원문을 따릅니다.', 'Draft: settings are stored in this browser only and are not yet connected to real agent runs, MCP calls or model deployments. The five source agents (BA01–BA05) cannot be deleted and keep the source autonomy cap.')));
    const list = h('div', { class: 'ag-list' }, ...ST.agents.map(x => { const b = h('button', { type: 'button', class: 'ag-item' + (x.id === a.id ? ' sel' : '') + (x.status === 'paused' ? ' off' : ''), 'data-own': 1 }, h('div', { class: 'ag-ih' }, h('b', {}, x.id), lvl(x), x.src ? pill('src', T('과제', 'Case')) : pill(x.kind === 'sre' ? 'sre' : '', x.kind === 'sre' ? 'SRE' : T('추가', 'Custom'))), h('div', { class: 'ag-in' }, x.name), h('div', { class: 'ag-ik' }, isEn() ? x.name : x.ko), h('div', { class: 'ag-ir' }, T(x.role[0], x.role[1]).slice(0, 70) + '…')); b.addEventListener('click', () => { sel = x.id; R(); }); return b; }));
    const left = h('div', { class: 'card ag-left' }, h('h3', {}, h('span', {}, T('Agent', 'Agents') + ' (' + ST.agents.length + ')'), ed ? btn(T('＋ 새 Agent', '＋ New'), createModal, 'pri') : ''), list);
    const tabs = h('div', { class: 'ag-tabs', role: 'tablist' }, ...TABS.map(([k, ko, en]) => { const b = h('button', { type: 'button', class: 'ag-tab' + (tab === k ? ' on' : ''), role: 'tab', 'data-own': 1 }, T(ko, en)); b.addEventListener('click', () => { tab = k; R(); }); return b; }));
    const t = TABS.find(x => x[0] === tab) || TABS[0];
    const right = h('div', { class: 'card ag-right' }, h('div', { class: 'ag-head' }, h('div', {}, h('b', { class: 'ag-title' }, a.name), h('em', {}, a.id + (isEn() ? '' : ' · ' + a.ko))), h('div', { class: 'ag-hd-r' }, lvl(a), pill(a.status === 'active' ? 'ok' : '', a.status === 'active' ? T('운영 중', 'Active') : T('일시 중지', 'Paused')), pill('', MODELS.find(m => m[0] === a.model)[1]))), tabs, t[3](a));
    root.append(h('div', { class: 'ag-wrap' }, left, right));
    return root;
  };

  // ── 포털 화면에 담당 Agent 표시 + 높이 맞춤 ──
  function chips() {
    document.querySelectorAll('.agchips').forEach(e => e.remove());
    const k = (location.hash || '#overview').slice(1), key = (window.S && S.kpi && k === 'overview') ? S.kpi : k;
    const ag = ST.agents.filter(a => a.status === 'active' && (a.features.includes(key) || (key === 'overview' && !S.kpi && a.features.includes('overview')))); if (!ag.length || k === 'agents') return;
    const t = document.getElementById('view'); if (!t) return;
    const el = h('div', { class: 'agchips', 'data-own': 1 }, h('span', {}, T('담당 Agent', 'Agents')), ...ag.slice(0, 4).map(a => { const b = h('button', { type: 'button', class: 'agchip', title: T(a.role[0], a.role[1]), 'data-own': 1 }, a.id); b.addEventListener('click', () => { sel = a.id; tab = 'ov'; location.hash = '#agents'; }); return b; }));
    t.prepend(el);
  }
  function fit() { const w = document.querySelector('.ag-wrap'); if (!w) return; const top = w.getBoundingClientRect().top + window.scrollY; w.style.height = Math.max(480, window.innerHeight - top - 18) + 'px'; }
  const prev = window.afterGo; window.afterGo = function () { if (prev) prev.apply(this, arguments); try { chips(); } catch (e) { } fit(); requestAnimationFrame(fit); setTimeout(fit, 200); };
  window.addEventListener('resize', fit);
  window.AMA_AGENTS = { state: () => ST, reset: () => { ST = seed(); save(); R(); } };
})();
