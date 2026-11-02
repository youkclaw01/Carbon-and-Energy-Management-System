'use strict';
// AMA 아이콘 세트(직접 제작 SVG). 24x24 격자, 둥근 선 1.7, 보조색(ac/af)은 테마의 강조색을 따릅니다.
const ICONS = {
  bot: '<rect x="4.5" y="8" width="15" height="11" rx="3.2"/><path d="M12 8V4.6"/><circle cx="12" cy="3.8" r="1.2"/><circle cx="9" cy="13" r="1.1"/><circle cx="15" cy="13" r="1.1"/><path d="M9.2 16.4h5.6M2.8 12.5v2.6M21.2 12.5v2.6"/>',
  book: '<path d="M5 4.6h11.4a2.6 2.6 0 0 1 2.6 2.6V20H7.6A2.6 2.6 0 0 1 5 17.4z"/><path d="M5 17.4A2.6 2.6 0 0 1 7.6 15H19"/><path class="af" d="M9 8.4h6M9 11.2h4"/>',
  home: '<path d="M3 11.2 12 3.6l9 7.6"/><path d="M5.4 9.6V20.4h13.2V9.6"/><rect class="af" x="10" y="13.4" width="4" height="7" rx=".9"/>',
  factory: '<path d="M3.2 20.6V11l5.4 3.2V11l5.4 3.2V20.6z"/><path d="M14 20.6V6.2h4.4v14.4"/><path d="M2.6 20.6h18.8"/><rect class="af" x="5.4" y="16.4" width="2.2" height="2.2" rx=".4"/><rect class="af" x="10.4" y="16.4" width="2.2" height="2.2" rx=".4"/><path class="ac" d="M15.2 3.4c0-1 1.6-1 1.6 0"/>',
  bars: '<path d="M2.6 21h18.8"/><rect class="af" x="3.6" y="13.6" width="3.2" height="7" rx=".7"/><rect class="af" x="8.4" y="9.6" width="3.2" height="11" rx=".7"/><rect class="af" x="13.2" y="6.4" width="3.2" height="14.2" rx=".7"/><rect class="af" x="18" y="3.4" width="3.2" height="17.2" rx=".7"/>',
  trend: '<path d="M3.4 3.4v17.2H21"/><path class="ac" d="m6.6 15.6 3.6-4 3 2.2L19 7.2"/><path d="M15.4 7.2H19v3.6"/><circle class="af" cx="10.2" cy="11.6" r="1.4"/><circle class="af" cx="13.2" cy="13.8" r="1.4"/>',
  doc: '<path d="M6.2 3h8.4L19 7.4V21H6.2z"/><path d="M14.6 3v4.6H19"/><path class="ac" d="M9.2 12.4h6.6M9.2 16h6.6"/>',
  people: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20.4c0-3.6 2.7-6 6-6s6 2.4 6 6"/><circle class="af" cx="17.2" cy="9.4" r="2.4"/><path class="ac" d="M17.2 14.4c2.4 0 4.2 1.8 4.2 4.6"/>',
  shield: '<path d="M12 3 19.4 6v5.6c0 4.6-3.1 8-7.4 9.4-4.3-1.4-7.4-4.8-7.4-9.4V6z"/><path class="ac" d="m8.6 12.2 2.5 2.5 4.4-4.7"/>',
  leaf: '<path class="af" d="M5 19.2C5 9.6 10.4 4.6 20 4c0 9.6-5.2 15.2-15 15.2z"/><path class="ac" d="M5 19.2 13 11.2"/>',
  coin: '<circle cx="12" cy="12" r="9"/><circle class="af" cx="12" cy="12" r="5.6"/><path class="ac" d="m9 9.8 1.2 4.4 1.8-4.4 1.8 4.4L15 9.8M8.6 11.5h6.8M8.6 13.1h6.8"/>',
  alert: '<path d="M12 3.6 21.4 20H2.6z"/><path class="ac" d="M12 10v4.4"/><circle class="af" cx="12" cy="17.2" r=".9"/>',
  db: '<ellipse cx="12" cy="6" rx="7.5" ry="3"/><path d="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6"/><path class="ac" d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>',
  folder: '<path d="M3 7.2V18a1.6 1.6 0 0 0 1.6 1.6h14.8A1.6 1.6 0 0 0 21 18V9.6A1.6 1.6 0 0 0 19.4 8H12L10 5.4H4.6A1.6 1.6 0 0 0 3 7z"/><path class="ac" d="M3 10.4h18"/>',
  note: '<path d="M18 12.4V18a2 2 0 0 1-2 2H6.4a2 2 0 0 1-2-2V7.6a2 2 0 0 1 2-2h5.6"/><path class="ac" d="M7.6 10.4h4M7.6 14h3.4"/><path class="af" d="m17.2 4.4 2.4 2.4-6.2 6.2-3 .6.6-3z"/>',
  signal: '<circle class="af" cx="12" cy="10" r="1.7"/><path d="m12 11.7-3.4 9.3M12 11.7l3.4 9.3M9.9 17.4h4.2"/><path class="ac" d="M8.2 6.6a5.4 5.4 0 0 0 0 6.8M15.8 6.6a5.4 5.4 0 0 1 0 6.8M5.4 4.2a9 9 0 0 0 0 11.6M18.6 4.2a9 9 0 0 1 0 11.6"/>',
  horn: '<path d="M4 10v4h3.2l7 4.6V5.4L7.2 10z"/><path d="m7.4 14.2 1 5h2.6l-.9-4.4"/><path class="ac" d="M17.4 9.4a3.6 3.6 0 0 1 0 5.2M19.6 7a7 7 0 0 1 0 10"/>',
  box: '<path d="m12 3 8 4.2v9.6L12 21l-8-4.2V7.2z"/><path d="m4 7.2 8 4.4 8-4.4M12 11.6V21"/><path class="af" d="m8 5.1 8 4.3v3L8 8.1z"/>',
  plug: '<path d="M9 3v5M15 3v5"/><path class="af" d="M6.4 8h11.2v3.4a5.6 5.6 0 0 1-11.2 0z"/><path class="ac" d="M12 17v4"/>',
  flame: '<path d="M12 3c1 3.6 5.6 5.4 5.6 10.4A5.6 5.6 0 0 1 12 19a5.6 5.6 0 0 1-5.6-5.6c0-2 1-3.4 2.1-4.3.2 1.6 1 2.4 2 2.7C10.3 9 10.4 5.6 12 3z"/><path class="af" d="M12 19a2.6 2.6 0 0 1-2.6-2.6c0-1.6 1.3-2.4 2.6-3.9 1.3 1.5 2.6 2.3 2.6 3.9A2.6 2.6 0 0 1 12 19z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path class="ac" d="M12 7v5.2l3.6 2.2"/>',
  receipt: '<path d="M6 3h12v18l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5L6 21z"/><path class="ac" d="M9 8h6M9 12h6M9 16h3.2"/>',
  sigma: '<path d="M18 5H6.4l6 7-6 7H18"/><path class="ac" d="M6.4 5 12.4 12"/>',
  hourglass: '<path d="M7 3h10M7 21h10"/><path d="M8 3c0 5 4 5.2 4 9s-4 4-4 9M16 3c0 5-4 5.2-4 9s4 4 4 9"/><path class="af" d="M9.6 18.8h4.8L12 15.6z"/>',
  bolt: '<path class="af" d="M13.2 3 5.6 13.6h5.4L10 21l8.4-11H13z"/>',
  check: '<circle cx="12" cy="12" r="9"/><path class="ac" d="m7.9 12.4 2.8 2.8 5.5-5.8"/>'
};
// 이모지 코드 → 아이콘 이름
const ICON_OF = { '128211': 'book', '129302': 'bot', '8962': 'home', '127981': 'factory', '128202': 'bars', '128200': 'trend', '128196': 'doc', '128101': 'people', '128737': 'shield', '127807': 'leaf', '128176': 'coin', '128178': 'coin', '9888': 'alert', '128190': 'db', '128193': 'folder', '128221': 'note', '128225': 'signal', '128226': 'horn', '128230': 'box', '128267': 'plug', '128293': 'flame', '128337': 'clock', '129534': 'receipt', '8721': 'sigma', '9203': 'hourglass', '9889': 'bolt', '9989': 'check' };
const TONE = { leaf: 'gr', plug: 'gr', check: 'gr', shield: 'gr', coin: 'yl', bolt: 'yl', flame: 'yl', hourglass: 'yl', alert: 'yl', receipt: 'yl', horn: 'yl' };
function ico(html) { const m = /&#(\d+);/.exec(html || ''), n = m && ICON_OF[m[1]]; return n ? `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n].replace(/<(path|rect|circle|ellipse)/g, '<$1 pathLength="1"')}</svg>` : (html || ''); }
function tone(html) { const m = /&#(\d+);/.exec(html || ''); return (m && TONE[ICON_OF[m[1]]]) || 'cy'; }

ICON_OF['128506'] = ICON_OF['128225'] || ICON_OF['9889'];   // 리소스 구성도 메뉴 아이콘
