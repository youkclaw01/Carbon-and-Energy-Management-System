'use strict';
// 지식 검색(Azure AI Search 연동 설계의 화면 시안): 규정·방법론·정책·런북을 한곳에서 찾고, 같은 검색을 Agent에 연결합니다.
// 시안: 실제 Azure AI Search에는 아직 연결하지 않았고, 브라우저 안의 샘플 말뭉치로 검색을 흉내 냅니다(키워드+동의어 확장).
// 실제 연결 시 이 파일의 search()만 서버 API(검색 MCP 도구 search_knowledge)로 바꾸면 됩니다.
(function () {
  const T = (ko, en) => (window.I18N && I18N.lang === 'en') ? en : ko;
  const IDX = [
    { id: 'regulations', ko: '규정·제도', en: 'Regulations', desc: ['배출권거래제 등 국가별 제도 요약', 'National allowance-scheme summaries'], docs: 3, upd: '10-28' },
    { id: 'methods', ko: '산정 방법론', en: 'Methodology', desc: ['Scope 1/2 산정식·배출계수·검증 체크리스트', 'Scope 1/2 formulas, factors, verification checklist'], docs: 4, upd: '10-27' },
    { id: 'policies', ko: '내부 정책', en: 'Internal policies', desc: ['조달 한도·고객 공개·증빙 보존', 'Procurement limits, disclosure, evidence retention'], docs: 3, upd: '10-26' },
    { id: 'runbooks', ko: '운영 런북', en: 'Runbooks', desc: ['야간 중지·복구, 수신 지연 대응', 'Night stop/restore, ingestion-lag response'], docs: 3, upd: '10-30' }
  ];
  // 샘플 말뭉치(요약·시안): 제도의 구체적 수치·조항은 원문 대조 전이므로 담지 않습니다.
  const C = [
    { id: 'r1', idx: 'regulations', c: 'KR', type: '제도', ver: 'v1', doc: 'K-ETS 제도 요약', sec: '개요', ko: '한국 배출권거래제(K-ETS)는 사업장에 배출허용량을 할당하고, 이행 기간이 끝나면 실제 배출량만큼 배출권을 제출하게 하는 제도입니다. 부족분은 시장(경매·거래)에서 구매하고 남는 양은 이월·판매할 수 있습니다.', en: 'The Korea ETS allocates emission allowances to sites; at the end of each compliance period sites surrender allowances equal to actual emissions. Shortfalls are bought on the market; surpluses can be banked or sold.' },
    { id: 'r2', idx: 'regulations', c: 'KR', type: '제도', ver: 'v1', doc: 'K-ETS 제도 요약', sec: '시세·거래', ko: '배출권 시세는 한국거래소(KRX) 배출권시장에서 공개되며 KAU(할당배출권) 종목의 일별 종가·거래량을 확인할 수 있습니다. 조달 검토는 시세 위치·변동성·거래량과 함께 승인 한도를 봅니다.', en: 'Allowance prices are published by the KRX ETS market; KAU daily closes and volumes are available. Procurement reviews look at price position, volatility, volume and approval limits.' },
    { id: 'r3', idx: 'regulations', c: 'JP', type: '제도', ver: 'v1', doc: '일본 제도 요약(GX-ETS)', sec: '개요', ko: '일본은 GX 추진 체계 안에서 배출량 거래 제도를 단계적으로 도입하고 있습니다. 일본 사업장의 비용 환산에는 한국 시세를 그대로 쓰지 않고 별도 참고 가격을 둡니다(대조 전).', en: 'Japan is phasing in an emissions-trading scheme under its GX framework. Japanese sites use a separate reference price rather than the Korean price (not yet reconciled).' },
    { id: 'r4', idx: 'regulations', c: 'SG', type: '제도', ver: 'v1', doc: '싱가포르 제도 요약(탄소세)', sec: '개요', ko: '싱가포르는 일정 규모 이상의 배출 시설에 탄소세를 부과합니다. 한국 시세와 직접 비교하기보다 국가별 참고 가격으로 비용을 환산합니다(대조 전).', en: 'Singapore levies a carbon tax on larger emitters. Costs are converted with a country reference price instead of comparing directly with the Korean price (not yet reconciled).' },
    { id: 'm1', idx: 'methods', c: '공통', type: '방법론', ver: 'v1', doc: 'GHG Protocol 요약', sec: 'Scope 1/2 정의', ko: 'Scope 1은 사업장에서 직접 태우는 연료 등의 직접 배출, Scope 2는 구매한 전력·열·증기의 간접 배출입니다. Scope 2는 위치 기반(지역 평균 계수)과 시장 기반(계약·인증서 반영) 두 방식으로 계산합니다.', en: 'Scope 1 covers direct emissions from fuel burned on site; Scope 2 covers indirect emissions from purchased electricity, heat and steam. Scope 2 is reported location-based (grid average factor) and market-based (contracts and certificates).' },
    { id: 'm2', idx: 'methods', c: '공통', type: '방법론', ver: 'v2', doc: '산정 방법서', sec: '산정식', ko: '배출량 = 활동량 × 배출계수입니다. 활동량(전력 MWh, 연료 사용량)은 설비 계측값, 배출계수는 국가·연도별 버전 표에서 가져오며, 사용한 계수 버전을 결과와 함께 기록합니다.', en: 'Emissions = activity × emission factor. Activity (MWh, fuel use) comes from metering; factors come from versioned country-year tables, and the factor version is stored with each result.' },
    { id: 'm3', idx: 'methods', c: '공통', type: '방법론', ver: 'v1', doc: '배출계수 버전 정책', sec: '버전 관리', ko: '배출계수는 발행 기관·연도·적용 범위와 함께 버전으로 관리합니다. 계수가 바뀌면 이전 결과를 덮어쓰지 않고 새 버전으로 다시 계산해 차이를 기록합니다.', en: 'Emission factors are versioned with issuer, year and scope. When a factor changes, earlier results are not overwritten; a new version is recalculated and the difference recorded.' },
    { id: 'm4', idx: 'methods', c: '공통', type: '체크리스트', ver: 'v1', doc: '검증 체크리스트', sec: '증빙', ko: '검증에는 활동량의 원천(계측·청구서), 사용한 계수와 버전, 계산 이력, 승인 기록이 필요합니다. 증빙 취합 Agent는 이 항목을 모아 초안을 만들고 외부 검증은 수행하지 않습니다.', en: 'Verification needs the source of activity data (metering, invoices), the factor and version used, the calculation history and approval records. The evidence agent assembles these as a draft and does not perform external verification.' },
    { id: 'p1', idx: 'policies', c: '공통', type: '정책', ver: 'v2', doc: '조달 한도 정책', sec: '승인 기준', ko: '조달은 1회·일 한도 안에서만 자동으로 제안하며, 승인 필요 기준을 넘으면 관리자 또는 검수자의 승인을 요청합니다. 외부 거래 실행은 승인 방식이 확정되기 전까지 차단됩니다.', en: 'Procurement is proposed automatically only within per-trade and daily limits; above the approval threshold a human must approve. External execution stays blocked until the approval method is settled.' },
    { id: 'p2', idx: 'policies', c: '공통', type: '정책', ver: 'v2', doc: '고객 공개정책', sec: '공개 범위', ko: '고객에게 제공하는 제품 탄소 정보는 공개정책에 허용된 항목만 응답합니다. 정책 밖 항목이나 국가 경계를 넘는 정보는 응답하지 않고 담당자 승인을 요청합니다.', en: 'Product-carbon information for customers is limited to items allowed by the disclosure policy. Out-of-policy items and cross-border data are withheld and escalated to an owner.' },
    { id: 'p3', idx: 'policies', c: '공통', type: '정책', ver: 'v1', doc: '증빙 보존 정책', sec: '보존', ko: '계산 근거와 승인 기록은 정해진 기간 동안 변경할 수 없는 형태로 보존하고, 보고서에는 근거 식별자를 함께 적습니다.', en: 'Calculation evidence and approvals are retained in a tamper-evident form for the required period, and reports carry the evidence identifiers.' },
    { id: 'b1', idx: 'runbooks', c: '공통', type: '런북', ver: 'v1', doc: '야간 중지·복구 절차', sec: '복구', ko: '테넌트 자동화가 매일 00:46~00:52에 VM과 게이트웨이를 중지합니다. 복구 작업이 00:52·00:55·01:00에 게이트웨이를 시작하며 게이트웨이는 시작에 약 4분이 걸립니다.', en: 'Tenant automation stops VMs and the gateway daily around 00:46–00:52. The restore job starts the gateway at 00:52, 00:55 and 01:00; a gateway takes about 4 minutes to start.' },
    { id: 'b2', idx: 'runbooks', c: '공통', type: '런북', ver: 'v1', doc: '데이터 수신 지연 대응', sec: '1차 조치', ko: '수신율이 95% 아래로 내려가면 지연 설비를 확인하고, 해당 시간대 산정을 보류 표시합니다. 30분 이상 지연되면 담당자에게 알리고 복구 후 해당 구간을 다시 계산합니다.', en: 'If the receive rate drops below 95%, identify the delayed device and mark that window as on hold. After 30 minutes notify the owner and recalculate the window after recovery.' },
    { id: 'b3', idx: 'runbooks', c: '공통', type: '런북', ver: 'v1', doc: '게이트웨이 장애 대응', sec: '확인 순서', ko: '포털이 열리지 않으면 ① 게이트웨이 상태 ② 컨테이너 앱 개정 상태 ③ 최근 배포를 순서대로 확인하고, 이전 개정으로 되돌릴 수 있습니다.', en: 'If the portal does not open, check ① gateway state ② container app revision ③ recent deployments, and roll back to the previous revision if needed.' }
  ];
  const SYN = { 배출권: ['ets', '할당', '거래제', 'allowance', '시세'], 시세: ['가격', 'price', 'kau', 'krx'], 승인: ['한도', '임계', 'approval', 'limit'], 한도: ['승인', 'limit', '상한'], 계수: ['factor', '배출계수', '버전'], 증빙: ['검증', 'evidence', '근거', '보존'], 스코프: ['scope'], scope: ['스코프', '직접', '간접'], 복구: ['재시작', '중지', 'restore', '장애'], 지연: ['수신', 'lag', '끊김'], 공개: ['고객', 'disclosure'], 고객: ['공개', 'customer'], 일본: ['jp', 'gx', 'japan'], 싱가포르: ['sg', '탄소세', 'singapore'], 한국: ['kr', 'k-ets', 'korea'], 세금: ['탄소세', 'tax'], 검증: ['증빙', 'verification', '체크리스트'] };
  const tok = q => (q || '').toLowerCase().split(/[\s,.;:!?()/·]+/).filter(x => x.length >= 1);
  function search(q, o = {}) {
    const mode = o.mode || 'hybrid', idx = o.idx && o.idx.length ? o.idx : IDX.map(i => i.id), words = tok(q), en = window.I18N && I18N.lang === 'en';
    if (!words.length) return [];
    const exp = new Set(words); if (mode !== 'keyword') words.forEach(w => (SYN[w] || []).forEach(s => exp.add(s)));
    const res = C.filter(x => idx.includes(x.idx) && (!o.country || x.c === o.country || x.c === '공통')).map(x => {
      const hay = (x.doc + ' ' + x.sec + ' ' + x.ko + ' ' + x.en + ' ' + x.type + ' ' + x.c).toLowerCase(); let s = 0, hit = [];
      words.forEach(w => { const n = hay.split(w).length - 1; if (n) { s += Math.min(n, 4) * (w.length > 1 ? 2 : .5) + ((x.doc + x.sec).toLowerCase().includes(w) ? 3 : 0); hit.push(w); } });
      if (mode !== 'keyword') [...exp].filter(w => !words.includes(w)).forEach(w => { if (hay.includes(w)) { s += 1.2; hit.push(w); } });
      if (mode === 'vector') s = s * .85 + (hay.length ? 1 : 0);
      if (mode === 'hybrid' && s > 0) s += .8;                       // 시맨틱 랭커가 상위 의미 일치에 주는 가산(시안)
      return { ...x, score: s, hit: [...new Set(hit)] };
    }).filter(x => x.score > 0).sort((a, b) => b.score - a.score).slice(0, o.topK || 6);
    const mx = res[0] ? res[0].score : 1; res.forEach(r => { r.rel = Math.min(.99, r.score / mx * .92 + .05); r.text = en ? r.en : r.ko; });
    return res;
  }
  const hl = (text, hit) => { let t = text.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c])); hit.filter(w => w.length > 1).sort((a, b) => b.length - a.length).forEach(w => { t = t.replace(new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), m => `<mark>${m}</mark>`); }); return t; };
  window.AMA_KNOW = { IDX, C, search, hl };

  // ── 지식 검색 화면: 왼쪽은 AI와 대화로 묻고 답을 받는 공간, 오른쪽은 인덱스·담당 Agent·사용 현황 ──
  const MODES = [['hybrid', '하이브리드 + 시맨틱 랭커', 'Hybrid + semantic ranker'], ['keyword', '키워드(BM25)', 'Keyword (BM25)'], ['vector', '벡터(의미)', 'Vector (semantic)']];
  // 질문 주제(가장 관련 높은 인덱스)에 따라 담당 Agent가 정해집니다. 기본 담당은 근거를 모아 인용하는 BA05입니다.
  const AG = {
    regulations: { id: 'BA05', en: 'Evidence Assembly', ko: '증빙 취합', why: ['제도 근거를 모아 출처와 함께 정리', 'Collects regulatory evidence with citations'] },
    methods: { id: 'BA01', en: 'Emissions Calculation', ko: '배출 산정', why: ['산정식·계수 설명과 계산 근거 안내', 'Explains formulas, factors and calculation basis'] },
    policies: { id: 'BA03', en: 'Procurement Positioning', ko: '조달 포지셔닝', why: ['조달 한도·승인 기준 안내', 'Explains procurement limits and approval rules'] },
    runbooks: { id: 'SRE01', en: 'Platform SRE', ko: '플랫폼 SRE', why: ['운영 절차·장애 대응 안내', 'Guides operations and incident response'] }
  };
  const LEAD = AG.regulations;
  const KS = window.__ks = window.__ks || { q: '', mode: 'hybrid', idx: IDX.map(i => i.id), country: '', topK: 4, chat: [], n: 0 };
  KS.chat = KS.chat || []; KS.n = KS.n || 0;
  const first = t => { const m = t.match(/^.*?[.。](\s|$)/); return m ? m[0].trim() : t; };
  function answer(q) {
    const r = search(q, { mode: KS.mode, idx: KS.idx, country: KS.country, topK: KS.topK }), en = window.I18N && I18N.lang === 'en';
    if (!r.length) return { ag: LEAD, none: true, text: T('선택한 인덱스에서 근거를 찾지 못했습니다. 근거 없이 추측해서 답하지 않습니다. 검색어를 바꾸거나 인덱스·국가 설정을 넓혀 보세요.', 'No supporting passage was found in the selected indexes. I do not answer without evidence. Try different words or widen the index/country settings.'), src: [], follow: [T('배출계수 버전', 'emission factor versions'), T('승인 한도', 'approval limits')] };
    const ag = AG[r[0].idx] || LEAD, top = r.slice(0, 3);
    const head = T(`${r.length}개 근거를 찾았습니다. 가장 관련 높은 내용부터 정리합니다.`, `Found ${r.length} supporting passages. Summary, most relevant first.`);
    const body = top.map((x, i) => `[${i + 1}] ${first(x.text)}`);
    const follow = [...new Set(r.map(x => x.doc))].slice(0, 3).map(d => T(`${d} 자세히`, `More on ${d}`));
    return { ag, text: head, body, src: top, follow, more: r.length - top.length };
  }
  V.know = () => {
    const root = h('div', { class: 'view kview' });
    const msgs = h('div', { class: 'kc-msgs', 'aria-live': 'polite' });
    const input = h('input', { type: 'text', class: 'kc-in', placeholder: T('무엇이든 물어보세요 — 예: 배출계수 버전은 어떻게 관리해? · 승인 한도가 넘으면?', 'Ask anything — e.g. how are emission factors versioned? · what if the approval limit is exceeded?'), 'data-own': 1, 'aria-label': T('지식 검색 질문', 'Knowledge question') });
    const send = h('button', { type: 'button', class: 'kc-send', 'data-own': 1, 'aria-label': T('보내기', 'Send') }, T('보내기', 'Send'));
    const seg = h('div', { class: 'ks-seg', role: 'group' }, MODES.map(([k, ko, en]) => { const b = h('button', { type: 'button', class: 'ks-sb' + (KS.mode === k ? ' on' : ''), 'data-own': 1 }, T(ko, en)); b.addEventListener('click', () => { KS.mode = k; seg.querySelectorAll('.ks-sb').forEach((x, i) => x.classList.toggle('on', MODES[i][0] === k)); }); return b; }));
    const chips = h('div', { class: 'ks-idx' }, IDX.map(i => { const b = h('button', { type: 'button', class: 'ks-ic' + (KS.idx.includes(i.id) ? ' on' : ''), 'data-own': 1, title: T(i.desc[0], i.desc[1]) }, T(i.ko, i.en), h('em', {}, String(C.filter(x => x.idx === i.id).length))); b.addEventListener('click', () => { KS.idx = KS.idx.includes(i.id) ? KS.idx.filter(x => x !== i.id) : KS.idx.concat(i.id); b.classList.toggle('on'); }); return b; }));
    const ctry = h('select', { class: 'ks-sel', 'data-own': 1, 'aria-label': T('국가', 'Country') }, [['', T('모든 국가', 'All countries')], ['KR', T('한국', 'Korea')], ['JP', T('일본', 'Japan')], ['SG', T('싱가포르', 'Singapore')]].map(([v, t]) => h('option', Object.assign({ value: v }, KS.country === v ? { selected: 'selected' } : {}), t)));
    ctry.addEventListener('change', () => { KS.country = ctry.value; });
    const bubble = (m) => {
      if (m.role === 'me') return h('div', { class: 'kc-m me' }, h('div', { class: 'kc-b' }, m.text));
      const a = m.a, el = h('div', { class: 'kc-m ai' }, h('div', { class: 'kc-who' }, h('b', {}, a.ag.id), h('span', {}, ' ' + T(a.ag.ko, a.ag.en) + ' Agent'), h('em', {}, T(' · 담당 배정: ', ' · assigned: ') + T(a.ag.why[0], a.ag.why[1]))),
        h('div', { class: 'kc-b' }, h('p', {}, a.text), ...(a.body || []).map(t => h('p', { class: 'kc-li' }, t)), a.more > 0 ? h('p', { class: 'mut small' }, T(`그 밖의 근거 ${a.more}건은 설정에서 결과 수를 늘리면 보입니다.`, `${a.more} more passages: raise the result count in settings.`)) : ''),
        a.src.length ? h('div', { class: 'kc-src' }, h('div', { class: 'kc-sh' }, T('출처', 'Sources')), ...a.src.map((x, i) => h('details', { class: 'kc-sd' }, h('summary', {}, h('b', {}, `[${i + 1}] ${x.doc}`), h('span', {}, ` § ${x.sec} · ${x.ver} · ${x.c === '공통' ? T('공통', 'Shared') : x.c}`), h('i', { class: 'kc-rel', style: `--w:${Math.round(x.rel * 100)}%` })), h('p', { html: hl(x.text, x.hit) })))) : '',
        a.follow && a.follow.length ? h('div', { class: 'qfu' }, h('span', { class: 'mut small' }, T('이어서 물어보기', 'Ask next')), ...a.follow.map(f => { const b = h('button', { type: 'button', class: 'ks-e', 'data-own': 1 }, f); b.addEventListener('click', () => ask(f)); return b; })) : '');
      return el;
    };
    const welcome = () => h('div', { class: 'kc-m ai' }, h('div', { class: 'kc-who' }, h('b', {}, LEAD.id), h('span', {}, ' ' + T(LEAD.ko, LEAD.en) + ' Agent'), h('em', {}, T(' · 기본 담당', ' · default owner'))),
      h('div', { class: 'kc-b' }, h('p', {}, T('규정·산정 방법·내부 정책·운영 런북을 찾아서 출처와 함께 답해 드립니다. 질문 주제에 따라 담당 Agent가 자동으로 바뀝니다(제도 BA05 · 산정 BA01 · 정책 BA03 · 런북 SRE01).', 'I search regulations, methodology, internal policies and runbooks and answer with sources. The owning agent switches with the topic (regulations BA05 · methodology BA01 · policies BA03 · runbooks SRE01).'))),
      h('div', { class: 'ks-ex' }, [T('배출계수 버전', 'emission factor versions'), T('승인 한도', 'approval limits'), T('Scope 2 위치 기반', 'Scope 2 location-based'), T('수신 지연 대응', 'ingestion lag response'), T('일본 제도', 'Japan scheme')].map(x => { const b = h('button', { type: 'button', class: 'ks-e', 'data-own': 1 }, x); b.addEventListener('click', () => ask(x)); return b; })));
    const paint = () => { msgs.replaceChildren(welcome(), ...KS.chat.map(bubble)); msgs.scrollTop = msgs.scrollHeight; };
    function ask(q) {
      q = (q || '').trim(); if (!q) return; input.value = ''; KS.n++;
      KS.chat.push({ role: 'me', text: q }); paint();
      const thinking = h('div', { class: 'kc-m ai' }, h('div', { class: 'kc-b kc-dots' }, h('i'), h('i'), h('i'))); msgs.append(thinking); msgs.scrollTop = msgs.scrollHeight;
      setTimeout(() => { KS.chat.push({ role: 'ai', a: answer(q) }); paint(); }, 650);
    }
    send.addEventListener('click', () => ask(input.value)); input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) ask(input.value); });
    const clear = h('button', { type: 'button', class: 'mk-aib', 'data-own': 1, title: T('새 대화', 'New chat') }, T('새 대화', 'New'));
    clear.addEventListener('click', () => { KS.chat = []; paint(); });
    const chat = h('div', { class: 'card kc' }, h('div', { class: 'kc-head' }, h('b', {}, T('지식 검색 AI', 'Knowledge search AI')), h('span', { class: 'tag' }, T('예시', 'Sample')), clear), h('div', { class: 'kc-set' }, seg, ctry, chips), msgs, h('div', { class: 'kc-bar' }, input, send), h('div', { class: 'mut small kc-foot' }, T('시안: 규칙 기반 모의 답변이며 근거는 샘플 문서입니다. 근거가 없으면 답하지 않고, 투자·법률 자문이 아닙니다.', 'Draft: rule-based mock answers over sample documents. No evidence, no answer; not investment or legal advice.')));
    const ag = (() => { try { return window.AMA_AGENTS.state().agents; } catch (e) { return []; } })();
    const rows = Object.entries(AG).map(([k, a]) => { const ix = IDX.find(i => i.id === k); return h('div', { class: 'ks-rt' }, h('div', { class: 'ks-rth' }, h('b', {}, a.id), h('span', {}, T(a.ko, a.en)), h('em', {}, T(ix.ko, ix.en))), h('p', {}, T(a.why[0], a.why[1]))); });
    const stat = (k, v, s) => h('div', { class: 'ks-st' }, h('span', {}, k), h('b', {}, v), h('em', {}, s));
    const faq = [T('배출계수 버전은 어떻게 관리해?', 'How are emission factors versioned?'), T('승인 한도를 넘으면 어떻게 돼?', 'What happens above the approval limit?'), T('Scope 2 위치 기반이 뭐야?', 'What is location-based Scope 2?'), T('수신율이 95% 아래면?', 'What if the receive rate is below 95%?'), T('일본 사업장은 어떤 가격을 써?', 'Which price do Japanese sites use?')];
    const side = h('div', { class: 'ks-side' },
      card(T('연결된 인덱스', 'Connected indexes'), T('설계', 'Design'), ...IDX.map(i => h('div', { class: 'ks-ix' }, h('div', { class: 'ks-ixh' }, h('b', {}, T(i.ko, i.en)), h('em', {}, T('문서 ', 'docs ') + i.docs + ' · ' + C.filter(x => x.idx === i.id).length + T(' 조각', ' chunks') + ' · ' + T('색인 ', 'indexed ') + i.upd)))), h('a', { class: 'ks-link', href: '#agents' }, T('Agent 관리에서 연결 설정 ›', 'Connect to agents ›'))),
      card(T('담당 Agent 배정', 'Owning agents'), T('자동', 'Auto'), ...rows),
      card(T('자주 묻는 질문', 'Frequently asked'), '', h('div', { class: 'ks-faq' }, faq.map(f => { const b = h('button', { type: 'button', class: 'ks-fq', 'data-own': 1 }, f); b.addEventListener('click', () => { ask(f); }); return b; }))),
      card(T('사용 현황과 구성', 'Usage & architecture'), '', h('div', { class: 'ks-sts' }, stat(T('오늘 질문', 'Questions today'), String(18 + KS.n), T('모의', 'mock')), stat(T('출처 인용', 'Cited'), '100%', T('근거 없으면 답변 보류', 'no evidence, no answer')), stat(T('평균 응답', 'Avg reply'), '1.8s', T('모의', 'mock'))), h('p', { class: 'ks-note' }, T('Azure AI Search(S1·한국 중부·비공개 접속)는 생성됐지만 색인·권한 전이라 샘플 문서로 동작합니다.', 'Azure AI Search (S1 · Korea Central · private) exists, but with no index or permissions yet this runs on sample documents.'))));
    root.append(h('div', { class: 'ks-grid' }, chat, side));
    paint(); return root;
  };
})();
