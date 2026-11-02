'use strict';
// 종합 분석 보고서 생성기: Executive Summary(의견) → 상세 분석 → 부록(그래프+해석). Word·PowerPoint·Excel 공통 구조.
(function () {
  const I = ReportGen._i, esc = I.esc, n0 = I.n0, n1 = I.n1, n2 = I.n2, sum = I.sumA2;
  const isEn = () => window.I18N && I18N.lang === 'en', T = (ko, en) => isEn() ? en : ko;
  const OP = { BUY: { fill: 'FDECEA', acc: 'D93025', soft: 'F8D7D3' }, HOLD: { fill: 'FFF6E0', acc: 'C98A00', soft: 'FBE9B7' }, SELL: { fill: 'E7F6EC', acc: '1E8E3E', soft: 'CDEBD6' }, NA: { fill: 'EEF1F5', acc: '6E6E73', soft: 'DDE2E8' } };
  const opOf = m => OP[m.hasKR ? m.dec.code : 'NA'];
  const wlen = s => { let n = 0; for (const ch of String(s)) n += /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3\u3000-\u9fff\uff00-\uffef]/.test(ch) ? 1 : .56; return n; };

  // ── 그래프 생성 ────────────────────────────────────────────
  async function graphs(d, m) {
    const k = m.k, out = [], ids = d.ids, MON = MONTHS.slice();
    const png = async (node, w, legend) => I.chartPng(node, w, legend);
    const zone = r => r > 1 ? 'er' : r > 1 - k.bufPct ? 'wn' : 'ok';
    const marks = [{ v: Math.round((1 - k.bufPct) * 100), c: 'var(--yl)', label: T('안전선', 'Safety') }, { v: 100, c: 'var(--rd)', label: T('한도', 'Limit') }];
    const builders = {
      G1: async () => { const items = k.rows.map(r => ({ label: r.id + ' ' + r.site, v: r.proj.base / r.annual * 100, c: SC[zone(r.proj.base / r.annual)], txt: Math.round(r.proj.base / r.annual * 100) + '%' })); items.push({ label: T('한국 합계', 'Korea total'), v: k.P.base / k.A * 100, c: SC[zone(k.P.base / k.A)], txt: Math.round(k.P.base / k.A * 100) + '%' }); return png(hbarChart({ items, marks, max: Math.max(115, ...items.map(i => i.v + 8)), fmt: v => v + '%', L: 104, W: 760 }), 760); },
      G2: async () => {
        const T0 = D.TODAY, mEnd = i => D.di('2026-' + String(i + 1).padStart(2, '0') + '-01') + D.dim(i) - 1, cumA = e => sum(k.rows.map(r => D.em(r.id, 0, e))), cumT = e => sum(k.rows.map(r => D.target(r.id, 0, e, 'em'))), cumP = e => sum(k.rows.map(r => r.ytd + r.fac * D.target(r.id, T0 + 1, e, 'em')));
        const cm = D.mon(T0), x = Array.from({ length: 12 }, (_, i) => (i + 1) + (isEn() ? '' : '월')), act = x.map((_, i) => i < cm ? cumA(mEnd(i)) : i === cm ? cumA(T0) : null), proj = x.map((_, i) => i < cm ? null : i === cm ? cumA(T0) : cumP(Math.min(364, mEnd(i)))), tg = x.map((_, i) => cumT(Math.min(364, mEnd(i))));
        const node = lineChart({ x, h: 250, zero: true, series: [{ n: T('누적 실적', 'Cumulative actual'), c: 'var(--cy)', d: act, f: v => n0(v) }, { n: T('연말 전망', 'Year-end outlook'), c: 'var(--yl)', d: proj, dash: true, f: v => n0(v) }, { n: T('목표 누적선', 'Cumulative target'), c: 'var(--mut)', d: tg, dash: true, f: v => n0(v) }], hl: [{ v: k.A, c: 'var(--rd)', label: T('연간 목표', 'Annual target') }], fl: v => n0(v) });
        return png(node, 760, [{ n: T('누적 실적', 'Cumulative actual'), c: 'var(--cy)' }, { n: T('연말 전망', 'Year-end outlook'), c: 'var(--yl)', dash: true }, { n: T('목표 누적선', 'Cumulative target'), c: 'var(--mut)', dash: true }, { n: T('연간 목표', 'Annual target'), c: 'var(--rd)', dash: true }]);
      },
      G3: async () => { const items = [['base', T('기본(최근 30일 속도)', 'Base (last-30-day pace)')], ['up', T('배출 +10%', 'Emissions +10%')], ['stress', T('스트레스(남은 기간 110%)', 'Stress (110% of target)')]].map(([key, lb]) => ({ label: lb, v: k.P[key] / k.A * 100, c: SC[zone(k.P[key] / k.A)], txt: Math.round(k.P[key] / k.A * 100) + '%' })); return png(hbarChart({ items, marks, max: Math.max(115, ...items.map(i => i.v + 8)), fmt: v => v + '%', L: 150, W: 760 }), 760); },
      G4: async () => {
        const S_ = MKT.series.slice(-22), x = S_.map(r => r.d.slice(5)), series = [{ n: T('종가', 'Close'), c: 'var(--cy)', d: S_.map(r => r.c), f: v => n0(v) }, { n: T('5일 평균', '5-day avg'), c: '#f5a524', d: S_.map(r => r.m5), f: v => n0(v) }, { n: T('20일 평균', '20-day avg'), c: '#a06af5', d: S_.map(r => r.m20), f: v => n0(v) }];
        return png(lineChart({ x, h: 250, zero: false, series, fl: v => n0(v) }), 760, series.map(s => ({ n: s.n, c: s.c })));
      },
      G6: async () => png(hbarChart({ items: d.plants.map(r => ({ label: r.id + ' ' + r.site, v: r.usage * 100, c: SC[D.lvl(r.usage)], txt: Math.round(r.usage * 100) + '%' })), marks: [{ v: 70, c: 'var(--yl)', label: T('주의', 'Caution') }, { v: 90, c: 'var(--rd)', label: T('경고', 'Warning') }], max: 110, fmt: v => v + '%', L: 104, W: 760 }), 760),
      G7: async () => png(stackedArea({ x: MON.map((_, i) => (i + 1) + (isEn() ? '' : '월')), series: d.c.rows.map((r, i) => ({ n: r.n, c: r.c, d: MON.map(([a, b]) => srcCalc(ids, a, b).rows[i].e) })) }), 760, d.c.rows.map(r => ({ n: r.n, c: r.c }))),
      G8: async () => png(donutChart({ parts: d.c.rows.map(r => ({ n: r.n, v: r.e, c: r.c })), center: n1(d.c.tot), sub: 'tCO₂' }), 300),
      G9: async () => { const ct = d.byC.map(x => ({ n: x.n, q: srcCalc(D.P.filter(p => p.c === x.n).map(p => p.id), S.a, S.b) })), items = ct.flatMap(x => [{ label: x.n + T(' 위치', ' location'), v: x.q.s1 + x.q.s2, c: CC[x.n] }, { label: x.n + T(' 시장', ' market'), v: x.q.s1 + x.q.s2m, c: CC[x.n] }]); return png(hbarChart({ items, fmt: v => n0(v), L: 110, rh: 24, W: 760 }), 760); }
    };
    for (const g of m.graphs) { const f = builders[g.key]; if (!f) continue; try { const img = await f(); out.push({ g, img }); } catch (e) { out.push({ g, img: null, err: String(e && e.message || e) }); } }
    return out;
  }

  // ── DOCX ───────────────────────────────────────────────────
  const WP = (t, o = {}) => I.para(t, o), RUN = I.run;
  const lp = (label, text, o = {}) => `<w:p><w:pPr><w:spacing w:after="${o.after == null ? 100 : o.after}"/>${o.ind ? `<w:ind w:left="${o.ind}"/>` : ''}</w:pPr>${RUN(label + '  ', { b: true, color: o.lc || '0071E3', sz: o.sz })}${RUN(text, { sz: o.sz })}</w:p>`;
  const pageBreak = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>';
  function callout(op, label, text, sub) {
    const W = 9638, cell = `<w:tc><w:tcPr><w:tcW w:w="${W}" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="${op.fill}"/></w:tcPr>${WP(label, { b: true, sz: 34, color: op.acc, after: 80 })}${WP(text, { sz: 22, after: 80 })}${sub ? WP(sub, { sz: 18, color: '6E6E73', after: 40 }) : ''}</w:tc>`;
    return `<w:tbl><w:tblPr><w:tblW w:w="${W}" w:type="dxa"/><w:tblBorders><w:left w:val="single" w:sz="48" w:space="0" w:color="${op.acc}"/></w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="160" w:type="dxa"/><w:left w:w="240" w:type="dxa"/><w:bottom w:w="120" w:type="dxa"/><w:right w:w="200" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid><w:gridCol w:w="${W}"/></w:tblGrid><w:tr>${cell.replace('<w:tc>', '<w:tc>')}</w:tr></w:tbl>${WP('', { after: 120 })}`;
  }
  function dTable(t) { const n = t.head.length, first = n >= 6 ? 1900 : n === 5 ? 2400 : 2800, rest = Math.floor((9638 - first) / (n - 1)), widths = [first, ...Array(n - 1).fill(rest)], al = t.al.split('').map(c => c === 'l' ? 'l' : 'r'); return I.table([t.head, ...t.rows], widths, al); }
  function docxBody(d, m, gi, figNo) {
    const k = m.k, op = opOf(m), B = [];
    B.push(WP(T('AMA 탄소·에너지 비용 종합 분석 보고서', 'AMA Carbon & Energy Cost Summary Analysis Report'), { style: 'Title' }), WP(`${d.name} · ${d.period} · ${d.basis} · ${T('기준일', 'As of')} ${m.asof}`, { sz: 24, color: '6E6E73', after: 60 }), WP(T('시안(모의 자료)으로 만든 예시 보고서입니다. 실제 운영 데이터가 아니며 투자 권유가 아닙니다.', 'An example report built from mock data in a design draft. Not actual operating data and not investment advice.'), { sz: 18, color: '86868B', after: 240 }));
    B.push(WP('1. Executive Summary', { style: 'Heading1' }), callout(op, m.label, m.headline, T('신뢰도: ', 'Confidence: ') + m.conf));
    B.push(I.table([[T('지표', 'Indicator'), T('값', 'Value'), T('비고', 'Note')], ...m.kpi.slice(1).map(r => [r[0], r[1], r[2]])], [3200, 3200, 3238], ['l', 'r', 'l']));
    B.push(WP(T('1.1 종합 의견의 근거 6가지', '1.1 Six grounds for the opinion'), { style: 'Heading2' }));
    m.es.forEach((e, i) => B.push(lp(`${i + 1}. ${e.title}`, e.point)));
    B.push(WP(T('1.2 실행 권고', '1.2 Recommended actions'), { style: 'Heading2' }), ...m.actions.map((a, i) => lp(`${i + 1}.`, a, { lc: '1D1D1F' })));
    if (m.triggers.length) B.push(WP(T('1.3 의견이 바뀌는 조건', '1.3 Conditions that change the opinion'), { style: 'Heading2' }), ...m.triggers.map(t => I.bullet(t)));
    B.push(pageBreak, WP(T('2. 상세 분석', '2. Detailed analysis'), { style: 'Heading1' }), WP(T('Executive Summary의 근거 6가지를 순서대로 자료와 함께 설명합니다.', 'Each of the six grounds in the Executive Summary is explained in order with supporting data.'), { sz: 20, color: '6E6E73' }));
    m.details.forEach((dt, i) => {
      B.push(WP(`2.${i + 1} ${dt.id}. ${dt.title}`, { style: 'Heading2' }), ...dt.paras.filter(Boolean).map(p => WP(p, { after: 120 })));
      if (dt.table) B.push(dTable(dt.table));
      const fl = (dt.figs || []).map(f => figNo[f]).filter(Boolean); if (fl.length) B.push(WP(T('관련 그래프: ', 'Related figures: ') + fl.map(x => (isEn() ? 'Figure A-' : '그림 A-') + x).join(', ') + T(' (부록 A)', ' (Appendix A)'), { sz: 18, color: '0071E3', after: 200 }));
    });
    B.push(WP(T('3. 방법·가정·유의사항', '3. Method, assumptions and caveats'), { style: 'Heading1' }), I.bullet(T('연말 예상 = 올해 누적 + (최근 30일 목표 대비 소진 속도 × 남은 기간 목표 배출). 연간 목표(예시)를 할당량 대용으로 사용했습니다.', 'Year-end estimate = YTD + (last-30-day usage rate × remaining target). The annual target (example) is used as an allocation proxy.')), I.bullet(T(`안전 여유 = 불확실도×3 + 자료 미수신율 + (한도 근접 공장 있으면 3%p), 최소 8% → ${(k.bufPct * 100).toFixed(1)}%.`, `Safety margin = uncertainty×3 + missing-data rate + (3 pt if a plant is near its limit), minimum 8% → ${(k.bufPct * 100).toFixed(1)}%.`)), I.bullet(T('의견 규칙: 기본 과부족<0이면 매수, 안전 여유 미만이거나 스트레스에서 부족이면 관망, 안전 여유 초과분만 매도 검토.', 'Opinion rules: buy if the base gap < 0; hold if inside the safety margin or short under stress; sell only the amount above the safety margin.')), I.bullet(T('KAU26 가격은 KRX 일 종가(2026-10-28 조회)이며 실시간이 아닙니다. 최근 5거래일 이전 구간은 모의 보강입니다.', 'KAU26 prices are KRX daily closes (as of 2026-10-28), not real-time. Points older than five sessions are simulated.')), I.bullet(T('이 보고서는 디자인 시안의 모의 자료로 만든 예시이며 법령 원문·확정 할당량과 대조 전입니다.', 'This report is an example from mock data and has not been reconciled with legal texts or confirmed allocations.')));
    B.push(pageBreak, WP(T('부록 A. 그래프와 해석', 'Appendix A. Graphs and interpretation'), { style: 'Heading1' }), WP(T('각 그래프는 무엇을 보여주는지, 어떻게 읽는지, 종합 의견과 어떻게 연결되는지, 주의할 점을 함께 적었습니다.', 'For each graph: what it shows, how to read it, how it connects to the opinion, and cautions.'), { sz: 20, color: '6E6E73' }));
    gi.forEach((x, i) => {
      const g = x.g, no = i + 1; B.push(WP(`${isEn() ? 'Figure A-' : '그림 A-'}${no}. ${g.title}`, { style: 'Heading2' }));
      if (x.img) B.push(I.image('rIdG' + no, x.img.w, x.img.h, g.key === 'G8' ? 2900000 : 5900000, g.title));
      B.push(lp(T('분석 대상', 'Scope'), g.what, { sz: 19 }), lp(T('분석 개요', 'Overview'), g.read, { sz: 19 }), ...(g.numbers ? [lp(T('핵심 지표', 'Key metrics'), g.numbers, { sz: 19 })] : []), lp(T('시사점', 'Implications'), g.insight, { sz: 19, lc: op.acc }), lp(T('유의사항', 'Caveats'), g.caution, { sz: 19, lc: '86868B', after: g.watch ? 80 : 220 }), ...(g.watch ? [lp(T('후속 과제', 'Next steps'), g.watch, { sz: 19, lc: '86868B', after: 220 })] : []));
    });
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${I.W_NS}><w:body>${B.join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>`;
  }
  function buildDocx(d, m, gi, figNo) {
    I.resetImg(); const R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships', ok = gi.map((x, i) => ({ x, no: i + 1 })).filter(o => o.x.img);
    const files = [
      { name: '[Content_Types].xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>' },
      { name: '_rels/.rels', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>' },
      { name: 'docProps/core.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>AMA 탄소·에너지 비용 종합 분석 보고서(시안)</dc:title><dc:creator>AMA</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}</dcterms:created></cp:coreProperties>` },
      { name: 'docProps/app.xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>AMA Report Generator</Application></Properties>' },
      { name: 'word/styles.xml', data: I.DOCX_STYLES.replace(/<w:lang [^>]*\/>/, isEn() ? '<w:lang w:val="en-US" w:eastAsia="ko-KR"/>' : '<w:lang w:val="ko-KR" w:eastAsia="ko-KR"/>') },
      { name: 'word/_rels/document.xml.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdSt" Type="${R}/styles" Target="styles.xml"/>${ok.map(o => `<Relationship Id="rIdG${o.no}" Type="${R}/image" Target="media/g${o.no}.png"/>`).join('')}</Relationships>` },
      { name: 'word/document.xml', data: docxBody(d, m, gi, figNo) }, ...ok.map(o => ({ name: `word/media/g${o.no}.png`, data: o.x.img.bytes }))];
    return I.zip(files, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
  }

  // ── PPTX ───────────────────────────────────────────────────
  const E = I.E, SW = I.SW, SH = I.SH, MG = I.MG, ap = I.ap;
  function fitSz(paras, wIn, hIn, sizes = [16, 15, 14, 13, 12, 11, 10, 9]) { for (const sz of sizes) { const per = wIn * 72 / sz; let lines = 0; paras.forEach(p => { lines += Math.max(1, Math.ceil(wlen(p) / (per * .94))); }); const hh = (lines * sz * 1.32 + paras.length * sz * .45) / 72; if (hh <= hIn) return sz; } return sizes[sizes.length - 1]; }
  function sp(sz) { return ap(' ', { sz }); }
  function tbl2(x, y, widths, rows, aligns, rowH, fs) {
    const id = (I.pptxSid = (I.pptxSid || 100) + 1), w = sum(widths), hh = rowH * rows.length, no = t => `<a:${t} w="0"><a:noFill/></a:${t}>`, ln = (t, c, wd) => `<a:${t} w="${wd}" cap="flat" cmpd="sng"><a:solidFill><a:srgbClr val="${c}"/></a:solidFill></a:${t}>`;
    const cell = (t, ci, hd) => `<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="${aligns[ci] === 'r' ? 'r' : 'l'}"/><a:r>${I.rp({ sz: fs, b: hd, color: hd ? '6E6E73' : '1D1D1F' })}<a:t>${esc(t)}</a:t></a:r></a:p></a:txBody><a:tcPr marL="54864" marR="54864" marT="27432" marB="27432" anchor="ctr">${no('lnL')}${no('lnR')}${no('lnT')}${ln('lnB', hd ? 'D2D2D7' : 'E5E5EA', hd ? 12700 : 6350)}<a:noFill/></a:tcPr></a:tc>`;
    return `<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="${id}" name="Table ${id}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${hh}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1"/><a:tblGrid>${widths.map(v => `<a:gridCol w="${v}"/>`).join('')}</a:tblGrid>${rows.map((r, ri) => `<a:tr h="${rowH}">${r.map((t, ci) => cell(t, ci, ri === 0)).join('')}</a:tr>`).join('')}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;
  }
  function buildPptx(d, m, gi, figNo) {
    const k = m.k, op = opOf(m), W2 = SW - 2 * MG, slides = [], rels = [], R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships', T_ = window.RPT_TPL;
    const add = (shapes, imgs) => { slides.push(I.slide(shapes)); rels.push(imgs || []); };
    const foot = I.foot(d), mk = (...a) => I.textBox(...a), hd = (t, s) => I.head(t, s);
    const reset = () => { I.resetSid(); I.pptxSid = 100; };
    // ── 템플릿 양식(Environment: 상단 짙은 초록 내비 줄, 연회색 둥근 그림자 카드, 큰 초록 숫자, 둥근 모서리 초록 패널, 가벼운 제목) ──
    const C = { dark: '2D5A34', deep: '1F4A2A', mid: '8DB38A', pale: 'E6EFE4', card: 'F2F2F2', ink: '1A1A1A', mut: '8E968E', line: 'E3E6E3', hero: '14403F' };
    const pid = () => (I.pptxSid = (I.pptxSid || 100) + 1);
    const SHD = '<a:effectLst><a:outerShdw blurRad="88900" dist="38100" dir="5400000" algn="t" rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="16000"/></a:srgbClr></a:outerShdw></a:effectLst>';
    const bx = (x, y, w, h, paras, o = {}) => { const id = pid(), prst = o.prst || (o.round ? 'roundRect' : 'rect'), geom = `<a:prstGeom prst="${prst}">${prst === 'roundRect' ? `<a:avLst><a:gd name="adj" fmla="val ${o.round || 8000}"/></a:avLst>` : '<a:avLst/>'}</a:prstGeom>`, fill = o.fill ? `<a:solidFill><a:srgbClr val="${o.fill}"/></a:solidFill>` : '<a:noFill/>', ln = o.line ? `<a:ln w="${o.lw || 12700}"><a:solidFill><a:srgbClr val="${o.line}"/></a:solidFill></a:ln>` : '<a:ln><a:noFill/></a:ln>';
      return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${esc(o.name || 'Shape ' + id)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${h}"/></a:xfrm>${geom}${fill}${ln}${o.shadow ? SHD : ''}</p:spPr><p:txBody><a:bodyPr wrap="square" lIns="${o.pad == null ? 91440 : o.pad}" tIns="${o.padT == null ? 45720 : o.padT}" rIns="${o.pad == null ? 91440 : o.pad}" bIns="45720" anchor="${o.anchor || 't'}"><a:noAutofit/></a:bodyPr><a:lstStyle/>${(paras && paras.length ? paras : [ap(' ', { sz: 8 })]).join('')}</p:txBody></p:sp>`; };
    let pn = 1;
    // 상단 내비 줄: 왼쪽 문서명, 오른쪽 Page 번호 + 현재 장 알약
    const nav = sec => { pn++; return [bx(0, 0, SW, E(.3), [], { fill: C.dark, name: 'Nav bar' }), mk(E(.4), E(.02), E(4), E(.26), [ap('AMA · ' + T('종합 분석 보고서', 'Summary Analysis Report'), { sz: 8, color: 'FFFFFF' })], { name: 'Nav left' }), mk(SW - E(4.7), E(.02), E(1.0), E(.26), [ap('Page ' + pn, { sz: 8, color: 'FFFFFF', align: 'r' })], { name: 'Page' }), bx(SW - E(3.5), E(.04), E(1.9), E(.22), [ap(sec, { sz: 8, b: 1, color: C.deep, align: 'ctr' })], { fill: C.mid, round: 20000, pad: 0, padT: 0, anchor: 'ctr', name: 'Section pill' })]; };
    const ttl = (t, sub) => [mk(MG, E(.5), W2, E(.62), [ap(t, { sz: 26, b: 1, color: C.ink })], { name: 'Title' }), sub ? mk(MG, E(1.1), W2, E(.32), [ap(sub, { sz: 10, b: 1, color: C.ink })], { name: 'Subtitle' }) : ''];
    const card = (x, y, w, h, paras, o = {}) => bx(x, y, w, h, paras, { fill: C.card, round: 7000, shadow: 1, pad: E(.18), padT: E(.14), ...o });
    const tbl3 = (x, y, widths, rows, aligns, rowH, fs) => {
      const id = pid(), w = sum(widths), hh = rowH * rows.length, no = t => `<a:${t} w="0"><a:noFill/></a:${t}>`, ln = (t, c, wd) => `<a:${t} w="${wd}" cap="flat" cmpd="sng"><a:solidFill><a:srgbClr val="${c}"/></a:solidFill></a:${t}>`;
      const cell = (t, ci, ri) => { const hd = ri === 0, fill = hd ? C.dark : ri % 2 === 0 ? C.card : 'FFFFFF'; return `<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="${aligns[ci] === 'r' ? 'r' : 'l'}"/><a:r>${I.rp({ sz: fs, b: hd || ci === 0, color: hd ? 'FFFFFF' : (ci === 0 ? C.dark : C.ink) })}<a:t>${esc(t)}</a:t></a:r></a:p></a:txBody><a:tcPr marL="64008" marR="64008" marT="27432" marB="27432" anchor="ctr">${no('lnL')}${no('lnR')}${no('lnT')}${ln('lnB', C.line, 6350)}<a:solidFill><a:srgbClr val="${fill}"/></a:solidFill></a:tcPr></a:tc>`; };
      return `<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="${id}" name="Table ${id}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="${x}" y="${y}"/><a:ext cx="${w}" cy="${hh}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>${widths.map(v => `<a:gridCol w="${v}"/>`).join('')}</a:tblGrid>${rows.map((r, ri) => `<a:tr h="${rowH}">${r.map((t, ci) => cell(t, ci, ri)).join('')}</a:tr>`).join('')}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;
    };
    const hero = (t1, t2, extra = []) => [bx(0, 0, SW, SH, [], { fill: C.hero, name: 'Hero bg' }), bx(0, Math.round(SH * .62), SW, Math.round(SH * .38), [], { fill: C.deep, name: 'Field' }), bx(0, Math.round(SH * .56), SW, Math.round(SH * .12), [], { fill: C.dark, round: 50000, name: 'Hill' }), mk(E(1), E(1.9), SW - E(2), E(1.2), [ap(t1, { sz: 44, b: 1, color: 'FFFFFF', align: 'ctr' })], { name: 'Hero title' }), mk(E(1), E(3.05), SW - E(2), E(.5), [ap(t2, { sz: 13, color: 'DCE8DC', align: 'ctr' })], { name: 'Hero sub' }), ...extra];
    // 1 표지
    reset(); add([...hero(T('종합 분석 보고서', 'Summary Analysis Report'), 'AMA ' + T('탄소·에너지 비용', 'Carbon & Energy Cost') + ' · ' + d.name), mk(E(1), SH - E(1.2), SW - E(2), E(.8), [ap(`${d.period} · ${d.basis} · ${T('기준일', 'As of')} ${m.asof}`, { sz: 10, color: 'DCE8DC', align: 'ctr' }), ap(T('시안(모의 자료)으로 만든 예시이며 투자 권유가 아닙니다.', 'An example built from mock data; not investment advice.'), { sz: 10, color: 'B7C9B7', align: 'ctr' })])]);
    // 2 종합 의견: 왼쪽 제목·본문, 오른쪽 둥근 초록 패널(의견), 아래 회색 KPI 카드 4개
    reset(); { const hs = fitSz([m.headline], 4.6, 2.4, [15, 14, 13, 12, 11]), cards = [m.kpi[1], m.kpi[2], m.hasKR && m.dec.code === 'BUY' ? m.kpi[4] : m.kpi[3], m.kpi[5]], pw = E(6.6), px = SW - MG - pw, cw = Math.round((W2 - 3 * E(.2)) / 4);
      add([...nav('Executive Summary'), ...ttl('Executive Summary', T('지금 탄소(배출권)를 사야 하는가, 안 사도 되는가, 팔아도 되는가', 'Should we buy, not buy, or sell carbon allowances now?')), mk(MG, E(1.7), E(5.2), E(1.1), [ap(T('종합 의견', 'Overall opinion'), { sz: 10, color: C.mut }), ap(m.label, { sz: 20, b: 1, color: C.dark })], { name: 'Opinion label' }), mk(MG, E(3.0), E(5.2), E(.5), [ap(T('신뢰도: ', 'Confidence: ') + m.conf, { sz: 11, b: 1, color: C.ink })]), bx(px, E(1.6), pw, E(2.55), [ap(m.headline, { sz: hs, color: 'FFFFFF' })], { fill: C.dark, round: 9000, pad: E(.3), padT: E(.3), anchor: 'ctr', name: 'Opinion panel' }), ...cards.map((c, i) => card(MG + i * (cw + E(.2)), E(4.5), cw, E(1.75), [ap(c[0], { sz: 10, color: C.mut }), ap(c[1], { sz: c[1].length > 14 ? 15 : 24, color: i % 2 ? C.mid : C.dark }), ap(c[2] || ' ', { sz: 9, color: C.mut })], { name: 'KPI ' + (i + 1) })), foot]); }
    // 3 근거 6가지: Carbon Emissions 01/02/03 카드
    reset(); { const cw = Math.round((W2 - 2 * E(.25)) / 3), chh = E(2.2); add([...nav(T('근거', 'Grounds')), ...ttl(T('종합 의견의 근거 6가지', 'Six grounds for the opinion'), T('각 근거는 이어지는 상세 분석에서 자료로 설명합니다', 'Each ground is explained with data in the detailed analysis')), ...m.es.map((e, i) => { const x = MG + (i % 3) * (cw + E(.25)), y = E(1.6) + Math.floor(i / 3) * (chh + E(.2)), sz = fitSz([e.point], cw / 914400 - .4, chh / 914400 - .95, [11, 10, 9]); return card(x, y, cw, chh, [ap(String(i + 1).padStart(2, '0') + '.', { sz: 24, color: i % 2 ? C.mid : C.dark, align: 'ctr' }), ap(e.title, { sz: 11, b: 1, color: C.ink, align: 'ctr' }), ap(e.point, { sz, color: C.mut, align: 'ctr' })], { name: e.id }); }), foot]); }
    // 4 실행 권고 / 조건: Our Responsibility 스타일(큰 초록 숫자 + 가는 선)
    reset(); { const half = Math.round((W2 - E(.5)) / 2), a = m.actions, c = m.triggers, ra = Math.min(E(.95), Math.floor(E(4.4) / Math.max(1, a.length))), rc = Math.min(E(.95), Math.floor(E(4.4) / Math.max(1, c.length))), sa = fitSz(a, half / 914400 - 1.0, ra / 914400 - .1, [13, 12, 11, 10, 9]), sc = fitSz(c, half / 914400 - 1.0, rc / 914400 - .1, [13, 12, 11, 10, 9]);
      const rowsOf = (arr, x, rh, sz, col) => arr.flatMap((t, i) => [mk(x, E(1.75) + i * rh, E(.9), rh - E(.08), [ap(String(i + 1).padStart(2, '0'), { sz: 24, color: col })], { name: 'Num ' + (i + 1) }), mk(x + E(.9), E(1.75) + i * rh, half - E(.9), rh - E(.08), [ap(t, { sz, color: C.ink })], { name: 'Item ' + (i + 1) }), bx(x, E(1.75) + (i + 1) * rh - E(.06), half, E(.012), [], { fill: C.line, name: 'Line' })]);
      add([...nav(T('실행 권고', 'Actions')), ...ttl(T('실행 권고와 의견이 바뀌는 조건', 'Recommended actions and conditions that change the opinion')), mk(MG, E(1.35), half, E(.35), [ap(T('실행 권고', 'Recommended actions'), { sz: 12, b: 1, color: C.dark })]), ...rowsOf(a, MG, ra, sa, C.dark), mk(MG + half + E(.5), E(1.35), half, E(.35), [ap(T('의견이 바뀌는 조건', 'Conditions that change the opinion'), { sz: 12, b: 1, color: C.dark })]), ...rowsOf(c, MG + half + E(.5), rc, sc, C.mid), foot]); }
    // 5~ 근거 장표: ES마다 ① 설명+표+한눈에 보기 ② 그래프 장표(그래프 + 읽는 법·핵심 수치·해석·주의·다음 점검)
    const gm = {}; gi.forEach((x, i) => { gm[x.g.id] = Object.assign({ no: i + 1 }, x); });
    const tag = (x, y, w, t, fill) => bx(x, y, w, E(.26), [ap(t, { sz: 8, b: 1, color: fill === C.mid ? C.deep : 'FFFFFF', align: 'ctr' })], { fill, round: 50000, pad: 0, padT: 0, anchor: 'ctr', name: 'Tag' });
    const txt = (sh, dt, x, y, w, h, mx = 12) => { const ps = dt.paras.filter(Boolean), sz = fitSz(ps, w / 914400, h / 914400, [mx, 11, 10, 9, 8]); sh.push(mk(x, y, w, h, ps.flatMap(p => [ap(p, { sz, color: C.ink }), sp(4)]), { name: 'Text' })); };
    const tb = (sh, dt, x, y, w, rowH, fs) => { const t = dt.table, rows = [t.head, ...t.rows].slice(0, 9), wt = t.head.map((_, c) => Math.min(34, Math.max(5, ...rows.map(r => wlen(String(r[c] == null ? '' : r[c])))))), tot = wt.reduce((q, v) => q + v, 0), ws = wt.map(v => Math.max(E(.55), Math.round(w * v / tot))), sc = w / ws.reduce((q, v) => q + v, 0); sh.push(tbl3(x, y, ws.map(v => Math.round(v * sc)), rows, t.al.split(''), rowH, fs)); };
    const num = (sh, i) => sh.push(mk(SW - MG - E(1.6), E(.36), E(1.6), E(.7), [ap(String(i + 1).padStart(2, '0'), { sz: 34, color: C.mid, align: 'r' })], { name: 'Big number' }));
    // 한눈에 보기: 큰 숫자 카드 3장
    const stats = (sh, dt, x, y, w, h) => { const st = (dt.stats || []).filter(r => r && r[1] !== ''); if (!st.length) return; const cw = Math.round((w - (st.length - 1) * E(.2)) / st.length); st.forEach((r, i) => sh.push(card(x + i * (cw + E(.2)), y, cw, h, [ap(r[0], { sz: 10, color: C.mut }), ap(r[1], { sz: String(r[1]).length > 12 ? 16 : 24, color: i % 2 ? C.mid : C.dark }), ap(r[2] || ' ', { sz: 9, color: C.mut })], { name: 'Stat ' + (i + 1), anchor: 'ctr' }))); };
    // 설명 카드(왼쪽 포인트 막대 + 라벨 + 본문)
    const note = (sh, x, y, w, h, label, text, tone, mx = 11) => { const sz = fitSz([text], w / 914400 - .35, h / 914400 - .38, [mx, 10, 9, 8, 7]); sh.push(card(x, y, w, h, [ap(label, { sz: sz + 1, b: 1, color: C.dark }), ap(text, { sz, color: C.ink })], { name: 'Note ' + label, pad: E(.2), padT: E(.08) })); sh.push(bx(x, y + E(.1), E(.06), h - E(.2), [], { fill: tone, name: 'Accent' })); };
    const imgCard = (sh, imgs, e, x, y, w, h) => { sh.push(card(x, y, w, h, [], { round: 4000, name: 'Fig ' + e.g.id, pad: 0 })); sh.push(mk(x + E(.15), y + E(.08), w - E(1.1), E(.3), [ap(e.g.title, { sz: 10, b: 1, color: C.dark })], { name: 'Fig title' })); sh.push(tag(x + w - E(.95), y + E(.1), E(.8), isEn() ? 'Fig. ' + e.g.id : '그래프 ' + e.g.id, C.mid));
      if (e.img) { const aw = w - E(.3), ah = h - E(.55); let iw = aw, ih = Math.round(aw * e.img.h / e.img.w); if (ih > ah) { ih = ah; iw = Math.round(ah * e.img.w / e.img.h); } const rid = 'rIdI' + (imgs.length + 1); sh.push(I.pic(rid, x + Math.round((w - iw) / 2), y + E(.45) + Math.round((ah - ih) / 2), iw, ih, e.g.title)); imgs.push([rid, 'g' + e.no]); } };
    const items = e => [[T('분석 개요', 'Overview'), e.g.read, C.dark], [T('핵심 지표', 'Key metrics'), e.g.numbers || e.g.what, C.mid], [T('시사점', 'Implications'), e.g.insight, C.dark], [T('유의사항', 'Caveats'), e.g.caution, C.mid], [T('후속 과제', 'Next steps'), e.g.watch || '', C.dark]].filter(r => r[1]);
    // 큰 그래프 + 오른쪽 설명 카드 (모양이 정사각·보통 비율일 때)
    const figBig = (dt, i, id) => { const e = gm[id]; if (!e) return; reset(); const sh = [...nav(dt.id + ' · ' + T('그래프', 'Graph')), ...ttl(`${dt.id}. ${dt.title}`, e.g.what)], im = []; num(sh, i); const lw = E(6.9), rx = MG + lw + E(.25), rw = W2 - lw - E(.25), ch = Math.min(E(3.9), e.img ? Math.round((lw - E(.3)) * e.img.h / e.img.w) + E(.65) : E(3.0));
      imgCard(sh, im, e, MG, E(1.65), lw, ch); const it = items(e), ny = E(1.65) + ch + E(.15); if (it[1]) note(sh, MG, ny, lw, E(6.85) - ny, it[1][0], it[1][1], it[1][2], 13); const rest = it.filter((r, j) => j !== 1), gh = Math.floor((E(5.2) - (rest.length - 1) * E(.12)) / rest.length); rest.forEach((r, j) => note(sh, rx, E(1.65) + j * (gh + E(.12)), rw, gh, r[0], r[1], r[2], 13)); sh.push(foot); add(sh, im); };
    // 가로로 긴 그래프 + 아래 5칸 설명
    const figWide = (dt, i, id) => { const e = gm[id]; if (!e) return; reset(); const sh = [...nav(dt.id + ' · ' + T('그래프', 'Graph')), ...ttl(`${dt.id}. ${dt.title}`, e.g.what)], im = []; num(sh, i); const ch = e.img ? Math.min(E(2.9), Math.round((W2 - E(.4)) * e.img.h / e.img.w) + E(.65)) : E(2.4);
      imgCard(sh, im, e, MG, E(1.65), W2, ch); const it = items(e), n = it.length, cw = Math.round((W2 - (n - 1) * E(.15)) / n), ny = E(1.65) + ch + E(.18), nh = E(6.9) - ny; it.forEach((r, j) => note(sh, MG + j * (cw + E(.15)), ny, cw, nh, r[0], r[1], r[2], 11)); sh.push(foot); add(sh, im); };
    const first = (dt, i) => { reset(); const sh = [...nav(dt.id), ...ttl(`${dt.id}. ${dt.title}`, T('설명 · 자료 · 한눈에 보기', 'Explanation, data and at-a-glance numbers'))]; num(sh, i); const lw = E(4.6), rw = W2 - lw - E(.3); txt(sh, dt, MG, E(1.65), lw, E(3.7), 11); { const nr = Math.min(9, dt.table.rows.length + 1); tb(sh, dt, MG + lw + E(.3), E(1.7), rw, E(Math.min(.55, 3.6 / nr)), dt.table.head.length >= 7 ? 10 : 11); } stats(sh, dt, MG, E(5.5), W2, E(1.3)); sh.push(foot); add(sh, []); };
    const FIG = { ES1: [['G2', figBig], ['G7', figBig]], ES2: [['G1', figWide]], ES3: [['G6', figBig]], ES4: [['G3', figWide]], ES5: [['G4', figBig]], ES6: [['G9', figWide], ['G8', figBig]] };
    m.details.forEach((dt, i) => { first(dt, i); (FIG[dt.id] || []).forEach(([id, fn]) => fn(dt, i, id)); });
    // 방법·유의: Call to Action 스타일(큰 회색 카드 안에 번호 원 목록)
    reset(); { const ps = [T('연말 예상 = 올해 누적 + (최근 30일 목표 대비 소진 속도 × 남은 기간 목표). 연간 목표(예시)를 할당량 대용으로 사용했습니다.', 'Year-end estimate = YTD + (last-30-day usage rate × remaining target); the annual target (example) is the allocation proxy.'), T(`안전 여유 ${(k.bufPct * 100).toFixed(1)}% = 불확실도×3 + 자료 미수신율 + 한도 근접 공장 가산(3%p), 최소 8%.`, `Safety margin ${(k.bufPct * 100).toFixed(1)}% = uncertainty×3 + missing-data rate + 3 pt near-limit add-on, minimum 8%.`), T('의견 규칙: 기본 과부족<0이면 매수, 안전 여유 미만이거나 스트레스 부족이면 관망, 안전 여유 초과분만 매도 검토.', 'Rules: buy if the base gap < 0; hold if inside the margin or short under stress; sell only above the margin.'), T('KAU26은 KRX 일 종가(2026-10-28)이며 실시간이 아닙니다. 5거래일 이전은 모의 보강입니다.', 'KAU26 is the KRX daily close (2026-10-28), not real-time; points before the last five sessions are simulated.'), T('모의 자료로 만든 예시이며 법령 원문·확정 할당량과 대조 전입니다. 투자 권유가 아닙니다.', 'Built from mock data and not reconciled with legal texts or confirmed allocations. Not investment advice.')], rh = Math.floor(E(4.5) / ps.length), sz = fitSz(ps, 10.2, rh / 914400 - .12, [14, 13, 12, 11, 10]);
      add([...nav(T('방법', 'Method')), ...ttl(T('방법·가정·유의사항', 'Method, assumptions and caveats')), card(MG, E(1.55), W2, E(4.75), [], { round: 4000, name: 'Big card' }), ...ps.flatMap((p, i) => [bx(MG + E(.25), E(1.55) + E(.12) + i * rh + Math.round((rh - E(.44)) / 2), E(.44), E(.44), [ap(String(i + 1), { sz: 13, b: 1, color: 'FFFFFF', align: 'ctr' })], { prst: 'ellipse', fill: i % 2 ? C.mid : C.dark, pad: 0, padT: 0, anchor: 'ctr', name: 'Badge' }), mk(MG + E(.9), E(1.55) + E(.12) + i * rh, W2 - E(1.2), rh - E(.04), [ap(p, { sz, color: C.ink })], { name: 'Note ' + (i + 1) })]), foot]); }
    // 마지막: Thank You
    reset(); add([...hero(T('감사합니다', 'Thank You'), T('AMA 종합 분석 보고서 · ', 'AMA Summary Analysis Report · ') + m.asof), mk(E(1.5), SH - E(1.2), SW - E(3), E(.8), [ap(T('시안(모의 자료) 기반 예시이며 법령 원문·확정 할당량과 대조 전입니다. KAU26은 KRX 일 종가이며 실시간이 아닙니다. 투자 권유가 아닙니다.', 'Example built from mock data; not reconciled with legal texts or confirmed allocations. KAU26 is the KRX daily close, not real-time. Not investment advice.'), { sz: 10, color: 'B7C9B7', align: 'ctr' })])]);
    const files = [{ name: '[Content_Types].xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>${Array.from({ length: 11 }, (_, i) => `<Override PartName="/ppt/slideLayouts/slideLayout${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>`).join('')}<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/><Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/><Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/><Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>${slides.map((_, i) => `<Override PartName="/ppt/slides/slide${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join('')}<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>` },
      { name: '_rels/.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${R}/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="${R}/extended-properties" Target="docProps/app.xml"/></Relationships>` },
      { name: 'docProps/core.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>AMA 탄소·에너지 비용 종합 분석 보고서(시안)</dc:title><dc:creator>AMA</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${new Date().toISOString().replace(/\.\d+Z$/, 'Z')}</dcterms:created></cp:coreProperties>` },
      { name: 'docProps/app.xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>AMA Report Generator</Application></Properties>' },
      { name: 'ppt/presentation.xml', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation ${I.P_NS} saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>${slides.map((_, i) => `<p:sldId id="${256 + i}" r:id="rId${6 + i}"/>`).join('')}</p:sldIdLst><p:sldSz cx="${SW}" cy="${SH}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>` },
      { name: 'ppt/_rels/presentation.xml.rels', data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${R}/slideMaster" Target="slideMasters/slideMaster1.xml"/><Relationship Id="rId2" Type="${R}/presProps" Target="presProps.xml"/><Relationship Id="rId3" Type="${R}/viewProps" Target="viewProps.xml"/><Relationship Id="rId4" Type="${R}/theme" Target="theme/theme1.xml"/><Relationship Id="rId5" Type="${R}/tableStyles" Target="tableStyles.xml"/>${slides.map((_, i) => `<Relationship Id="rId${6 + i}" Type="${R}/slide" Target="slides/slide${i + 1}.xml"/>`).join('')}</Relationships>` }];
    Object.keys(T_).forEach(kk => files.push({ name: kk, data: T_[kk] }));
    slides.forEach((s, i) => { files.push({ name: `ppt/slides/slide${i + 1}.xml`, data: s }, { name: `ppt/slides/_rels/slide${i + 1}.xml.rels`, data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${R}/slideLayout" Target="../slideLayouts/slideLayout7.xml"/>${rels[i].map(([rid, f]) => `<Relationship Id="${rid}" Type="${R}/image" Target="../media/${f}.png"/>`).join('')}</Relationships>` }); });
    gi.forEach((x, i) => { if (x.img) files.push({ name: `ppt/media/g${i + 1}.png`, data: x.img.bytes }); });
    return I.zip(files, 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
  }

  // ── XLSX (Executive Summary + 상세 + 그래프 해석 + 수식 모델 + 기존 데이터 시트) ──
  function xSheet2(rows, widths, o = {}) {
    const hs = o.heights || {};
    const body = rows.map((r, i) => `<row r="${i + 1}"${hs[i] ? ` ht="${hs[i]}" customHeight="1"` : ''}>${(r || []).map((c, j) => I.xCell(c, I.colL(j) + (i + 1))).join('')}</row>`).join('');
    const cols = widths ? `<cols>${widths.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('')}</cols>` : '';
    const merges = o.merges && o.merges.length ? `<mergeCells count="${o.merges.length}">${o.merges.map(x => `<mergeCell ref="${x}"/>`).join('')}</mergeCells>` : '';
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetViews><sheetView workbookViewId="0" showGridLines="0"${o.first ? ' tabSelected="1"' : ''}/></sheetViews><sheetFormatPr defaultRowHeight="18"/>${cols}<sheetData>${body}</sheetData>${merges}<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/><pageSetup orientation="landscape"/>${o.drawing ? '<drawing r:id="rId1"/>' : ''}</worksheet>`;
  }
  function buildXlsx(d, m, gi, figNo) {
    const k = m.k, op = opOf(m), ST = I.ST, wcols = [26, 18, 18, 18, 18, 18, 18, 18], tw = sum(wcols.slice(1));
    const rh = (txt, w = tw) => Math.max(20, Math.ceil(wlen(txt) / (w * .92)) * 16 + 6);
    // 스타일 추가: 11 wrap, 12 big label, 13 section
    const extraStyles = { wrap: 11, big: 12, sec: 13, box: 14 };
    // 1) Executive Summary
    const rows = [], hts = {}, mg = []; const R_ = (arr, h_) => { rows.push(arr); if (h_) hts[rows.length - 1] = h_; return rows.length; };
    R_([{ v: T('AMA 탄소·에너지 비용 종합 분석 보고서', 'AMA Carbon & Energy Cost Summary Analysis'), s: ST.title }]); R_([{ v: `${d.name} · ${d.period} · ${d.basis} · ${T('기준일', 'As of')} ${m.asof}`, s: ST.note }]); R_([{ v: T('시안(모의 자료)으로 만든 예시이며 투자 권유가 아닙니다.', 'Example built from mock data; not investment advice.'), s: ST.note }]); R_([]);
    R_([{ v: 'Executive Summary', s: extraStyles.sec }]); let r = R_([{ v: T('종합 의견', 'Overall opinion'), s: ST.tb }, { v: m.label, s: extraStyles.big }], 30); mg.push(`B${r}:H${r}`);
    r = R_([{ v: T('결론', 'Conclusion'), s: ST.tb }, { v: m.headline, s: extraStyles.wrap }], rh(m.headline)); mg.push(`B${r}:H${r}`);
    r = R_([{ v: T('신뢰도', 'Confidence'), s: ST.tb }, { v: m.conf, s: extraStyles.wrap }], rh(m.conf)); mg.push(`B${r}:H${r}`); R_([]);
    R_([{ v: T('핵심 지표', 'Key indicators'), s: extraStyles.sec }]); R_([{ v: T('지표', 'Indicator'), s: ST.hd }, { v: T('값', 'Value'), s: ST.hd }, { v: T('비고', 'Note'), s: ST.hd }]); m.kpi.slice(1).forEach(x => R_([x[0], { v: x[1], s: ST.tb }, x[2]])); R_([]);
    R_([{ v: T('종합 의견의 근거 6가지', 'Six grounds for the opinion'), s: extraStyles.sec }]); m.es.forEach((e, i) => { const rr = R_([{ v: `${i + 1}. ${e.title}`, s: ST.tb }, { v: e.point, s: extraStyles.wrap }], rh(e.point)); mg.push(`B${rr}:H${rr}`); }); R_([]);
    R_([{ v: T('실행 권고', 'Recommended actions'), s: extraStyles.sec }]); m.actions.forEach((a, i) => { const rr = R_([{ v: String(i + 1), s: ST.tb }, { v: a, s: extraStyles.wrap }], rh(a)); mg.push(`B${rr}:H${rr}`); }); R_([]);
    if (m.triggers.length) { R_([{ v: T('의견이 바뀌는 조건', 'Conditions that change the opinion'), s: extraStyles.sec }]); m.triggers.forEach((a, i) => { const rr = R_([{ v: '•', s: ST.tb }, { v: a, s: extraStyles.wrap }], rh(a)); mg.push(`B${rr}:H${rr}`); }); }
    const s1 = ['Executive Summary', xSheet2(rows, wcols, { merges: mg, heights: hts, first: true })];
    // 2) 상세 분석
    const r2 = [], h2 = {}, m2 = []; const P2 = (arr, h_) => { r2.push(arr); if (h_) h2[r2.length - 1] = h_; return r2.length; };
    P2([{ v: T('상세 분석', 'Detailed analysis'), s: ST.title }]); P2([{ v: T('Executive Summary의 근거 6가지를 자료와 함께 설명합니다.', 'Each ground of the Executive Summary explained with data.'), s: ST.note }]); P2([]);
    m.details.forEach((dt, i) => {
      P2([{ v: `${i + 1}. ${dt.id}. ${dt.title}`, s: extraStyles.sec }]); dt.paras.filter(Boolean).forEach(p => { const rr = P2([{ v: '', s: 0 }, { v: p, s: extraStyles.wrap }], rh(p)); m2.push(`B${rr}:H${rr}`); });
      if (dt.table) { P2([...[''].concat([]), ...dt.table.head.map(h => ({ v: h, s: ST.hd }))].slice(0, 9)); dt.table.rows.forEach(rw => P2([''].concat(rw.map((c, ci) => ({ v: c, s: 0 }))))); }
      const fl = (dt.figs || []).map(f => figNo[f]).filter(Boolean); if (fl.length) P2([{ v: '', s: 0 }, { v: T('관련 그래프: ', 'Related figures: ') + fl.map(x => (isEn() ? 'Figure A-' : '그림 A-') + x).join(', ') + T(' ("그래프 해석" 시트)', ' ("Graph interpretation" sheet)'), s: ST.note }]); P2([]);
    });
    const s2 = [T('상세 분석', 'Detailed analysis'), xSheet2(r2, [3, 24, 16, 16, 16, 16, 16, 16, 16], { merges: m2, heights: h2 })];
    // 3) 그래프 해석 (그림 + 설명)
    const r3 = [], h3 = {}, m3 = [], anchors = []; const P3 = (arr, h_) => { r3.push(arr); if (h_) h3[r3.length - 1] = h_; return r3.length; };
    P3([{ v: T('그래프와 해석', 'Graphs and interpretation'), s: ST.title }]); P3([{ v: T('각 그래프의 의미와 종합 의견과의 연결을 함께 적었습니다.', 'Each graph is shown with its meaning and its link to the opinion.'), s: ST.note }]); P3([]);
    gi.forEach((x, i) => {
      const g = x.g, no = i + 1; P3([{ v: `${isEn() ? 'Figure A-' : '그림 A-'}${no}. ${g.title}`, s: extraStyles.sec }]);
      if (x.img) { const pxW = g.key === 'G8' ? 300 : 700, pxH = Math.round(pxW * x.img.h / x.img.w), rowsUsed = Math.ceil(pxH / 24) + 1; anchors.push({ no, row: r3.length, w: pxW, h: pxH, key: 'g' + no }); for (let q = 0; q < rowsUsed; q++) P3([]); }
      [[T('분석 대상', 'Scope'), g.what], [T('분석 개요', 'Overview'), g.read], [T('핵심 지표', 'Key metrics'), g.numbers || ''], [T('시사점', 'Implications'), g.insight], [T('유의사항', 'Caveats'), g.caution], [T('후속 과제', 'Next steps'), g.watch || '']].filter(r => r[1]).forEach(([lb, tx]) => { const rr = P3([{ v: lb, s: ST.tb }, { v: tx, s: extraStyles.wrap }], rh(tx, 7 * 18 * .92)); m3.push(`B${rr}:H${rr}`); }); P3([]);
    });
    const s3 = [T('그래프 해석', 'Graph interpretation'), xSheet2(r3, [22, 18, 18, 18, 18, 18, 18, 18], { merges: m3, heights: h3, drawing: anchors.length > 0 })];
    // 4) 수식 모델(가격·안전 여유를 바꾸면 의견 수치가 다시 계산)
    const r4 = [], m4 = []; const P4 = arr => { r4.push(arr); return r4.length; };
    P4([{ v: T('한국 할당 과부족 모델 (수식)', 'Korea allocation gap model (formulas)'), s: ST.title }]); P4([{ v: T('파란 글씨 칸(가격·안전 여유)을 바꾸면 아래 수치가 다시 계산됩니다. 연간 목표는 할당량 대용(예시)입니다.', 'Change the input cells (price, safety margin) and the figures recalculate. The annual target is an allocation proxy (example).'), s: ST.note }]); P4([]);
    P4([{ v: T('입력', 'Inputs'), s: extraStyles.sec }]); const rP = P4([T('KAU26 가격 (원/톤)', 'KAU26 price (KRW/t)'), { v: m.pr ? m.pr.px : 30250, s: ST.n0 }, T('KRX 종가, 필요 시 변경', 'KRX close; edit if needed')]), rB = P4([T('안전 여유 (%)', 'Safety margin (%)'), { v: k.bufPct, s: ST.pct }, T('불확실도×3 + 미수신율 (+3%p), 최소 8%', 'uncertainty×3 + missing data (+3 pt), min 8%')]); P4([]);
    const hdr = P4([T('공장', 'Plant'), T('연간 목표', 'Annual target'), T('올해 누적', 'YTD'), T('연말 예상(기본)', 'Year-end (base)'), T('연말 예상(+10%)', 'Year-end (+10%)'), T('연말 예상(스트레스)', 'Year-end (stress)'), T('과부족(기본)', 'Gap (base)'), T('과부족 %', 'Gap %')].map(x => ({ v: x, s: ST.hd })));
    const f0 = rows4(); function rows4() { return r4.length + 1; }
    k.rows.forEach((rw, i) => { const rr = f0 + i; P4([rw.id + ' ' + rw.site, { v: rw.annual, s: ST.n0 }, { v: rw.ytd, s: ST.n0 }, { v: rw.proj.base, s: ST.n0 }, { v: rw.proj.up, s: ST.n0 }, { v: rw.proj.stress, s: ST.n0 }, { v: rw.annual - rw.proj.base, s: ST.n0, f: `B${rr}-D${rr}` }, { v: (rw.annual - rw.proj.base) / rw.annual, s: ST.pct, f: `G${rr}/B${rr}` }]); });
    const f1 = f0 + k.rows.length - 1, tr = P4([{ v: T('한국 합계', 'Korea total'), s: ST.tb }, ...['B', 'C', 'D', 'E', 'F', 'G'].map((c, ci) => ({ v: [k.A, k.Y, k.P.base, k.P.up, k.P.stress, k.gap.base][ci], s: ST.tn0, f: `SUM(${c}${f0}:${c}${f1})` })), { v: k.gap.base / k.A, s: ST.pct, f: `G${f0 + k.rows.length}/B${f0 + k.rows.length}` }]); P4([]);
    P4([{ v: T('의견 계산', 'Opinion calculation'), s: extraStyles.sec }]);
    const cT = 'B' + tr, rBuf = P4([T('안전 여유 수량 (tCO₂)', 'Safety margin quantity (tCO₂)'), { v: k.buf, s: ST.n0, f: `${cT}*B${rB}` }]), rGB = tr, rGS = P4([T('스트레스 과부족 (tCO₂)', 'Stress gap (tCO₂)'), { v: k.gap.stress, s: ST.n0, f: `B${tr}-F${tr}` }]);
    const rSell = P4([T('매도 검토 가능분 (tCO₂)', 'Sellable amount (tCO₂)'), { v: Math.max(0, Math.min(k.gap.stress - k.buf, k.gap.base - k.buf)), s: ST.n0, f: `MAX(0,MIN(B${rGS}-B${rBuf},G${tr}-B${rBuf}))` }]), rBuy = P4([T('매수 필요량 (tCO₂)', 'Required purchase (tCO₂)'), { v: Math.max(0, -k.gap.base), s: ST.n0, f: `MAX(0,-G${tr})` }]);
    P4([T('매도 검토 금액 (억 원)', 'Sellable value (KRW 100M)'), { v: m.dec.code === 'SELL' ? m.dec.value : E8x(Math.max(0, Math.min(k.gap.stress - k.buf, k.gap.base - k.buf)) * (m.pr ? m.pr.px : 30250)), s: ST.n2, f: `B${rSell}*B${rP}/100000000` }]); P4([T('매수 필요 금액 (억 원)', 'Purchase cost (KRW 100M)'), { v: E8x(Math.max(0, -k.gap.base) * (m.pr ? m.pr.px : 30250)), s: ST.n2, f: `B${rBuy}*B${rP}/100000000` }]);
    P4([T('의견(수식)', 'Opinion (formula)'), { v: m.label, s: ST.tb, f: `IF(G${tr}<0,"${T('매수 검토 필요', 'Consider buying')}",IF(OR(B${rGS}<0,G${tr}<B${rBuf}),"${T('구매 불필요 · 매도 보류(관망)', 'No purchase needed · hold off selling')}",IF(B${rSell}>=0.02*B${tr},"${T('구매 불필요 · 초과 여유분 일부 매도 검토', 'No purchase needed · consider selling part of the surplus')}","${T('구매 불필요 · 매도 보류(관망)', 'No purchase needed · hold off selling')}")))` }]);
    function E8x(v) { return v / 1e8; }
    const s4 = [T('할당 과부족 모델', 'Allocation gap model'), xSheet2(r4, [34, 18, 18, 18, 18, 20, 18, 14], { merges: m4 })];
    const dataSheets = I.xlsxSheets(d);
    const sheets = [s1, s2, s3, s4, ...dataSheets];
    // 그림 파트
    const extra = { ct: '', files: [] };
    if (anchors.length) {
      const di = 1, imgs = anchors.filter(a => gi[a.no - 1].img);
      extra.ct = `<Override PartName="/xl/drawings/drawing${di}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>`;
      extra.files.push({ name: `xl/worksheets/_rels/sheet3.xml.rels`, data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing${di}.xml"/></Relationships>` });
      extra.files.push({ name: `xl/drawings/drawing${di}.xml`, data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">${imgs.map((a, i) => `<xdr:oneCellAnchor><xdr:from><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>${a.row}</xdr:row><xdr:rowOff>60000</xdr:rowOff></xdr:from><xdr:ext cx="${a.w * 9525}" cy="${a.h * 9525}"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="${i + 2}" name="Figure A-${a.no}" descr="Figure A-${a.no}"/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId${i + 1}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${a.w * 9525}" cy="${a.h * 9525}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>`).join('')}</xdr:wsDr>` });
      extra.files.push({ name: `xl/drawings/_rels/drawing${di}.xml.rels`, data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${imgs.map((a, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/g${a.no}.png"/>`).join('')}</Relationships>` });
      imgs.forEach(a => extra.files.push({ name: `xl/media/g${a.no}.png`, data: gi[a.no - 1].img.bytes }));
    }
    return I.xlsxPack(sheets, extra);
  }

  // 서버 작성: 한국어 PowerPoint는 사용자 템플릿 + AI 문장(서버)으로 만든다. 실패하면 이 브라우저에서 만든 기본 문서를 그대로 쓴다.
  async function viaServer(blob, say) {
    try {
      say('분석 데이터를 내부 작성 서비스로 보내는 중…');
      // 포털 앞단 WAF는 요청 본문을 128KB까지만 검사하므로, 파일을 90KB 조각으로 나누어 올린다(각 조각은 그대로 검사된다).
      const ur = await fetch('/api/report/uploads', { method: 'POST' }); if (!ur.ok) throw new Error('HTTP ' + ur.status);
      const uid = (await ur.json()).id, buf = new Uint8Array(await blob.arrayBuffer()), CH = 90 * 1024, n = Math.ceil(buf.length / CH);
      for (let i = 0; i < n; i += 4) {
        const rs = await Promise.all([0, 1, 2, 3].filter(j => i + j < n).map(j => fetch(`/api/report/uploads/${uid}/chunk?i=${i + j}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: buf.subarray((i + j) * CH, (i + j + 1) * CH) })));
        if (rs.some(x => !x.ok)) throw new Error('upload HTTP ' + (rs.find(x => !x.ok).status));
        say(`분석 데이터를 내부 작성 서비스로 보내는 중… ${Math.min(n, i + 4)}/${n}`);
      }
      const r = await fetch(`/api/report/uploads/${uid}/start?n=${n}`, { method: 'POST' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const { id } = await r.json();
      for (let i = 0; i < 150; i++) {
        await new Promise(s => setTimeout(s, 2000));
        const s = await (await fetch('/api/report/jobs/' + id, { cache: 'no-store' })).json();
        say((s.step || '작성 중') + '… ' + (s.sec || 0) + '초');
        if (s.status === 'done') { const f = await fetch('/api/report/jobs/' + id + '/file', { cache: 'no-store' }); return { blob: await f.blob(), meta: s.meta }; }
        if (s.status === 'error') throw new Error(s.error || 'error');
      }
      throw new Error('시간 초과');
    } catch (e) { return { err: String(e && e.message || e) }; }
  }
  async function build(kind, scope, onStatus) {
    const say = t => { try { onStatus && onStatus(t); } catch (e) { } };
    const d = ReportGen.data(scope), m = ReportModel.build(d); m.hasKR = m.hasKR; const gi = await graphs(d, m), figNo = {}; gi.forEach((x, i) => { figNo[x.g.id] = i + 1; });
    let blob = kind === 'docx' ? buildDocx(d, m, gi, figNo) : kind === 'pptx' ? buildPptx(d, m, gi, figNo) : buildXlsx(d, m, gi, figNo), ai = null, fallback = null;
    if (kind === 'pptx' && !isEn()) { const sv = await viaServer(blob, say); if (sv.blob) { blob = sv.blob; ai = sv.meta || {}; } else fallback = sv.err; }
    const safe = s => String(s).replace(/[^\w가-힣.\-]+/g, '_').replace(/^_+|_+$/g, '');
    const SE = { all: 'All', 한국: 'Korea', 일본: 'Japan', 싱가포르: 'Singapore' }, nm = isEn() ? `AMA-Summary-Report_${SE[scope || 'all'] || safe(scope)}_${m.asof}.${kind}` : `AMA-종합분석보고서_${safe(scope === 'all' || !scope ? '통합' : scope)}_${safe(d.period)}.${kind}`;
    return { blob, name: nm, d, m, gi, ai, fallback };
  }
  window.ReportDoc = { build, graphs };
})();
