/* v7.45 메뉴·가독성 통일(2026-11-02, 사용자 요청): 메뉴 묶음·하위 탭, 카드 행 끝선 정렬, 최소 글자 크기.
   화면 내용·API는 바꾸지 않는다. 되돌리려면 index.html에서 unify.css/unify.js 두 줄을 지운다. */
(function () {
  const $1 = s => document.querySelector(s);
  const GROUPS = [['관제', ['overview', 'plants', 'factory', 'flow']], ['분석·계획', ['calc', 'sim', 'cust']], ['조달·통제', ['proc', 'audit']], ['지식·AI', ['know', 'agents']], ['시스템', ['topo', 'users', 'account']]];
  const MIN_FONT = 11.5;
  const curKey = () => (location.hash || '#overview').slice(1).split('?')[0];
  const label = a => { const s = a.querySelector('span:not(.ni)'); return (s ? s.textContent : a.textContent).trim(); };
  const visible = a => a.style.display !== 'none';

  /* 1) 왼쪽 메뉴를 묶음 순서로 정렬하고 묶음 이름을 끼운다 */
  let navSig = '';
  function regroup() {
    const nav = $1('#nav'); if (!nav) return;
    const links = [...nav.querySelectorAll('a[data-k]')]; const sig = links.map(a => a.dataset.k).join(',');
    if (sig === navSig && nav.querySelector('.ng-cap')) return;
    const by = {}; links.forEach(a => { by[a.dataset.k] = a; }); const used = new Set();
    nav.querySelectorAll('.ng-cap').forEach(e => e.remove());
    GROUPS.forEach(([cap, keys]) => {
      const ks = keys.filter(k => by[k]); if (!ks.length) return;
      const c = document.createElement('div'); c.className = 'ng-cap'; c.textContent = cap; nav.appendChild(c);
      ks.forEach(k => { nav.appendChild(by[k]); used.add(k); });
    });
    links.filter(a => !used.has(a.dataset.k)).forEach(a => nav.appendChild(a));
    navSig = [...nav.querySelectorAll('a[data-k]')].map(a => a.dataset.k).join(',');
  }

  /* 2) 제목 줄 아래 하위 탭: 같은 묶음의 화면으로 바로 이동 */
  function renderTabs() {
    const main = $1('main.main'), view = $1('#view'); if (!main || !view) return;
    let bar = $1('#subtabs'); if (!bar) { bar = document.createElement('nav'); bar.id = 'subtabs'; bar.setAttribute('aria-label', '하위 메뉴'); view.before(bar); }
    const key = curKey(), g = GROUPS.find(([, ks]) => ks.includes(key)); const nav = $1('#nav');
    if (!g || !nav) { bar.hidden = true; bar.textContent = ''; return; }
    const tabs = g[1].map(k => nav.querySelector(`a[data-k="${k}"]`)).filter(a => a && visible(a));
    const sig = g[0] + '|' + key + '|' + tabs.map(a => a.dataset.k + label(a)).join(',');
    if (bar.dataset.sig === sig) return; bar.dataset.sig = sig; bar.hidden = tabs.length < 2; bar.textContent = '';
    const cap = document.createElement('span'); cap.className = 'st-cap'; cap.textContent = g[0]; bar.appendChild(cap);
    tabs.forEach(a => {
      const b = document.createElement('a'); b.href = '#' + a.dataset.k; b.textContent = label(a); if (a.dataset.k === key) { b.className = 'on'; b.setAttribute('aria-current', 'page'); } bar.appendChild(b);
    });
  }

  /* 3) 첫 화면 제목 "Asia Plant Control Center"는 의도된 표기(사용자 2026-11-02)이므로 바꾸지 않는다 */

  /* 4) 같은 줄에 놓인 카드는 아래 끝선을 맞춘다(짧은 카드를 늘림, 내용은 그대로) */
  function eqRows() {
    const v = $1('#view'); if (!v) return;
    v.querySelectorAll('[data-eq]').forEach(c => { c.style.minHeight = ''; delete c.dataset.eq; });
    /* 한 줄(grid·flex)에 나란히 놓인 묶음은 아래 끝선을 맞춘다. 짧은 묶음의 마지막 카드만 늘린다(내용은 그대로).
       위에서 아래로 처리하며 매번 다시 측정한다. 늘린 양이 600px을 넘는 경우는 구조가 다른 것으로 보고 건드리지 않는다 */
    const boxes = [v, ...v.querySelectorAll('*')].filter(e => !e.closest('svg') && e.children.length > 1 && /grid|flex/.test(getComputedStyle(e).display) && e.querySelector('.card'));
    boxes.forEach(box => {
      const kids = [...box.children].map(c => { const b = c.getBoundingClientRect(); return { c, t: Math.round(b.top + scrollY), b: b.bottom + scrollY, w: b.width, h: b.height }; }).filter(x => x.w > 150 && x.h > 40 && (x.c.classList.contains('card') || x.c.querySelector('.card')));
      const rows = []; kids.sort((a, b) => a.t - b.t).forEach(x => { const r = rows.find(r => Math.abs(r[0].t - x.t) <= 3); r ? r.push(x) : rows.push([x]); });
      rows.forEach(r => {
        if (r.length < 2) return; const mx = Math.max(...r.map(x => x.b));
        r.forEach(x => {
          const d = mx - x.b; if (d <= 2 || d >= 600) return;
          const cs = [x.c, ...x.c.querySelectorAll('.card')].filter(c => c.classList.contains('card')); if (!cs.length) return;
          const tgt = cs.reduce((m, c) => (c.getBoundingClientRect().bottom > m.getBoundingClientRect().bottom ? c : m));
          tgt.style.minHeight = Math.ceil(tgt.getBoundingClientRect().height + d) + 'px'; tgt.dataset.eq = '1';
        });
      });
    });
  }

  /* 5) 너무 작은 글자(HTML 텍스트)를 최소 크기로 올린다. SVG 그래프 글자는 그래프 비율에 맡긴다 */
  function fontFloor() {
    const v = $1('#view'); if (!v) return;
    v.querySelectorAll('*').forEach(e => {
      if (e.closest('svg') || e.closest('iframe') || e.dataset.ff) return;
      let own = false; for (const n of e.childNodes) if (n.nodeType === 3 && n.textContent.trim()) { own = true; break; } if (!own) return;
      const s = parseFloat(getComputedStyle(e).fontSize); if (s && s < MIN_FONT) { e.style.fontSize = MIN_FONT + 'px'; e.dataset.ff = '1'; }
    });
  }

  let timer = 0;
  function pass() { [regroup, renderTabs, fontFloor, eqRows].forEach(f => { try { f(); } catch (e) { console.warn('unify', f.name, e && e.message); } }); }
  function later() { clearTimeout(timer); timer = setTimeout(pass, 220); }
  function init() {
    pass();
    window.addEventListener('hashchange', () => { renderTabs(); [400, 1400, 3200, 6000].forEach(ms => setTimeout(pass, ms)); });
    window.addEventListener('resize', later);
    const v = $1('#view'); if (v) { new MutationObserver(later).observe(v, { childList: true, subtree: true }); if (window.ResizeObserver) new ResizeObserver(later).observe(v); }
    const n = $1('#nav'); if (n) new MutationObserver(() => { regroup(); renderTabs(); }).observe(n, { childList: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(later);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else setTimeout(init, 0);
})();
