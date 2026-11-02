'use strict';
// 화면 스킨: 하나의 규격(스펙)에서 CSS 변수 전체를 계산해 적용합니다. <head>에서 동기 실행해 깜빡임을 막습니다.
(function () {
  const hex = c => { c = c.replace('#', ''); if (c.length === 3) c = c.split('').map(x => x + x).join(''); return [0, 2, 4].map(i => parseInt(c.substr(i, 2), 16)); };
  const toHex = a => '#' + a.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
  const mix = (a, b, t) => { const x = hex(a), y = hex(b); return toHex(x.map((v, i) => v * (1 - t) + y[i] * t)); };
  const wl = c => { const [r, g, b] = hex(c).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
  const cr = (a, b) => { const x = wl(a), y = wl(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const onColor = bg => cr(bg, '#ffffff') >= cr(bg, '#10141c') ? '#ffffff' : '#10141c';   // 채운 색 위 글자: 흰색·짙은색 중 대비가 큰 쪽
  // id, 이름, 계열, 설명, 색 규격
  const SKINS = [
    { id: 'maison', n: '메종', m: 'dark', d: 'v2 기본. 따뜻한 그레이지(웜 그래파이트) 바탕과 샴페인 골드, 원색을 쓰지 않는 고급 톤.', s: { bg: '#2a2723', sf: '#37332d', ln: '#544d42', tx: '#f6f1e6', mu: '#b0a797', ac: '#dcc08a', ok: '#8fc4af', wn: '#e5a766', bd: '#d57d89', pu: '#b3a6d0' }, x: { '--seaA': '#3b362e', '--seaB': '#2a2722', '--seaGrid': '#d9bf8a14', '--lndA': '#4d463b', '--lndB': '#3f392f', '--lndLine': '#d9bf8a80', '--glow': '#d9bf8a33' } },
    { id: 'ivory', n: '아이보리', m: 'light', d: 'v2 밝은 톤. 아이보리 종이 질감과 청동 포인트.', s: { bg: '#f4efe6', sf: '#fffdf8', ln: '#e4dccd', tx: '#211d17', mu: '#7b7264', ac: '#9a7b3f', ok: '#4f8a76', wn: '#b9873a', bd: '#b8604f', pu: '#7a6b9a' }, x: { '--seaA': '#efe8d8', '--seaB': '#e3dac6', '--seaGrid': '#9a7b3f14', '--lndA': '#fbf8f0', '--lndB': '#efe8d8', '--lndLine': '#bfae8a', '--glow': '#9a7b3f30' } },
    { id: 'cloudwhite', n: '클라우드 화이트', m: 'light', d: 'v2 밝은 톤. 구름처럼 은은한 청회색 흰색과 슬레이트 포인트.', s: { bg: '#eceff3', sf: '#fafbfc', ln: '#d9dee5', tx: '#1d2530', mu: '#667384', ac: '#5c7089', ok: '#53917f', wn: '#b8854d', bd: '#b2616c', pu: '#7d7699' }, x: { '--seaA': '#e2e8ef', '--seaB': '#d4dce6', '--seaGrid': '#5c708914', '--lndA': '#f7f9fb', '--lndB': '#e9eef3', '--lndLine': '#a9b6c6', '--glow': '#5c708930' } },
    { id: 'pearl', n: '펄 화이트', m: 'light', d: 'v2 밝은 톤. 진주빛 라일락 회백색과 모브 포인트.', s: { bg: '#efedf0', sf: '#fcfbfc', ln: '#dedbe3', tx: '#241f2b', mu: '#74707f', ac: '#75688f', ok: '#58968a', wn: '#b98a55', bd: '#b0626f', pu: '#8a79a8' }, x: { '--seaA': '#e6e2ea', '--seaB': '#d9d4e0', '--seaGrid': '#75688f14', '--lndA': '#f9f8fa', '--lndB': '#ece9f0', '--lndLine': '#b6aec8', '--glow': '#75688f30' } },
    { id: 'mist', n: '미스트 그린', m: 'light', d: 'v2 밝은 톤. 안개 낀 아침 같은 세이지 흰색.', s: { bg: '#ecf0ed', sf: '#f9fbf9', ln: '#d6dfd8', tx: '#1d2a23', mu: '#64756a', ac: '#5b8270', ok: '#4f8f78', wn: '#b8884a', bd: '#b2646a', pu: '#7a7a9c' }, x: { '--seaA': '#e0e8e2', '--seaB': '#d0dcd4', '--seaGrid': '#5b827014', '--lndA': '#f6f9f6', '--lndB': '#e7eee9', '--lndLine': '#a6b9ac', '--glow': '#5b827030' } },
    { id: 'porcelain', n: '포슬린 블루', m: 'light', d: 'v2 밝은 톤. 도자기처럼 맑은 회청색 흰색과 더스티 블루 포인트.', s: { bg: '#ebf0f4', sf: '#fafcfd', ln: '#d5dfe7', tx: '#1a2632', mu: '#61758a', ac: '#557996', ok: '#4f9484', wn: '#b78950', bd: '#b0626c', pu: '#7a78a0' }, x: { '--seaA': '#dfe8f0', '--seaB': '#cfdbe6', '--seaGrid': '#55799614', '--lndA': '#f6f9fb', '--lndB': '#e7eef4', '--lndLine': '#a3b6c8', '--glow': '#55799630' } },
    { id: 'blush', n: '블러시 화이트', m: 'light', d: 'v2 밝은 톤. 은은한 장밋빛 흰색과 더스티 로즈 포인트.', s: { bg: '#f3eeef', sf: '#fdfbfb', ln: '#e6dadd', tx: '#2a2024', mu: '#7a6a70', ac: '#9a6677', ok: '#5b9487', wn: '#bb8654', bd: '#b05868', pu: '#8a74a2' }, x: { '--seaA': '#ece2e4', '--seaB': '#e0d3d6', '--seaGrid': '#9a667714', '--lndA': '#fbf7f8', '--lndB': '#f0e7e9', '--lndLine': '#c6aab2', '--glow': '#9a667730' } },
    { id: 'cloud', n: '클라우드', m: 'light', d: '기본 스킨. 흰 배경과 애플 톤의 중립 회색·블루.', s: { bg: '#f5f5f7', sf: '#ffffff', ln: '#e3e3e8', tx: '#1d1d1f', mu: '#6e6e73', ac: '#0071e3', ok: '#2fa84f', wn: '#c77c02', bd: '#d93f35', pu: '#8e5bb5' } },
    { id: 'midnight', n: '미드나이트', m: 'dark', d: '기본 남색 다크. 청록 포인트.', s: { bg: '#06121f', sf: '#0e263c', ln: '#1c3f5c', tx: '#e8f1f8', mu: '#8aa6bd', ac: '#38bdd6', ok: '#34d399', wn: '#fbbf24', bd: '#f87171', pu: '#a78bfa' } },
    { id: 'black', n: '블랙', m: 'dark', d: '애플 다크 톤. 순흑에 가까운 배경과 밝은 블루.', s: { bg: '#000000', sf: '#1d1d1f', ln: '#2f2f33', tx: '#f5f5f7', mu: '#a1a1a6', ac: '#2997ff', ok: '#30d158', wn: '#ff9f0a', bd: '#ff6961', pu: '#bf5af2' } },
    { id: 'graphite', n: '그래파이트', m: 'dark', d: '중립 회색 다크. 인디고 포인트(Linear 스타일).', s: { bg: '#0d0e12', sf: '#16181e', ln: '#272b34', tx: '#e6e8ee', mu: '#8b92a1', ac: '#7c83ff', ok: '#3fcf8e', wn: '#f5b84a', bd: '#f0646b', pu: '#b693ff' } },
    { id: 'forest', n: '포레스트', m: 'dark', d: '깊은 녹색 다크. 에메랄드 포인트(Supabase 스타일).', s: { bg: '#0a1210', sf: '#12201b', ln: '#21403a', tx: '#e5f2ec', mu: '#86a396', ac: '#3ecf8e', ok: '#4ade80', wn: '#e8b84a', bd: '#ef6b6b', pu: '#a78bfa' } },
    { id: 'aurora', n: '오로라', m: 'dark', d: '보랏빛 다크. 바이올렛 포인트(Superhuman 스타일).', s: { bg: '#0e0b1a', sf: '#181330', ln: '#2e2549', tx: '#ece8fb', mu: '#9a90bf', ac: '#a78bfa', ok: '#4ade80', wn: '#fbbf24', bd: '#fb7185', pu: '#f0abfc' } },
    { id: 'indigo', n: '인디고', m: 'light', d: '흰 카드와 인디고 포인트(Stripe 스타일).', s: { bg: '#f6f9fc', sf: '#ffffff', ln: '#e5edf5', tx: '#061b31', mu: '#64748d', ac: '#533afd', ok: '#108c3d', wn: '#9b6829', bd: '#ea2261', pu: '#665efd' } },
    { id: 'sage', n: '세이지', m: 'light', d: '부드러운 연녹색 배경. 친환경 느낌.', s: { bg: '#f1f6ef', sf: '#ffffff', ln: '#d5e3d1', tx: '#14301f', mu: '#5d7566', ac: '#2e8b57', ok: '#2e9e4f', wn: '#c27c0e', bd: '#d0473f', pu: '#7a5cc7' } },
    { id: 'sand', n: '샌드', m: 'light', d: '따뜻한 크림 배경. 테라코타 포인트.', s: { bg: '#f6f1e9', sf: '#fffdf9', ln: '#e6dccb', tx: '#2b2118', mu: '#7a6a58', ac: '#c2410c', ok: '#3f7d3b', wn: '#b7791f', bd: '#c0392b', pu: '#7c5cb0' } },
    { id: 'paper', n: '페이퍼', m: 'light', d: '흑백 미니멀. 최소한의 색(Vercel 스타일).', s: { bg: '#f5f5f5', sf: '#ffffff', ln: '#e2e2e2', tx: '#111111', mu: '#666666', ac: '#222222', ok: '#0f8a43', wn: '#b26a00', bd: '#d92d20', pu: '#6f42c1' } }
  ];
  // 원색 완화: 채도를 낮춰(회색과 혼합) 눈이 편한 톤으로 사용합니다.
  const lum = c => { const [r, g, b] = hex(c); return .3 * r + .59 * g + .11 * b; };
  const soft = (c, k) => { const y = lum(c), g = toHex([y, y, y]); return mix(c, g, k); };
  const KEYS = ['--onac', '--bg', '--txt', '--mut', '--line', '--cy', '--gr', '--yl', '--rd', '--pu', '--dl', '--side1', '--side2', '--navhov', '--navon1', '--navon2', '--navonb', '--navons', '--card1', '--card2', '--row', '--item', '--btn', '--btnh', '--btnb', '--btntxt', '--sel', '--nt-bg', '--nt-b', '--nt-t', '--bok', '--bwn', '--ber', '--bin', '--bdr', '--map1', '--map2', '--grid', '--tile', '--tileb', '--tt', '--dotb', '--glow', '--shadow', '--seaA', '--seaB', '--seaGrid', '--lndA', '--lndB', '--lndLine', '--c6', '--c7', '--c8'];
  function vars(sk) {
    const s0 = sk.s, L = sk.m === 'light', v = {}; const s = Object.assign({}, s0, L ? { ac: soft(s0.ac, .1), ok: soft(s0.ok, .3), wn: soft(s0.wn, .3), bd: soft(s0.bd, .3), pu: soft(s0.pu, .3) } : { ac: soft(s0.ac, .24), ok: soft(s0.ok, .4), wn: soft(s0.wn, .4), bd: soft(s0.bd, .4), pu: soft(s0.pu, .4) });
    v['--c6'] = L ? '#5f87bb' : '#7a9fd0'; v['--c7'] = L ? '#b0698f' : '#cc8aae'; v['--c8'] = L ? '#c28350' : '#d6a070';
    v['--bg'] = s.bg; v['--txt'] = s.tx; v['--mut'] = s.mu; v['--line'] = s.ln; v['--cy'] = s.ac; v['--gr'] = s.ok; v['--yl'] = s.wn; v['--rd'] = s.bd; v['--pu'] = s.pu; v['--dl'] = mix(s.mu, s.bg, .25);
    v['--dotb'] = '#ffffff'; v['--onac'] = onColor(s.ac); v['--glow'] = s.ac + '33'; v['--card1'] = s.sf;
    if (L) {
      v['--card2'] = mix(s.sf, s.bg, .4); v['--row'] = mix(s.bg, s.ln, .5); v['--item'] = mix(s.sf, s.bg, .55); v['--side1'] = s.sf; v['--side2'] = mix(s.sf, s.bg, .5); v['--navhov'] = mix(s.bg, s.sf, .35);
      v['--navon1'] = mix(s.sf, s.ac, .1); v['--navon2'] = mix(s.sf, s.ac, .18); v['--navonb'] = mix(s.ln, s.ac, .5); v['--navons'] = mix(s.ln, s.ac, .25);
      v['--btn'] = s.ac; v['--btnh'] = mix(s.ac, '#000000', .18); v['--btnb'] = s.ac; v['--btntxt'] = onColor(s.ac); v['--sel'] = s.sf;
      v['--nt-bg'] = mix(s.sf, s.bd, .08); v['--nt-b'] = mix(s.ln, s.bd, .6); v['--nt-t'] = mix(s.bd, '#000000', .25);
      v['--bok'] = mix(s.sf, s.ok, .16); v['--bwn'] = mix(s.sf, s.wn, .18); v['--ber'] = mix(s.sf, s.bd, .14); v['--bin'] = mix(s.sf, s.ac, .12); v['--bdr'] = mix(s.sf, s.pu, .14);
      v['--map1'] = mix(s.sf, s.ac, .1); v['--map2'] = s.bg; v['--grid'] = s.ln; v['--tile'] = s.sf; v['--tileb'] = mix(s.ln, s.ac, .5); v['--tt'] = s.tx;
      v['--shadow'] = '0 1px 2px #0f172a0f,0 8px 24px #0f172a10';
      v['--seaA'] = mix('#ffffff', s.ac, .07); v['--seaB'] = mix('#ffffff', s.ac, .15); v['--seaGrid'] = '#ffffff90'; v['--lndA'] = '#f6f4ec'; v['--lndB'] = '#e7e3d6'; v['--lndLine'] = '#b9b29c';
    } else {
      v['--card2'] = mix(s.sf, s.bg, .45); v['--row'] = mix(s.sf, s.ln, .5); v['--item'] = mix(s.bg, s.sf, .6); v['--side1'] = mix(s.bg, s.sf, .35); v['--side2'] = s.bg; v['--navhov'] = mix(s.bg, s.sf, .8);
      v['--navon1'] = mix(s.sf, s.ac, .22); v['--navon2'] = mix(s.sf, s.ac, .12); v['--navonb'] = mix(s.ln, s.ac, .55); v['--navons'] = mix(s.ln, s.ac, .3);
      v['--btn'] = mix(s.sf, s.ac, .26); v['--btnh'] = mix(s.sf, s.ac, .4); v['--btnb'] = mix(s.ln, s.ac, .5); v['--btntxt'] = s.tx; v['--sel'] = mix(s.bg, s.sf, .5);
      v['--nt-bg'] = mix(s.bg, s.bd, .14); v['--nt-b'] = mix(s.ln, s.bd, .6); v['--nt-t'] = mix(s.tx, s.bd, .45);
      v['--bok'] = mix(s.sf, s.ok, .22); v['--bwn'] = mix(s.sf, s.wn, .22); v['--ber'] = mix(s.sf, s.bd, .22); v['--bin'] = mix(s.sf, s.ac, .2); v['--bdr'] = mix(s.sf, s.pu, .22);
      v['--map1'] = mix(s.sf, s.ac, .15); v['--map2'] = s.bg; v['--grid'] = mix(s.sf, s.ln, .7); v['--tile'] = mix(s.sf, s.ac, .1); v['--tileb'] = mix(s.ln, s.ac, .5); v['--tt'] = mix(s.tx, s.ac, .12);
      v['--shadow'] = '0 1px 2px #00000055,0 8px 22px #00000040';
      v['--seaA'] = mix(s.bg, s.ac, .26); v['--seaB'] = mix(s.bg, '#000000', .1); v['--seaGrid'] = '#ffffff10'; v['--lndA'] = mix(s.sf, s.ok, .32); v['--lndB'] = mix(s.bg, s.ok, .2); v['--lndLine'] = mix(s.ln, s.ok, .5) + '99';
    }
    return v;
  }
  const root = document.documentElement, LS = (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }, SS = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const norm = id => ({ light: 'cloud', dark: 'midnight' }[id] || id);
  function apply(id) {
    id = norm(id); const sk = SKINS.find(x => x.id === id) || SKINS.find(x => x.id === 'cloudwhite');
    KEYS.forEach(k => root.style.removeProperty(k)); SKINS.forEach(z => Object.keys(z.x || {}).forEach(k => root.style.removeProperty(k)));
    { const v = vars(sk); KEYS.forEach(k => root.style.setProperty(k, v[k])); Object.keys(sk.x || {}).forEach(k => root.style.setProperty(k, sk.x[k])); }
    root.setAttribute('data-theme', sk.id); root.setAttribute('data-mode', sk.m); root.style.colorScheme = sk.m;
    SS('ama-skin-v4', sk.id); try { window.dispatchEvent(new CustomEvent('skinchange', { detail: sk.id })); } catch (e) {} return sk;
  }
  function radius(r) { const m = { sharp: '6px', normal: '12px', round: '18px' }; root.style.setProperty('--rad', m[r] || m.normal); SS('ama-radius', r || 'normal'); }
  function motion(on) { root.classList.toggle('nomotion', !on); SS('ama-motion', on ? 'on' : 'off'); }
  const q = new URLSearchParams(location.search);
  window.SKINS = { list: SKINS, vars, contrast: cr, apply, radius, motion, current: () => norm(LS('ama-skin-v4', 'cloudwhite')), get: id => SKINS.find(x => x.id === norm(id)) || SKINS.find(x => x.id === 'cloudwhite') };
  apply(q.get('theme') || q.get('skin') || LS('ama-skin-v4', 'cloudwhite')); radius(LS('ama-radius', 'round')); motion(LS('ama-motion', 'on') !== 'off');
})();
