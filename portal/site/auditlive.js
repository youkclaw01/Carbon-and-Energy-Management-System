'use strict';
// 증빙·감사 — 실연결: 증빙 서비스(evid-api)의 실제 건수·요청 목록을 위에 보여 주고, 기존 샘플은 "예시"로 아래에 둔다(읽기 전용).
(function () {
  if (typeof V === 'undefined' || !V.audit) return;
  const orig = V.audit, ST = { PACKAGE_READY: ['패키지 준비됨', 'ok'], REQUESTED: ['요청됨', 'wn'], FAILED: ['실패', 'bad'], LOCAL_UNSIGNED_DRAFT_READY: ['서명 전 초안', 'wn'] };
  const esc = s => String(s == null ? '' : s).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
  V.audit = () => {
    const root = orig(), live = h('div', { class: 'view-live' }, h('p', { class: 'mut small' }, '증빙 서비스 조회 중…'));
    root.prepend(live);
    root.append(h('p', { class: 'mut small', style: 'margin-top:8px' }, '위쪽 “실제 증빙”은 증빙 서비스(evid-api) 조회 값입니다. 이 아래 카드는 화면 구성을 보여 주는 예시이며 실제 값이 아닙니다.'));
    Promise.all([fetch('/api/evidence/health', { cache: 'no-store' }).then(r => r.json()), fetch('/api/evidence/v1/evidence-requests?limit=20', { cache: 'no-store' }).then(r => r.json())]).then(([hl, ls]) => {
      const items = ls.items || [], rows = items.map(x => [String(x.createdAt || '').slice(0, 16).replace('T', ' ') + ' UTC', x.plantId, x.purpose, badge((ST[x.generationState] || [x.generationState, 'wn'])[0], (ST[x.generationState] || [0, 'wn'])[1]), String(x.requestId).slice(0, 8) + '…', String(x.runId || '').slice(0, 8) + '…']);
      live.replaceChildren(h('div', { class: 'row r4' }, kpi('&#128193;', '증빙 요청', String((hl.db || {}).requests == null ? items.length : hl.db.requests), '건', '실데이터 · evid-api', '', '실데이터'), kpi('&#128230;', '증빙 패키지', String((hl.db || {}).packages == null ? '–' : hl.db.packages), '건', '서명·해시 포함', '', '실데이터'), kpi('&#128221;', '감사 기록', String((hl.db || {}).audits == null ? '–' : hl.db.audits), '건', '추가 기록형', '', '실데이터'), kpi('&#9989;', '서비스 버전', String(hl.version || '–'), '', '조회 시각 기준', '', '실데이터')),
        h('div', { class: 'row', style: 'grid-template-columns:1fr' }, card('실제 증빙 요청 (최근 20건)', '실연결', rows.length ? table(['요청 시각', '공장', '목적', '상태', '요청 ID', '산정 실행'], rows) : h('p', { class: 'mut small' }, '증빙 요청이 아직 없습니다.'))));
    }).catch(() => live.replaceChildren(h('p', { class: 'mut small' }, '증빙 서비스 조회에 실패했습니다. 아래는 예시입니다.')));
    return root;
  };
})();
