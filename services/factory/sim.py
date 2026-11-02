"""가상 공장(KR-01 울산) 운전 모델. 같은 seed·시각이면 같은 값을 낸다(합성 자료, mode=SIMULATED).
계수(배출계수 등)는 설계용 예시이며 공식 계수가 아니다."""
import math, random, time, collections
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
EF_GRID = 0.4594      # kgCO2/kWh (예시)
EF_GAS = 2.10         # kgCO2/Nm3 (예시)
# 설비 정의: id, 이름, 라인, 정격 kW, 기준 속도(단위)
EQUIP = [
    ('E-101', '압출기 A', 'L1', 185, 62), ('E-102', '압출기 B', 'L1', 185, 58),
    ('F-201', '성형기 1', 'L2', 140, 14), ('F-202', '성형기 2', 'L2', 140, 14),
    ('P-301', '열처리로', 'L3', 210, 0), ('P-302', '냉각·세척', 'L3', 55, 0), ('P-303', '포장 라인', 'L3', 40, 0),
    ('U-401', '공기압축기', 'UT', 110, 0), ('U-402', '칠러·냉각탑', 'UT', 95, 0),
]
LINES = {'L1': '압출', 'L2': '성형', 'L3': '후처리', 'UT': '유틸리티'}
PRODUCTS = [('PE-100A', 'PE 배관 100A', 'kg'), ('PE-150B', 'PE 배관 150B', 'kg'), ('PP-CAP', 'PP 캡 부품', 'EA'), ('HD-FIT', 'HDPE 피팅', 'EA'), ('PE-050C', 'PE 배관 50C', 'kg')]
FAULTS = {'E': [('E-OVERTEMP', '배럴 과온', 'major'), ('E-TORQUE', '스크류 토크 과부하', 'major')], 'F': [('F-CLAMP', '형체력 편차', 'minor'), ('F-MOLDTEMP', '금형 온도 편차', 'minor')],
          'P': [('P-FURN', '로 온도 편차', 'major'), ('P-CONV', '컨베이어 정지', 'minor')], 'U': [('U-PRESS', '공압 저하', 'minor'), ('U-CHILL', '냉각수 온도 상승', 'major')]}
# ---- 철강 데모 프로필(포스코 공개 규모 기준 모의): 기본은 꺼짐(값 불변). kw·gas·prod는 원래 소규모 공장 대비 배수 ----
STEEL = dict(on=False, kw=1.0, gas=1.0, prod=1.0)
STEEL_NAMES = {'E-101': '고로 1호기', 'E-102': '고로 2호기', 'F-201': '전로 1호기', 'F-202': '열연 압연기', 'P-301': '소둔로(연속)', 'P-302': '냉각·산세', 'P-303': '코일 포장 라인', 'U-401': '산소 플랜트', 'U-402': '냉각수·집진 설비'}
CENTER_NAMES = {'E-101': '슬리팅 라인 1', 'E-102': '슬리팅 라인 2', 'F-201': '블랭킹 프레스 1', 'F-202': '블랭킹 프레스 2', 'P-301': '연속 도금·소둔로', 'P-302': '냉각·세정', 'P-303': '코일 포장 라인', 'U-401': '공기압축기', 'U-402': '냉각수 설비'}
CENTER_LINES = {'L1': '슬리팅', 'L2': '블랭킹', 'L3': '후처리·포장', 'UT': '유틸리티'}
CENTER_PRODUCTS = [('HR-100', '열연 코일(HR) 가공', 'kg'), ('CR-200', '냉연 강판(CR) 가공', 'kg'), ('GI-300', '아연도금 강판(GI) 가공', 'kg'), ('BL-A', '블랭크(자동차 부품용)', 'EA'), ('EL-400', '전기강판 가공', 'kg')]
STEEL_LINES = {'L1': '제선', 'L2': '제강·압연', 'L3': '후처리·가공', 'UT': '유틸리티'}
STEEL_PRODUCTS = [('HR-100', '열연 코일(HR)', 'kg'), ('CR-200', '냉연 강판(CR)', 'kg'), ('GI-300', '아연도금 강판(GI)', 'kg'), ('SL-A', '슬래브(연주)', 'EA'), ('PL-500', '후판(Plate)', 'kg')]
STEEL_FAULTS = {'E': [('E-OVERTEMP', '노체 과온', 'major'), ('E-TORQUE', '송풍기 과부하', 'major')], 'F': [('F-CLAMP', '압연 하중 편차', 'minor'), ('F-MOLDTEMP', '롤 온도 편차', 'minor')],
                'P': [('P-FURN', '로 온도 편차', 'major'), ('P-CONV', '컨베이어 정지', 'minor')], 'U': [('U-PRESS', '산소 압력 저하', 'minor'), ('U-CHILL', '냉각수 온도 상승', 'major')]}
