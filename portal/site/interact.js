'use strict';
// 버튼·선택·표 행의 동작(모의). 실제 운영·저장과 연결되어 있지 않습니다.
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  function toast(msg) { const t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = msg; document.body.append(t); setTimeout(() => t.classList.add('out'), 2400); setTimeout(() => t.remove(), 2900); }
  function modal(title, nodes, foot) {
    close(); const bg = document.createElement('div'); bg.className = 'modal-bg'; bg.id = 'modal';
    const m = document.createElement('div'); m.className = 'modal'; m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true'); m.setAttribute('aria-label', title);
    const hd = document.createElement('div'); hd.className = 'mh'; hd.innerHTML = '<b></b><span class="tag">시안 · 모의</span>'; hd.firstChild.textContent = title;
    const x = document.createElement('button'); x.className = 'mx'; x.setAttribute('aria-label', '닫기'); x.textContent = '×'; x.onclick = close; hd.append(x);
    const bd = document.createElement('div'); bd.className = 'mb'; nodes.forEach(n => bd.append(n));
    const ft = document.createElement('div'); ft.className = 'mf'; (foot || []).forEach(n => ft.append(n));
    const cb = document.createElement('button'); cb.textContent = '닫기'; cb.onclick = close; ft.append(cb);
    m.append(hd, bd, ft); bg.append(m); bg.addEventListener('click', e => { if (e.target === bg) close(); }); document.body.append(bg); cb.focus();
  }
  window.AMAUI = { toast: (m) => toast(m), modal: (t, n, f) => modal(t, n, f), close: () => close() };
  function close() { const m = $('#modal'); if (m) m.remove(); }
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
  const kv = rows => { const g = el('div', 'kv'); rows.forEach(([k, v]) => { g.append(el('span', '', k), el('span', '', v)); }); return g; };
  const steps = (names, on) => { const s = el('div', 'steps'); names.forEach((n, i) => s.append(el('div', 'st' + (i < on ? ' on' : ''), (i + 1) + '. ' + n))); return s; };
  const note = t => el('p', 'mnote', t);
  document.addEventListener('click', e => {
    const b = e.target.closest('#view button:not(.chip)'); const tr = e.target.closest('#view tbody tr:not([data-own])'); if (b && b.dataset.own) return; if (tr && tr.closest('[data-nomodal]')) return;
    if (b && !b.disabled) {
      const t = b.textContent.trim(), row = b.closest('.it'), label = row ? row.querySelector('span').textContent.trim() : t;
      if (t === '검토' || t === '근거 확인') {
        modal((t === '검토' ? '검토 · ' : '근거 확인 · ') + label.split(' · ')[0].replace(/^원인 분석 /, ''),
          [kv([['항목', label], ['상태', '검토 대기'], ['기준 시각', '2026.10.31 09:00'], ['산정 버전', 'CALC v3.2 (예시)']]), note('근거 예시: 전월 대비 사용량 +14%, 수신 지연 설비 1건, 계수 버전 변경 없음.'), steps(['초안', '검토', '승인'], 1)],
          [Object.assign(el('button', '', '검토 시작 (모의)'), { onclick: () => { close(); toast('검토를 시작했습니다 (모의 · 저장되지 않음)'); } })]);
      } else if (t === '시나리오 저장') toast('시나리오를 저장했습니다 (모의 · 실제 저장 안 됨)');
      else if (t === '검토 요청') toast('검토 요청을 보냈습니다 (모의 · 실제 전송 안 됨)');
      else toast(t + ' (모의 동작)');
      return;
    }
    if (tr && !e.target.closest('button')) {
      const heads = [...tr.closest('table').querySelectorAll('thead th')].map(x => x.textContent.trim()), cells = [...tr.children].map(x => x.textContent.trim());
      modal('상세 · ' + (cells[0] || ''), [kv(heads.map((h, i) => [h, cells[i] || '-'])), note('이 화면은 디자인 시안이며 모든 값은 가상의 모의 자료입니다.')]);
    }
  });
  function nav() { const a = $('#nav a.on'); if (a && a.scrollIntoView) a.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' }); }
  window.addEventListener('hashchange', () => setTimeout(nav, 30)); setTimeout(nav, 100);
  document.querySelectorAll('#view button:disabled').forEach(b => b.title = '시안 단계: 실제 실행과 연결되어 있지 않습니다');
  new MutationObserver(() => document.querySelectorAll('#view button:disabled').forEach(b => b.title = '시안 단계: 실제 실행과 연결되어 있지 않습니다')).observe($('#view'), { childList: true });
})();
