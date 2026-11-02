// 장기 작업(S12) 화면(읽기 전용): 수동 엔진이 처리한 작업 상태를 보여 줍니다. 엔진 호출·취소는 이 화면에서 하지 않습니다(승인·호출자 등록 후 별도).
(function () {
  const ST = { PENDING: ['대기(엔진 처리 전)', '--dl'], READY: ['준비', '--cy'], RUNNING: ['실행 중', '--cy'], WAITING_SOURCE: ['원천 대기', '--yl'], WAITING_APPROVAL: ['승인 대기', '--yl'], SUCCEEDED: ['완료', '--gr'], FAILED: ['실패', '--rd'], CANCEL_REQUESTED: ['취소 접수', '--yl'], CANCELLED: ['취소됨', '--dl'] };
  const WT = { 'calc.run': '탄소 산정 관찰(S02)', 'evidence.assemble': '증빙 조립 관찰(S06)', 'ingest.followup': '수신 후속(S01)' };
  const WR = { DQ_FAILED: '데이터 품질 실패', DEADLINE_EXCEEDED: '마감 초과', RUN_KEY_MISMATCH: '산정 키 불일치', S02_RUN_NOT_FOUND: 'S02에 산정 없음', S06_MANIFEST_NOT_FOUND: 'S06에 매니페스트 없음' };
  const KST = s => { try { return new Date(s).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch (e) { return s || '–'; } };
  TITLES.jobs = '장기 작업'; MENUS.push(['jobs', '장기 작업', '&#9201;']); ['관리자', '관제 담당', '승인자'].forEach(r => { if (ROLES[r] && !ROLES[r].includes('jobs')) ROLES[r] = ROLES[r].concat('jobs'); });
  const nav = $('#nav'); if (nav) nav.append(h('a', { href: '#jobs', 'data-k': 'jobs', id: 'nav-jobs', html: `<span class="ni">${ico('&#9201;')}</span><span>장기 작업</span>` }));
  V.jobs = () => {
    const root = h('div', { class: 'view' }), body = h('div', {}), c = card('장기 작업', '수동 엔진 · 읽기 전용', h('p', { class: 'mnote' }, '엔진은 호출할 때만 작업을 처리하며 자동 반복은 없습니다. "완료"는 작업이 끝났다는 뜻이고 확정 발행·승인·거래 성공이 아닙니다.'), body);
    async function load() {
      if (!c.isConnected) { clearInterval(tm); return; }
      try {
        const r = await fetch('/api/workflow/v1/jobs', { cache: 'no-store' }); if (!r.ok) throw new Error('HTTP ' + r.status); const items = (await r.json()).items || [];
        if (!items.length) { body.replaceChildren(h('p', { class: 'mnote' }, '등록된 작업이 없습니다.')); return; }
        const cnt = {}; items.forEach(x => cnt[x.state] = (cnt[x.state] || 0) + 1);
        const chips = h('div', { style: 'display:flex;gap:6px;flex-wrap:wrap;margin:6px 0' }, Object.keys(cnt).map(k => h('span', { class: 'tag', style: `color:var(${(ST[k] || ['', '--dl'])[1]});border-color:var(${(ST[k] || ['', '--dl'])[1]})` }, `${(ST[k] || [k])[0]} ${cnt[k]}`)));
        body.replaceChildren(chips, table(['작업', '유형', '상태', '사유', '마감(KST)', '갱신(KST)'], items.map(x => [x.jobKey, WT[x.workflowType] || x.workflowType, (ST[x.state] || [x.state])[0], WR[x.waitingReason] || x.waitingReason || '–', KST(x.deadlineAt), KST(x.updatedAt)])));
      } catch (e) { body.replaceChildren(h('p', { class: 'mnote' }, '작업 목록을 불러오지 못했습니다. 잠시 후 다시 시도합니다.')); }
    }
    root.append(c); const tm = setInterval(load, 30000); setTimeout(load, 60); return root;
  };
})();
