'use strict';
// 에이전트 관리 — 실연결: AI 서비스(agent-api)의 모델·실행 건수·최근 실행(읽기 전용)을 위에 보여 준다.
// 아래 기존 편집 화면은 브라우저에만 저장되는 구성 예시이며 서비스 설정에는 반영되지 않는다.
(function () {
  if (typeof V === 'undefined' || !V.agents) return;
  const orig = V.agents;
  const TK = { judge_allowance_position: '한국 배출권 판단 설명', judge_gx_position: '일본 GX-ETS 판단 설명', judge_sg_tax_position: '싱가포르 탄소세 판단 설명', explain_calc_run: '산정 결과 설명', explain_scenario: '시나리오 설명', explain_procurement: '조달 설명' };
  const ST = { DRAFT: ['초안', 'ok'], REJECTED: ['거부', 'bad'], FAILED: ['실패', 'bad'], BLOCKED: ['차단됨', 'bad'], REQUESTED: ['요청됨', 'wn'] };
  V.agents = () => {
    const root = orig(), live = h('div', { class: 'view-live' }, h('p', { class: 'mut small' }, 'AI 서비스 조회 중…'));
    root.prepend(live);
    root.append(h('p', { class: 'mut small', style: 'margin-top:8px' }, '위쪽 “실제 AI 서비스”는 agent-api 조회 값입니다. 아래 편집 화면은 구성 예시이며 이 브라우저에만 저장되고 서비스 설정에는 반영되지 않습니다. AI는 초안 설명만 하며 승인·실행 권한이 없습니다.'));
    Promise.all([fetch('/api/agent/health', { cache: 'no-store' }).then(r => r.json()), fetch('/api/agent/agent-runs?limit=10', { cache: 'no-store' }).then(r => r.json())]).then(([hl, ls]) => {
      const items = ls.items || [], rows = items.map(x => [String(x.createdAt || '').slice(0, 16).replace('T', ' ') + ' UTC', TK[x.task] || x.task, badge((ST[x.state] || [x.state, 'wn'])[0], (ST[x.state] || [0, 'wn'])[1]), String(x.agentRunId).slice(0, 8) + '…']);
      const db = hl.db || {};
      live.replaceChildren(h('div', { class: 'row r4' }, kpi('&#129302;', '사용 모델', String(hl.model || '–'), '', '실데이터 · agent-api', '', '실데이터'), kpi('&#128221;', 'AI 초안 실행', String(db.runs == null ? '–' : db.runs), '건', '승인 권한 없음', '', '실데이터'), kpi('&#128209;', '감사 기록', String(db.audits == null ? '–' : db.audits), '건', '추가 기록형', '', '실데이터'), kpi('&#128260;', '처리한 요청', String(hl.requests == null ? '–' : hl.requests), '건', '서비스 시작 후', '', '실데이터')),
        h('div', { class: 'row', style: 'grid-template-columns:1fr' }, card('실제 AI 실행 (최근 10건)', '실연결', rows.length ? table(['실행 시각', '과제', '상태', '실행 ID'], rows) : h('p', { class: 'mut small' }, '실행 이력이 없습니다.'))));
    }).catch(() => live.replaceChildren(h('p', { class: 'mut small' }, 'AI 서비스 조회에 실패했습니다. 아래는 구성 예시입니다.')));
    return root;
  };
})();
