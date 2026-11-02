'use strict';
// 겹침 방지: 표시 우선순위가 낮은 SVG 글자(.dc, 지도의 나라·바다 이름)가 다른 글자·상자·점·선과 겹치면 숨깁니다(툴팁은 유지).
(function () {
  const R = e => e.getBoundingClientRect(), hit = (a, b, m) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > m && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > m;
  function run() {
    document.querySelectorAll('#view svg').forEach(svg => {
      svg.querySelectorAll('.ctitle').forEach(t => { const g = t.parentNode, s = g && g.querySelector('.csum'); if (!s) return; if (!t.dataset.fs0) t.dataset.fs0 = t.getAttribute('font-size'); let fs = +t.dataset.fs0; t.setAttribute('font-size', fs); for (let k = 0; k < 10 && hit(R(t), R(s), -3) && fs > 9; k++) { fs -= 1; t.setAttribute('font-size', fs); }
      if (!s.dataset.fs0) s.dataset.fs0 = s.getAttribute('font-size'); let sf = +s.dataset.fs0; s.setAttribute('font-size', sf); for (let k = 0; k < 6 && hit(R(t), R(s), -3) && sf > 9; k++) { sf -= 1; s.setAttribute('font-size', sf); }
      if (hit(R(t), R(s), -3) && /\s(plants?|개)$/i.test(t.textContent)) { t.textContent = t.textContent.replace(/\s(plants?|개)$/i, ''); t.setAttribute('font-size', t.dataset.fs0); for (let k = 0; k < 10 && hit(R(t), R(s), -3) && +t.getAttribute('font-size') > 9; k++) t.setAttribute('font-size', +t.getAttribute('font-size') - 1); } });
      const hide = [...svg.querySelectorAll('text.dc, text.mlab')]; if (!hide.length) return;
      hide.forEach(t => { t.style.visibility = ''; });
      const fixed = [...svg.querySelectorAll('text')].filter(t => !hide.includes(t) && t.textContent.trim() && getComputedStyle(t).visibility !== 'hidden').map(R);
      svg.querySelectorAll('.cbox,.anc,circle').forEach(e => { if (!e.closest('text')) fixed.push(R(e)); });
      const lines = [...svg.querySelectorAll('.lead')].map(e => { const r = R(e); return r; });
      const acc = [];
      hide.forEach(t => { const r = R(t); if (r.width < 1) return; const bad = fixed.some(f => f.width > 0 && hit(r, f, 1)) || acc.some(a => hit(r, a, 1)) || lines.some(l => hit(r, l, 1) && lineCross(svg, t)); if (bad) t.style.visibility = 'hidden'; else acc.push(r); });
    });
  }
  // 지도 지시선(lead)과 글자 교차: 선 양끝 좌표로 정확히 판정
  function lineCross(svg, t) {
    const r = R(t), m = svg.getScreenCTM(); if (!m) return false;
    return [...svg.querySelectorAll('.lead')].some(l => { const a = [+l.getAttribute('x1'), +l.getAttribute('y1')], c = [+l.getAttribute('x2'), +l.getAttribute('y2')]; for (let k = 0; k <= 30; k++) { const x = a[0] + (c[0] - a[0]) * k / 30, y = a[1] + (c[1] - a[1]) * k / 30, X = m.a * x + m.c * y + m.e, Y = m.b * x + m.d * y + m.f; if (X > r.left && X < r.right && Y > r.top && Y < r.bottom) return true; } return false; });
  }
  let raf = 0; const sched = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => { try { run(); } catch (e) {} }); };
  const v = document.getElementById('view'); if (v) new MutationObserver(sched).observe(v, { childList: true, subtree: true, characterData: true });
  window.addEventListener('resize', sched); [300, 900].forEach(ms => setTimeout(sched, ms)); window.declutter = run;
})();
