import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'procapi'))
import allowance_core as C
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
p = C.position(); r = p['result']
chk('모의 표시·정본 포인터', p['mode'] == 'SIMULATED' and p['positionKey'] == 'POSCO-DEMO-2026')
chk('2026 이월은 공시·보도 값(11,808,259)', p['actual']['carryOver2026Ton'] == 11808259)
chk('연말 잔여 = 이월 + 할당 − 배출(가정)', r['endBalanceTon'] == 11808259 + 63580000 - 69000000, r)
chk('허용 구간 하한 = ceil(S/(N+1))', r['minSellTon'] == -(-r['endBalanceTon'] // 7) and r['minSellTon'] == 912609, r)
chk('허용 구간 상한 = S − 부족분', r['maxSellTon'] == r['endBalanceTon'] - r['annualDeficitTon'], r)
chk('권고 수량은 구간 안·1만t 단위', r['minSellTon'] <= r['recommendedSellTon'] <= r['maxSellTon'] and r['recommendedSellTon'] % 10000 == 0, r)
c = {x['sellTon']: x for x in p['candidates']}
chk('권고 후보: 이월 한도 이내·소멸 0·다음 해 부족 0', c[960000]['verdict'] == 'RECOMMEND' and c[960000]['lostTon'] == 0 and c[960000]['nextYearShortTon'] == 0, c[960000])
chk('과다 매도 후보는 다음 해 부족 발생·비권고', c[3000000]['verdict'] == 'NOT_RECOMMENDED_TOO_LARGE' and c[3000000]['nextYearShortTon'] > 0, c[3000000])
small = C.position(candidates=(500000,))['candidates'][0]
chk('과소 매도는 이월 한도 초과분 소멸·비권고', small['verdict'] == 'NOT_RECOMMENDED_TOO_SMALL' and small['lostTon'] > 0, small)
chk('주문표: 시장 회원 경유·공매도 금지·T+0 명시', '회원' in p['order']['venue'] and '공매도' in p['order']['preconditions'] and 'T+0' in p['order']['settlement'])
chk('2025 잉여 − 순매각 = 2026 이월(공개 자료 정합)', 14169911 - 2361652 == 11808259)
g = C.gx_position(); sg = C.sg_position()
chk('일본 GX: 부족분×상·하한 가격 = 비용 범위, 상한 4,300·하한 1,700', g['result']['costAtCapMillionJpy'] == round(g['result']['shortageTon'] * 4300 / 1e6, 1) and g['actual']['priceFloorJpyPerT'] == 1700 and g['mode'] == 'SIMULATED', g['result'])
chk('싱가포르: 세액=배출×S$45, ICC 상한=5%, 절감=ICC량×(45−가정가격)', sg['result']['taxSgd'] == sg['assumed']['expectedEmissionTon'] * 45 and sg['result']['iccMaxTon'] == round(sg['assumed']['expectedEmissionTon'] * .05) and sg['result']['savingSgd'] == round(sg['result']['iccMaxTon'] * (45 - 30)), sg['result'])
chk('JP·SG 모두 대상 기준 초과(10만 t·2.5만 t) 판정', g['result']['aboveTargetThreshold'] and sg['result']['aboveTaxableThreshold'], '')
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
