// 계정 메뉴(2026-10-31): 포털 안에서 실제 계정(로그인·MFA·지문·내 정보)과 관리자 계정 관리 화면을 연다. 실제 로그인 세션이 있으면 모의 역할 로그인을 건너뛰고 등급에 맞는 역할로 표시한다.
(function () {
  const B = '/api/approval/v1', GRADE_ROLE = { admin: '관리자', approver: '승인자', operator: '관제 담당', viewer: '감사' }; let ME = null;
  TITLES.account = '계정'; TITLES.users = '계정 관리'; TITLES.topo = 'Azure 리소스 구성도';
  const frame = src => h('div', { class: 'view', style: 'padding:0' }, h('iframe', { src, title: TITLES[src.indexOf('users') > -1 ? 'users' : 'account'], style: 'display:block;width:100%;height:calc(100vh - 150px);min-height:620px;border:0;background:transparent;color-scheme:normal', allow: 'fullscreen', allowfullscreen: '' }));
  V.account = () => frame('/account.html?v=6.9'); V.users = () => frame('/users.html?v=7.3'); V.topo = () => frame('/topo/');
  const base = window.AUTHZ; window.AUTHZ = k => k === 'account' ? true : (k === 'users' || k === 'topo') ? !!(ME && ME.grants.includes('admin')) : base(k);
  [['account', '계정', '&#128100;'], ['users', '계정 관리', '&#128101;'], ['topo', '리소스 구성도', '&#128506;']].forEach(([k, t, i]) => { MENUS.push([k, t, i]); $('#nav').append(h('a', { href: '#' + k, 'data-k': k, id: 'nav-' + k, html: `<span class="ni">${ico(i)}</span><span>${t}</span>` })); });
  const usersNav = $('#nav-users'), topoNav = $('#nav-topo'); if (usersNav) usersNav.style.display = 'none'; if (topoNav) topoNav.style.display = 'none';
  function chipMenu(anchor, adm) {
    const old = document.getElementById('rolemenu'); if (old) { old.remove(); return; }
    const r = anchor.getBoundingClientRect(), box = h('div', { id: 'rolemenu', role: 'menu', style: `position:fixed;z-index:90;top:${Math.round(r.bottom + 6)}px;right:${Math.max(8, Math.round(innerWidth - r.right))}px;min-width:190px;background:var(--card1,#fff);color:var(--txt);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:6px;display:flex;flex-direction:column;gap:4px` }), close = () => { box.remove(); document.removeEventListener('click', close); };
    const item = (t, fn, sel) => { const b = h('button', { type: 'button', role: 'menuitem', 'data-own': 1, style: 'text-align:left;border:0;background:' + (sel ? 'var(--cy)' : 'transparent') + ';color:' + (sel ? 'var(--bg)' : 'var(--txt)') + ';padding:8px 10px;border-radius:8px;width:100%' }, t); b.addEventListener('click', ev => { ev.stopPropagation(); close(); fn(); }); return b; };
    if (adm) { box.append(h('div', { class: 'mut', style: 'font-size:11px;padding:2px 10px' }, '역할 전환(관리자)')); Object.keys(ROLES).forEach(k => box.append(item((k === S.role ? '✓ ' : '') + k, () => { sessionStorage.setItem('ama-role-sel', k); S.role = k; sessionStorage.setItem('ama-role', k); applyRole(); anchor.textContent = ME.username + ' · ' + k; if (!AUTHZ((location.hash || '#overview').slice(1))) location.hash = '#overview'; go(true); }, k === S.role))); }
    box.append(item('계정 설정', () => { location.hash = '#account'; }), item('로그아웃', async () => { try { await fetch(B + '/auth/logout', { method: 'POST', headers: { Authorization: 'Bearer ' + sessionStorage.getItem('ama_tok') } }); } catch (e) {} sessionStorage.removeItem('ama_tok'); sessionStorage.removeItem('ama-role'); sync(); }));
    document.body.append(box); setTimeout(() => document.addEventListener('click', close), 0);
  }
  async function sync() {
    const t = sessionStorage.getItem('ama_tok'); ME = null; window.AMA_ME = null;
    if (t) { try { const r = await fetch(B + '/auth/me', { headers: { Authorization: 'Bearer ' + t }, cache: 'no-store' }); if (r.ok) ME = await r.json(); else sessionStorage.removeItem('ama_tok'); window.AMA_ME = ME; } catch (e) {} }
    if (usersNav) usersNav.style.display = ME && ME.grants.includes('admin') ? '' : 'none'; if (topoNav) topoNav.style.display = ME && ME.grants.includes('admin') ? '' : 'none';
    const rc = $('#rolechip');
    if (!ME) { S.role = null; sessionStorage.removeItem('ama-role'); applyRole(); showLogin(); }
    if (ME) {
      const adm = ME.grants.includes('admin'), sel = sessionStorage.getItem('ama-role-sel'); S.role = adm ? (ROLES[sel] ? sel : '관리자') : (GRADE_ROLE[ME.grade] || '감사'); sessionStorage.setItem('ama-role', S.role); const lg = $('#login'); if (lg) lg.remove(); applyRole();
      if (rc) { const n = rc.cloneNode(true); rc.replaceWith(n); n.textContent = ME.username + ' · ' + S.role; n.title = adm ? '역할 전환 · 계정' : '계정'; n.addEventListener('click', ev => { ev.stopPropagation(); chipMenu(n, adm); }); }
    }
    go(true);
  }
  window.addEventListener('message', e => { if (e.origin === location.origin && e.data === 'ama-auth') sync(); });
  sync();
})();
