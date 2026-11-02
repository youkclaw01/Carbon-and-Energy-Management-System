'use strict';
// 보고서 생성기: 현재 화면의 모의 자료로 Word(.docx)·PowerPoint(.pptx) 파일을 브라우저에서 직접 만듭니다(서버·외부 라이브러리 없음).
(function () {
  const enc = new TextEncoder();
  const T = (ko, en) => window.I18N && I18N.lang === 'en' ? en : ko;
  const esc = s => (window.I18N && I18N.lang === 'en' ? I18N.tr(String(s == null ? '' : s)) : String(s == null ? '' : s)).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const n0 = v => Math.round(v).toLocaleString('en-US'), n1 = v => (+v).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }), n2 = v => (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const sumA2 = a => a.reduce((s, v) => s + v, 0);

  // ── ZIP(무압축) ────────────────────────────────────────────────
  const crcT = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = u => { let c = 0xFFFFFFFF; for (let i = 0; i < u.length; i++) c = crcT[(c ^ u[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function zip(files, mime) {
    const u16 = v => [v & 255, (v >>> 8) & 255], u32 = v => [v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255];
    const out = [], cd = []; let off = 0;
    files.forEach(f => {
      const nm = enc.encode(f.name), data = typeof f.data === 'string' ? enc.encode(f.data) : f.data, crc = crc32(data), sz = data.length;
      const lh = new Uint8Array([0x50, 0x4b, 3, 4, ...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc), ...u32(sz), ...u32(sz), ...u16(nm.length), ...u16(0)]);
      out.push(lh, nm, data);
      cd.push(new Uint8Array([0x50, 0x4b, 1, 2, ...u16(20), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc), ...u32(sz), ...u32(sz), ...u16(nm.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(off)]), nm);
      off += lh.length + nm.length + sz;
    });
    const cdLen = cd.reduce((s, x) => s + x.length, 0);
    const end = new Uint8Array([0x50, 0x4b, 5, 6, ...u16(0), ...u16(0), ...u16(files.length), ...u16(files.length), ...u32(cdLen), ...u32(off), ...u16(0)]);
    return new Blob([...out, ...cd, end], { type: mime });
  }

  // ── 보고서 자료 ───────────────────────────────────────────────
  const CTYS = ['한국', '일본', '싱가포르'];
  function data(scope) {
    scope = scope || 'all'; const use = scope === 'all' ? CTYS : [scope], a = S.a, b = S.b;
    const ids = D.P.filter(p => use.includes(p.c)).map(p => p.id), c = srcCalc(ids, a, b), s2 = pick2(c), tot = c.s1 + s2;
    const byC = use.map(n => { const ii = D.P.filter(p => p.c === n).map(p => p.id), cc = srcCalc(ii, a, b), t = cc.s1 + pick2(cc); return { n, count: ii.length, s1: cc.s1, s2: pick2(cc), tot: t, usd: LAW[n].usd, cost: t * LAW[n].usd * FXK / 1e8, sys: LAW[n].sys, th: LAW[n].th, rep: LAW[n].rep, cyc: LAW[n].cyc }; });
    const plants = ids.map(id => { const p = D.plant(id), e = D.em(id, a, b), s = D.status(id, a, b, 'em'); return { id, site: p.site, c: p.c, e, usage: s.usage, tg: s.tg }; }).sort((x, y) => y.e - x.e);
    const unc = c.rows.reduce((s, r) => s + r.e * r.unc, 0) / (c.tot || 1);
    const monthly = MONTHS.map(([x, y], i) => ({ m: (i + 1) + '월', q: srcCalc(ids, x, y) }));
    return { monthly, scope, name: scope === 'all' ? '통합(한국·일본·싱가포르)' : scope, ids, c, s1: c.s1, s2, tot, byC, plants, unc, basis: S.cb === 'mkt' ? '시장 기준' : '위치 기준', period: periodLabel(), rcv: Math.round(sumA2(ids.map(D.recv)) / ids.length), delay: sumA2(ids.map(D.delay)), cost: sumA2(byC.map(x => x.cost)), warn: plants.filter(p => p.usage >= .9).length, gen: new Date().toISOString().slice(0, 10) };
  }
  const lvlTxt = u => u >= 1 ? '초과' : u >= .9 ? '경고' : u >= .7 ? '주의' : '정상';
  const SRC_COL = ['2F6F8F', 'C7893A', '5E8C6A', '8E6BB0'];

  // ── 차트 이미지(밝은 스킨 색으로 오프스크린 렌더 → PNG) ──────────
  async function chartPng(node, widthPx, legend) {
    const host = document.createElement('div'), v = SKINS.vars(SKINS.get('cloud'));
    host.className = 'nomotion'; host.style.cssText = `position:fixed;left:-12000px;top:0;width:${widthPx}px;background:#fff;`;
    Object.keys(v).forEach(k => host.style.setProperty(k, v[k])); host.style.color = v['--txt']; host.append(node); document.body.append(host);
    try {
      const svg = node.tagName && node.tagName.toLowerCase() === 'svg' ? node : node.querySelector('svg'), clone = svg.cloneNode(true);
      const so = [svg, ...svg.querySelectorAll('*')], co = [clone, ...clone.querySelectorAll('*')];
      so.forEach((e, i) => { const cs = getComputedStyle(e), t = co[i]; ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'opacity', 'fill-opacity', 'stroke-opacity', 'font-size', 'font-weight', 'font-family', 'text-anchor', 'stop-color', 'stop-opacity'].forEach(p => { const val = cs.getPropertyValue(p); if (val) t.style.setProperty(p, val); }); t.removeAttribute('class'); });
      const vb = svg.viewBox.baseVal, w = vb.width, h = vb.height, sc = 2.4;
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); clone.setAttribute('width', w * sc); clone.setAttribute('height', h * sc);
      const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(clone)), img = new Image();
      await new Promise((res, rej) => { img.onload = res; img.onerror = () => rej(new Error('차트 이미지 변환 실패')); img.src = url; });
      const lh = legend && legend.length ? Math.round(34 * sc / 2) : 0, cv = document.createElement('canvas'); cv.width = Math.round(w * sc); cv.height = Math.round(h * sc) + lh; const g = cv.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height); g.drawImage(img, 0, lh, Math.round(w * sc), Math.round(h * sc));
      if (lh) { const rc = c => c && c.startsWith('var(') ? (getComputedStyle(host).getPropertyValue(c.slice(4, -1)).trim() || '#0071e3') : (c || '#0071e3'); g.font = `${Math.round(12 * sc * .9)}px 'Pretendard Variable', 'Segoe UI', sans-serif`; g.textBaseline = 'middle'; let x = Math.round(54 * sc * .5); const y = lh / 2; legend.forEach(it => { g.strokeStyle = rc(it.c); g.lineWidth = 3 * sc * .6; g.setLineDash(it.dash ? [8, 5] : []); g.beginPath(); g.moveTo(x, y); g.lineTo(x + 24 * sc * .7, y); g.stroke(); g.setLineDash([]); x += 24 * sc * .7 + 8 * sc * .6; g.fillStyle = '#3a3a3c'; g.fillText(it.n, x, y); x += g.measureText(it.n).width + 18 * sc * .8; }); }
      const blob = await new Promise(r => cv.toBlob(r, 'image/png')); return { bytes: new Uint8Array(await blob.arrayBuffer()), w: cv.width, h: cv.height };
    } finally { host.remove(); }
  }
  async function charts(d) {
    const ids = d.ids, month = MONTHS.slice(), out = {};
    out.area = await chartPng(stackedArea({ x: month.map((_, i) => (i + 1) + '월'), series: d.c.rows.map((r, i) => ({ n: r.n, c: r.c, d: month.map(([x, y]) => srcCalc(ids, x, y).rows[i].e) })) }), 760);
    out.donut = await chartPng(donutChart({ parts: d.c.rows.map(r => ({ n: r.n, v: r.e, c: r.c })), center: n1(d.c.tot), sub: 'tCO₂' }), 300);
    out.bars = await chartPng(hbarChart({ items: d.plants.map(r => ({ label: r.id + ' ' + r.site, v: r.usage * 100, c: SC[D.lvl(r.usage)], txt: Math.round(r.usage * 100) + '%' })), marks: [{ v: 70, c: 'var(--yl)', label: '주의' }, { v: 90, c: 'var(--rd)', label: '경고' }], max: 110, fmt: v => v + '%', L: 98 }), 760);
    return out;
  }

  // ── DOCX ───────────────────────────────────────────────────────
  const W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"';
  const FONT = '<w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" w:eastAsia="Malgun Gothic" w:cs="Segoe UI"/>';
  const run = (t, o = {}) => `<w:r><w:rPr>${FONT}${o.b ? '<w:b/>' : ''}${o.i ? '<w:i/>' : ''}${o.color ? `<w:color w:val="${o.color}"/>` : ''}${o.sz ? `<w:sz w:val="${o.sz}"/><w:szCs w:val="${o.sz}"/>` : ''}</w:rPr><w:t xml:space="preserve">${esc(t)}</w:t></w:r>`;
  const para = (t, o = {}) => `<w:p><w:pPr>${o.style ? `<w:pStyle w:val="${o.style}"/>` : ''}${o.keep ? '<w:keepNext/>' : ''}${o.after != null ? `<w:spacing w:after="${o.after}"/>` : ''}${o.align ? `<w:jc w:val="${o.align}"/>` : ''}</w:pPr>${t === '' ? '' : run(t, o)}</w:p>`;
  const bullet = t => `<w:p><w:pPr><w:spacing w:after="60"/><w:ind w:left="360" w:hanging="240"/></w:pPr>${run('•  ', { color: '86868B' })}${run(t)}</w:p>`;
  function table(rows, widths, aligns) {
    const total = sumA2(widths);
    const cell = (t, ci, hd) => `<w:tc><w:tcPr><w:tcW w:w="${widths[ci]}" w:type="dxa"/>${hd ? '<w:shd w:val="clear" w:color="auto" w:fill="F5F5F7"/>' : ''}<w:vAlign w:val="center"/></w:tcPr><w:p><w:pPr><w:spacing w:after="0"/>${aligns && aligns[ci] === 'r' ? '<w:jc w:val="right"/>' : ''}</w:pPr>${run(t, { b: hd, sz: hd ? 18 : 19, color: hd ? '6E6E73' : '1D1D1F' })}</w:p></w:tc>`;
    return `<w:tbl><w:tblPr><w:tblW w:w="${total}" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="D2D2D7"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="D2D2D7"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="E5E5EA"/></w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="70" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="70" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${widths.map(w => `<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${rows.map((r, ri) => `<w:tr>${ri === 0 ? '<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>' : '<w:trPr><w:cantSplit/></w:trPr>'}${r.map((t, ci) => cell(t, ci, ri === 0)).join('')}</w:tr>`).join('')}</w:tbl>${para('', { after: 120 })}`;
  }
  let imgSeq = 0;
  function image(rid, wpx, hpx, maxEmu, name) {
    const cx = maxEmu, cy = Math.round(maxEmu * hpx / wpx), id = ++imgSeq;
    return `<w:p><w:pPr><w:spacing w:after="60"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${id}" name="${esc(name)}" descr="${esc(name)}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="${id}" name="${esc(name)}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>`;
  }
  function docxBody(d, im) {
    const W = 9638, B = [], hdrLaw = d.byC.length > 1;
    B.push(para('AMA 탄소·에너지 비용 보고서', { style: 'Title' }), para(`${d.name} · ${d.period} · ${d.basis}`, { sz: 24, color: '6E6E73', after: 60 }), para(`작성일 ${d.gen} · 시안(모의 자료) — 실제 운영 데이터가 아니며 외부 참고값은 과제 원문 대조 전입니다.`, { sz: 18, color: '86868B', after: 240 }));
    B.push(para('1. 핵심 요약', { style: 'Heading1' }), table([['구분', '값', '비고'], ['직접 배출 (Scope 1)', n1(d.s1) + ' tCO₂', '고정·이동 연소'], [`간접 배출 (Scope 2 · ${d.basis})`, n1(d.s2) + ' tCO₂', '전력·열'], ['합계', n1(d.tot) + ' tCO₂', d.basis], ['참고 가격 환산 비용', n2(d.cost) + ' 억 원', '1 US$ = 1,380원 가정'], ['자료 완전성', d.rcv + ' %', `수신 지연 설비 ${d.delay}대`]], [3400, 2600, 3638], ['l', 'r', 'l']));
    const top = d.plants[0]; B.push(bullet(`배출 최상위 공장: ${top.id} ${top.site} (전체의 ${(top.e / (sumA2(d.plants.map(p => p.e)) || 1) * 100).toFixed(1)}%)`), bullet(`목표 대비 사용률 90% 이상(경고·초과) 공장: ${d.warn}개 / ${d.plants.length}개`), bullet(`가중 불확실도 ±${(d.unc * 100).toFixed(1)}% · 검증 상태: 내부 초안(제3자 검증 전)`), para('', { after: 120 }));
    B.push(para('월별 배출 구성 추이 (올해 누적, 에너지원별)', { style: 'Heading2' }), image('rIdImg1', im.area.w, im.area.h, 5900000, '월별 배출 구성 추이'), para('그림 1. 월별 배출 구성 추이(tCO₂). 모든 값은 모의 자료입니다.', { style: 'Caption' }));
    B.push(para('2. 배출 구성', { style: 'Heading1' }), table([['에너지원', 'Scope', '배출량 (tCO₂)', '비율', '불확실도'], ...d.c.rows.map(r => [r.n, 'Scope ' + r.sc, n1(r.e), (r.e / d.c.tot * 100).toFixed(1) + '%', '±' + (r.unc * 100).toFixed(1) + '%'])], [2800, 1500, 2100, 1500, 1738], ['l', 'l', 'r', 'r', 'r']), image('rIdImg2', im.donut.w, im.donut.h, 2400000, '배출 구성 도넛'), para('그림 2. 에너지원별 배출 구성. 에너지원별 비율은 모의 가정(85/15, 95/5)입니다.', { style: 'Caption' }));
    B.push(para('3. ' + (hdrLaw ? '국가별 현황' : d.name + ' 공장별 현황'), { style: 'Heading1' }));
    if (hdrLaw) B.push(table([['국가', '공장 수', 'Scope 1', 'Scope 2', '합계 (tCO₂)', '참고 가격 (US$/t)', '환산 (억 원)'], ...d.byC.map(x => [x.n, String(x.count), n1(x.s1), n1(x.s2), n1(x.tot), String(x.usd), n2(x.cost)])], [1400, 1000, 1400, 1400, 1700, 1400, 1338], ['l', 'r', 'r', 'r', 'r', 'r', 'r']));
    else B.push(para(`${d.byC[0].sys} · ${d.byC[0].th}`, { sz: 19, color: '6E6E73' }), para(`보고 형식: ${d.byC[0].rep} · 제출 주기: ${d.byC[0].cyc} · 현재 상태: 미제출(시안)`, { sz: 19, color: '6E6E73' }));
    B.push(table([['공장', '지역', '배출 (tCO₂)', '목표 대비', '상태'], ...d.plants.map(p => [p.id + ' ' + p.site, p.c, n1(p.e), Math.round(p.usage * 100) + '%', lvlTxt(p.usage)])], [2600, 1600, 2100, 1700, 1638], ['l', 'l', 'r', 'r', 'l']), image('rIdImg3', im.bars.w, im.bars.h, 5900000, '공장별 목표 대비 사용률'), para('그림 3. 공장별 목표 대비 사용률(70% 주의 · 90% 경고).', { style: 'Caption' }));
    B.push(para('4. 산정 방법·계수', { style: 'Heading1' }), bullet('배출량 = 활동량 × 배출계수. 계수 버전 EF-2026.1(가상).'), bullet('Scope 2는 위치 기준(국가 전력 계수)과 시장 기준(재생에너지 인증 반영)을 구분해 표시합니다.'), bullet(`이 보고서는 ${d.basis} 합계를 사용합니다.`), bullet('에너지원별 비율, 계수, 가격은 모의 가정이며 제3자 검증을 거치지 않았습니다.'));
    B.push(para('5. 유의사항·출처', { style: 'Heading1' }), bullet('외부 참고 가격: World Bank Carbon Pricing Dashboard(조회 2026-10-28, 2025-04 기준). 법령 원문·실제 적용 가격은 확인 전입니다.'), bullet('국가별 제도 명칭과 제출 주기는 시안 표기이며, 실제 제출 전 법령 원문 대조가 필요합니다.'), bullet('본 문서는 디자인 시안에서 생성된 예시 보고서입니다.'));
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W_NS}><w:body>${B.join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>`;
  }
  const DOCX_STYLES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI" w:eastAsia="Malgun Gothic" w:cs="Segoe UI"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="en-US" w:eastAsia="ko-KR"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:rPr><w:color w:val="1D1D1F"/></w:rPr></w:style><w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont"><w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/></w:style><w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:uiPriority w:val="99"/><w:semiHidden/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="240" w:after="80" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:b/><w:color w:val="1D1D1F"/><w:sz w:val="56"/><w:szCs w:val="56"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="400" w:after="140"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="1D1D1F"/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="3A3A3C"/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="200"/><w:jc w:val="center"/></w:pPr><w:rPr><w:color w:val="6E6E73"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:style></w:styles>`;
  function buildDocx(d, im) {
    imgSeq = 0;
    const files = [
      { name: '[Content_Types].xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>' },
      { name: '_rels/.rels', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>' },
      { name: 'docProps/core.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>AMA 탄소·에너지 비용 보고서(시안)</dc:title><dc:creator>AMA</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}</dcterms:created></cp:coreProperties>` },
      { name: 'docProps/app.xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>AMA Report Generator</Application></Properties>' },
      { name: 'word/styles.xml', data: DOCX_STYLES },
      { name: 'word/_rels/document.xml.rels', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdSt" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rIdImg1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/><Relationship Id="rIdImg2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image2.png"/><Relationship Id="rIdImg3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image3.png"/></Relationships>' },
      { name: 'word/document.xml', data: docxBody(d, im) },
      { name: 'word/media/image1.png', data: im.area.bytes }, { name: 'word/media/image2.png', data: im.donut.bytes }, { name: 'word/media/image3.png', data: im.bars.bytes }
    ];
    return zip(files, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
  }

  // ── PPTX ───────────────────────────────────────────────────────
  const E = v => Math.round(v * 914400), SW = 12192000, SH = 6858000, MG = E(.6);
  const P_NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"';
  const rp = (o = {}) => `<a:rPr lang="ko-KR" sz="${Math.round((o.sz || 14) * 100)}"${o.b ? ' b="1"' : ''} dirty="0"><a:solidFill><a:srgbClr val="${o.color || '1D1D1F'}"/></a:solidFill><a:latin typeface="Malgun Gothic"/><a:ea typeface="Malgun Gothic"/><a:cs typeface="Malgun Gothic"/></a:rPr>`;
  const ap = (t, o = {}) => `<a:p><a:pPr algn="${o.align || 'l'}">${o.bullet ? '<a:buNone/>' : '<a:buNone/>'}</a:pPr><a:r>${rp(o)}<a:t>${esc(t)}</a:t></a:r></a:p>`;
  let sid = 1;
  const nid = () => ++sid;
  function textBox(x, y, w, h, paras, o = {}) {
    const id = nid(), fill = o.fill ? `<a:solidFill><a:srgbClr val="${o.fill}"/></a:solidFill>` : '<a:noFill/>', geom = o.round ? `<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val ${o.round}"/></a:avLst></a:prstGeom>` : '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>';
    return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${esc(o.name || 'Text ' + id)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>${geom}${fill}<a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="${o.pad == null ? 91440 : o.pad}" tIns="${o.padT == null ? 45720 : o.padT}" rIns="${o.pad == null ? 91440 : o.pad}" bIns="45720" anchor="${o.anchor || 't'}"><a:noAutofit/></a:bodyPr><a:lstStyle/>${paras.join('')}</p:txBody></p:sp>`;
  }
  function pic(rid, x, y, w, h, name) { const id = nid(); return `<p:pic><p:nvPicPr><p:cNvPr id="${id}" name="${esc(name)}" descr="${esc(name)}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="${rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>`; }
  function tbl(x, y, widths, rows, aligns, rowH) {
    const id = nid(), w = sumA2(widths), h = rowH * rows.length, ln = (t, c, wd) => `<a:${t} w="${wd}" cap="flat" cmpd="sng"><a:solidFill><a:srgbClr val="${c}"/></a:solidFill></a:${t}>`, no = t => `<a:${t} w="0"><a:noFill/></a:${t}>`;
    const cell = (t, ci, hd) => `<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="${aligns && aligns[ci] === 'r' ? 'r' : 'l'}"/><a:r>${rp({ sz: hd ? 11 : 12, b: hd, color: hd ? '6E6E73' : '1D1D1F' })}<a:t>${esc(t)}</a:t></a:r></a:p></a:txBody><a:tcPr marL="91440" marR="91440" marT="45720" marB="45720" anchor="ctr">${no('lnL')}${no('lnR')}${no('lnT')}${ln('lnB', hd ? 'D2D2D7' : 'E5E5EA', hd ? 12700 : 6350)}<a:noFill/></a:tcPr></a:tc>`;
    return `<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="${id}" name="Table ${id}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1"/><a:tblGrid>${widths.map(v => `<a:gridCol w="${v}"/>`).join('')}</a:tblGrid>${rows.map((r, ri) => `<a:tr h="${rowH}">${r.map((t, ci) => cell(t, ci, ri === 0)).join('')}</a:tr>`).join('')}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;
  }
  const slide = (shapes) => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld ${P_NS}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>${shapes.join('')}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
  const head = (t, sub) => [textBox(MG, E(.42), SW - 2 * MG, E(.6), [ap(t, { sz: 28, b: 1 })], { name: 'Title' }), sub ? textBox(MG, E(1.0), SW - 2 * MG, E(.4), [ap(sub, { sz: 13, color: '6E6E73' })], { name: 'Subtitle' }) : ''];
  const foot = d => textBox(MG, SH - E(.5), SW - 2 * MG, E(.3), [ap(`AMA · ${d.name} · ${d.period} · ${T('시안(모의 자료)', 'Design draft (mock data)')}`, { sz: 9, color: '86868B' })], { name: 'Footer' });
  function pptxSlides(d, im) {
    const S_ = [], rels = []; // rels[i] = 이미지 목록 [{rid, file}]
    const W2 = SW - 2 * MG, top = d.plants[0], totE = sumA2(d.plants.map(p => p.e)) || 1;
    sid = 1; S_.push(slide([textBox(MG, E(2.0), W2, E(1.3), [ap('AMA 탄소·에너지 비용 보고서', { sz: 40, b: 1 })], { name: 'Title' }), textBox(MG, E(3.35), W2, E(.5), [ap(d.name, { sz: 20, color: '1D1D1F' })]), textBox(MG, E(3.85), W2, E(.4), [ap(`${d.period} · ${d.basis} · 작성일 ${d.gen}`, { sz: 14, color: '6E6E73' })]), textBox(MG, SH - E(1.0), W2, E(.4), [ap('시안(모의 자료) — 실제 운영 데이터가 아니며 외부 참고값은 과제 원문 대조 전입니다.', { sz: 11, color: '86868B' })])])); rels.push([]);
    sid = 1; { const cw = Math.round((W2 - 3 * E(.2)) / 4), cards = [['직접 배출 (Scope 1)', n0(d.s1), 'tCO₂'], [`간접 배출 (Scope 2 · ${d.basis})`, n0(d.s2), 'tCO₂'], ['합계', n0(d.tot), 'tCO₂'], ['참고 가격 환산 비용', n1(d.cost), '억 원']];
      S_.push(slide([...head('핵심 요약', `${d.name} · ${d.period}`), ...cards.map((c, i) => textBox(MG + i * (cw + E(.2)), E(1.6), cw, E(1.7), [ap(c[0], { sz: 12, color: '6E6E73' }), ap(c[1], { sz: 32, b: 1 }), ap(c[2], { sz: 12, color: '6E6E73' })], { fill: 'F5F5F7', round: 7000, pad: E(.18), padT: E(.16), name: 'KPI ' + (i + 1) })), textBox(MG, E(3.7), W2, E(2.4), [ap(`•  배출 최상위 공장: ${top.id} ${top.site} (전체의 ${(top.e / totE * 100).toFixed(1)}%)`, { sz: 16 }), ap(`•  목표 대비 사용률 90% 이상(경고·초과) 공장: ${d.warn}개 / ${d.plants.length}개`, { sz: 16 }), ap(`•  자료 완전성 ${d.rcv}% · 수신 지연 설비 ${d.delay}대`, { sz: 16 }), ap(`•  가중 불확실도 ±${(d.unc * 100).toFixed(1)}% · 검증 상태: 내부 초안`, { sz: 16 })], { name: 'Highlights' }), foot(d)])); rels.push([]); }
    sid = 1; { const dh = E(3.9), dw = Math.round(dh * im.donut.w / im.donut.h);
      S_.push(slide([...head('배출 구성', '에너지원별 비율 (Scope 1 = 고정·이동 연소, Scope 2 = 전력·열)'), pic('rIdI1', MG, E(1.6), dw, dh, '배출 구성 도넛'), tbl(MG + dw + E(.4), E(1.8), [E(2.4), E(1.0), E(1.6), E(1.0)], [['에너지원', 'Scope', 'tCO₂', '비율'], ...d.c.rows.map(r => [r.n, 'Scope ' + r.sc, n1(r.e), (r.e / d.c.tot * 100).toFixed(1) + '%'])], ['l', 'l', 'r', 'r'], E(.5)), textBox(MG, E(5.9), W2, E(.4), [ap('에너지원별 비율은 모의 가정(85/15, 95/5)입니다.', { sz: 11, color: '86868B' })]), foot(d)])); rels.push([['rIdI1', 'donut']]); }
    sid = 1; { const iw = W2, ih = Math.round(iw * im.area.h / im.area.w);
      S_.push(slide([...head('월별 배출 구성 추이', '올해 누적 · 에너지원별 (tCO₂)'), pic('rIdI1', MG, E(1.5), iw, Math.min(ih, E(4.7)), '월별 배출 구성 추이'), foot(d)])); rels.push([['rIdI1', 'area']]); }
    sid = 1; { let bw = E(6.4), bh = Math.round(bw * im.bars.h / im.bars.w); if (bh > E(4.9)) { bh = E(4.9); bw = Math.round(bh * im.bars.w / im.bars.h); } const tb = d.byC.length > 1 ? [['국가', '공장', '합계 tCO₂', '환산 억 원'], ...d.byC.map(x => [x.n, String(x.count), n0(x.tot), n2(x.cost)])] : [['공장', '배출 tCO₂', '목표 대비'], ...d.plants.slice(0, 8).map(p => [p.id + ' ' + p.site, n1(p.e), Math.round(p.usage * 100) + '%'])], ws = d.byC.length > 1 ? [E(1.5), E(.8), E(1.6), E(1.3)] : [E(2.2), E(1.6), E(1.4)];
      S_.push(slide([...head(d.byC.length > 1 ? '국가·공장 현황' : d.name + ' 공장 현황', '목표 대비 사용률: 70% 주의 · 90% 경고'), tbl(MG, E(1.7), ws, tb, d.byC.length > 1 ? ['l', 'r', 'r', 'r'] : ['l', 'r', 'r'], E(.46)), pic('rIdI1', SW - MG - bw, E(1.4), bw, bh, '공장별 목표 대비 사용률'), foot(d)])); rels.push([['rIdI1', 'bars']]); }
    sid = 1; S_.push(slide([...head('산정 방법·유의사항'), textBox(MG, E(1.5), W2, E(4.6), [ap('산정 방법', { sz: 18, b: 1 }), ap('•  배출량 = 활동량 × 배출계수 (계수 버전 EF-2026.1, 가상)', { sz: 14 }), ap(`•  Scope 2는 위치 기준·시장 기준을 구분하며, 이 보고서는 ${d.basis} 합계를 사용`, { sz: 14 }), ap(' ', { sz: 8 }), ap('유의사항', { sz: 18, b: 1 }), ap('•  외부 참고 가격: World Bank Carbon Pricing Dashboard(2025-04 기준, 조회 2026-10-28)', { sz: 14 }), ap('•  법령 원문·실제 적용 가격은 확인 전이며, 제3자 검증을 거치지 않은 내부 초안입니다', { sz: 14 }), ap('•  본 문서는 디자인 시안에서 생성된 예시 보고서입니다', { sz: 14 })], { name: 'Notes' }), foot(d)])); rels.push([]);
    return { slides: S_, rels };
  }
  function buildPptx(d, im) {
    const { slides, rels } = pptxSlides(d, im), T = window.RPT_TPL, imgs = { donut: im.donut, area: im.area, bars: im.bars }, files = [];
    const n = slides.length, REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
    files.push({ name: '[Content_Types].xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>${Array.from({ length: 11 }, (_, i) => `<Override PartName="/ppt/slideLayouts/slideLayout${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>`).join('')}<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/><Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/><Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/><Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>${slides.map((_, i) => `<Override PartName="/ppt/slides/slide${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join('')}<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>` });
    files.push({ name: '_rels/.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${REL}/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="${REL}/extended-properties" Target="docProps/app.xml"/></Relationships>` });
    files.push({ name: 'docProps/core.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>AMA 탄소·에너지 비용 보고서(시안)</dc:title><dc:creator>AMA</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}</dcterms:created></cp:coreProperties>` });
    files.push({ name: 'docProps/app.xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>AMA Report Generator</Application></Properties>' });
    files.push({ name: 'ppt/presentation.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation ${P_NS} saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>${slides.map((_, i) => `<p:sldId id="${256 + i}" r:id="rId${6 + i}"/>`).join('')}</p:sldIdLst><p:sldSz cx="${SW}" cy="${SH}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>` });
    files.push({ name: 'ppt/_rels/presentation.xml.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${REL}/slideMaster" Target="slideMasters/slideMaster1.xml"/><Relationship Id="rId2" Type="${REL}/presProps" Target="presProps.xml"/><Relationship Id="rId3" Type="${REL}/viewProps" Target="viewProps.xml"/><Relationship Id="rId4" Type="${REL}/theme" Target="theme/theme1.xml"/><Relationship Id="rId5" Type="${REL}/tableStyles" Target="tableStyles.xml"/>${slides.map((_, i) => `<Relationship Id="rId${6 + i}" Type="${REL}/slide" Target="slides/slide${i + 1}.xml"/>`).join('')}</Relationships>` });
    Object.keys(T).forEach(k => files.push({ name: k, data: T[k] }));
    slides.forEach((x, i) => {
      files.push({ name: `ppt/slides/slide${i + 1}.xml`, data: x });
      files.push({ name: `ppt/slides/_rels/slide${i + 1}.xml.rels`, data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${REL}/slideLayout" Target="../slideLayouts/slideLayout7.xml"/>${rels[i].map(([rid, k]) => `<Relationship Id="${rid}" Type="${REL}/image" Target="../media/${k}.png"/>`).join('')}</Relationships>` });
    });
    Object.keys(imgs).forEach(k => files.push({ name: `ppt/media/${k}.png`, data: imgs[k].bytes }));
    return zip(files, 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
  }

  // ── XLSX ───────────────────────────────────────────────────────
  const colL = i => { let s = ''; i++; while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = (i - m - 1) / 26; } return s; };
  // 셀: 문자열 | 숫자 | {v, s(스타일), f(수식)}
  const ST = { def: 0, hd: 1, n1: 2, n0: 3, pct: 4, title: 5, note: 6, tn1: 7, tb: 8, n2: 9, tn0: 10 };
  function xCell(c, ref) {
    if (c == null || c === '') return '';
    let o = typeof c === 'object' ? c : { v: c }, s = o.s != null ? o.s : 0;
    if (o.f) return `<c r="${ref}" s="${s}"><f>${esc(o.f)}</f><v>${o.v == null ? 0 : +o.v}</v></c>`;
    if (typeof o.v === 'number' && isFinite(o.v)) return `<c r="${ref}" s="${s}"><v>${o.v}</v></c>`;
    return `<c r="${ref}" s="${s}" t="inlineStr"><is><t xml:space="preserve">${esc(o.v)}</t></is></c>`;
  }
  function xSheet(rows, widths, o = {}) {
    const body = rows.map((r, i) => `<row r="${i + 1}"${r && r._h ? ` ht="${r._h}" customHeight="1"` : ''}>${(r || []).map((c, j) => xCell(c, colL(j) + (i + 1))).join('')}</row>`).join('');
    const cols = widths ? `<cols>${widths.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('')}</cols>` : '';
    const pane = o.freeze ? `<sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="${o.freeze}" topLeftCell="A${o.freeze + 1}" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>` : `<sheetViews><sheetView workbookViewId="0" showGridLines="0"/></sheetViews>`;
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">${pane}<sheetFormatPr defaultRowHeight="18"/>${cols}<sheetData>${body}</sheetData>${o.autofilter ? `<autoFilter ref="${o.autofilter}"/>` : ''}<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/><pageSetup orientation="landscape" fitToHeight="0"/></worksheet>`;
  }
  const XSTYLES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="3"><numFmt numFmtId="164" formatCode="#,##0.0"/><numFmt numFmtId="165" formatCode="0.0%"/><numFmt numFmtId="166" formatCode="#,##0.00"/></numFmts>
<fonts count="7"><font><sz val="11"/><color rgb="FF1D1D1F"/><name val="Malgun Gothic"/></font><font><b/><sz val="10"/><color rgb="FF6E6E73"/><name val="Malgun Gothic"/></font><font><b/><sz val="16"/><color rgb="FF1D1D1F"/><name val="Malgun Gothic"/></font><font><i/><sz val="9"/><color rgb="FF86868B"/><name val="Malgun Gothic"/></font><font><b/><sz val="11"/><color rgb="FF1D1D1F"/><name val="Malgun Gothic"/></font><font><b/><sz val="14"/><color rgb="FF1D1D1F"/><name val="Malgun Gothic"/></font><font><b/><sz val="12"/><color rgb="FF0071E3"/><name val="Malgun Gothic"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF5F5F7"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="3"><border><left/><right/><top/><bottom/><diagonal/></border><border><left/><right/><top/><bottom style="thin"><color rgb="FFD2D2D7"/></bottom><diagonal/></border><border><left/><right/><top style="thin"><color rgb="FFD2D2D7"/></top><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="15"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="164" fontId="4" fillId="0" borderId="2" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/><xf numFmtId="0" fontId="4" fillId="0" borderId="2" xfId="0" applyFont="1" applyBorder="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="4" fillId="0" borderId="2" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="6" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"/><xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`;
  function xlsxSheets(d) {
    const sheets = [], H = a => a.map(v => ({ v, s: ST.hd })), r2 = (k, v, s) => [k, { v, s }];
    // 1 요약
    const em = sumA2(d.plants.map(p => p.e));
    sheets.push([T('요약', 'Summary'), xSheet([
      [{ v: T('AMA 탄소·에너지 비용 종합 보고서', 'AMA Carbon & Energy Cost Summary Report'), s: ST.title }], [{ v: T(`${d.name} · ${d.period} · ${d.basis} · 작성일 ${d.gen}`, `${d.name} · ${d.period} · ${d.basis} · Created ${d.gen}`), s: ST.note }], [{ v: T('시안(모의 자료): 실제 운영 데이터가 아니며 외부 참고값은 과제 원문 대조 전입니다.', 'Design draft (mock data): not actual operating data; external reference values are not yet checked against the case-study text.'), s: ST.note }], [],
      H(T(['항목', '값', '단위', '비고'], ['Item', 'Value', 'Unit', 'Note'])),
      [T('직접 배출 (Scope 1)', 'Direct emissions (Scope 1)'), { v: d.s1, s: ST.n1 }, 'tCO₂', T('고정·이동 연소', 'Stationary & mobile combustion')],
      [T(`간접 배출 (Scope 2 · ${d.basis})`, `Indirect emissions (Scope 2 · ${d.basis})`), { v: d.s2, s: ST.n1 }, 'tCO₂', T('전력·열', 'Electricity & heat')],
      [{ v: T('합계', 'Total'), s: ST.tb }, { v: d.tot, s: ST.tn1, f: 'B6+B7' }, { v: 'tCO₂', s: ST.tb }, { v: d.basis, s: ST.tb }],
      [T('참고 가격 환산 비용', 'Cost at reference prices'), { v: d.cost, s: ST.n2 }, T('억 원', 'KRW 100M'), T('1 US$ = 1,380원 가정 · 국가별 참고 가격', 'Assuming 1 US$ = KRW 1,380 · per-country reference prices')],
      [T('자료 완전성', 'Data completeness'), { v: d.rcv / 100, s: ST.pct }, '%', T(`수신 지연 설비 ${d.delay}대`, `${d.delay} equipment with delayed reception`)],
      [T('가중 불확실도', 'Weighted uncertainty'), { v: d.unc, s: ST.pct }, '%', T('내부 초안(제3자 검증 전)', 'Internal draft (before third-party verification)')],
      [T('배출 최상위 공장', 'Top-emitting plant'), d.plants[0].id + ' ' + d.plants[0].site, '', T(`전체의 ${(d.plants[0].e / (em || 1) * 100).toFixed(1)}%`, `${(d.plants[0].e / (em || 1) * 100).toFixed(1)}% of total`)],
      [T('목표 대비 90% 이상(경고·초과) 공장', 'Plants at 90%+ of target (warning/over)'), { v: d.warn, s: ST.n0 }, T('개', 'plants'), T(`전체 ${d.plants.length}개 중`, `of ${d.plants.length} total`)],
    ], [38, 22, 10, 44])]);
    // 2 에너지원별
    const rs = d.c.rows, r0 = 5;
    sheets.push([T('에너지원별', 'By energy source'), xSheet([
      [{ v: T('에너지원별 산정 (활동량 × 배출계수 = 배출량)', 'Calculation by energy source (activity × factor = emissions)'), s: ST.title }], [{ v: T('계수 버전 EF-2026.1(가상). 에너지원별 비율은 모의 가정(85/15, 95/5)입니다.', 'Factor version EF-2026.1 (fictional). Per-source ratios are mock assumptions (85/15, 95/5).'), s: ST.note }], [],
      H(T(['에너지원', 'Scope', '활동량', '단위', '배출계수', '계수 단위', '배출량 (tCO₂)', '비율', '불확실도'], ['Energy source', 'Scope', 'Activity', 'Unit', 'Factor', 'Factor unit', 'Emissions (tCO₂)', 'Share', 'Uncertainty'])),
      ...rs.map((x, i) => [x.n, 'S' + x.sc, { v: x.act, s: ST.n0 }, x.u, { v: x.f, s: ST.n2 === 9 ? 9 : 9 }, x.fu, { v: x.e, s: ST.n1 }, { v: x.e / d.c.tot, s: ST.pct, f: `G${r0 + i}/G${r0 + rs.length}` }, { v: x.unc, s: ST.pct }]),
      [{ v: T('합계', 'Total'), s: ST.tb }, '', '', '', '', '', { v: d.c.tot, s: ST.tn1, f: `SUM(G${r0}:G${r0 + rs.length - 1})` }, { v: 1, s: ST.tb, f: `SUM(H${r0}:H${r0 + rs.length - 1})` }, ''],
    ], [20, 8, 14, 8, 12, 14, 18, 10, 12], { freeze: 4 })]);
    // 3 국가별
    const cr = 5, cq = d.byC.map(x => srcCalc(D.P.filter(p => p.c === x.n).map(p => p.id), S.a, S.b));
    sheets.push([T('국가별', 'By country'), xSheet([
      [{ v: T('국가별 배출·참고 비용', 'Emissions and reference cost by country'), s: ST.title }], [{ v: T(`Scope 2는 위치 기준·시장 기준을 함께 표시합니다. 이 보고서는 ${d.basis} 합계를 사용합니다.`, `Scope 2 is shown on both location and market basis. This report uses the ${d.basis} total.`), s: ST.note }], [],
      H(T(['국가', '공장 수', 'Scope 1', 'Scope 2 위치', 'Scope 2 시장', '합계 (' + d.basis + ')', '참고 가격 (US$/t)', '환산 (억 원)', '제도', '제출 주기'], ['Country', 'Plants', 'Scope 1', 'Scope 2 location', 'Scope 2 market', 'Total (' + d.basis + ')', 'Reference price (US$/t)', 'Converted (KRW 100M)', 'Scheme', 'Filing cycle'])),
      ...d.byC.map((x, i) => { const q = cq[i]; return [x.n, { v: x.count, s: ST.n0 }, { v: x.s1, s: ST.n1 }, { v: q.s2, s: ST.n1 }, { v: q.s2m, s: ST.n1 }, { v: x.tot, s: ST.n1, f: `C${cr + i}+${S.cb === 'mkt' ? 'E' : 'D'}${cr + i}` }, { v: x.usd, s: ST.n0 }, { v: x.cost, s: ST.n2, f: `F${cr + i}*G${cr + i}*1380/100000000` }, x.sys, x.cyc]; }),
      d.byC.length > 1 ? [{ v: T('합계', 'Total'), s: ST.tb }, { v: sumA2(d.byC.map(x => x.count)), s: ST.tn0, f: `SUM(B${cr}:B${cr + d.byC.length - 1})` }, ...['C', 'D', 'E', 'F'].map((c, k) => ({ v: [sumA2(d.byC.map(x => x.s1)), sumA2(cq.map(q => q.s2)), sumA2(cq.map(q => q.s2m)), d.tot][k], s: ST.tn1, f: `SUM(${c}${cr}:${c}${cr + d.byC.length - 1})` })), '', { v: d.cost, s: ST.tn1, f: `SUM(H${cr}:H${cr + d.byC.length - 1})` }, '', ''] : [],
    ], [12, 9, 14, 16, 16, 20, 16, 14, 30, 20], { freeze: 4 })]);
    // 4 공장별
    sheets.push([T('공장별', 'By plant'), xSheet([
      [{ v: T('공장별 배출·목표 대비', 'Emissions vs target by plant'), s: ST.title }], [{ v: T('상태 기준: 70% 주의 · 90% 경고 · 100% 초과', 'Status basis: 70% caution · 90% warning · 100% over'), s: ST.note }], [],
      H(T(['공장', '지역', '배출 (tCO₂)', '목표 (tCO₂)', '목표 대비', '상태'], ['Plant', 'Region', 'Emissions (tCO₂)', 'Target (tCO₂)', 'vs target', 'Status'])),
      ...d.plants.map((p, i) => [p.id + ' ' + p.site, p.c, { v: p.e, s: ST.n1 }, { v: p.tg, s: ST.n1 }, { v: p.usage, s: ST.pct, f: `C${5 + i}/D${5 + i}` }, lvlTxt(p.usage)]),
    ], [24, 12, 16, 16, 12, 10], { freeze: 4, autofilter: `A4:F${4 + d.plants.length}` })]);
    // 5 월별
    sheets.push([T('월별', 'Monthly'), xSheet([
      [{ v: T('월별 배출 (에너지원별)', 'Monthly emissions (by energy source)'), s: ST.title }], [{ v: T('올해 누적. 마지막 달은 기준일까지입니다.', 'Year to date. The last month runs to the reference date.'), s: ST.note }], [],
      H([T('월', 'Month'), ...rs.map(x => x.n + ' (tCO₂)'), T('합계 (tCO₂)', 'Total (tCO₂)')]),
      ...d.monthly.map((m, i) => [m.m, ...m.q.rows.map(x => ({ v: x.e, s: ST.n1 })), { v: m.q.s1 + m.q.s2, s: ST.tn1 === 7 ? 2 : 2, f: `SUM(B${5 + i}:${colL(rs.length)}${5 + i})` }]),
      [{ v: T('합계', 'Total'), s: ST.tb }, ...rs.map((x, k) => ({ v: sumA2(d.monthly.map(m => m.q.rows[k].e)), s: ST.tn1, f: `SUM(${colL(k + 1)}5:${colL(k + 1)}${4 + d.monthly.length})` })), { v: sumA2(d.monthly.map(m => m.q.s1 + m.q.s2)), s: ST.tn1, f: `SUM(${colL(rs.length + 1)}5:${colL(rs.length + 1)}${4 + d.monthly.length})` }],
    ], [10, 18, 18, 18, 18, 18], { freeze: 4 })]);
    // 6 배출권 시세(KRX 실제 5거래일)
    if (window.MKT && MKT.series) {
      const rl = MKT.series.filter(x => x.real);
      sheets.push([T('배출권시세', 'Allowance prices'), xSheet([
        [{ v: T('배출권 시세 KAU26 (KRX 실제 최근 5거래일)', 'KAU26 allowance price (last 5 actual KRX sessions)'), s: ST.title }], [{ v: T('출처: KRX 배출권시장 정보플랫폼(ets.krx.co.kr) 2026-10-28 공개 종가표 · 일 1회 마감 값, 실시간 아님', 'Source: KRX ETS information platform (ets.krx.co.kr) public closing-price table of 2026-10-28 · one daily closing value, not real-time'), s: ST.note }], [],
        H(T(['날짜', '종가 (원/톤)', '대비', '등락률 (%)', '거래량 (톤)'], ['Date', 'Close (KRW/t)', 'Change', 'Change rate (%)', 'Volume (t)'])),
        ...rl.slice().reverse().map(x => [x.d, { v: x.c, s: ST.n0 }, { v: x.chg, s: ST.n0 }, { v: x.rate, s: ST.n2 }, { v: x.v, s: ST.n0 }]),
      ], [14, 16, 12, 14, 16], { freeze: 4 })]);
    }
    return sheets;
  }
  function buildXlsx(d) { return xlsxPack(xlsxSheets(d)); }
  function xlsxPack(sheets, extra) {
    extra = extra || {};
    const files = [
      { name: '[Content_Types].xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>${extra.ct || ''}<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>` },
      { name: '_rels/.rels', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>' },
      { name: 'docProps/core.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>AMA 탄소·에너지 비용 종합 보고서(시안)</dc:title><dc:creator>AMA</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}</dcterms:created></cp:coreProperties>` },
      { name: 'docProps/app.xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>AMA Report Generator</Application></Properties>' },
      { name: 'xl/workbook.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews><sheets>${sheets.map((s, i) => `<sheet name="${esc(s[0])}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>` },
      { name: 'xl/_rels/workbook.xml.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>` },
      { name: 'xl/styles.xml', data: XSTYLES },
      ...sheets.map((s, i) => ({ name: `xl/worksheets/sheet${i + 1}.xml`, data: s[1] })),
      ...(extra.files || [])
    ];
    return zip(files, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  }

  // ── 외부 진입점 ───────────────────────────────────────────────
  const safe = s => String(s).replace(/[^\w가-힣.\-]+/g, '_').replace(/^_+|_+$/g, '');
  async function build(kind, scope) {
    if (window.ReportDoc && window.ReportModel) return ReportDoc.build(kind, scope, arguments[2]);
    const d = data(scope); let blob; if (kind === 'xlsx') blob = buildXlsx(d); else { const im = await charts(d); blob = kind === 'docx' ? buildDocx(d, im) : buildPptx(d, im); }
    const name = `AMA-탄소에너지-종합보고서_${safe(scope === 'all' || !scope ? '통합' : scope)}_${safe(d.period)}.${kind}`;
    return { blob, name, d };
  }
  function download(blob, name) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 4000); }
  function reportCard() {
    S.rs = S.rs || 'all';
    const st = h('div', { class: 'rp-st mut small', 'aria-live': 'polite' }, 'Word·Excel은 이 브라우저에서 만들어집니다. PowerPoint(한국어)는 분석 데이터가 같은 환경의 내부 서버로 전달되어 AI가 문장을 작성합니다.');
    const mk = (kind, label) => { const b = h('button', { type: 'button', class: 'rp-btn', 'data-own': 1, 'data-rp': kind }, label); b.addEventListener('click', async () => { const all = b.parentNode.querySelectorAll('button'); all.forEach(x => x.disabled = true); st.textContent = '보고서를 만드는 중…'; try { const r = await build(kind, S.rs, t => { st.textContent = t; }); download(r.blob, r.name); window.__lastReport = r; st.textContent = `완료: ${r.name} (${Math.round(r.blob.size / 1024)} KB)` + (r.ai ? (r.ai.ai ? ` · AI 작성(${r.ai.model}, ${r.ai.slots}칸)` : ' · 규칙 기반 문장(AI 연결 전)') : (r.fallback ? ' · 서버 작성 불가 → 기본 문서' : '')); } catch (e) { st.textContent = '생성 실패: ' + (e && e.message || e); } all.forEach(x => x.disabled = false); }); return b; };
    const sc = seg([['all', '통합'], ...CTYS.map(n => [n, n])], S.rs, k => { S.rs = k; rerender(); });
    return card('보고서 내보내기 (Word · PowerPoint)', '예시', h('div', { class: 'rp-row' }, h('span', { class: 'mut' }, '대상'), sc), h('div', { class: 'rp-row' }, mk('docx', 'Word 보고서 (.docx)'), mk('pptx', 'PowerPoint 보고서 (.pptx)')), st);
  }
  function reportMenu() {
    S.rs = S.rs || 'all';
    const st = h('div', { class: 'rpm-st mut small', 'aria-live': 'polite' }, 'Word·Excel은 이 브라우저에서 만들어집니다. PowerPoint(한국어)는 분석 데이터가 같은 환경의 내부 서버로 전달되어 AI가 문장을 작성합니다.');
    const pop = h('div', { class: 'rpm-pop', role: 'dialog', 'aria-label': '종합 보고서 생성', hidden: 'hidden' });
    const wrap = h('div', { class: 'rpm' });
    const btn0 = h('button', { type: 'button', class: 'rpm-btn', 'data-own': 1, 'aria-haspopup': 'dialog', 'aria-expanded': 'false' }, h('span', { class: 'rpm-ic', html: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 1.8h5.2L12.5 5v9.2H4z"/><path d="M9 1.8V5h3.5M6.2 8.6h4M6.2 11h4"/></svg>' }), h('span', {}, '종합 보고서 생성'), h('span', { class: 'rpm-car', 'aria-hidden': 'true' }));
    const kinds = [['pptx', 'PowerPoint', '.pptx · Executive Summary·상세·그래프 부록', 'P'], ['xlsx', 'Excel', '.xlsx · 종합 의견·상세·그래프 해석·수식 모델·데이터', 'X'], ['docx', 'Word', '.docx · 종합 의견→상세 분석→그래프 해석 부록', 'W']];
    const mkRow = ([k, name, sub, ic]) => { const b = h('button', { type: 'button', class: 'rpm-it', 'data-own': 1, 'data-rp': k }, h('span', { class: 'rpm-fi ' + k }, ic), h('span', { class: 'rpm-tx' }, h('b', {}, name), h('span', { class: 'mut small' }, sub))); b.addEventListener('click', async () => { const all = pop.querySelectorAll('button'); all.forEach(x => x.disabled = true); st.textContent = '보고서를 만드는 중…'; try { const r = await build(k, S.rs, t => { st.textContent = t; }); download(r.blob, r.name); window.__lastReport = r; st.textContent = `완료: ${r.name} (${Math.round(r.blob.size / 1024)} KB)` + (r.ai ? (r.ai.ai ? ` · AI 작성(${r.ai.model}, ${r.ai.slots}칸)` : ' · 규칙 기반 문장(AI 연결 전)') : (r.fallback ? ' · 서버 작성 불가 → 기본 문서' : '')); } catch (e) { st.textContent = '생성 실패: ' + (e && e.message || e); } all.forEach(x => x.disabled = false); }); return b; };
    const sc = seg([['all', '통합'], ...CTYS.map(n => [n, n])], S.rs, k => { S.rs = k; sc.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.textContent === (k === 'all' ? '통합' : k))); });
    pop.append(h('div', { class: 'rpm-h' }, h('b', {}, '종합 보고서 생성'), h('span', { class: 'mut small' }, ' 현재 기간·기준으로 만듭니다')), h('div', { class: 'rpm-row' }, h('span', { class: 'mut' }, '대상'), sc), h('div', { class: 'rpm-list' }, kinds.map(mkRow)), st);
    const close = () => { pop.hidden = true; btn0.setAttribute('aria-expanded', 'false'); wrap.classList.remove('open'); document.removeEventListener('mousedown', outside, true); document.removeEventListener('keydown', esc, true); };
    const outside = e => { if (!wrap.contains(e.target)) close(); }, esc = e => { if (e.key === 'Escape') { close(); btn0.focus(); } };
    btn0.addEventListener('click', () => { if (!pop.hidden) { close(); return; } pop.hidden = false; btn0.setAttribute('aria-expanded', 'true'); wrap.classList.add('open'); setTimeout(() => { document.addEventListener('mousedown', outside, true); document.addEventListener('keydown', esc, true); }, 0); });
    wrap.append(btn0, pop); return wrap;
  }
  window.reportMenu = reportMenu;
  window.ReportGen = { build, download, data, reportCard, _i: { zip, esc, run, para, bullet, table, image, W_NS, DOCX_STYLES, E, SW, SH, MG, P_NS, textBox, pic, tbl, slide, head, foot, ap, rp, resetSid: () => { sid = 1; }, resetImg: () => { imgSeq = 0; }, xCell, colL, ST, XSTYLES, chartPng, sumA2, CTYS, lvlTxt, buildXlsx, xlsxSheets, xlsxPack, pptxParts: null, n0, n1, n2 } };
  window.reportCard = reportCard;
})();
