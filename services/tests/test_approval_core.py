import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'approvalapi'))
import approval_core as A
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, info)
def rej(fn, code):
    try: fn(); return False
    except A.Reject as e: return e.code == code
base = dict(action='procurement.rec.purchase', resource='REC', purpose='HEDGE', operationKey='KR|AMA-KR|S04|op-1', intentDigest='a' * 64, canonicalizationVersion=A.CANON, digestAlgorithmId='sha256', amount=dict(value='1000000', currency='KRW'))
r = A.evaluate(base); chk('API07: D12 미결 → needs-approval/POLICY_UNRESOLVED/proposeOnly(허용·예약·서명 없음)', r['decision'] == 'needs-approval' and r['reasonCode'] == 'POLICY_UNRESOLVED' and r['proposeOnly'] and r['amountMinor'] == 1000000)
chk('금액: USD 12.34 → 1234(최소단위 정수), KRW 소수/float/음수/미지원 통화 거절', A.minor('12.34', 'USD') == 1234 and rej(lambda: A.minor('1.5', 'KRW'), 'BAD_AMOUNT') and rej(lambda: A.minor(1.5, 'KRW'), 'BAD_AMOUNT') and rej(lambda: A.minor('-1', 'KRW'), 'BAD_AMOUNT') and rej(lambda: A.minor('1', 'BTC'), 'BAD_CURRENCY'))
chk('미지원 정규화 규약 → 422(관용 동치 없음)', rej(lambda: A.evaluate(dict(base, canonicalizationVersion='x')), 'CANONICALIZATION_UNSUPPORTED') and rej(lambda: A.evaluate(dict(base, digestAlgorithmId='md5')), 'CANONICALIZATION_UNSUPPORTED'))
chk('필수 필드·digest 형식 검사', rej(lambda: A.evaluate({k: v for k, v in base.items() if k != 'operationKey'}), 'BAD_REQUEST') and rej(lambda: A.evaluate(dict(base, intentDigest='ZZ')), 'BAD_DIGEST'))
chk('결정: MFA 문맥 없으면 503(승인 불가)', rej(lambda: A.decide('pending', 'u1', 'u2', 'approve', False, True, 1, 1), 'AUTH_CONTEXT_UNAVAILABLE'))
chk('결정: 신청자=승인자 403', rej(lambda: A.decide('pending', 'u1', 'u1', 'approve', True, True, 1, 1), 'SEPARATION_OF_DUTY'))
chk('결정: 버전 불일치 409(자동 재승인 없음)', rej(lambda: A.decide('pending', 'u1', 'u2', 'approve', True, True, 1, 2), 'VERSION_CONFLICT'))
chk('결정: intent 재검증 불가 → 승인 503, 반려는 가능', rej(lambda: A.decide('pending', 'u1', 'u2', 'approve', True, False, 1, 1), 'BLOCKED_DEPENDENCY') and A.decide('pending', 'u1', 'u2', 'reject', True, False, 1, 1) == 'rejected')
chk('결정: 정상 승인 pending→approved, 종료 상태는 전이 불가', A.decide('pending', 'u1', 'u2', 'approve', True, True, 1, 1) == 'approved' and rej(lambda: A.decide('rejected', 'u1', 'u2', 'cancel', True, True, 1, 1), 'BAD_STATE'))
acc = dict(cap=1000, held=0, settled=0, rev=1); a1 = A.reserve(acc, 600); chk('한도: 예약 600/1000 held=600, rev 증가, 원본 불변', a1['held'] == 600 and a1['rev'] == 2 and acc['held'] == 0)
chk('한도: 초과 예약 409(cap ≥ held+settled 유지)', rej(lambda: A.reserve(a1, 401), 'LIMIT_EXCEEDED') and A.reserve(a1, 400)['held'] == 1000)
a2 = A.settle(a1, 600, 550); chk('정산: held 0·settled 550(증거 있는 정산)', a2['held'] == 0 and a2['settled'] == 550 and a2['cap'] >= a2['held'] + a2['settled'])
chk('정산: 실제>예약 → review-required(자동 보정 없음)', rej(lambda: A.settle(a1, 600, 601), 'SETTLEMENT_MISMATCH'))
chk('해제: 증거 불충분이면 held 유지(거절), 충분할 때만 해제', rej(lambda: A.release(a1, 600, False), 'RELEASE_EVIDENCE_INSUFFICIENT') and A.release(a1, 600, True)['held'] == 0)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
