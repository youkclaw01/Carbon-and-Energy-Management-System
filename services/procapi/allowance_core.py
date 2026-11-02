"""배출권 포지션 판단(S04, 모의·읽기 전용): 포스코 공개 자료 기준 데이터셋(posco_demo.json)에서 결정론으로 계산한다.
규칙(KRX·제4차 할당계획에서 확인): 잉여업체는 해당 이행연도 KAU 순매도량의 N배까지만 이월(2026→2027 N=6). 소멸을 피하려면 순매도 X ≥ S/(N+1),
이월 후 잔량이 다음 해 구조적 부족을 덮으려면 X ≤ S − 부족. 이 모듈은 값을 계산할 뿐 주문·승인·실행 권한이 없다."""
import os, json, uuid, math
DEMO_KEY = 'POSCO-DEMO-2026'
DEMO_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, 'ama-demo-posco-20261101'))
def load(path=None):
    return json.load(open(path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'posco_demo.json'), encoding='utf-8'))
def mt(n): return round(n / 1e6, 2)
def eok(n): return round(n / 1e8)
def position(d=None, candidates=(960000, 3000000)):
    d = d or load(); a, s = d['actual'], d['assumptions']
    carry = a['surplus']['carryOverTo2026']; alloc = s['allocation2026']['value']; em = s['emission2026Expected']['value']; N = a['rules']['carryMultiple']['2026']
    price = a['market']['KAU26']; end = carry + alloc - em; deficit = max(0, em - alloc)
    lo = math.ceil(end / (N + 1)); hi = max(0, end - deficit); rec = (hi // 10000) * 10000
    def judge(q):
        after = end - q; limit = q * N; carried = min(after, limit); lost = max(0, after - limit); short = max(0, deficit - carried)
        ok = q >= lo and q <= hi
        return dict(sellTon=q, sellValueEokKrw=eok(q * price), afterBalanceTon=after, carryLimitTon=limit, carriedTon=carried, lostTon=lost, nextYearShortTon=short, withinWindow=ok,
                    verdict='RECOMMEND' if ok else ('NOT_RECOMMENDED_TOO_SMALL' if q < lo else 'NOT_RECOMMENDED_TOO_LARGE'))
    return dict(positionKey=DEMO_KEY, positionId=DEMO_ID, mode='SIMULATED', basis='포스코 공개 자료(실제)와 2026 가정(모의)', asOf=d['asOf'], instrument='KAU26', unit='tCO2e',
                actual=dict(carryOver2026Ton=carry, carryOver2026Mt=mt(carry), emission2025Ton=a['ghg']['years']['2025']['total'], priceKauKrw=price, priceAsOf=a['market']['asOf']),
                assumed=dict(allocation2026Ton=alloc, allocation2026Mt=mt(alloc), emission2026ExpectedTon=em, emission2026ExpectedMt=mt(em)),
                rule=dict(carryMultiple=N, text='잉여업체 이월 한도 = 해당 이행연도 KAU 순매도량 × N(2026→2027 N=6). 한도를 넘는 잉여는 소멸'),
                result=dict(endBalanceTon=end, endBalanceMt=mt(end), annualDeficitTon=deficit, annualDeficitMt=mt(deficit), carryCoverYears=round(carry / deficit, 1) if deficit else None,
                            carryValueEokKrw=eok(carry * price), minSellTon=lo, maxSellTon=hi, recommendedSellTon=rec, recommendedValueEokKrw=eok(rec * price), recommendedAfterBalanceTon=end - rec, recommendedAfterBalanceMt=mt(end - rec)),
                candidates=[judge(q) for q in candidates],
                order=dict(venue='KRX 배출권시장(시장 회원 시스템으로만 제출)', method='협의매매 1,000~3,000,000t 또는 10:00~11:30 경쟁매매 분할', hours='호가접수 09:00~12:00, 매매 10:00~12:00', settlement='당일결제(T+0)', preconditions='매도 수량 ≤ GIR 배출권등록부 보유 수량(공매도 금지)', executedBy='관리자·검수자 승인 후 모의 체결(AMA는 주문표까지)'),
                note='규칙 기반 계산 결과이며 주문·승인·실행 권한이 없다.')

# ---- 일본(GX-ETS)·싱가포르(탄소세) 판단: 한국과 같은 방식(규칙 계산, 읽기 전용, 모의) ----
DEMO_ID_JP = str(uuid.uuid5(uuid.NAMESPACE_URL, 'ama-demo-gx-jp-20261101')); DEMO_ID_SG = str(uuid.uuid5(uuid.NAMESPACE_URL, 'ama-demo-sgtax-sg-20261101'))
def _sites(): return json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sites_demo.json'), encoding='utf-8'))
def _annualize(s): return round(s['emission2026Ytd'] * 12 / s['monthsYtd'])    # 2026 연환산 = 1~10월 누적 × 12/10(단순 가정)
def gx_position(d=None):
    """일본 GX-ETS(JP-01~04 합계, 한 법인 가정): 2026년도 무상할당(가정)과 예상 배출의 차이, 참고 상한(4,300엔/t)·하한(1,700엔/t) 가격대의 비용 범위. 법 근거: GX推進法(배출실적과 같은 양의 배출枠을 다음 연도 1월 31일까지 보유)."""
    s = (d or _sites())['sites']['JP']; em = _annualize(s); alloc = round(s['emission2025'] * 0.95)   # 가정: 할당 = 2025 모의 배출의 95%(업종 기준 할당 수치는 미확인)
    short = max(0, em - alloc); cap, floor = 4300, 1700
    return dict(positionKey='GX-DEMO-JP-FY2026', mode='SIMULATED', basis='모의 이력 기반 연환산, 무상할당은 가정', instrument='GX-ETS 배출枠(일본)', siteId='JP-01~04',
                actual=dict(priceCapJpyPerT=cap, priceFloorJpyPerT=floor, holdDeadline='할당연도의 다음 연도 1월 31일', targetThresholdTon=100000, law='GX推進法 脱炭素成長型投資事業者排出枠(保有義務)'),
                assumed=dict(expectedEmissionTon=em, allocationTon=alloc, allocationRule='2025 모의 배출의 95%(가정)', emission2025Ton=s['emission2025']),
                rule='배출실적과 같은 양의 배출枠을 기한까지 보유. 부족분은 시장에서 매입(가격은 하한~상한 범위로 안내)',
                result=dict(shortageTon=short, surplusTon=max(0, alloc - em), costAtFloorMillionJpy=round(short * floor / 1e6, 1), costAtCapMillionJpy=round(short * cap / 1e6, 1), aboveTargetThreshold=em >= 100000),
                candidates=[dict(plan='부족분 전량 매입', buyTon=short, costFloorMillionJpy=round(short * floor / 1e6, 1), costCapMillionJpy=round(short * cap / 1e6, 1))],
                order=dict(venue='ERMS(배출량 취급 관리 시스템)·거래소 경유. AMA는 직접 주문·이전 불가', preconditions=['관리자·검수자의 건별 승인', '법인 ERMS 계정·보유 구좌', '등록확인기관 확인'], executedBy='관리자·검수자·기관 시스템'))
def sg_position(d=None, icc_price=30.0):
    """싱가포르 탄소세(SG-01~03 합계, 시설별 과세는 합산 가정): 2026년 세율 S$45/t, 적격 ICC로 과세 배출의 5%까지 상쇄. ICC 가격은 가정."""
    s = (d or _sites())['sites']['SG']; em = _annualize(s); rate = 45; tax = em * rate; icc_t = round(em * 0.05); saving = round(icc_t * (rate - icc_price))
    return dict(positionKey='SGTAX-DEMO-SG-2026', mode='SIMULATED', basis='모의 이력 기반 연환산, ICC 가격은 가정', instrument='탄소세(싱가포르)·ICC 상쇄', siteId='SG-01~03',
                actual=dict(taxRateSgdPerT=rate, iccOffsetMaxPct=5, payDeadline='9월 30일', taxableThresholdTon=25000, law='Carbon Pricing Act 2018, NEA ICC Guidance v1.2'),
                assumed=dict(expectedEmissionTon=em, iccPriceSgdPerT=icc_price, emission2025Ton=s['emission2025']),
                rule='과세 배출 × 세율. 적격 ICC를 소각해 과세 배출의 5%까지 세금 대신 납부할 수 있음',
                result=dict(taxSgd=round(tax), taxMillionSgd=round(tax / 1e6, 2), iccMaxTon=icc_t, iccCostSgd=round(icc_t * icc_price), savingSgd=saving, aboveTaxableThreshold=em >= 25000),
                candidates=[dict(plan='ICC 상쇄 없음', paySgd=round(tax)), dict(plan='ICC 5% 상쇄', paySgd=round(tax - icc_t * rate + icc_t * icc_price), iccTon=icc_t)],
                order=dict(venue='NEA EDMA·ICC 등록부 경유. AMA는 직접 구매·소각 불가', preconditions=['관리자·검수자의 건별 승인', '적격 ICC(NEA 승인) 확보', 'NOA 대비 소각 증빙'], executedBy='관리자·검수자·기관 시스템'))
