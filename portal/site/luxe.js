'use strict';
// v2 디자인 보조: 스킨 표식, 순차 등장 지연값, 명령 팔레트(Ctrl/⌘+K), 레일 메뉴 포커스 정리.
(function () {
  const root = document.documentElement;
  const LUX = ['maison', 'ivory', 'cloudwhite', 'pearl', 'mist', 'porcelain', 'blush'];
  const mark = () => root.toggleAttribute('data-lux', true); // 모든 스킨이 같은 v2 화면을 쓰고 색만 바뀝니다.
  mark(); window.addEventListener('skinchange', mark);
  const T = (ko, en) => (window.I18N && I18N.lang === 'en') ? en : ko;

  // ── 순차 등장: 각 행·카드에 순번(--i) 부여 ──
  let raf = 0;
  function stagger() {
    raf = 0; const v = document.getElementById('view'); if (!v) return;
    const give = p => [...p.children].forEach((c, i) => c.style.setProperty('--i', Math.min(i, 9)));
    give(v); v.querySelectorAll('.row,.kxrow').forEach(give); strip(); insights(); chksum();
  }
  // 지도 아래 국가별 요약 띠: 지도를 키우지 않고 빈 공간을 정보로 채웁니다.
  function strip() {
    if (typeof D === 'undefined' || typeof S === 'undefined') return;
    document.querySelectorAll('.row.r21>.card:first-child').forEach(card => {
      const mb = card.querySelector(':scope>.mapbox'); if (!mb || card.querySelector('.cstrip')) return;
      const wrap = document.createElement('div'); wrap.className = 'cstrip';
      ['한국', '일본', '싱가포르'].forEach(n => {
        const ids = D.P.filter(p => p.c === n).map(p => p.id); if (!ids.length) return;
        const em = ids.reduce((s, i) => s + D.em(i, S.a, S.b), 0), tg = ids.reduce((s, i) => s + D.target(i, S.a, S.b, 'em'), 0), u = tg ? em / tg : 0;
        const d = document.createElement('div'); d.className = 'cs'; d.innerHTML = '<span class="cn"></span><b class="cv"></b><span class="cu"></span><i class="cb"><u></u></i>';
        d.querySelector('.cn').textContent = n; d.querySelector('.cv').textContent = em.toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' tCO\u2082';
        d.querySelector('.cu').textContent = T('목표 대비 ', 'of target ') + Math.round(u * 100) + '%';
        const bar = d.querySelector('u'); bar.style.width = Math.min(100, u * 100) + '%'; try { bar.style.background = SC[D.lvl(u)]; } catch (e) { }
        try {
          const T0 = D.TODAY, vals = []; for (let a = 0; a <= T0; a += 30) vals.push(ids.reduce((s, i) => s + D.em(i, a, Math.min(T0, a + 29)), 0));
          if (vals.length > 2) {
            const mx = Math.max(...vals) * 1.1, mn = Math.min(...vals) * .85, X = i => (i / (vals.length - 1)) * 100, Y = v => 30 - ((v - mn) / (mx - mn || 1)) * 28 - 1;
            const pts = vals.map((v, i) => X(i).toFixed(1) + ',' + Y(v).toFixed(1)).join(' ');
            const sp = document.createElement('div'); sp.className = 'csp';
            sp.innerHTML = '<svg viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true"><polygon points="0,30 ' + pts + ' 100,30"/><polyline points="' + pts + '"/></svg><span>' + T('월별 배출 추이', 'Monthly emissions') + '</span>';
            d.append(sp);
          }
        } catch (e) { }
        wrap.append(d);
      });
      mb.after(wrap);
      // 국가 요약 아래 남는 공간: 목표 대비 사용률이 높은 공장을 골라 이유와 함께 보여 주고, 누르면 그 공장 화면으로 갑니다.
      try {
        const top = D.P.map(p => ({ p, s: D.status(p.id, S.a, S.b, 'em') })).sort((a, b) => b.s.usage - a.s.usage).slice(0, 4);
        const cw = document.createElement('div'); cw.className = 'cwatch';
        const hd = document.createElement('div'); hd.className = 'cw-h'; hd.innerHTML = '<b></b><span></span>'; hd.querySelector('b').textContent = T('주목할 공장', 'Plants to watch'); hd.querySelector('span').textContent = T('목표 대비 사용률이 높은 순 · 누르면 공장 화면', 'By usage vs target · click to open the plant');
        const g = document.createElement('div'); g.className = 'cw-g';
        top.forEach(({ p, s: st }) => {
          const col = (() => { try { return SC[D.lvl(st.usage)]; } catch (e) { return 'var(--cy)'; } })(), b = document.createElement('button'); b.type = 'button'; b.className = 'cw'; b.dataset.own = 1;
          const mom = st.mom == null ? '' : (st.mom > 0 ? '+' : '') + (st.mom * 100).toFixed(1) + '%', why = (st.why && (st.why[1] || st.why[0])) || '';
          b.innerHTML = '<span class="cw-t"><i></i><b></b><em></em></span><span class="cw-bar"><u></u><s style="left:70%"></s><s style="left:90%"></s></span><span class="cw-m"></span><span class="cw-v"><small></small><b></b><i>tCO\u2082</i></span>';
          b.querySelector('i').style.background = col; b.querySelector('b').textContent = p.id; b.querySelector('em').textContent = Math.round(st.usage * 100) + '%'; b.querySelector('em').style.color = col;
          const u = b.querySelector('u'); u.style.width = Math.min(100, st.usage * 100) + '%'; u.style.background = col;
          b.querySelector('.cw-m').textContent = p.site + (mom ? T(' · 전월 대비 ', ' · MoM ') + mom : '');
          const cur = D.em(p.id, S.a, S.b); b.querySelector('.cw-v small').textContent = T('현재 배출 · 올해 누적', 'Current emissions · YTD'); b.querySelector('.cw-v b').textContent = cur.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
          b.addEventListener('click', () => { S.plant = p.id; location.hash = '#plants'; });
          g.append(b);
        });
        cw.append(hd, g); wrap.after(cw);
      } catch (e) { }
    });
  }

  // 개요 하단 인사이트 행: 프로젝트 목표(탄소·에너지 비용 운영)에 맞춰 연말 전망·주의 공장·AI 브리핑을 보여 줍니다.
  function insights() {
    if (typeof D === 'undefined' || typeof S === 'undefined' || !window.ReportModel) return;
    const main = document.querySelector('#view .row.r21.main'); if (!main || main.nextElementSibling && main.nextElementSibling.classList.contains('ins')) return;
    let k; try { k = ReportModel.krCalc(); } catch (e) { return; }
    const f0 = v => Math.round(v).toLocaleString('en-US'), sg = v => v > 0 ? '+' : v < 0 ? '\u2212' : '';
    const card = (title, tag) => { const c = document.createElement('div'); c.className = 'card insc'; const h = document.createElement('h3'); h.textContent = title; if (tag) { const t = document.createElement('span'); t.className = 'tag'; t.textContent = tag; h.append(' ', t); } c.append(h); return c; };
    const row = document.createElement('div'); row.className = 'row r3 ins';
    // 1) 연말 전망(한국)
    const c1 = card(T('연말 배출권 전망 · 한국', 'Year-end allowance outlook · Korea'), T('예시', 'Mock'));
    const gp = k.gap.base / k.A, ok = k.gap.base >= k.buf;
    const big = document.createElement('div'); big.className = 'ibig'; big.textContent = sg(k.gap.base) + f0(Math.abs(k.gap.base)); const u = document.createElement('small'); u.textContent = ' tCO\u2082'; big.append(u);
    const sub = document.createElement('div'); sub.className = 'isub'; sub.textContent = T('연간 목표 대비 ', 'of annual target ') + sg(gp) + Math.abs(gp * 100).toFixed(1) + '% \u00b7 ' + (k.gap.base < 0 ? T('부족 예상', 'shortfall expected') : ok ? T('여유 예상', 'surplus expected') : T('여유 부족(안전 여유 미달)', 'below safety margin'));
    c1.append(big, sub);
    [[T('기본(최근 30일 속도)', 'Base (last-30-day pace)'), k.gap.base], [T('배출 +10%', 'Emissions +10%'), k.gap.up], [T('스트레스', 'Stress'), k.gap.stress]].forEach(([n, g]) => {
      const r = document.createElement('div'); r.className = 'li'; const a = document.createElement('span'); a.textContent = n; const b = document.createElement('b'); b.textContent = sg(g) + f0(Math.abs(g)); b.style.color = g < 0 ? 'var(--bd)' : g < k.buf ? 'var(--wn)' : 'var(--ok)'; r.append(a, b); c1.append(r);
    });
    const nt = document.createElement('p'); nt.className = 'inote'; nt.textContent = T('안전 여유 ', 'Safety margin ') + f0(k.buf) + ' tCO\u2082 \u00b7 ' + T('종합 의견은 \u2018산정 결과 \u203a 종합 보고서\u2019', 'full opinion in Calculation \u203a Report'); c1.append(nt);
    // 2) 주의 공장 Top 3
    const c2 = card(T('한도 근접 공장 Top 3', 'Plants closest to limit'), T('올해 누적', 'YTD'));
    D.P.map(p => { const e = D.em(p.id, S.a, S.b), t = D.target(p.id, S.a, S.b, 'em'); return { id: p.id, c: p.c, u: t ? e / t : 0, e, dl: D.delay(p.id) }; }).sort((a, b) => b.u - a.u).slice(0, 3).forEach(p => {
      const r = document.createElement('div'); r.className = 'pf'; r.innerHTML = '<b></b><span></span><i class="cb"><u></u></i><em></em>';
      r.querySelector('b').textContent = p.id; r.querySelector('span').textContent = p.c;
      const bar = r.querySelector('u'); bar.style.width = Math.min(100, p.u * 100) + '%'; try { bar.style.background = SC[D.lvl(p.u)]; } catch (e) { }
      r.querySelector('em').textContent = Math.round(p.u * 100) + '%' + (p.dl > 0 ? ' \u00b7 ' + T('수신 지연', 'late') : ''); c2.append(r);
    });
    const n2 = document.createElement('p'); n2.className = 'inote'; n2.textContent = T('기준: 선택 기간 배출 \u00f7 목표(주의 70% \u00b7 경고 90%). 공장별 상세는 \u2018공장 운영\u2019에서 확인합니다.', 'Basis: period emissions \u00f7 target (watch 70% \u00b7 alert 90%). Per-plant detail is under Plant operations.'); c2.append(n2);
    // 3) AI 브리핑
    const c3 = card(T('오늘의 AI 브리핑', 'Today\u2019s AI briefing'), T('규칙 기반', 'Rule-based'));
    const sh = (k.c.rows || []).slice().sort((a, b) => b.e - a.e)[0];
    const lines = [
      T('확인이 필요한 항목은 \u2018확인 필요\u2019 카드에서 AI와 대화해 원인을 좁히고 담당자 메일까지 작성합니다.', 'Open items on the Needs-review card are narrowed down with AI, up to drafting the owner email.'),
      k.delayed.length ? T('자료 수신이 지연된 한국 공장은 ' + k.delayed.map(r => r.id).join(', ') + ' 입니다. 지연 구간은 추정값이라 산정 신뢰도가 낮아집니다.', 'Delayed Korean plants: ' + k.delayed.map(r => r.id).join(', ') + '. Estimated periods lower confidence.') : T('한국 공장의 자료 수신은 모두 정상입니다.', 'All Korean plants are reporting on time.'),
      sh ? T('가장 큰 배출원은 ' + (sh.n || sh.k) + ' 입니다. 전력·연료 절감과 재생에너지 반영이 가장 큰 비용 절감 레버입니다.', 'The largest source is ' + (({ fix: 'stationary combustion', mob: 'mobile combustion', pwr: 'purchased electricity' })[sh.k] || sh.k) + '. Power and fuel savings plus renewables are the biggest cost levers.') : '',
      T('목표: 탄소 비용 예측 가능성 확보 \u00b7 자료 신뢰도 \u00b7 승인 전 관리자·검수자 확인', 'Goal: predictable carbon cost \u00b7 data trust \u00b7 human check before action')
    ].filter(Boolean);
    lines.forEach(t => { const p = document.createElement('p'); p.className = 'bl'; p.textContent = t; c3.append(p); });
    row.append(c1, c2, c3); main.after(row);
  }

  // ── 작업 일지 화면: 공개 블로그(GitHub Pages)의 최신 글 목록을 보여 줍니다. ──
  const JOURNAL = 'https://github-user.github.io/living-only-for-today/';
  if (typeof V !== 'undefined') V.journal = () => {
    const root = h('div', { class: 'view' });
    const open = h('a', { class: 'jbtn', href: JOURNAL, target: '_blank', rel: 'noopener' }, T('일지 전체 보기 (영문) \u2197', 'Open the full journal \u2197'));
    const list = h('div', { class: 'jlist' }, h('p', { class: 'inote' }, T('최신 글을 불러오는 중…', 'Loading the latest posts…')));
    root.append(h('div', { class: 'row r21' },
      card(T('오늘만 사는 나', 'Living Only for Today'), T('공개 블로그 · 영문', 'Public blog · English'), h('p', { class: 'jlead' }, T('AI 에이전트와 함께 설계하고 만든 과정을 영문 일기로 날짜별 공개합니다. 짧은 일기 \u00b7 변경 내용 \u00b7 개선된 점 \u00b7 이슈 \u00b7 배운 점으로 구성합니다.', 'A public, dated diary of designing and building this system together with an AI agent: summary, changes, improvements, issues and lessons.')), list),
      card(T('공개 원칙', 'Publishing rules'), '', h('p', { class: 'bl' }, T('구독·테넌트 ID, IP, 비밀 값, 내부 증빙 원문은 싣지 않습니다.', 'No subscription/tenant IDs, IPs, secrets or raw internal evidence.')), h('p', { class: 'bl' }, T('화면의 수치는 모의 자료이며 투자 권유가 아닙니다.', 'Figures on screen are mock data, not investment advice.')), open)));
    root.querySelectorAll('.row>.card').forEach(c => c.classList.add('jtop'));
    fetch(JOURNAL + 'feed.json', { cache: 'no-cache' }).then(r => r.json()).then(d => {
      list.replaceChildren(...d.posts.map(p => h('a', { class: 'jitem', translate: 'no', href: p.url, target: '_blank', rel: 'noopener' }, h('span', { class: 'jd' }, p.date.slice(5).replace('-', '.')), h('span', { class: 'jt' }, p.title), h('span', { class: 'js' }, p.summary))));
    }).catch(() => list.replaceChildren(h('p', { class: 'inote' }, T('일지를 불러오지 못했습니다. 위 버튼으로 직접 열어 주세요.', 'Could not load the journal. Use the button to open it directly.'))));
    return root;
  };

  // 확인 필요 카드 하단: 심각도별 개수와 비율 막대로 빈 공간을 채웁니다.
  function chksum() {
    if (typeof openRV === 'undefined' || typeof sevOrd === 'undefined' || typeof stB === 'undefined') return;
    document.querySelectorAll('.row.r21 .col>.card').forEach(card => {
      const h3 = card.querySelector('h3'); if (!h3 || !/확인 필요|Needs review/.test(h3.textContent)) return; card.classList.add('chkc'); if (card.querySelector('.chsum')) return;
      let items = []; try { items = openRV(); } catch (e) { return; } if (!items.length) return;
      const by = {}; items.forEach(r => { by[r.sev] = (by[r.sev] || 0) + 1; });
      const col = { er: 'var(--rd)', wn: 'var(--yl)', dl: 'var(--mut)', ok: 'var(--gr)' };
      const box = document.createElement('div'); box.className = 'chsum';
      const bar = document.createElement('i'); bar.className = 'cbar';
      const leg = document.createElement('div'); leg.className = 'cleg';
      Object.keys(sevOrd).forEach(k => { if (!by[k]) return; const u = document.createElement('u'); u.style.flex = by[k]; u.style.background = col[k]; bar.append(u); const s = document.createElement('span'); s.append(stB(k), ' ' + by[k]); leg.append(s); });
      const first = items.slice().sort((a, b) => sevOrd[a.sev] - sevOrd[b.sev])[0];
      const p = document.createElement('p'); p.className = 'cnext'; p.textContent = T('가장 먼저 볼 항목: ', 'Look at first: ') + first.plant + ' \u00b7 ' + first.type;
      box.append(bar, leg, p); card.append(box);
    });
  }
  function watch() {
    const v = document.getElementById('view'); if (!v) return;
    new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(stagger); }).observe(v, { childList: true, subtree: true });
    stagger();
  }

  // ── 레일 메뉴: 검색 버튼, 클릭 뒤 포커스 해제(자동 접힘) ──
  function rail() {
    const side = document.querySelector('.side'), foot = document.querySelector('.side-foot'); if (!side || side.querySelector('.kbtn')) return;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'kbtn'; b.setAttribute('aria-label', T('메뉴·공장 검색', 'Search menus and plants'));
    b.innerHTML = '<span class="ni"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg></span><span>' + T('검색', 'Search') + '</span><kbd>Ctrl K</kbd>';
    b.addEventListener('click', openKp); side.insertBefore(b, foot);
    document.getElementById('nav').addEventListener('click', () => setTimeout(() => { const a = document.activeElement; if (a && a.blur) a.blur(); }, 0));
  }

  // ── 명령 팔레트 ──
  let kp, input, list, items = [], idx = 0;
  function actions() {
    const A = [];
    (typeof MENUS !== 'undefined' ? MENUS : []).forEach(([k, t]) => A.push({ i: '&#8594;', t, s: T('메뉴', 'Menu'), f: () => { location.hash = '#' + k; } }));
    ((typeof D !== 'undefined' && D.P) || []).forEach(p => A.push({ i: '&#9679;', t: `${p.id} · ${p.site}`, s: T('공장', 'Plant'), f: () => { if (typeof S !== 'undefined') S.plant = p.id; location.hash = '#plants'; if (typeof go === 'function') go(); } }));
    if (window.SKINS) [['cloudwhite', T('화면: 클라우드 화이트', 'Theme: Cloud White')], ['pearl', T('화면: 펄 화이트', 'Theme: Pearl White')], ['mist', T('화면: 미스트 그린', 'Theme: Mist Green')], ['porcelain', T('화면: 포슬린 블루', 'Theme: Porcelain Blue')], ['blush', T('화면: 블러시 화이트', 'Theme: Blush White')], ['maison', T('화면: 메종(어두운 샴페인)', 'Theme: Maison (dark champagne)')], ['ivory', T('화면: 아이보리(밝은 청동)', 'Theme: Ivory (light bronze)')]].forEach(([id, t]) => A.push({ i: '&#9680;', t, s: T('화면', 'Theme'), f: () => SKINS.apply(id) }));
    if (window.I18N) A.push({ i: 'A', t: T('언어 전환: English', 'Language: 한국어'), s: T('언어', 'Language'), f: () => I18N.setLang(I18N.lang === 'en' ? 'ko' : 'en') });
    return A;
  }
  function draw() {
    const q = input.value.trim().toLowerCase(), all = actions();
    items = all.filter(a => !q || (a.t + ' ' + a.s).toLowerCase().includes(q)).slice(0, 40); idx = Math.min(idx, Math.max(0, items.length - 1));
    list.innerHTML = '';
    items.forEach((a, n) => { const d = document.createElement('div'); d.className = 'kp-it' + (n === idx ? ' on' : ''); d.innerHTML = `<i>${a.i}</i><span></span><small>${a.s}</small>`; d.children[1].textContent = a.t; d.addEventListener('click', () => run(n)); d.addEventListener('mousemove', () => { idx = n; [...list.children].forEach((c, k) => c.classList.toggle('on', k === n)); }); list.append(d); });
    if (!items.length) { const d = document.createElement('div'); d.className = 'kp-it'; d.textContent = T('일치하는 항목이 없습니다', 'No matches'); list.append(d); }
  }
  function run(n) { const a = items[n]; if (!a) return; closeKp(); a.f(); }
  function build() {
    kp = document.createElement('div'); kp.className = 'kp'; kp.setAttribute('role', 'dialog'); kp.setAttribute('aria-modal', 'true');
    kp.innerHTML = '<div class="kp-box"><input type="text" autocomplete="off" spellcheck="false"><div class="kp-list"></div><div class="kp-ft"></div></div>';
    input = kp.querySelector('input'); list = kp.querySelector('.kp-list'); kp.querySelector('.kp-ft').textContent = T('↑↓ 이동 · Enter 선택 · Esc 닫기', '↑↓ move · Enter select · Esc close');
    input.placeholder = T('메뉴·공장·화면을 검색하세요', 'Search menus, plants and themes'); document.body.append(kp);
    kp.addEventListener('mousedown', e => { if (e.target === kp) closeKp(); });
    input.addEventListener('input', () => { idx = 0; draw(); });
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { idx = Math.min(items.length - 1, idx + 1); e.preventDefault(); } else if (e.key === 'ArrowUp') { idx = Math.max(0, idx - 1); e.preventDefault(); }
      else if (e.key === 'Enter') { run(idx); return; } else if (e.key === 'Escape') { closeKp(); return; } else return;
      [...list.children].forEach((c, k) => c.classList.toggle('on', k === idx)); const on = list.children[idx]; if (on && on.scrollIntoView) on.scrollIntoView({ block: 'nearest' });
    });
  }
  function openKp() { if (!kp) build(); kp.classList.add('on'); input.value = ''; idx = 0; draw(); setTimeout(() => input.focus(), 30); }
  function closeKp() { if (kp) kp.classList.remove('on'); }
  window.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); kp && kp.classList.contains('on') ? closeKp() : openKp(); }
    else if (e.key === 'Escape') closeKp();
  });
  window.AMA_PALETTE = { open: openKp, close: closeKp };

  function init() { rail(); watch(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

// 지도 틀의 좌우 끝과 아래 국가 카드 줄의 좌우 끝을 맞춥니다.
// 지도(957×605 비율)는 높이에 맞춰 줄어들어 양옆에 빈 바탕이 생기므로, 아래 줄을 조금 낮춰 지도를 키우고 두 영역 폭을 같게 합니다.
(function () {
  let busy = false;
  function alignMap() {
    if (busy) return; busy = true;
    try {
      document.querySelectorAll('.row.r21>.card:first-child').forEach(card => {
        const mb = card.querySelector('.mapbox'), cs = card.querySelector('.cstrip'), sv = mb && mb.querySelector('svg.asia'); if (!mb || !cs || !sv) return;
        [mb, cs].forEach(e => { e.style.width = ''; e.style.marginLeft = e.style.marginRight = ''; }); cs.style.height = ''; mb.style.height = ''; mb.style.aspectRatio = ''; mb.classList.remove('wide'); if (sv.dataset.vb0) sv.setAttribute('viewBox', sv.dataset.vb0); else sv.dataset.vb0 = sv.getAttribute('viewBox');
        if (window.innerWidth <= 1000) return;
        const ch = cs.getBoundingClientRect().height, wc0 = cs.getBoundingClientRect().width, hb0 = mb.getBoundingClientRect().height, take = card.querySelector('.cwatch') ? 0 : Math.min(Math.max(0, ch - 118), Math.max(34, Math.ceil(wc0 * 605 / 957 - hb0))); if (take > 0) cs.style.height = (ch - take) + 'px';
        const wc = cs.getBoundingClientRect().width, hb = mb.getBoundingClientRect().height, w = wc;
        [mb, cs].forEach(e => { e.style.width = w + 'px'; e.style.marginLeft = e.style.marginRight = 'auto'; });
        // 지도 상자를 좌우 끝까지 넓히고, 늘어난 폭만큼 바다 배경을 양옆으로 이어 그린다(지도·말풍선 좌표는 그대로).
        mb.style.height = hb + 'px'; mb.style.aspectRatio = 'auto'; mb.classList.add('wide');
        const VW = sv.viewBox.baseVal.width || 957, VH = sv.viewBox.baseVal.height || 605, X0 = sv.dataset.x0 !== undefined ? +sv.dataset.x0 : sv.viewBox.baseVal.x, want = VH * (w / hb), ex = Math.max(0, (want - VW) / 2);
        sv.dataset.x0 = X0; sv.setAttribute('viewBox', `${X0 - ex} 0 ${VW} ${VH}`.replace(`${VW} ${VH}`, `${want > VW ? want : VW} ${VH}`));
        const sea = sv.querySelector('rect'); if (sea) { sea.setAttribute('x', X0 - ex - 2); sea.setAttribute('width', (want > VW ? want : VW) + 4); }
      });
      document.querySelectorAll('.cwatch').forEach(cw => { cw.classList.remove('thin'); if (cw.getBoundingClientRect().height < 92) cw.classList.add('thin'); });
    } finally { busy = false; }
  }
  const prev = window.afterGo; window.afterGo = function () { if (prev) prev.apply(this, arguments); if (!document.querySelector('.mkcard.aifull')) document.body.classList.remove('mk-ai-open'); requestAnimationFrame(alignMap); setTimeout(alignMap, 220); setTimeout(alignMap, 700); };
  window.addEventListener('resize', () => requestAnimationFrame(alignMap));
})();
// 차트 글자 크기 정돈: viewBox 확대로 글자가 커지는 것을 막아 카드 제목·표와 같은 밀도로 맞춘다(굵은 라벨 ≤11.5px, 보조 ≤10px).
(function () {
  const CAP_B = 11.5, CAP_N = 10;
  function fit() {
    document.querySelectorAll('.view svg[viewBox]').forEach(svg => {
      if (svg.closest('.tw-stage, .mapbox, .mkcard .spark, .nofit') || svg.dataset.fitting) return;
      const vb = svg.viewBox.baseVal; if (!vb || !vb.width) return;
      const r = svg.getBoundingClientRect(); if (!r.width) return;
      const k = Math.min(r.width / vb.width, vb.height ? r.height / vb.height : 9) || r.width / vb.width;
      const sc = (svg.getAttribute('preserveAspectRatio') === 'none') ? r.width / vb.width : k;
      svg.querySelectorAll('text').forEach(t => {
        if (t.dataset.fs0 === undefined) t.dataset.fs0 = parseFloat(t.getAttribute('font-size') || getComputedStyle(t).fontSize) || 11;
        const s0 = +t.dataset.fs0, bold = /700|600|bold/.test(t.getAttribute('font-weight') || getComputedStyle(t).fontWeight);
        const cap = bold ? CAP_B : CAP_N, px = s0 * sc;
        if (px > cap) t.style.fontSize = (cap / sc).toFixed(2) + 'px'; else t.style.fontSize = '';
      });
    });
  }
  let q = 0; const go = () => { cancelAnimationFrame(q); q = requestAnimationFrame(fit); };
  const prev = window.afterGo; window.afterGo = function () { if (prev) prev.apply(this, arguments); go(); setTimeout(fit, 250); setTimeout(fit, 800); };
  window.addEventListener('resize', go);
  const v = document.getElementById('view'); if (v) new MutationObserver(go).observe(v, { childList: true, subtree: true });
  window.__fitText = fit;
})();
// 오늘 누적 배출 카드: 옆 카드 높이에 맞춰 차트를 다시 그려 빈 공간을 없앤다.
(function () {
  function tdFit() {
    document.querySelectorAll('.view .tdr').forEach(c => { if (!c._re || c.dataset.fitBusy) return;
    const r = c.getBoundingClientRect(); if (!r.height) return; let mb = r.top;
    c.querySelectorAll('*').forEach(e => { const q = e.getBoundingClientRect(); if (q.height > 0 && q.bottom > mb && q.bottom < r.bottom + 2) mb = q.bottom; });
    const gap = r.bottom - mb - 18, svg = c.querySelector('.tdc svg'); if (gap < 24 || !svg) return;
    const vb = svg.viewBox.baseVal, s = svg.getBoundingClientRect().width / vb.width; if (!s) return;
    c.dataset.fitBusy = 1; c._re(Math.round(vb.height + gap / s)); setTimeout(() => { delete c.dataset.fitBusy; if (window.__fitText) window.__fitText(); }, 60); });
  }
  const prev = window.afterGo; window.afterGo = function () { if (prev) prev.apply(this, arguments); setTimeout(tdFit, 300); setTimeout(tdFit, 900); };
  window.addEventListener('resize', () => setTimeout(tdFit, 200));
})();
