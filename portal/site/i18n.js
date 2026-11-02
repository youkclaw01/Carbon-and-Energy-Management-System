'use strict';
// 한영 변환: 화면은 항상 한국어 원문으로 그려지고, 영어 모드에서는 이 모듈이 텍스트 노드를 영어로 바꿉니다.
// 원문은 WeakMap에 보관해 한국어로 즉시 복원합니다(새로고침·깜빡임 없음). 모든 값·구조는 동일하며 문구만 바뀝니다.
(function () {
  const N = '([-+]?[\\d.,]+)';
  const EXACT = {
    '탄소·에너지': 'Carbon & Energy', '오늘만 사는 나': 'Living Only for Today', '에이전트 관리': 'Agent Management', '공장 VM 현장': 'Factory VM Floor', '데이터 흐름': 'Data Flow', '지식 검색': 'Knowledge Search', '메종': 'Maison', '클라우드 화이트': 'Cloud White', '펄 화이트': 'Pearl White', '미스트 그린': 'Mist Green', '포슬린 블루': 'Porcelain Blue', '블러시 화이트': 'Blush White', '아이보리': 'Ivory', '종합 관제': 'Overview', '공장 운영': 'Plant Operations', '산정 결과': 'Calculation Results', '시뮬레이션': 'Simulation', '조달·승인': 'Procurement & Approval', '고객 탄소정보': 'Customer Carbon Data', '증빙·감사': 'Evidence & Audit',
    '🌐 국가·지역별 자료 경계': '🌐 Country / region data boundaries', '아시아 공장 종합 관제': 'Asia Plant Control Center',
    '디자인 시안 · 모의 자료 · 실제 운영 미연결': 'Design draft · Mock data · Not connected to live operations',
    '디자인 시안 · 실제 운영 미연결 · 모든 수치는 가상의 모의 자료입니다 · AMA 설계 v3 (한국 리전 목표 구성)': 'Design draft · Not connected to live operations · All figures are fictitious mock data · AMA design v3 (target Korea-region configuration)',
    '추정값은 검증 전': 'Estimates are not yet verified', '전체 지역': 'All regions', '한국': 'Korea', '일본': 'Japan', '싱가포르': 'Singapore',
    '배출 추정': 'Emission estimate', '추정·검증 전': 'Estimate · unverified', '추정': 'Estimate', '에너지 비용': 'Energy cost', '억 원': '×100M KRW', '억': '×100M KRW', '환율 기준 예시 · KRW': 'Sample FX basis · KRW', '관제 공장': 'Monitored plants', '예시': 'Sample', '개': 'plants', '건': 'items',
    '정상': 'Normal', '주의': 'Caution', '경고': 'Warning', '자료 지연': 'Data delay', '초과 예상': 'Over forecast', '확인 필요': 'Needs review', '검토 대기': 'Pending review', '누르면 AI와 확인·메일 작성': 'Click to check with AI and draft an email',
    '아시아 공장 현황': 'Asia plant status', '국가별 배치 · 지리 좌표 아님': 'Placement by country · not geographic coordinates', '중국': 'China', '인도': 'India', '몽골': 'Mongolia', '태평양': 'Pacific Ocean', '인도양': 'Indian Ocean', 'ⓘ 기준': 'ⓘ Criteria',
    '공장': 'Plant', '배출': 'Emissions', '목표': 'Target', '비용': 'Cost', '생산': 'Production', '전력': 'Power', '지역': 'Region', '상태': 'Status', '배출 (기간)': 'Emissions (period)', '비용 (기간)': 'Cost (period)', '생산량 (기간)': 'Production (period)', '전력 (기간)': 'Power (period)', '목표 대비': 'vs target',
    '공장 운영에서 자세히': 'Details in Plant Operations', '이번 달 예측 보기': 'View this month\'s forecast', '실적 추이로 돌아가기': 'Back to actual trend', '검토': 'Review',
    '"검토"를 누르면 AI와 대화하며 원인 확인·담당자 메일 작성까지 진행할 수 있습니다.': 'Click "Review" to chat with AI, check the cause, and draft an email to the owner.',
    '디자인 시안 · 모의 로그인입니다. 입력값은 검증·저장되지 않습니다.': 'Design draft · Mock login. Inputs are not validated or stored.', '아이디': 'User ID', '비밀번호': 'Password', '역할 선택(시안: 역할별 메뉴 권한 확인용)': 'Select a role (draft: to check role-based menu access)', '관제 담당': 'Control operator', '승인자': 'Approver', '감사': 'Auditor', '로그인 (모의)': 'Log in (mock)',
    '실제 인증(Entra ID 등)은 별도 설계 대상이며 시안에는 연결되어 있지 않습니다.': 'Real authentication (e.g., Entra ID) is a separate design item and is not connected in this draft.', '모의 기준일': 'Mock reference date',
    '사용률 70% 이상 주의 · 90% 이상 경고 · 전월 +10% 급증 시 한 단계 상향 · 수신 6시간 이상 끊기면 자료 지연': 'Usage 70%+ = Caution · 90%+ = Warning · +10% month-over-month surge raises one level · No data for 6h+ = Data delay',
    '예측·추정 · 모의': 'Forecast / estimate · Mock', '지금까지(실적)': 'So far (actual)', '예상': 'Forecast', '80% 예상 범위': '80% forecast range', '기준일': 'Reference date', '결론: 주의': 'Conclusion: Caution', '결론: 문제 없음': 'Conclusion: No problem', '결론: 이번 달 문제 예상': 'Conclusion: Problem expected this month', '근거·요인 보기': 'View basis and drivers', '예측 근거': 'Forecast basis', '확인할 곳': 'Where to check',
    '역할 선택 · 관리자만 고를 수 있고 일반 계정은 등급별로 고정됩니다': 'Role · only administrators can choose; other accounts are fixed by grade', '음영은 최근 28일 변동폭으로 계산한 80% 예상 범위입니다.': 'The shaded area is the 80% forecast range based on the last 28 days of variation.',
    '단순 추세 기반 모의 예측이며 확정값이 아닙니다. 실제 예측 모델은 별도 설계 대상입니다.': 'This is a simple trend-based mock forecast, not a confirmed value. The real forecasting model is a separate design item.',
    '공장 운영 → 시간대별 전력(피크)과 공정 부하': 'Plant Operations → hourly power (peak) and process load', '설비 수신 상태(지연 설비가 있으면 추정이 부정확)': 'Equipment data status (estimates are less accurate if equipment is delayed)', '확인 필요 목록의 관련 항목': 'Related items in the review list',
    '사용량 변화': 'Usage change', '환율 영향': 'FX effect', '단가·시간대(피크) 영향': 'Unit price / time-of-day (peak) effect', '이번 달 누적(실적)': 'This month cumulative (actual)', '월말까지 예상': 'Forecast to month-end',
    '배출 추정 · 공장별 현황': 'Emission estimate · Plant status', '에너지 비용 · 공장별 현황': 'Energy cost · Plant status', '현재(tCO₂)': 'Current (tCO₂)', '현재(억 원)': 'Current (×100M KRW)', '목표 대비 ': 'vs target ', '예산 대비': 'vs budget', '여유': 'Headroom', '이번 달 예상(tCO₂)': 'This-month forecast (tCO₂)', '이번 달 예상(억 원)': 'This-month forecast (×100M KRW)', '직전 대비': 'vs previous', '단가·환율 영향': 'Price / FX effect', '예측 상태': 'Forecast status', '실적만': 'Actual only',
    '올해 누적은 비교할 직전 동일 기간이 없어 "직전 대비" 열을 숨겼습니다. 증감은 기간을 "이번 달/최근 1개월/최근 3개월"로 바꾸면 표시됩니다.': 'Year-to-date has no previous equal period to compare, so the "vs previous" column is hidden. Change the period to "This month / Last 1 month / Last 3 months" to see changes.',
    '행을 누르면 아래에 해당 공장의 이번 달 예측이 열립니다. 열 제목을 누르면 정렬됩니다. 상태 기준: 70% 주의 · 90% 경고 · 100% 초과.': 'Click a row to open that plant\'s forecast for this month below. Click a column header to sort. Status thresholds: 70% caution · 90% warning · 100% exceeded.',
    '현재 누적(이번 달)': 'Cumulative so far (this month)', '현재 상태': 'Current status', '월말 예상': 'Month-end forecast', '한도 대비 예상': 'Forecast vs limit', '예산 대비 예상': 'Forecast vs budget',
    '공장 운영에서 보기': 'View in Plant Operations', '이 공장 확인 필요 보기': 'View review items for this plant', '관제 공장 · 공장을 선택하세요': 'Monitored plants · Select a plant', '생산량': 'Production',
    '공장을 누르면 아래에 그 공장의 상세 카드(생산·에너지·탄소·설비 현황)가 나타납니다.': 'Click a plant to show its detail cards (production, energy, carbon, equipment) below.',
    '근거 수치': 'Supporting figures', '원인': 'Cause', '확인 순서': 'Steps to verify', '모의 응답': 'Mock reply', 'AI 도우미': 'AI assistant', '요약': 'Summary', '핵심 원인': 'Key cause', '나': 'Me',
    '근거 수치와 확인 순서는 왼쪽 항목 아래에 펼쳐져 있습니다. 궁금한 점은 아래 버튼이나 입력창으로 물어보세요.': 'The supporting figures and verification steps are expanded under the item on the left. Ask anything with the buttons or the input box below.',
    '왜 확인이 필요한가요?': 'Why is this review needed?', '어떻게 확인하나요?': 'How do I check it?', '근거 수치 보기': 'Show supporting figures', '이번 달 예측': 'This month\'s forecast', '담당자에게 메일': 'Email the owner', '해결 처리': 'Mark resolved', '보내기': 'Send', '담당자 메일 작성': 'Draft email to owner',
    'AI 응답은 시안용 모의 대본입니다. 실제 구현에서는 공장 데이터를 근거로 설명하며, 메일 등 외부 발송은 검수자가 확인한 뒤에만 수행합니다.': 'AI replies are mock scripts for this draft. In the real implementation, explanations are based on plant data, and external sends such as email are made only after a person confirms.',
    '질문을 입력하세요 (예: 어떻게 확인하나요?)': 'Type a question (e.g., How do I check it?)', '질문 입력': 'Question input',
    '가상 위치(지역 단위)': 'Virtual locations (region level)', '이번 달 · 10.01~10.20': 'This month · 10.01~10.20',
    '선택한 기간에 이번 달이 포함되어야 예측을 볼 수 있습니다': 'The selected period must include this month to view the forecast', '시안 단계: 실제 실행과 연결되어 있지 않습니다': 'Draft stage: not connected to real execution',
    '마지막 수신': 'Last received', '오늘 현황 (기준일 10.20 12:00, 모의)': 'Today (reference date 10.20 12:00, mock)', '전력 수요(현재)': 'Power demand (now)', '오늘 사용량(누적)': 'Today\'s usage (cumulative)', '오늘 배출(누적)': 'Today\'s emissions (cumulative)', '추정 · 직접+간접': 'Estimate · direct + indirect', '자료 수신 상태': 'Data reception status',
    '가동률': 'Utilization', '불량률': 'Defect rate', '양호': 'Good', '주의 수준(2% 초과)': 'Caution level (over 2%)', '원단위': 'Intensity', '목표·예산 대비': 'vs target / budget', '배출 한도 사용률': 'Emission limit usage', '에너지 비용 예산 사용률': 'Energy cost budget usage',
    '시간대별 전력 수요 (기준일 10.20)': 'Hourly power demand (reference day 10.20)', '실제': 'Actual', '기준선': 'Baseline', '기간 추이': 'Period trend', '공정별 부하 열지도 (%, 기준일)': 'Process load heatmap (%, reference day)', '압출': 'Extrusion', '성형': 'Molding', '후처리': 'Post-processing',
    '진할수록 부하가 높은 시간대입니다. 피크(14~17시)에 부하가 몰리면 전력 단가가 높아집니다.': 'Darker cells mean higher load. When load concentrates at peak hours (14–17h), the power unit price rises.',
    '설비 목록': 'Equipment list', '설비 ID': 'Equipment ID', '설비명': 'Equipment', '공정': 'Process', '자료 수신': 'Data reception', '압출기 1호': 'Extruder #1', '성형기 2호': 'Molder #2', '냉각탑': 'Cooling tower', '컴프레서': 'Compressor', '보일러': 'Boiler', '수배전반': 'Switchgear', '수신 없음': 'No data',
    '이 공장의 확인 필요 항목이 없습니다.': 'No review items for this plant.', 'AI와 확인': 'Check with AI', '확인이 필요한 항목이 없습니다.': 'No items need review.', '확인이 필요한 항목이 없습니다. 모두 처리되었습니다.': 'No items need review. All have been handled.', '왼쪽에서 항목을 선택하세요.': 'Select an item on the left.',
    '직접 배출 (Scope 1)': 'Direct emissions (Scope 1)', '간접 배출 (Scope 2)': 'Indirect emissions (Scope 2)', '지역 기반': 'Location-based', '선택 기준 합계': 'Total (selected basis)', '시장 기반 병행': 'Market-based (parallel)', '산정 상태': 'Calculation status', '초안': 'Draft', '계수 버전 EF-2026.1': 'Factor version EF-2026.1', '월별 배출 추이 (KR-01)': 'Monthly emission trend (KR-01)', '배출 구성': 'Emission breakdown', '배출 결과 (KR-01)': 'Emission results (KR-01)', '예시 · 초안': 'Sample · Draft',
    '구분': 'Category', '활동량': 'Activity', '단위': 'Unit', '계수': 'Factor', '계수 버전': 'Factor version', '배출량(tCO₂)': 'Emissions (tCO₂)', '고정 연소': 'Stationary combustion', '이동 연소': 'Mobile combustion', '구입 전력': 'Purchased electricity', '구입 열': 'Purchased heat',
    '시나리오 가정 (예시)': 'Scenario assumptions (sample)', '미검증': 'Unverified', '재생에너지 비중': 'Renewable energy share', '피크 시간 사용': 'Peak-hour usage', '연료 전환': 'Fuel switching', '시나리오 저장': 'Save scenario', '검토 요청': 'Request review', '실행 (비활성)': 'Run (disabled)', '시나리오 결과': 'Scenario results', '가정 · 예상 · 미검증': 'Assumed · Forecast · Unverified', '예상 배출': 'Forecast emissions', '가정 기반 · 미검증': 'Assumption-based · Unverified', '예상 에너지 비용': 'Forecast energy cost', '가정 기반': 'Assumption-based', '대안 상태': 'Alternative status', '검토 요청 전': 'Before review request', '저장·검토 요청만 가능 (실행 불가)': 'Save / request review only (cannot execute)', '기준': 'Baseline', '현재 가정': 'Current assumption', '피크 10%↓': 'Peak −10%', '전환 20%': '20% switch',
    '조달 필요 (예시 합계)': 'Procurement needed (sample total)', '월 기준': 'Monthly basis', '확정 커버리지': 'Confirmed coverage', '확정 계약 기준': 'Based on confirmed contracts', '예상 비용': 'Forecast cost', '모의': 'Mock', '승인 대기': 'Awaiting approval', '직무 분리 적용': 'Segregation of duties applied', '월별 조달 커버리지 (예시)': 'Monthly procurement coverage (sample)', '승인 요청 목록': 'Approval requests', '요청': 'Request', '내용': 'Description', '금액': 'Amount', 'REC 구매 10,000': 'REC purchase 10,000', '검토 중': 'Under review', '전력 PPA 연장': 'Power PPA extension', '탄소배출권': 'Carbon credits', '요청 생성': 'Create request', '제한 실행 (비활성)': 'Limited execution (disabled)', '거래 시스템 미연결 · 승인 후에도 이 화면에서는 실행되지 않습니다': 'Trading system not connected · Not executed from this screen even after approval',
    '제품 수': 'Products', '종': 'types', '선언 단위 1 kg': 'Declared unit 1 kg', '공개 승인': 'Publication approval', '초안 → 승인 대기': 'Draft → Awaiting approval', '고객 전송': 'Send to customer', '비활성 (시안)': 'Disabled (draft)', '다음 마감': 'Next deadline', '일': 'd', '제품 목록': 'Product list', '제품 ID': 'Product ID', '제품명': 'Product', '선언 단위': 'Declared unit', '탄소발자국(kgCO₂e)': 'Carbon footprint (kgCO₂e)', '냉연 강판': 'Cold-rolled steel', '도금 강판': 'Coated steel', '고강도 강판': 'High-strength steel', '화학 소재 A': 'Chemical material A', '선택 제품 · P-104 고강도 강판': 'Selected product · P-104 High-strength steel', '탄소발자국': 'Carbon footprint', '산정 경계': 'Calculation boundary', '요람~공장 문': 'Cradle-to-gate', '배분 방법': 'Allocation method', '질량 배분': 'Mass allocation', '승인 후 열람 가능': 'Viewable after approval', '전송': 'Send',
    '증빙 문서': 'Evidence documents', '검증 완료율': 'Verification rate', '무결성 검토 대기': 'Integrity check pending', '감사 기록': 'Audit log', '추가 기록형 (개념 표기)': 'Append-only (conceptual)', '증빙 목록': 'Evidence list', '문서': 'Document', '버전': 'Version', '국가': 'Country', '체크섬': 'Checksum', 'CALC-026 근거': 'CALC-026 basis', '검증': 'Verified', '전력 청구서 10월': 'Power bill (Oct)', '공장 계량 기록': 'Plant metering record', '배출계수 표': 'Emission factor table', '공통': 'Common', '근거 흐름 · CALC-026': 'Evidence flow · CALC-026', '측정 자료': 'Measured data', '변환·검증': 'Convert · verify', '산정': 'Calculate', '승인': 'Approve', '시각': 'Time', '행위': 'Action', '대상': 'Target', '증빙 추가': 'Add evidence', ' (디자인 시안)': ' (design draft)',
    '권한 없음': 'No access', '시안': 'Draft', '필요하면 권한이 있는 역할로 다시 로그인하세요.': 'If needed, log in again with a role that has access.', '종합 관제로 이동': 'Go to Overview', '확인 순서입니다.': 'Here are the steps.', '근거 수치입니다.': 'Here are the supporting figures.',
    '1. 공장 운영 → "시간대별 전력 수요"에서 최근 피크(기준선 대비)를 확인합니다.': 'Plant Operations → check the recent peak (vs baseline) in "Hourly power demand".', '공장 운영 → "시간대별 전력 수요"에서 최근 피크(기준선 대비)를 확인합니다.': 'Plant Operations → check the recent peak (vs baseline) in "Hourly power demand".',
    '"공정 부하 열지도"에서 부하가 높아진 공정과 시간대를 찾습니다.': 'Find the processes and hours with higher load in the "Process load heatmap".', '설비 목록에서 컴프레서·냉각탑의 수신 상태와 가동 이력을 확인합니다.': 'In the equipment list, check the data status and run history of the compressor and cooling tower.', '담당자에게 가동 일정 변경·정비 이력을 문의합니다.': 'Ask the owner about operating-schedule changes and maintenance history.',
    '배출 추정 → 공장별 현황에서 이 공장의 목표 대비·이번 달 예상을 확인합니다.': 'Emission estimate → in Plant status, check this plant\'s vs-target and this month\'s forecast.', '공장 운영 → 시간대별 전력에서 피크 시간대를 확인합니다.': 'Plant Operations → check the peak hours in hourly power.', '간접 배출(전력) 비중이 높으면 피크 이동·재생에너지 시나리오를 시뮬레이션에서 비교합니다.': 'If the indirect (power) share is high, compare peak-shift and renewable scenarios in Simulation.',
    '근거 누락 1건 (활동 자료 ↔ 증빙 문서 미연결)': '1 missing basis (activity data ↔ evidence document not linked)', '계수 버전 EF-2026.1 (모의)': 'Factor version EF-2026.1 (mock)', '산정 상태: 초안·검증 전': 'Calculation status: draft · unverified',
    '활동 자료 1건에 근거 문서(계량 파일)가 연결되지 않았고, 계수 버전 EF-2026.1이 적용되었는지 확인이 필요합니다. 근거가 확인되기 전에는 확정 발행·고객 공개에 쓰면 안 됩니다.': 'One activity record has no linked evidence document (metering file), and you need to confirm that factor version EF-2026.1 was applied. Do not use it for final publication or customer disclosure until the basis is confirmed.',
    '산정 결과 → CALC 실행 정보에서 계수 버전과 기준 기간을 확인합니다.': 'Calculation Results → check the factor version and base period in the CALC run info.', '증빙·감사 → 근거 추적에서 누락된 활동 자료의 증빙 문서를 찾습니다.': 'Evidence & Audit → find the evidence document for the missing activity data in basis tracing.', '누락이면 담당자에게 증빙 업로드를 요청하고, 확인되면 검토를 완료 처리합니다.': 'If missing, ask the owner to upload the evidence; once confirmed, complete the review.',
    '자료가 끊기면 배출·비용 추정이 실제보다 낮게 계산될 수 있어 이 공장은 "자료 지연"으로 따로 표시합니다. 성과(목표 대비)와는 별개로 먼저 수신을 복구해야 합니다.': 'If data stops, emission and cost estimates can be calculated lower than actual, so this plant is shown separately as "Data delay". Restore reception first, independent of performance (vs target).',
    '공장 운영 → 설비 목록에서 마지막 수신 시각을 확인합니다.': 'Plant Operations → check the last received time in the equipment list.', '현장 게이트웨이·네트워크 상태를 담당자에게 확인합니다.': 'Ask the owner to check the on-site gateway and network status.', '복구 후 누락 구간 자료가 보충되는지(백필) 확인하고, 그동안의 추정값은 "추정"으로 표시합니다.': 'After recovery, confirm that the missing interval is backfilled; estimates for that time are labeled "Estimate".',
    '담당자 메일 작성 · ': 'Draft email to owner · ', '수신자': 'To', '참조': 'Cc', '제목': 'Subject', '본문(AI 초안 · 수정 가능)': 'Body (AI draft · editable)', 'AI는 초안만 작성합니다. 외부로 나가는 메일은 검수자가 확인한 뒤에만 발송됩니다(승인 단계 표시).': 'AI only writes the draft. Outgoing email is sent only after a person confirms (approval step shown).', '내용을 직접 확인했습니다(발송 전 검수자 확인 필수)': 'I have reviewed the content myself (human confirmation required before sending)', '발송 (모의)': 'Send (mock)', '닫기': 'Close', '시안 · 모의': 'Draft · Mock',
    '이 항목에 대해 "왜 확인이 필요한지", "어떻게 확인하는지", "근거 수치", "담당자 메일", "해결 처리"를 도와드릴 수 있습니다. 어느 쪽이 필요하신가요? (시안용 모의 응답입니다)': 'For this item I can help with "why a review is needed", "how to check", "supporting figures", "owner email", and "mark resolved". Which do you need? (mock reply for this draft)',
    '원인 확인과 조치가 끝났다면 해결 처리할 수 있습니다. 처리하면 목록과 KPI 건수에서 빠집니다.': 'If the cause has been checked and action is complete, you can mark it resolved. It will be removed from the list and the KPI count.', '메일 작성 창 열기': 'Open email draft', '예측 차트 보기': 'View forecast chart',
    '항목을 선택하면 오른쪽에서 AI와 대화하며 원인을 확인하고, 담당자 메일을 작성할 수 있습니다.': 'Select an item to chat with AI on the right, check the cause, and draft an email to the owner.', '필터 해제 ✕': 'Clear filter ✕',
    '이번 달': 'This month', '최근 1개월': 'Last 1 month', '최근 3개월': 'Last 3 months', '지난 분기': 'Last quarter', '올해 누적': 'Year to date', '달력에서 선택': 'Pick from calendar', '사용자 지정': 'Custom', '적용': 'Apply', '취소': 'Cancel', '시작 —': 'Start —', '종료 —': 'End —', '기간 선택': 'Select period',
    '월': 'Mon', '화': 'Tue', '수': 'Wed', '목': 'Thu', '금': 'Fri', '토': 'Sat', '1월': 'Jan', '2월': 'Feb', '3월': 'Mar', '4월': 'Apr', '5월': 'May', '6월': 'Jun', '7월': 'Jul', '8월': 'Aug', '9월': 'Sep', '10월': 'Oct',
    '지금까지': 'So far', '누적 실적': 'Cumulative actual', '예상 누적': 'Forecast cumulative', '직접(연료)': 'Direct (fuel)', '간접(전력)': 'Indirect (power)', '직접(연료·공정)': 'Direct (fuel / process)', '간접(구입 전력)': 'Indirect (purchased power)', '이달 예산': 'Monthly budget', '이달 한도': 'Monthly limit', '배출량': 'Emissions', '모의 응답입니다': 'Mock reply',
    '기준: 70% 주의 · 90% 경고': 'Criteria: 70% caution · 90% warning', '입력 중…': 'Typing…', '(모의 동작)': '(mock action)', '시나리오를 저장했습니다 (모의 · 실제 저장 안 됨)': 'Scenario saved (mock · nothing actually saved)', '검토 요청을 보냈습니다 (모의 · 실제 전송 안 됨)': 'Review request sent (mock · nothing actually sent)', '검토를 시작했습니다 (모의 · 저장되지 않음)': 'Review started (mock · not saved)', '메일 발송 완료(모의 · 실제 발송 안 됨)': 'Email sent (mock · nothing actually sent)',
    '이 화면은 디자인 시안이며 모든 값은 가상의 모의 자료입니다.': 'This screen is a design draft and all values are fictitious mock data.', '근거 예시: 전월 대비 사용량 +14%, 수신 지연 설비 1건, 계수 버전 변경 없음.': 'Basis example: usage +14% vs last month, 1 equipment with data delay, no factor version change.', '검토 시작 (모의)': 'Start review (mock)', '항목': 'Item', '기준 시각': 'Reference time', '산정 버전': 'Calc version', 'CALC v3.2 (예시)': 'CALC v3.2 (sample)', '근거 확인 · ': 'Check basis · ', '검토 · ': 'Review · ', '상세 · ': 'Detail · ',
    '증가(전월 대비 늘림)': 'Increase (up vs last month)', '감소': 'Decrease', '배출 비중·구성': 'Share · composition', '증감 기여': 'Change contribution',
    '에너지 비용 상승': 'Energy cost increase', '배출 목표 근접(주의)': 'Approaching emission target (caution)', '산정 근거 검토': 'Calculation basis review', '자료 수신 지연': 'Data reception delay', '관제 총괄(가상)': 'Control supervisor (fictional)', '(가상)': '(fictional)', '모든 지역': 'All regions',
    '독도': 'Dokdo', '배출 목표 사용': 'Emission target used', '비용 예산 사용': 'Cost budget used', '바 = 목표(예산) 대비 사용률 · 눈금 70% 주의 · 90% 경고': 'Bar = usage vs target (budget) · ticks: 70% caution · 90% warning', '울산': 'Ulsan', '포항': 'Pohang', '광양': 'Gwangyang', '당진': 'Dangjin', '광주': 'Gwangju', '기타큐슈': 'Kitakyushu', '구라시키': 'Kurashiki', '지바': 'Chiba', '나고야': 'Nagoya', '주롱': 'Jurong', '투아스': 'Tuas', '우드랜즈': 'Woodlands',
    '김도윤': 'Kim Do-yun', '박서준': 'Park Seo-jun', '이하늘': 'Lee Ha-neul', '최민재': 'Choi Min-jae', '정유진': 'Jung Yu-jin', '다나카 켄': 'Ken Tanaka', '사토 유이': 'Yui Sato', '스즈키 렌': 'Ren Suzuki', '이토 아야': 'Aya Ito', '탄 웨이': 'Wei Tan', '리 메이': 'Mei Lee', '응 지아': 'Jia Ng'
  };
  const EN_C = { 한국: 'Korea', 일본: 'Japan', 싱가포르: 'Singapore' }, LV = { 정상: 'Normal', 주의: 'Caution', 경고: 'Warning', '자료 지연': 'Data delay', '초과 예상': 'Over forecast', '문제 없음': 'No problem', '문제 예상': 'Problem expected' };
  const U = s => s.replace(/(\d)\s*억 원/g, '$1 ×100M KRW').replace(/(\d)\s*억/g, '$1 ×100M KRW').replace(/억 원/g, '×100M KRW').replace(/억/g, '×100M KRW');
  const lim = k => k === '예산' ? 'budget' : 'limit', limz = k => k === '예산을' ? 'budget' : 'limit';
  const L2 = (s) => tr(s);
  // 문장 단위 규칙
  const RULES = [
    [/^· (.+)$/, m => '· ' + L2(m[1])],
    [/^(.+?) ([▲▼])$/, m => L2(m[1]) + ' ' + m[2]],
    [/^(\d)\. (.+)$/, m => m[1] + '. ' + L2(m[2])],
    [/^📅 (.+)$/, m => '📅 ' + L2(m[1])],
    [/^(.+?) · (\d\d\.\d\d)~(\d\d\.\d\d)$/, m => L2(m[1]) + ' · ' + m[2] + '~' + m[3]],
    [/^(한국|일본|싱가포르)(\d+)((?:·(?:한국|일본|싱가포르)\d+)*)$/, m => [m[0]].join('').split('·').map(x => { const q = x.match(/^(한국|일본|싱가포르)(\d+)$/); return EN_C[q[1]] + ' ' + q[2]; }).join(' · ')],
    [/^(한국|일본|싱가포르) · (\d+)개$/, m => EN_C[m[1]] + ' · ' + m[2] + ' plants'],
    [/^(한국|일본|싱가포르) 공장 현황$/, m => EN_C[m[1]] + ' plant status'],
    [/^경고 (\d+) · 주의 (\d+) · 지연 (\d+)$/, m => `Warning ${m[1]} · Caution ${m[2]} · Delayed ${m[3]}`],
    [/^(?:확인 필요|확인 필요 목록|주요 알림·확인 필요) \((\d+)건\)$/, m => `Needs review (${m[1]})`],
    [/^선택 공장 · (\S+?)( · 이번 달 예측)?$/, m => 'Selected plant · ' + m[1] + (m[2] ? ' · This month\'s forecast' : '')],
    [/^AI 확인 도우미 · (\S+) (.+)$/, m => 'AI review assistant · ' + m[1] + ' ' + L2(m[2])],
    [/^(KR|JP|SG)-\d\d · (.+) · 이번 달 (배출|비용) 예측$/, m => m[0].split(' · ')[0] + ' · ' + L2(m[2]) + ' · This month\'s ' + (m[3] === '배출' ? 'emissions' : 'cost') + ' forecast'],
    [/^(.+?) · 로그아웃$/, m => L2(m[1]) + ' · Log out'],
    [/^(목표|예산)(\(예시\))? (.+?) 대비 (\d+)% 사용 · (여유|초과) (\d+)%$/, m => `${m[1] === '목표' ? 'Target' : 'Budget'}${m[2] ? ' (sample)' : ''} ${U(m[3])} · ${m[4]}% used · ${m[5] === '여유' ? 'Headroom' : 'Over by'} ${m[6]}%`],
    [/^이번 달 예상 (.+?) \((?:한도|예산)의 (\d+)%\)$/, m => `This-month forecast ${U(m[1])} (${m[2]}% of ${/예산/.test(m[0]) ? 'budget' : 'limit'})`],
    [/^이번 달 예상 (.+?) \((\d+)%\) → (문제 없음|주의|문제 예상)$/, m => `This-month forecast ${U(m[1])} (${m[2]}%) → ${LV[m[3]]}`],
    [/^월말 예상 (.+?) \(범위 (.+?)\)$/, m => `Month-end forecast ${U(m[1])} (range ${U(m[2])})`],
    [/^이달 (한도|예산) (.+)$/, m => `Monthly ${lim(m[1])} ${U(m[2])}`],
    [/^계획선 (.+)$/, m => 'Plan line ' + U(m[1])],
    [/^기준일 10\.20 · (\d+)일 경과$/, m => `Reference date 10.20 · day ${m[1]}`],
    [/^기준일 (\d+)일$/, m => `Reference day ${m[1]}`],
    [/^(\d+)일$/, m => m[1]],
    [/^(\d+)시$/, m => m[1] + 'h'],
    [/^(\d+)분 전$/, m => m[1] + ' min ago'], [/^(\d+)시간 전$/, m => m[1] + ' h ago'],
    [/^(압출|성형|후처리) (\d+)시 (\d+)%$/, m => `${EXACT[m[1]]} ${m[2]}h ${m[3]}%`],
    [/^(\d+)\/(\d+)대 정상(?: · 지연 (\d+)대)?$/, m => `${m[1]}/${m[2]} normal` + (m[3] ? ` · ${m[3]} delayed` : '')],
    [/^계획 대비 (\d+)%$/, m => `${m[1]}% of plan`], [/^가동 (\S+)시간 \/ (\S+)시간$/, m => `Running ${m[1]} h / ${m[2]} h`], [/^탄소 (\S+) tCO₂\/t$/, m => `Carbon ${m[1]} tCO₂/t`],
    [/^기준선 대비 (\S+)% · 오늘 최대 (.+?)\((\d+)시\)$/, m => `${m[1]}% vs baseline · today's max ${m[2]} (${m[3]}h)`], [/^전일 같은 시간대 대비 (\S+)%$/, m => `${m[1]}% vs same hours yesterday`],
    [/^최대 (.+?) \((\d+)시, 기준선 대비 \+(\d+)%\) · 기준선=평소 같은 요일 평균\(모의\)$/, m => `Max ${m[1]} (${m[2]}h, +${m[3]}% vs baseline) · baseline = usual same-weekday average (mock)`],
    [/^수신 정상 (\d+)% \((\d+)\/(\d+)대\)$/, m => `Reception normal ${m[1]}% (${m[2]}/${m[3]} units)`],
    [/^(EQ-\d+) (.+?): 마지막 수신 (\d+)시간 전$/, m => `${m[1]} ${L2(m[2])}: last received ${m[3]} h ago`],
    [/^직접 (\S+)$/, m => 'Direct ' + m[1]], [/^간접 (\S+)$/, m => 'Indirect ' + m[1]], [/^전체의 (\S+)$/, m => 'Of total ' + m[1]],
    [/^초과 (\d+)%$/, m => 'Over ' + m[1] + '%'], [/^담당 ([^·]+)$/, m => 'Owner ' + L2(m[1].trim())], [/^감지 (\d{4}-\d\d-\d\d \d\d:\d\d)$/, m => 'Detected ' + m[1]], [/^시작 (.+)$/, m => 'Start ' + m[1]], [/^종료 (.+)$/, m => 'End ' + m[1]],
    [/^마지막 갱신 (.+?)\(모의\)$/, m => 'Last updated ' + m[1] + ' (mock)'], [/^마지막 수신 (.+?) \(모의\)$/, m => 'Last received ' + m[1] + ' (mock)'],
    [/^(.+?) \(가상 위치\)$/, m => L2(m[1]) + ' (virtual location)'], [/^가상 위치 (.+)$/, m => 'Virtual location ' + m[1]],
    [/^2026년 (\d+)월$/, m => ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+m[1]] + ' 2026'],
    [/^선택 가능: (.+?) ~ (.+?)\(기준일\)\. 시작일과 종료일을 차례로 누르세요\.$/, m => `Selectable: ${m[1]} ~ ${m[2]} (reference date). Click the start date, then the end date.`],
    [/^현재 역할\((.+?)\)로는 "(.+?)" 화면을 볼 수 없습니다\.$/, m => `Your current role (${L2(m[1])}) cannot view the "${L2(m[2])}" screen.`],
    [/^(목표|예산) 대비 (\d+)% 사용\(기준: 70% 주의·90% 경고\)$/, m => `${m[1] === '목표' ? 'Target' : 'Budget'}: ${m[2]}% used (thresholds: 70% caution · 90% warning)`],
    [/^직전 동일 기간 대비 ([-+]?[\d.]+)%(?:입니다\.)?$/, m => `${m[1]}% vs previous equal period` + (/입니다/.test(m[0]) ? '.' : '')],
    [/^직전 동일 기간 대비 ([-+]?[\d.]+)%로 급증 조건\(\+10%\)에 해당합니다\.$/, m => `${m[1]}% vs previous equal period meets the surge condition (+10%).`],
    [/^급증\(\+10% 이상\)으로 한 단계 상향$/, () => 'Raised one level due to surge (+10% or more)'],
    [/^검토 대기 (\d+)건$/, m => `${m[1]} pending review(s)`], [/^수신 지연 설비 (\d+)대\(6시간 이상 무수신\)$/, m => `${m[1]} equipment with data delay (no data for 6h+)`],
    [/^상태 근거: (.+)$/, m => 'Status basis: ' + L2(m[1])],
    [/^이 추세면 월말 (.+?)(?:로|으로) (한도|예산) (.+?)의 (\d+)%입니다\.$/, m => `At this pace, month-end will be ${U(m[1])}, ${m[4]}% of the ${lim(m[2])} (${U(m[3])}).`],
    [/^(\d+)일경 (한도를|예산을) 넘을 가능성이 있어 이번 달 문제가 예상됩니다\.$/, m => `It may exceed the ${limz(m[2])} around day ${m[1]}, so a problem is expected this month.`],
    [/^중앙 예상은 한도 안이지만 상한 기준으로는 (\d+)일경 넘을 수 있어 주의가 필요합니다\.$/, m => `The central forecast is within the limit, but on the upper bound it may be exceeded around day ${m[1]}, so caution is needed.`],
    [/^한도에 근접해 이번 달 문제가 예상됩니다\.$/, () => 'It is near the limit, so a problem is expected this month.'],
    [/^월말 예상은 (.+?)(?:로|으로) (한도|예산)의 (\d+)%입니다\. ?$/, m => `Month-end forecast is ${U(m[1])}, ${m[3]}% of the ${lim(m[2])}.`],
    [/^한도 안이지만 70%를 넘어 여유가 (\d+)%로 줄어 있어 추이를 지켜볼 필요가 있습니다\.$/, m => `It is within the limit but above 70%; headroom has shrunk to ${m[1]}%, so the trend should be watched.`],
    [/^이번 달은 문제가 없을 것으로 예상됩니다\.$/, () => 'No problem is expected this month.'],
    [/^월말 예상 (.+?)(?:로|으로) (한도|예산)의 (\d+)%이며 여유가 (\d+)%입니다\.$/, m => `Month-end forecast ${U(m[1])} is ${m[3]}% of the ${lim(m[2])}, with ${m[4]}% headroom.`],
    [/^최근 14일 요일 보정 평균을 남은 (\d+)일에 적용했습니다\(최근 8주 요일 패턴 사용\)\.$/, m => `The 14-day weekday-adjusted average was applied to the remaining ${m[1]} days (using the last 8 weeks' weekday pattern).`],
    [/^(생산량|전력)은 한도·예산이 없어 월말 예상 (.+?)\(범위 (.+?)\)만 표시합니다\.$/, m => `${EXACT[m[1]]} has no limit or budget, so only the month-end forecast ${m[2]} (range ${m[3]}) is shown.`],
    [/^비용 변화 요인 \(직전 동일 기간 대비 (.+?)\)$/, m => `Cost change drivers (vs previous equal period ${U(m[1])})`],
    [/^선택한 기간\((.+?)\)이 이번 달을 포함하지 않아 예측 열은 비우고 실적만 표시합니다\. 예측은 기간을 "이번 달\/최근 1개월\/최근 3개월\/올해 누적"으로 두면 표시됩니다\.$/, m => `The selected period (${L2(m[1])}) does not include this month, so forecast columns are left blank and only actuals are shown. Set the period to "This month / Last 1 month / Last 3 months / Year to date" to see forecasts.`],
    [/^선택한 기간\((.+?)\)에는 이번 달이 포함되지 않아 예측 대신 실적 비교를 표시합니다\.$/, m => `The selected period (${L2(m[1])}) does not include this month, so an actual comparison is shown instead of a forecast.`],
    [/^(·\s)?이번 달 누적 비용 (.+?) \/ 예산\(기간 비례\) (.+?) = (\d+)%$/, m => `This month's cumulative cost ${U(m[2])} / budget (pro-rated) ${U(m[3])} = ${m[4]}%`],
    [/^근거: (.+)$/, m => 'Basis: ' + L2(m[1])],
    [/^원인은 사용량 증가\((.+?)\), 환율\((.+?)\), 단가·피크 시간대\((.+?)\)로 나뉩니다\.$/, m => `The cause breaks down into usage increase (${U(m[1])}), FX (${U(m[2])}), and unit price / peak hours (${U(m[3])}).`],
    [/^사용량 증가가 가장 큽니다\(전력 사용량 (.+?)\)\.$/, m => `Usage increase is the largest (power usage ${m[1]}).`],
    [/^담당 (.+?) · 감지 (.+?) · 같은 내용을 오른쪽 AI 도우미가 요약해 설명합니다\.$/, m => `Owner ${L2(m[1])} · Detected ${m[2]} · The AI assistant on the right summarizes the same content.`],
    [/^같은 내용을 오른쪽 AI 도우미가 요약해 설명합니다\.$/, () => 'The AI assistant on the right summarizes the same content.'],
    [/^“(.+?)” 항목을 열었습니다\. 핵심만 요약해 드릴게요\.$/, m => `I opened "${L2(m[1])}". Here is a short summary.`],
    [/^(\S+?)\((.+?)\)의 이번 달 누적 비용이 직전 달 같은 기간보다 (\S+?)% 늘었습니다\((.+?) → (.+?)\)\.$/, m => `${m[1]} (${L2(m[2])}): this month's cumulative cost is ${m[3]}% higher than the same period last month (${U(m[4])} → ${U(m[5])}).`],
    [/^월말 예상은 (.+?)(?:로|으로) 예산의 (\d+)%라서 (이번 달 예산을 넘길 가능성이 있습니다|여유가 줄고 있습니다)\.$/, m => `The month-end forecast is ${U(m[1])}, ${m[2]}% of the budget, so ` + (m[3].includes('넘길') ? 'it may exceed this month\'s budget.' : 'headroom is shrinking.')],
    [/^(\S+?)의 올해 누적 배출이 목표의 (\d+)%로 70%\(주의\) 기준을 넘었습니다\.$/, m => `${m[1]}'s year-to-date emissions are ${m[2]}% of target, above the 70% (caution) threshold.`],
    [/^이번 달 예상은 한도의 (\d+)%입니다\.$/, m => `This month's forecast is ${m[1]}% of the limit.`],
    [/^(\S+?)는 배출량이 가장 큰 공장이라\(전체의 (\d+)%\) 작은 증가도 한도 소진에 크게 영향을 줍니다\.$/, m => `${m[1]} is the largest-emitting plant (${m[2]}% of total), so even a small increase strongly affects limit consumption.`],
    [/^최대 전력 (\S+) MW까지 올라가는 날이 있어 피크 관리가 효과적입니다\.$/, m => `Power rises up to ${m[1]} MW on some days, so peak management is effective.`],
    [/^올해 누적 (.+?) \/ 목표 (.+?) = (\d+)%$/, m => `Year-to-date ${U(m[1])} / target ${U(m[2])} = ${m[3]}%`],
    [/^(\S+?)의 산정 결과에 근거 확인이 필요한 항목이 있습니다\.$/, m => `${m[1]}'s calculation results include an item that needs basis confirmation.`],
    [/^배출 추정 (.+?)는 아직 "검증 전" 상태입니다\.$/, m => `The emission estimate ${m[1]} is still "unverified".`],
    [/^(\S+?)\((.+?)\)에서 설비 (\d+)대의 자료가 6시간 이상 들어오지 않고 있습니다\((.+)\)\.$/, m => `${m[1]} (${L2(m[2])}): data from ${m[3]} equipment unit(s) has not arrived for over 6 hours (${m[4].split(', ').map(L2).join(', ')}).`],
    [/^이번 달 예측: 월말 (.+?), (예산|한도)의 (\d+)% \((.+?)\)\. 자세한 차트는 "공장 예측"에서 볼 수 있습니다\.$/, m => `This month's forecast: month-end ${U(m[1])}, ${m[3]}% of the ${lim(m[2])} (${L2(m[4])}). A detailed chart is available under "Plant forecast".`],
    [/^담당자\((.+?)\)에게 보낼 메일 초안을 작성했습니다\. 내용을 확인·수정한 뒤 발송 여부를 직접 결정하세요\.$/, m => `I drafted an email to the owner (${L2(m[1])}). Review and edit it, then decide yourself whether to send.`],
    [/^(.+?) 담당자에게 메일을 발송했습니다\(모의 · 실제 발송 아님\)\. 회신을 받으면 "해결 처리"를 눌러 주세요\.$/, m => `I sent the email to owner ${L2(m[1])} (mock · not actually sent). When you get a reply, press "Mark resolved".`],
    [/^(\S+) 항목을 해결 처리했습니다\(모의\)$/, m => `${m[1]} item marked resolved (mock)`],
    [/^\[확인 요청\] (\S+) 에너지 비용 상승\(이번 달 예산 (\d+)% 예상\)$/, m => `[Review request] ${m[1]} Energy cost increase (${m[2]}% of this month's budget expected)`],
    [/^\[확인 요청\] (\S+) 배출 목표 (\d+)% 사용\(주의\)$/, m => `[Review request] ${m[1]} Emission target ${m[2]}% used (caution)`],
    [/^\[확인 요청\] (\S+) 산정 근거\(증빙\) 누락 1건$/, m => `[Review request] ${m[1]} 1 missing calculation basis (evidence)`],
    [/^\[확인 요청\] (\S+) 설비 자료 수신 지연 (\d+)대$/, m => `[Review request] ${m[1]} ${m[2]} equipment with data reception delay`],
    [/^(.+?) 담당자님,$/, m => `Dear ${L2(m[1])},`], [/^(.+?)@example\.com\(가상\)$/, m => L2(m[1]).replace(/ /g, '.').toLowerCase() + '@example.com (fictional)'],
    [/^(\S+?)\((.+?)\) 이번 달 에너지 비용이 직전 달 같은 기간 대비 (\S+?)% 늘었고, 월말 예상은 (.+?)(?:으로|로) 예산의 (\d+)%입니다\.$/, m => `${m[1]} (${L2(m[2])}) energy cost this month is up ${m[3]}% vs the same period last month, and the month-end forecast is ${U(m[4])}, ${m[5]}% of budget.`],
    [/^주요 요인은 전력 사용량 증가\((.+?)\)입니다\.$/, m => `The main driver is higher power usage (${m[1]}).`],
    [/^아래 사항을 확인해 회신 부탁드립니다\.$/, () => 'Please check the following and reply.'], [/^1\) 최근 가동 일정·생산 계획 변경 여부$/, () => '1) Any recent changes to the operating schedule or production plan'], [/^2\) 컴프레서·냉각탑 등 부하 설비의 이상 여부$/, () => '2) Any abnormality in load equipment such as compressors and cooling towers'], [/^3\) 피크 시간대\(14~17시\) 부하 분산 가능성$/, () => '3) Possibility of spreading load during peak hours (14–17h)'],
    [/^※ 본 메일은 시안\(모의\) 초안이며 실제 발송되지 않습니다\.$/, () => '※ This email is a draft (mock) and is not actually sent.'], [/^※ 시안\(모의\) 초안이며 실제 발송되지 않습니다\.$/, () => '※ This is a draft (mock) and is not actually sent.'], [/^관제 담당 드림$/, () => 'Control operator'],
    [/^(\S+?)의 올해 누적 배출이 목표의 (\d+)%에 도달해 주의 단계입니다\.$/, m => `${m[1]}'s year-to-date emissions have reached ${m[2]}% of target — caution level.`],
    [/^피크 시간대 부하 분산과 연말까지의 감축 계획을 검토해 주세요\.$/, () => 'Please review peak-hour load spreading and the reduction plan through year-end.'],
    [/^(\S+?)의 이번 산정에서 활동 자료 1건의 증빙 문서가 연결되어 있지 않습니다\.$/, m => `In this calculation for ${m[1]}, the evidence document for one activity record is not linked.`],
    [/^계량 파일 또는 ERP 출력 근거를 업로드해 주시면 검토 후 확정 절차를 진행하겠습니다\.$/, () => 'Once you upload the metering file or ERP output as evidence, we will review it and proceed with confirmation.'],
    [/^(\S+?)\((.+?)\) (.+?)에서 6시간 이상 자료가 수신되지 않고 있습니다\.$/, m => `${m[1]} (${L2(m[2])}): no data has been received from ${m[3].split(', ').map(L2).join(', ')} for over 6 hours.`],
    [/^현장 게이트웨이와 네트워크를 확인해 복구 후 알려 주세요\.$/, () => 'Please check the on-site gateway and network, and let us know after recovery.'],
    [/^(EQ-\d+) (.+)$/, m => m[1] + ' ' + L2(m[2])],
    [/^이번 달 누적 − 직전 달 동일 기간 (.+)$/, m => 'This month cumulative − same period last month ' + U(m[1])],
    [/^공장이 전체 배출에서 차지하는 비중입니다.+$/, () => 'Each plant\'s share of total emissions (% under the bars). Bar colors show the emission breakdown: yellow = direct emissions from fuel / processes; cyan = indirect emissions from purchased power. Plants with a large share and a high indirect ratio offer greater power-saving effect.'],
    [/^기간 현황 \((.+)\)$/, m => 'Period status (' + L2(m[1]) + ')'],
    [/^(.+?)\(3곳 합계 (\d+)%\)$/, m => L2(m[1]) + ' (top 3 total ' + m[2] + '%)'], [/^상위 기여: (.+)$/, m => 'Top contributors: ' + m[1]], [/^증가 상위: (.+)$/, m => 'Top increases: ' + m[1]],
    [/^월말 예상 (.+)$/, m => 'Month-end forecast ' + U(m[1])],
    [/^범위 (.+)$/, m => 'Range ' + U(m[1])]
  ];
  const FRAGS = [['마지막 갱신', 'Last updated'], ['(모의)', '(mock)'], ['가상 위치', 'Virtual location'], ['담당', 'Owner'], ['감지', 'Detected'], ['억 원', '×100M KRW'], ['억', '×100M KRW'], ['한국', 'Korea'], ['일본', 'Japan'], ['싱가포르', 'Singapore'], ['정상', 'Normal'], ['주의', 'Caution'], ['경고', 'Warning'], ['자료 지연', 'Data delay'], ['컴프레서', 'Compressor'], ['보일러', 'Boiler'], ['냉각탑', 'Cooling tower'], ['(예시)', '(sample)'], ['예시', 'Sample'], ['모의', 'Mock'], ['개', ' plants'], ['건', ' items']];
  ['울산', '포항', '광양', '당진', '광주', '기타큐슈', '구라시키', '지바', '나고야', '주롱', '투아스', '우드랜즈', '김도윤', '박서준', '이하늘', '최민재', '정유진', '다나카 켄', '사토 유이', '스즈키 렌', '이토 아야', '탄 웨이', '리 메이', '응 지아'].forEach(k => FRAGS.push([k, EXACT[k]]));