def configure_steel(kw, gas, prod, kind='mill'):
    """설비 이름·제품을 철강으로 바꾸고 전력(kw)·연료 가스(gas)·생산량(prod) 규모를 배수로 키운다. Plant 생성 전에 호출한다."""
    global EQUIP, LINES, PRODUCTS, FAULTS
    STEEL.update(on=True, kw=float(kw), gas=float(gas), prod=float(prod))
    names, lines, prods = (CENTER_NAMES, CENTER_LINES, CENTER_PRODUCTS) if kind == 'center' else (STEEL_NAMES, STEEL_LINES, STEEL_PRODUCTS)   # mill=일관제철소, center=가공센터
    EQUIP = [(i, names.get(i, nm), ln, rk, sp) for (i, nm, ln, rk, sp) in EQUIP]; LINES = dict(lines); PRODUCTS = list(prods); FAULTS = dict(STEEL_FAULTS)
def configure(tz_hours, ef_grid):
    global KST, EF_GRID
    KST = timezone(timedelta(hours=tz_hours)); EF_GRID = ef_grid
def kst(ts): return datetime.fromtimestamp(ts, KST)
def shift_of(ts):
    h = kst(ts).hour
    return 'A' if 6 <= h < 14 else ('B' if 14 <= h < 22 else 'C')
def sun(ts):
    d = kst(ts); h = d.hour + d.minute / 60 + d.second / 3600
    return max(0.0, math.sin((h - 6.2) / 12.0 * math.pi)) if 6.2 < h < 18.2 else 0.0

