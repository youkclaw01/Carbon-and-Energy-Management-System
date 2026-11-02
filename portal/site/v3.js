/* v3 요점화(2026-11-02, 사용자 승인): 요약을 먼저 보이고 상세는 "상세 보기"로 접는다. 내용·API·값은 바꾸지 않고 접기만 한다.
   접힘 상태는 화면별로 이 탭 세션 동안 기억한다. 되돌리려면 index.html에서 v3.js·v3.css 두 줄을 지운다. */
(function () {
  const $1 = s => document.querySelector(s);
  /* 화면별: 컨테이너, 접기 시작·끝 위치(자식 순서), 단추 이름 */
  const FOLDS = {
    calc: { box: '#view .cstack', from: 3, to: 6, name: "상세 분석 그래프·기준 정보" },
    overview: { box: '#view > .view', from: 3, to: 4, name: '추가 현황' },
    plants: { box: '#view > .view', from: 4, to: 9, name: "기간·목표·부하·설비 상세" }
  };
  const key = () => (location.hash || '#overview').slice(1).split('?')[0];
  const KEEP = k => 'v3fold:' + k;
  let busy = false;

  function slimBanner() {
    if (key() !== 'calc') return; const b = $1('#view > .view > .card.fx-q'); if (b) b.classList.add('v3-slim');
  }
  function fold() {
    const k = key(), f = FOLDS[k]; if (!f) return; const box = $1(f.box); if (!box || box.querySelector(':scope > .v3-fold')) return;
    const kids = [...box.children]; if (kids.length <= f.to) return;
    const part = kids.slice(f.from, f.to + 1); const cards = part.reduce((n, e) => n + (e.classList.contains('card') ? 1 : e.querySelectorAll('.card').length), 0);
    const wrap = document.createElement('div'); wrap.className = 'v3-fold';
    const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'v3-toggle';
    const open = sessionStorage.getItem(KEEP(k)) === '1';
    const paint = on => { wrap.hidden = !on; btn.setAttribute('aria-expanded', on ? 'true' : 'false'); btn.innerHTML = `<span>${f.name} ${on ? '접기' : '보기'}</span><em>${cards}개 카드</em><i>${on ? '▴' : '▾'}</i>`; };
    busy = true; box.insertBefore(btn, part[0]); box.insertBefore(wrap, part[0]); part.forEach(e => wrap.appendChild(e)); paint(open); busy = false;
    btn.addEventListener('click', () => { const on = wrap.hidden; sessionStorage.setItem(KEEP(k), on ? '1' : '0'); paint(on); window.dispatchEvent(new Event('resize')); });
  }
  function pass() { if (busy) return; try { slimBanner(); fold(); } catch (e) { console.warn('v3', e && e.message); } }
  function init() {
    pass(); window.addEventListener('hashchange', () => setTimeout(pass, 50));
    const v = $1('#view'); if (v) new MutationObserver(pass).observe(v, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else setTimeout(init, 0);
})();