FRAGS.sort((a, b) => b[0].length - a[0].length);
  let LANG = (() => { const s = localStorage.getItem('ama-lang'); if (s === 'en' || s === 'ko') return s; const nl = String(navigator.language || (navigator.languages || [])[0] || 'ko').toLowerCase(); return nl.startsWith('ko') ? 'ko' : 'en'; })(); const HAN = /[가-힣]/;
  function tr(s) {
    if (LANG !== 'en' || typeof s !== 'string' || !HAN.test(s)) return s;
    if (s.includes('\n')) return s.split('\n').map(tr).join('\n');
    const t = s.trim(), lead = s.slice(0, s.indexOf(t)), trail = s.slice(s.indexOf(t) + t.length);
    let out = null; if (EXACT[t] != null) out = EXACT[t]; else if (EXACT[s] != null) return EXACT[s];
    if (out == null) for (const [re, fn] of RULES) { const m = t.match(re); if (m) { out = fn(m); break; } }
    if (out == null && /[.!?]\s+\S/.test(t) && !/^\d\./.test(t)) { const parts = t.split(/(?<=[.])\s+/); if (parts.length > 1) { const tp = parts.map(tr); if (tp.some((x, i) => x !== parts[i])) out = tp.join(' '); } }
    if (out == null && t.includes(' · ')) { const parts = t.split(' · '), tp = parts.map(tr); if (tp.some((x, i) => x !== parts[i])) out = tp.join(' · '); }
    if (out == null) { out = t; for (const [k, v] of FRAGS) out = out.split(k).join(v); }
    return lead + out + trail;
  }
  const ORIG = new WeakMap(), TRD = new WeakMap(), AORIG = new WeakMap();
  function xText(node) { if (node.parentNode && node.parentNode.closest && node.parentNode.closest('[data-lang-btn],[translate="no"]')) return; const cur = node.textContent; if (!HAN.test(cur) && !ORIG.has(node)) return; if (TRD.get(node) === cur) return; const o = HAN.test(cur) ? cur : ORIG.get(node); ORIG.set(node, o); const t = tr(o); TRD.set(node, t); if (t !== cur) node.textContent = t; }
  function xAttr(el) { for (const a of ['placeholder', 'title', 'aria-label']) { const v = el.getAttribute && el.getAttribute(a); if (v == null) continue; let m = AORIG.get(el); if (!m) { m = {}; AORIG.set(el, m); } if (m[a] && m[a].t === v) continue; if (!HAN.test(v) && !m[a]) continue; const o = HAN.test(v) ? v : m[a].o, t = tr(o); m[a] = { o, t }; if (t !== v) el.setAttribute(a, t); } }
  function walk(root) {
    if (root.nodeType === 3) { xText(root); return; } if (root.nodeType !== 1) return; if (root.tagName === 'SCRIPT' || root.tagName === 'STYLE') return;
    xAttr(root); const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { if (n.nodeType === 3) { if (n.parentNode && (n.parentNode.tagName === 'TEXTAREA' || n.parentNode.tagName === 'SCRIPT' || n.parentNode.tagName === 'STYLE')) continue; xText(n); } else xAttr(n); }
  }
  function restore() {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) { if (ORIG.has(n)) { n.textContent = ORIG.get(n); ORIG.delete(n); TRD.delete(n); } } else { const m = AORIG.get(n); if (m) { for (const a in m) n.setAttribute(a, m[a].o); AORIG.delete(n); } } }
  }
  let busy = false;
  const mo = new MutationObserver(muts => { if (LANG !== 'en' || busy) return; busy = true; try { for (const m of muts) { if (m.type === 'childList') m.addedNodes.forEach(walk); else if (m.type === 'characterData') xText(m.target); else if (m.type === 'attributes') xAttr(m.target); } } finally { busy = false; } });
  function start() { mo.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['placeholder', 'title', 'aria-label'] }); }
  function setLang(l) {
    LANG = l === 'en' ? 'en' : 'ko'; localStorage.setItem('ama-lang', LANG); document.documentElement.lang = LANG; busy = true;
    try { if (LANG === 'en') walk(document.body); else restore(); } finally { busy = false; }
    document.querySelectorAll('select').forEach(sel => { const i = sel.selectedIndex; sel.selectedIndex = -1; sel.selectedIndex = i; });
    document.title = LANG === 'en' ? tr(document.title) : document.title; document.querySelectorAll('[data-lang-btn]').forEach(b => b.classList.toggle('on', b.dataset.langBtn === LANG));
    if (window.afterLang) window.afterLang(LANG);
  }
  window.I18N = { tr, setLang, get lang() { return LANG; }, start, walk, EXACT, RULES, FRAGS };
  window.tr = tr;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => { start(); if (LANG === 'en') setLang('en'); }); else { start(); }
})();
