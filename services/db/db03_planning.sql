-- DB03 비용 계획(sqldb-cems-prd-krc-planning-01) — 체크리스트 2-9. 설계: design/services/S03 §4. 입력 4종(생산계획·제약·가격·환율)은 PlanningInput에 kind별 불변 버전으로 둔다(설계의 개별 엔터티를 통합한 구현 편차, 키·불변성은 동일).
IF OBJECT_ID('dbo.PlanningInput') IS NULL CREATE TABLE dbo.PlanningInput (
  country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, kind NVARCHAR(12) NOT NULL, inputId NVARCHAR(60) NOT NULL, version INT NOT NULL, contentJson NVARCHAR(MAX) NOT NULL, digest CHAR(64) NOT NULL, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_PlanningInput PRIMARY KEY (country, orgId, kind, inputId, version), CONSTRAINT CK_PlanningInput_k CHECK (kind IN ('plan','constraints','price','fx')));
GO
IF OBJECT_ID('dbo.Scenario') IS NULL CREATE TABLE dbo.Scenario (
  scenarioId NVARCHAR(36) NOT NULL, scenarioVersion INT NOT NULL, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, plantId NVARCHAR(32) NOT NULL, principal NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  planRef NVARCHAR(100) NOT NULL, constraintRef NVARCHAR(100) NOT NULL, priceRef NVARCHAR(100) NOT NULL, fxRef NVARCHAR(100) NOT NULL, baselineRef NVARCHAR(MAX) NULL, objective NVARCHAR(40) NOT NULL, typedOverrides NVARCHAR(MAX) NOT NULL, calculationScope NVARCHAR(16) NOT NULL,
  inputDigest CHAR(64) NOT NULL, periodStart DATETIME2(3) NOT NULL, periodEnd DATETIME2(3) NOT NULL, reportingTimezone NVARCHAR(40) NOT NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT PK_Scenario PRIMARY KEY (scenarioId, scenarioVersion), CONSTRAINT UQ_Scenario_idem UNIQUE (country, orgId, principal, idemKey));
GO
IF OBJECT_ID('dbo.SimulationRun') IS NULL CREATE TABLE dbo.SimulationRun (
  runId NVARCHAR(36) NOT NULL CONSTRAINT PK_SimRun PRIMARY KEY, scenarioId NVARCHAR(36) NOT NULL, scenarioVersion INT NOT NULL, solverVersion NVARCHAR(24) NOT NULL, status NVARCHAR(24) NOT NULL, stateVersion INT NOT NULL, resultKind NVARCHAR(12) NOT NULL CONSTRAINT DF_SimRun_k DEFAULT 'SIMULATED',
  publishable BIT NOT NULL CONSTRAINT DF_SimRun_p DEFAULT 0, feasibility BIT NULL, metricStatus NVARCHAR(MAX) NOT NULL, resultJson NVARCHAR(MAX) NULL, resultHash CHAR(64) NULL, blockedReason NVARCHAR(200) NULL, checkedAt DATETIME2(3) NOT NULL,
  CONSTRAINT CK_SimRun_st CHECK (status IN ('SUCCEEDED','INFEASIBLE','BLOCKED_DEPENDENCY','CANCEL_REQUESTED','CANCELLED','FAILED')), CONSTRAINT CK_SimRun_nopub CHECK (resultKind = 'SIMULATED' AND publishable = 0));
GO
IF OBJECT_ID('dbo.PlanningAudit') IS NULL CREATE TABLE dbo.PlanningAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PlanAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
