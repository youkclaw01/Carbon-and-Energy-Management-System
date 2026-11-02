// 종합 관제 화면: 공장 VM이 분 단위로 보낸 자료를 중앙 수신에서 읽어 최근 분별 값을 보여 줍니다(초 단위 원자료는 "공장 VM 현장"의 VM 직접 화면). 값은 합성 자료입니다.
(function () {
  const SITES = [['KR-01', '포항(한국)', '/api/plant/v1/'], ['KR-02', '광양(한국)', '/api/plant/v1/'], ['KR-03', '울산(한국)', '/api/plant/v1/'], ['KR-04', '당진(한국)', '/api/plant/v1/'], ['KR-05', '광주(한국)', '/api/plant/v1/'], ['JP-01', '기타큐슈(일본)', '/api/plant-jp/v1/'], ['JP-02', '구라시키(일본)', '/api/plant-jp/v1/'], ['JP-03', '지바(일본)', '/api/plant-jp/v1/'], ['JP-04', '나고야(일본)', '/api/plant-jp/v1/'], ['SG-01', '주롱(싱가포르)', '/api/plant-sg/v1/'], ['SG-02', '투아스(싱가포르)', '/api/plant-sg/v1/'], ['SG-03', '우드랜즈(싱가포르)', '/api/plant-sg/v1/']], N = 3;
  const f1 = v => v == null || isNaN(v) ? '–' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 1 }), hm = t => new Date(t * 1000).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Seoul' });
  const SC = { ONLINE: ['수신 중', '#2e9e63'], DELAYED: ['지연', '#c98a1b'], OFFLINE: ['끊김', '#c0453a'] };
  const get = (b, p) => fetch(b + p, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
  function build() {
    const body = h('div', { class: 'mincard' }); const c = card('공장 수신 현황', '분 단위 · 합성 자료', h('p', { class: 'mnote' }, '공장 VM은 초 단위로 수집하고 1분마다 묶어 중앙으로 보냅니다. 아래는 중앙이 받은 최근 분별 평균입니다. 초 단위 현장 값은 "공장 VM 현장" 화면에서 봅니다.'), body);
    async function load() {
      if (!c.isConnected) { clearInterval(tm); return; }
      const parts = await Promise.all(SITES.map(async ([id, nm, b]) => { try { const [sites, ser] = await Promise.all([get(b, 'sites'), get(b, 'sites/' + id + '/series?minutes=15')]); const br = (sites.sites || []).find(x => x.id === id) || {}; return { id, nm, br, ser: ser.slice(-N) }; } catch (e) { return { id, nm, err: true, ser: [] }; } }));
      S.mcOpen = S.mcOpen || {}; const CN = { KR: '한국', JP: '일본', SG: '싱가포르' };
      const siteBlock = p => {
        const st = p.err ? SC.OFFLINE : (SC[p.br.status] || SC.OFFLINE), last = p.ser[p.ser.length - 1];
        const rows = p.ser.slice().reverse().map((r, i) => [hm(r.t) + (i === 0 ? ' (진행 중)' : ''), f1(r.n), f1(r.demand), f1(r.grid), f1(r.solar), f1(r.co2)]);
        const sum = h('summary', { class: 'mc-sum' }, h('b', {}, p.id + ' ' + p.nm), h('span', { class: 'tag', style: 'background:' + st[1] + ';color:#fff' }, st[0]), h('span', { class: 'mut' }, p.err ? '조회 실패' : `마지막 수신 ${p.br.age_s == null ? '–' : Math.round(p.br.age_s) + '초 전'}${last ? ' · CO₂ ' + f1(last.co2) + ' kg/h' : ''}`));
        const d = h('details', { class: 'mc-site' }, sum, rows.length ? table(['분(KST)', '수신 건수', '수요 kW', '계통 kW', '태양광 kW', 'CO₂ kg/h'], rows, [1, 2, 3, 4, 5]) : h('p', { class: 'mnote' }, '아직 받은 분 단위 자료가 없습니다.'));
        if (S.mcOpen[p.id]) d.open = true; d.addEventListener('toggle', () => { S.mcOpen[p.id] = d.open; }); return d;
      };
      body.replaceChildren(...['KR', 'JP', 'SG'].map(cc => {
        const ps = parts.filter(p => p.id.startsWith(cc)), on = ps.filter(p => !p.err && p.br.status === 'ONLINE').length, co2 = ps.reduce((s, p) => s + ((p.ser[p.ser.length - 1] || {}).co2 || 0), 0);
        const sum = h('summary', { class: 'mc-sum mc-cc' }, h('b', {}, CN[cc] + ' ' + ps.length + '곳'), h('span', { class: 'tag', style: 'background:' + (on === ps.length ? SC.ONLINE[1] : SC.DELAYED[1]) + ';color:#fff' }, '수신 중 ' + on + '/' + ps.length), h('span', { class: 'mut' }, '최근 분 CO₂ 합계 ' + f1(co2 / 1000) + ' t/h'));
        const d = h('details', { class: 'mc-group' }, sum, ...ps.map(siteBlock)); if (S.mcOpen[cc]) d.open = true; d.addEventListener('toggle', () => { S.mcOpen[cc] = d.open; }); return d;
      }));
    }
    const tm = setInterval(load, 30000); setTimeout(load, 60); return c;
  }
  const orig = V.overview; V.overview = () => { const r = orig(); r.append(build()); return r; };
})();