class Plant:
    def __init__(self, site_id='KR-01', site_name='울산', seed=20261030, t0=None):
        self.site_id, self.site_name, self.seed = site_id, site_name, seed
        self.rng = random.Random(seed); self.t = t0 or time.time(); self.tick_n = 0
        self.eq = {}
        for (i, nm, ln, kw, sp) in EQUIP:
            self.eq[i] = dict(id=i, name=nm, line=ln, rated_kw=kw * STEEL['kw'], base_speed=sp, state='RUN', since=self.t, speed=sp, kw=kw * STEEL['kw'] * .7, kwh=self.rng.uniform(5e4, 9e4),
                              temp=self.rng.uniform(205, 215) if i[0] == 'E' else (self.rng.uniform(55, 70) if i[0] == 'F' else (self.rng.uniform(430, 450) if i == 'P-301' else self.rng.uniform(22, 30))),
                              pressure=self.rng.uniform(180, 220) if i[0] == 'E' else (self.rng.uniform(6.6, 7.2) if i == 'U-401' else self.rng.uniform(1.2, 1.8)), load=.8, fault=None, mttr_until=0, changeover_until=0)
        self.alarms, self.alarm_seq = [], 0
        self.wo = {}; self.wo_seq = 0
        for ln in ('L1', 'L2', 'L3'): self._new_wo(ln)
        self.batt_soc = 62.0; self.batt_kw = 0.0; self.cloud = .8
        self.energy = dict(demand=0, grid=0, solar=0, ppa=0, batt=0, soc=62, co2_kg_h=0, scope1=0, scope2=0, whr_kw=0, gas_nm3h=0, water_m3h=0, curtail=0)
        self.counters = dict(good_kg=0.0, scrap_kg=0.0, forming_good=0, forming_scrap=0, packed=0, pallets=0, grid_kwh=0.0, solar_kwh=0.0, co2_kg=0.0)
        self.shipments = []; self.hist = collections.deque(maxlen=720)   # 5초 간격 약 1시간
        self.kpi = dict(oee=.0, availability=.0, performance=.0, quality=.0, kwh_per_t=.0, kgco2_per_t=.0, tph=.0)
        self.last = {}
    def _new_wo(self, ln):
        self.wo_seq += 1; pr = self.rng.choice([p for p in PRODUCTS if p[2] == ('EA' if ln == 'L2' else 'kg')])
        qty = self.rng.choice([4200, 5600, 7200, 9000]) if pr[2] == 'kg' else self.rng.choice([36000, 48000, 60000])
        qty = qty * STEEL['prod']
        self.wo[ln] = dict(id='WO-%s-%03d' % (kst(self.t).strftime('%Y%m%d'), self.wo_seq), line=ln, product=pr[0], name=pr[1], unit=pr[2], target=qty, done=0.0, scrap=0.0, started=self.t, status='RUNNING', batch='B%s%02d' % (kst(self.t).strftime('%m%d'), self.wo_seq % 100))
    def _alarm(self, kind, eid, code, msg, sev):
        self.alarm_seq += 1; a = dict(id='A%05d' % self.alarm_seq, equip=eid, code=code, msg=msg, sev=sev, raised=self.t, ack=None, cleared=None, state='ACTIVE'); self.alarms.insert(0, a); del self.alarms[200:]; return a
    def step(self, now):
        """now(실제시각)까지 진행하고 이번 틱에 생긴 이벤트(알람/작업지시/출하) 목록을 돌려준다."""
        dt = max(0.5, min(10.0, now - self.t)); self.t = now; self.tick_n += 1; out = []
        r = random.Random(self.seed * 1000003 + int(now))      # 같은 초에는 같은 난수
        sh = shift_of(now); h = kst(now).hour + kst(now).minute / 60
        brk = 12.0 <= h < 12.5 or 18.0 <= h < 18.4        # 식사·교대 휴식: 가동 속도 하향
        tot_kw = 0.0; run_cnt = 0
        for e in self.eq.values():
            if e['state'] == 'FAULT' and now >= e['mttr_until']:
                e['state'] = 'RUN'; e['since'] = now; code = e['fault']; e['fault'] = None
                for a in self.alarms:
                    if a['equip'] == e['id'] and a['state'] != 'CLEARED' and a['code'] == code: a['state'] = 'CLEARED'; a['cleared'] = now; out.append(('alarm.event', e['id'], dict(alarm_id=a['id'], code=a['code'], action='CLEARED', sev=a['sev'])))
            elif e['state'] == 'CHANGEOVER' and now >= e['changeover_until']: e['state'] = 'RUN'; e['since'] = now
            elif e['state'] == 'RUN':
                if r.random() < dt / 4200.0:                 # 평균 약 70분마다 고장
                    f = r.choice(FAULTS[e['id'][0]]); e['state'] = 'FAULT'; e['since'] = now; e['fault'] = f[0]; e['mttr_until'] = now + r.uniform(180, 420)
                    a = self._alarm('fault', e['id'], f[0], f[1], f[2]); out.append(('alarm.event', e['id'], dict(alarm_id=a['id'], code=f[0], msg=f[1], action='RAISED', sev=f[2])))
                elif r.random() < dt / 7200.0 and e['id'][0] in 'EF':   # 품목 변경
                    e['state'] = 'CHANGEOVER'; e['since'] = now; e['changeover_until'] = now + r.uniform(90, 200)
            tgt = e['base_speed']
            if e['state'] == 'RUN': load = (.88 if brk else .96) * (1 + r.uniform(-.03, .03))
            elif e['state'] == 'CHANGEOVER': load = .22
            elif e['state'] == 'FAULT': load = .03
            else: load = .1
            if e['id'] in ('P-301', 'P-302', 'P-303', 'U-401', 'U-402') and e['state'] == 'RUN': load = (.78 + .12 * math.sin(now / 900.0 + len(e['id']))) * (.9 if brk else 1) * (1 + r.uniform(-.02, .02))
            e['load'] += (load - e['load']) * min(1, dt / 8.0)
            e['speed'] = tgt * e['load'] if tgt else 0.0
            e['kw'] = e['rated_kw'] * (.12 + .88 * e['load']) * (1 + r.uniform(-.015, .015)); e['kwh'] += e['kw'] * dt / 3600.0; tot_kw += e['kw']; run_cnt += (e['state'] == 'RUN')
            if e['id'][0] == 'E': e['temp'] += ((212 if e['state'] == 'RUN' else 120) + (30 if e['state'] == 'RUN' and e['fault'] is None and e['id'] == 'E-101' and r.random() < .01 else 0) - e['temp']) * min(1, dt / 40) + r.uniform(-.5, .5); e['pressure'] = 200 * e['load'] + r.uniform(-2, 2)
            elif e['id'][0] == 'F': e['temp'] += ((64 if e['state'] == 'RUN' else 40) - e['temp']) * min(1, dt / 50) + r.uniform(-.2, .2); e['pressure'] = 780 * e['load'] + r.uniform(-5, 5)   # 형체력 kN
            elif e['id'] == 'P-301': e['temp'] += ((440 if e['state'] == 'RUN' else 220) - e['temp']) * min(1, dt / 90) + r.uniform(-.6, .6); e['pressure'] = 1.4 + r.uniform(-.05, .05)
            elif e['id'] == 'U-401': e['pressure'] = 6.9 + r.uniform(-.12, .12) - (.8 if e['state'] == 'FAULT' else 0); e['temp'] = 38 + 14 * e['load'] + r.uniform(-.3, .3)
            elif e['id'] == 'U-402': e['temp'] += ((26 + 4 * e['load'] + (6 if e['state'] == 'FAULT' else 0)) - e['temp']) * min(1, dt / 120) + r.uniform(-.1, .1); e['pressure'] = 3.1 + r.uniform(-.05, .05)
            else: e['temp'] += (28 - e['temp']) * min(1, dt / 100) + r.uniform(-.1, .1); e['pressure'] = 1.2 + r.uniform(-.03, .03)
        base_kw = (46 + 6 * math.sin(now / 1800.0)) * STEEL['kw']; demand = tot_kw + base_kw
        s = sun(now); self.cloud = min(1.0, max(.25, self.cloud + r.uniform(-.015, .015))); solar = 360 * s * self.cloud * (STEEL['kw'] / 4 if STEEL['on'] else 1)
        ppa = min(demand * .24, 380.0 * (STEEL['kw'] if STEEL['on'] else 1))
        bs = STEEL['kw'] / 4 if STEEL['on'] else 1.0      # 태양광·배터리는 전력 규모의 1/4 배수만 키운다
        hr = kst(now).hour; want = (-220 * bs if 17 <= hr < 21 else (160 * bs if solar > 120 * bs and self.batt_soc < 92 else 0))
        if want > 0: want = min(want, max(0, solar - 20 * bs))
        self.batt_kw += (want - self.batt_kw) * min(1, dt / 10.0)
        if self.batt_soc <= 22 and self.batt_kw < 0: self.batt_kw = 0.0
        if self.batt_soc >= 95 and self.batt_kw > 0: self.batt_kw = 0.0
        self.batt_soc = min(100, max(5, self.batt_soc + self.batt_kw * dt / 3600.0 / (1000.0 * bs) * 100.0))       # 용량 1.0MWh
        supply_ex_grid = solar + ppa - max(self.batt_kw, 0) + max(-self.batt_kw, 0)
        grid = max(0.0, demand - solar - ppa - max(-self.batt_kw, 0) + max(self.batt_kw, 0)); curtail = max(0.0, solar + ppa + max(-self.batt_kw, 0) - max(self.batt_kw, 0) - demand)
        furn = self.eq['P-301']; gas = (120 * furn['load'] + 55 * (1 if self.eq['E-101']['state'] == 'RUN' else .4) + r.uniform(-2, 2)) * STEEL['gas']; whr = .38 * (gas * 9.5) * .35
        water = 18 + 24 * self.eq['U-402']['load'] + r.uniform(-.4, .4); s1 = gas * EF_GAS * (1 - .0); s2 = grid * EF_GRID
        g = self.energy; g.update(demand=demand, grid=grid, solar=solar, ppa=ppa, batt=self.batt_kw, soc=self.batt_soc, co2_kg_h=s1 + s2, scope1=s1, scope2=s2, whr_kw=whr, gas_nm3h=gas, water_m3h=water, curtail=curtail, base_kw=base_kw)
        c = self.counters; c['grid_kwh'] += grid * dt / 3600; c['solar_kwh'] += solar * dt / 3600; c['co2_kg'] += (s1 + s2) * dt / 3600
        # 생산
        for ln in ('L1', 'L2', 'L3'):
            w = self.wo[ln]; es = [e for e in self.eq.values() if e['line'] == ln]; act = sum(1 for e in es if e['state'] == 'RUN') / len(es)
            if ln == 'L1': rate = sum(e['speed'] * 31 for e in es if e['state'] == 'RUN') / 3600.0 * dt * STEEL['prod']          # kg
            elif ln == 'L2': rate = sum(e['speed'] * 1.0 for e in es if e['state'] == 'RUN') * dt / 60.0 * 8 * STEEL['prod']        # EA (분당 14 사이클 * 8 캐비티)
            else: rate = act * 3.9 * dt / 3600.0 * 1000 / (1 if w['unit'] == 'kg' else 12) * STEEL['prod']
            scr = rate * max(.006, min(.06, .018 + (.02 if any(e['fault'] for e in es) else 0) + r.uniform(-.004, .004)))
            w['done'] += rate - scr; w['scrap'] += scr
            if ln == 'L1': c['good_kg'] += rate - scr; c['scrap_kg'] += scr
            elif ln == 'L2': c['forming_good'] += rate - scr; c['forming_scrap'] += scr
            else: c['packed'] += (rate - scr) / (40 if w['unit'] == 'EA' else 400)
            if w['done'] >= w['target']:
                w['status'] = 'DONE'; out.append(('production.workorder', ln, dict(wo=w['id'], product=w['product'], qty=round(w['done'], 1), scrap=round(w['scrap'], 1), unit=w['unit'], batch=w['batch'], action='COMPLETED')))
                if ln == 'L3' and w['unit'] in ('kg', 'EA'):
                    c['pallets'] += 1; sp = dict(id='SH-%s-%03d' % (kst(now).strftime('%m%d'), c['pallets']), product=w['product'], qty=round(w['done'], 0), unit=w['unit'], dest=r.choice(['부산 신항 CY', '평택 물류센터', '광양 출하장', '인천 내수']), at=now); self.shipments.insert(0, sp); del self.shipments[40:]
                    out.append(('shipment.dispatched', 'L3', dict(shipment=sp['id'], product=sp['product'], qty=sp['qty'], unit=sp['unit'], dest=sp['dest'])))
                self._new_wo(ln); out.append(('production.workorder', ln, dict(wo=self.wo[ln]['id'], product=self.wo[ln]['product'], target=self.wo[ln]['target'], unit=self.wo[ln]['unit'], action='STARTED')))
        # KPI
        tot_eq = [e for e in self.eq.values() if e['line'] != 'UT']; av = sum(1 for e in tot_eq if e['state'] == 'RUN') / len(tot_eq)
        perf = sum(e['load'] for e in tot_eq) / len(tot_eq); qual = c['good_kg'] / max(1.0, c['good_kg'] + c['scrap_kg'])
        tph = sum(e['speed'] * 31 for e in self.eq.values() if e['line'] == 'L1' and e['state'] == 'RUN') / 1000.0 * STEEL['prod']
        self.kpi = dict(oee=av * min(1, perf) * qual, availability=av, performance=min(1, perf), quality=qual, tph=tph, kwh_per_t=(demand / tph) if tph > .05 else 0, kgco2_per_t=((s1 + s2) / tph) if tph > .05 else 0, shift=sh, brk=brk)
        if self.tick_n % 3 == 0: self.hist.append(dict(t=now, demand=demand, grid=grid, solar=solar, ppa=ppa, batt=self.batt_kw, co2=s1 + s2, tph=tph, oee=self.kpi['oee'], soc=self.batt_soc))
        return out
    def snapshot(self):
        return dict(site=self.site_id, name=self.site_name, t=self.t, kpi=self.kpi, energy=self.energy, counters=self.counters, equipment=list(self.eq.values()), wo=list(self.wo.values()), alarms=self.alarms[:60], shipments=self.shipments[:12], shift=shift_of(self.t))
