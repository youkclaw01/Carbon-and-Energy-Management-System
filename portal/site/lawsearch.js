'use strict';
// 지식 검색 — 실연결 화면: Azure AI Search(법령 3국·공장별 5년 모의 이력)를 국가·공장 필터로 검색한다(읽기 전용).
// 기존 샘플 대화는 "예시 대화(시안)"으로 남기고, 처음 열면 실제 검색을 보여 준다. 법령 사본은 검색용이며 정본은 공식 사이트(출처 링크).
(function () {
  if (typeof V === 'undefined' || !V.know) return;
  const orig = V.know; S.lsMode = S.lsMode || 'real'; S.lsF = S.lsF || 'all'; S.lsQ = S.lsQ || ''; S.lsR = S.lsR || null;
  const F = [['all', '전체', ''], ['kr', '한국 법령', 'docType=law&country=KR'], ['jp', '일본 법령', 'docType=law&country=JP'], ['sg', '싱가포르 법령', 'docType=law&country=SG'],
    ['h1', '포항 KR-01 이력', 'docType=history&siteId=KR-01'], ['h2', '기타큐슈 JP-01 이력', 'docType=history&siteId=JP-01'], ['h3', '주롱 SG-01 이력', 'docType=history&siteId=SG-01']];
  const EX = [['배출권 이월 한도', 'kr'], ['排出枠 保有 義務 期限', 'jp'], ['carbon tax ICC offset 5%', 'sg'], ['2024년 배출량과 원단위', 'h1'], ['계획정비 달과 가동률', 'h2']];
  const CN = { KR: '한국', JP: '일본', SG: '싱가포르' };
  const esc = s => String(s == null ? '' : s).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
  async function run(q, key) {
    const f = F.find(x => x[0] === key) || F[0]; const t = sessionStorage.getItem('ama_tok');
    const r = await fetch('/api/agent/knowledge/search?q=' + encodeURIComponent(q) + '&top=8' + (f[2] ? '&' + f[2] : ''), { cache: 'no-store', headers: t ? { Authorization: 'Bearer ' + t } : {} });
    const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.message || ('HTTP ' + r.status)); return d;
  }
  const META = /^(country|language|source|version|retrievedAt|note|siteId|period|dataType|basis):/;
  const clean = t => String(t || '').split('\n').filter(l => !META.test(l.trim())).join(' ').replace(/#{1,6}\s*/g, '').replace(/\*\*/g, '').replace(/\s+/g, ' ').trim();   // 색인 머리말·마크다운 기호는 숨김
  function item(x) {
    const law = x.docType === 'law', tag = law ? (CN[x.country] || x.country || '') + ' 법령' : (x.siteId || '') + ' 모의 이력';
    return h('div', { class: 'ls-it' },
      h('div', { class: 'ls-ith' }, h('span', { class: 'ls-tag ' + (law ? 'law' : 'his') }, tag), h('b', {}, clean(x.section && x.section !== 'null' ? x.section : x.title) || x.source), x.section && x.section !== x.title ? h('span', { class: 'ls-sec' }, clean(x.title)) : null),
      h('p', { class: 'ls-sn' }, clean(x.snippet) || '(머리말 조각입니다 — 아래 근거 파일에서 본문을 확인하세요)'),
      h('div', { class: 'ls-ft' }, h('span', { class: 'mut small' }, '근거 파일 ' + x.source), x.sourceUrl && /^https?:/.test(x.sourceUrl) ? h('a', { href: x.sourceUrl, target: '_blank', rel: 'noopener' }, '공식 원문 열기 ↗') : (law ? null : h('span', { class: 'mut small' }, '모의 데이터(실제 값 아님)'))));
  }
  V.know = () => {
    if (S.lsMode === 'demo') { const n = orig(); const bar = h('div', { class: 'ls-back' }, h('button', { type: 'button', class: 'ks-sb on', 'data-own': 1 }, '← 실제 검색(법령·이력)으로'), h('span', { class: 'mut small' }, '아래는 코드에 적힌 예시 대화(시안)입니다.')); bar.firstChild.addEventListener('click', () => { S.lsMode = 'real'; go(); }); return h('div', {}, bar, n); }
    const input = h('input', { type: 'text', class: 'ls-in', placeholder: '예: 배출권 이월 한도 · 排出枠 保有 義務 · carbon tax ICC', 'aria-label': '검색어', value: S.lsQ, 'data-own': 1 });
    const go_ = h('button', { type: 'button', class: 'lgbtn ls-go', 'data-own': 1 }, '검색'); const out = h('div', { class: 'ls-out', 'aria-live': 'polite' });
    const chips = h('div', { class: 'ls-chips', role: 'group' }, F.map(f => { const b = h('button', { type: 'button', class: 'ks-ic' + (S.lsF === f[0] ? ' on' : ''), 'data-own': 1 }, f[1]); b.addEventListener('click', () => { S.lsF = f[0]; chips.querySelectorAll('button').forEach((x, i) => x.classList.toggle('on', F[i][0] === S.lsF)); if (input.value.trim().length > 1) ask(); }); return b; }));
    const paint = () => { const r = S.lsR; if (!r) { out.replaceChildren(h('div', { class: 'ls-empty' }, h('b', {}, '무엇을 찾으시나요?'), h('p', {}, '법령 조문, 제도 요건, 공장별 월별 배출 이력을 의미(벡터)+키워드로 찾습니다. 아래 예시를 눌러 보세요.'), h('div', { class: 'ls-ex' }, EX.map(e => { const b = h('button', { type: 'button', class: 'ks-ic', 'data-own': 1 }, e[0]); b.addEventListener('click', () => { input.value = e[0]; S.lsF = e[1]; chips.querySelectorAll('button').forEach((x, i) => x.classList.toggle('on', F[i][0] === S.lsF)); ask(); }); return b; })))); return; }
      if (r.err) { out.replaceChildren(h('div', { class: 'ls-empty' }, h('b', {}, '검색을 완료하지 못했습니다'), h('p', {}, r.err + ' — 잠시 뒤 다시 시도해 주세요. (값을 지어내지 않습니다)'))); return; }
      if (!r.items.length) { out.replaceChildren(h('div', { class: 'ls-empty' }, h('b', {}, '일치하는 근거가 없습니다'), h('p', {}, '다른 표현으로 검색하거나 "전체"로 범위를 넓혀 보세요. 근거가 없으면 답을 만들지 않습니다.'))); return; }
      out.replaceChildren(h('p', { class: 'mut small' }, `“${esc(r.query)}” · ${r.items.length}건 · ${r.vector ? '의미(벡터)+키워드+재순위' : '키워드+재순위(벡터 사용 불가: ' + (r.vectorError || '') + ')'}`), ...r.items.map(item)); };
    async function ask() { const q = input.value.trim(); if (q.length < 2) return; S.lsQ = q; out.replaceChildren(h('p', { class: 'mut' }, '검색 중…')); try { const d = await run(q, S.lsF); S.lsR = d; } catch (e) { S.lsR = { err: e.message || '오류' }; } paint(); }
    go_.addEventListener('click', ask); input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) ask(); }); paint();
    const side = h('div', { class: 'ls-side' },
      card('검색 범위', '실연결', h('div', {}, h('p', { class: 'small' }, '법령 원문 사본과 공장 이력은 Azure AI Search에 들어 있습니다(읽기 전용).'),
        h('ul', { class: 'ls-ul' }, h('li', {}, '한국: 배출권거래법 전문(2026-04-29 시행), 거래 규칙 확인본'), h('li', {}, '일본: GX推進法 전문(2026-04-01 시행), 経産省 제도 개요·가격 범위'), h('li', {}, '싱가포르: NEA 탄소세·ICC 안내(v1.2). Carbon Pricing Act는 앞부분 일부만(제1~5부)'), h('li', {}, '공장 이력: 포항·기타큐슈·주롱 2021-11~2026-10 월별(모의)')),
        h('p', { class: 'mut small' }, '법령 사본은 검색용입니다. 법적 판단은 “공식 원문 열기” 링크의 정본과 최신 개정으로 확인하세요.'))),
      card('예시 대화', '시안', h('div', {}, h('p', { class: 'small' }, '기존 질의응답 화면은 샘플 문서로 동작하는 예시입니다.'), (() => { const b = h('button', { type: 'button', class: 'ks-sb', 'data-own': 1 }, '예시 대화(시안) 보기'); b.addEventListener('click', () => { S.lsMode = 'demo'; go(); }); return b; })())));
    return h('div', { class: 'ls-grid' }, card('법령·이력 검색', '실연결', h('div', {}, h('div', { class: 'ls-bar' }, input, go_), chips, out)), side);
  };
})();
