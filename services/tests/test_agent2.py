import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agentapi'))
import agent_core as K
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
chk('작업 9종 등록: A01~A05와 소유 서비스 S02·S03·S04·S05·S06(A03은 의도 설명+한국·일본·싱가포르 판단+거래 건 질의응답 5종)', sorted((v[0], v[1]) for v in K.TASKS.values()) == [('AI-A01', 'S02'), ('AI-A02', 'S03'), ('AI-A03', 'S04'), ('AI-A03', 'S04'), ('AI-A03', 'S04'), ('AI-A03', 'S04'), ('AI-A03', 'S04'), ('AI-A04', 'S05'), ('AI-A05', 'S06')])
def v(task, role, owner='S03', ref='r1'): K.validate_run(dict(schemaVersion='1', role=role, task=task, purpose='explain', plantScope='KR-01', contextRefs=[dict(owner=owner, id=ref)]))
v('explain_scenario', 'AI-A02', 'S03'); chk('A02 요청 검증 통과', True)
for task, role, owner in [('explain_scenario', 'AI-A01', 'S03'), ('explain_scenario', 'AI-A02', 'S02'), ('explain_procurement_intent', 'AI-A02', 'S04'), ('explain_unknown', 'AI-A02', 'S03')]:
    try: v(task, role, owner); chk('잘못된 역할·owner·task 거절 %s/%s/%s' % (task, role, owner), False)
    except K.Reject as e: chk('잘못된 역할·owner·task 거절 %s/%s/%s → %s' % (task, role, owner, e.code), e.status in (422,))
PLAN = dict(runId='x', status='SUCCEEDED', feasibility=True, calculationScope='ENERGY_COST_ONLY', resultKind='SIMULATED', publishable=False, metricStatus=dict(energyCost='COMPLETE'), planRef='p@1', constraintRef='c@1', priceRef='pr@1', fxRef='none', result=dict(energyCostTotal=dict(value='62400000.000', currency='KRW'), totalCost=None, resultHash='h' * 64))
f = K.facts_plan(PLAN); chk('A02 FACTS: 성공 결과만, 해시 제외', f and f['result']['energyCostTotal']['value'] == '62400000.000' and 'resultHash' not in f['result'], f)
chk('A02: BLOCKED_DEPENDENCY(수치 없음)는 FACTS None', K.facts_plan(dict(PLAN, status='BLOCKED_DEPENDENCY', result=None)) is None)
chk('A02 숫자 근거 검사: FACTS 값 인용 통과·없는 숫자 차단', K.grounding('에너지 비용은 62400000.000 KRW입니다.', f)[0] and not K.grounding('에너지 비용은 70000000 KRW입니다.', f)[0])
INT = dict(intentId='i1', intentVersion=2, mode='SIMULATED', state='DRAFT', bindingState='UNRESOLVED', instrumentType='electricity', quantity=dict(value='1000', unit='MWh'), currency='KRW', delivery=dict(start='2026-11-01T00:00:00Z', end='2026-12-01T00:00:00Z'), blockers=['POLICY_D12_UNRESOLVED'], externalReady=False)
fi = K.facts_intent(INT); chk('A03 FACTS: 의도 초안 상태·차단 사유', fi and fi['blockers'] == ['POLICY_D12_UNRESOLVED'] and fi['quantity']['value'] == '1000', fi)
chk('A03: 의도 없음은 None', K.facts_intent({}) is None)
chk('A04: waiting_source(수치 없음)은 None=BLOCKED', K.facts_footprint(dict(requestId='q', requestState='waiting_source', result=None)) is None)
ff = K.facts_footprint(dict(requestId='q', requestState='ready', result=dict(value='1.5', unit='kgCO2e/kg'), disclosable=False)); chk('A04: 수치가 있으면 FACTS', ff and ff['result']['value'] == '1.5', ff)
EV = dict(manifestId='m', generationState='LOCAL_UNSIGNED_DRAFT_READY', label='미서명', signingState='NOT_CONFIGURED', externalVerificationState='NOT_VERIFIED', manifestCore=dict(items=[dict(itemId='S01-INGESTIONS', inclusionStatus='INCLUDED', digest='z'), dict(itemId='S05-DISCLOSURE', inclusionStatus='EXCLUDED')]))
fe = K.facts_evidence(EV); chk('A05 FACTS: 포함·제외 항목만(해시 제외)', fe and [i['itemId'] for i in fe['items']] == ['S01-INGESTIONS', 'S05-DISCLOSURE'] and 'digest' not in json.dumps(fe), fe)
chk('A05: 조립 중(REQUESTED)은 None', K.facts_evidence(dict(EV, generationState='REQUESTED')) is None)
for t in K.TASKS: chk('프롬프트 생성 %s' % t, 'FACTS=' in K.build_prompt({'a': '1'}, '', t) and K.TASKS[t][2] in K.build_prompt({'a': '1'}, '', t))
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
