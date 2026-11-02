-- DB02 탄소 산정(sqldb-cems-prd-krc-carbon-01) — 체크리스트 2-2-2. 설계: design/services/S02 §4·6.2·7.3.
-- 다른 서비스 DB와 join하지 않는다. 수치는 decimal 문자열(NVARCHAR)과 단위를 함께 저장한다(부동소수 미사용).
IF OBJECT_ID('dbo.MethodologyVersion') IS NULL CREATE TABLE dbo.MethodologyVersion (
  methodologyId NVARCHAR(64) NOT NULL, version NVARCHAR(16) NOT NULL, formula NVARCHAR(400) NOT NULL, rounding NVARCHAR(32) NOT NULL, contentDigest CHAR(64) NOT NULL,
  status NVARCHAR(16) NOT NULL CONSTRAINT DF_Meth_status DEFAULT 'ACTIVE', approvalRef NVARCHAR(200) NULL, createdAt DATETIME2(3) NOT NULL CONSTRAINT DF_Meth_c DEFAULT SYSUTCDATETIME(),
  CONSTRAINT PK_Methodology PRIMARY KEY (methodologyId, version));
GO
IF OBJECT_ID('dbo.FactorVersionRef') IS NULL CREATE TABLE dbo.FactorVersionRef (
  factorId NVARCHAR(64) NOT NULL, version NVARCHAR(16) NOT NULL, value NVARCHAR(40) NOT NULL, unit NVARCHAR(32) NOT NULL, validFrom DATE NOT NULL, validTo DATE NOT NULL,
  origin NVARCHAR(120) NOT NULL, contentDigest CHAR(64) NOT NULL, status NVARCHAR(16) NOT NULL CONSTRAINT DF_Fac_status DEFAULT 'ACTIVE',
  CONSTRAINT PK_Factor PRIMARY KEY (factorId, version), CONSTRAINT CK_Fac_period CHECK (validFrom < validTo));
GO
IF OBJECT_ID('dbo.CalcRun') IS NULL CREATE TABLE dbo.CalcRun (
  runId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_CalcRun PRIMARY KEY, runKey CHAR(64) NOT NULL, calculationKind NVARCHAR(16) NOT NULL, country CHAR(2) NOT NULL, organizationId NVARCHAR(40) NOT NULL, plantId NVARCHAR(32) NOT NULL,
  periodStart DATETIME2(3) NOT NULL, periodEnd DATETIME2(3) NOT NULL, timezone NVARCHAR(40) NOT NULL, boundaryRef NVARCHAR(40) NOT NULL, mode NVARCHAR(12) NOT NULL,
  inputSnapshotRef NVARCHAR(300) NOT NULL, inputSnapshotDigest CHAR(64) NOT NULL, versionSet NVARCHAR(MAX) NOT NULL, scenarioRef NVARCHAR(200) NULL, requestDigest CHAR(64) NOT NULL,
  businessState NVARCHAR(24) NOT NULL, calcRequestedBy NVARCHAR(120) NOT NULL, createdAt DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL, rowVersion ROWVERSION,
  CONSTRAINT UQ_CalcRun_key UNIQUE (runKey), CONSTRAINT CK_CalcRun_kind CHECK (calculationKind IN ('INVENTORY','WHAT_IF')), CONSTRAINT CK_CalcRun_mode CHECK (mode IN ('ACTUAL','SIMULATED')),
  CONSTRAINT CK_CalcRun_state CHECK (businessState IN ('accepted','awaiting_candidate','candidate_ready','validating','ready','dq_failed','cancellation_pending','cancelled')), CONSTRAINT CK_CalcRun_period CHECK (periodStart < periodEnd));
GO
IF OBJECT_ID('dbo.CalcCandidate') IS NULL CREATE TABLE dbo.CalcCandidate (
  runId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_CalcCandidate PRIMARY KEY, candidateHash CHAR(64) NOT NULL, valuesJson NVARCHAR(MAX) NOT NULL, samples INT NOT NULL, expectedSamples INT NOT NULL, coverage NVARCHAR(16) NOT NULL,
  manifestRef NVARCHAR(300) NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT FK_Cand_run FOREIGN KEY (runId) REFERENCES dbo.CalcRun(runId));
GO
IF OBJECT_ID('dbo.ValidationResult') IS NULL CREATE TABLE dbo.ValidationResult (
  validationId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Validation PRIMARY KEY, runId UNIQUEIDENTIFIER NOT NULL, candidateHash CHAR(64) NOT NULL, inputDigest CHAR(64) NOT NULL, dqPolicyVersion NVARCHAR(16) NOT NULL,
  checkerCodeDigest CHAR(64) NOT NULL, verdict NVARCHAR(20) NOT NULL, checksJson NVARCHAR(MAX) NOT NULL, checkedAt DATETIME2(3) NOT NULL,
  CONSTRAINT FK_Val_run FOREIGN KEY (runId) REFERENCES dbo.CalcRun(runId), CONSTRAINT CK_Val_verdict CHECK (verdict IN ('PASS','DQ_FAILED','RECALC_MISMATCH')));
GO
IF OBJECT_ID('dbo.ScenarioResult') IS NULL CREATE TABLE dbo.ScenarioResult (
  runId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_ScenarioResult PRIMARY KEY, scenarioRef NVARCHAR(200) NOT NULL, resultVersion INT NOT NULL, candidateHash CHAR(64) NOT NULL, validationId UNIQUEIDENTIFIER NULL,
  resultKind NVARCHAR(12) NOT NULL CONSTRAINT DF_Scn_kind DEFAULT 'SIMULATED', publicationEligible BIT NOT NULL CONSTRAINT DF_Scn_pub DEFAULT 0,
  CONSTRAINT CK_Scn_kind CHECK (resultKind = 'SIMULATED' AND publicationEligible = 0), CONSTRAINT FK_Scn_run FOREIGN KEY (runId) REFERENCES dbo.CalcRun(runId));
GO
IF OBJECT_ID('dbo.ReleaseCommand') IS NULL CREATE TABLE dbo.ReleaseCommand (
  commandId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_ReleaseCommand PRIMARY KEY, runId UNIQUEIDENTIFIER NOT NULL, validationId UNIQUEIDENTIFIER NOT NULL, commandDigest CHAR(64) NOT NULL,
  releaseRequestedBy NVARCHAR(120) NOT NULL, decisionRef NVARCHAR(200) NULL, approvedBy NVARCHAR(120) NULL, commandState NVARCHAR(24) NOT NULL, denyReason NVARCHAR(120) NULL, releaseId UNIQUEIDENTIFIER NULL,
  expectedRunVersion BINARY(8) NULL, expectedHeadVersion INT NULL, createdAt DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL,
  CONSTRAINT FK_RC_run FOREIGN KEY (runId) REFERENCES dbo.CalcRun(runId), CONSTRAINT CK_RC_state CHECK (commandState IN ('received','blocked','activated','rejected')),
  CONSTRAINT CK_RC_sep CHECK (approvedBy IS NULL OR approvedBy <> releaseRequestedBy));
GO
IF OBJECT_ID('dbo.Release') IS NULL CREATE TABLE dbo.Release (
  releaseId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_Release PRIMARY KEY, runId UNIQUEIDENTIFIER NOT NULL, validationId UNIQUEIDENTIFIER NOT NULL, scopeKey NVARCHAR(200) NOT NULL, revision INT NOT NULL,
  artifactRef NVARCHAR(300) NULL, manifestHash CHAR(64) NOT NULL, versionSet NVARCHAR(MAX) NOT NULL, status NVARCHAR(24) NOT NULL, statusVersion INT NOT NULL, restrictionFlag BIT NOT NULL CONSTRAINT DF_Rel_rf DEFAULT 0,
  denyReasons NVARCHAR(400) NULL, supersedesReleaseId UNIQUEIDENTIFIER NULL, reason NVARCHAR(400) NULL, issuedAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_Release_run UNIQUE (runId), CONSTRAINT CK_Rel_status CHECK (status IN ('issued','correction_pending','superseded','revoked')),
  CONSTRAINT FK_Rel_run FOREIGN KEY (runId) REFERENCES dbo.CalcRun(runId), CONSTRAINT FK_Rel_val FOREIGN KEY (validationId) REFERENCES dbo.ValidationResult(validationId));
GO
IF OBJECT_ID('dbo.ReleaseHead') IS NULL CREATE TABLE dbo.ReleaseHead (scopeKey NVARCHAR(200) NOT NULL CONSTRAINT PK_ReleaseHead PRIMARY KEY, currentReleaseId UNIQUEIDENTIFIER NOT NULL, headVersion INT NOT NULL,
  CONSTRAINT FK_Head_rel FOREIGN KEY (currentReleaseId) REFERENCES dbo.Release(releaseId));
GO
IF OBJECT_ID('dbo.ReleaseStatusHistory') IS NULL CREATE TABLE dbo.ReleaseStatusHistory (
  releaseId UNIQUEIDENTIFIER NOT NULL, statusVersion INT NOT NULL, fromStatus NVARCHAR(24) NULL, toStatus NVARCHAR(24) NOT NULL, actor NVARCHAR(120) NOT NULL, policyRef NVARCHAR(120) NULL, reason NVARCHAR(400) NULL, traceId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL,
  CONSTRAINT PK_RSH PRIMARY KEY (releaseId, statusVersion), CONSTRAINT FK_RSH_rel FOREIGN KEY (releaseId) REFERENCES dbo.Release(releaseId));
GO
IF OBJECT_ID('dbo.IdempotencyEntry') IS NULL CREATE TABLE dbo.IdempotencyEntry (
  country CHAR(2) NOT NULL, organizationId NVARCHAR(40) NOT NULL, principal NVARCHAR(120) NOT NULL, operation NVARCHAR(40) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL, resultRef NVARCHAR(80) NOT NULL, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_Idem PRIMARY KEY (country, organizationId, principal, operation, idemKey));
GO
IF OBJECT_ID('dbo.PublicationOutbox') IS NULL CREATE TABLE dbo.PublicationOutbox (
  eventId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_PubOutbox PRIMARY KEY, aggregateId UNIQUEIDENTIFIER NOT NULL, aggregateRevision INT NOT NULL, eventType NVARCHAR(60) NOT NULL, payloadJson NVARCHAR(MAX) NOT NULL, digest CHAR(64) NOT NULL,
  state NVARCHAR(12) NOT NULL CONSTRAINT DF_PO_state DEFAULT 'PENDING', attempts INT NOT NULL CONSTRAINT DF_PO_att DEFAULT 0, createdAt DATETIME2(3) NOT NULL, CONSTRAINT CK_PO_state CHECK (state IN ('PENDING','SENT','FAILED')));
GO
IF OBJECT_ID('dbo.CarbonAudit') IS NULL CREATE TABLE dbo.CarbonAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_CarbonAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL,
  result NVARCHAR(20) NOT NULL, reason NVARCHAR(400) NULL, traceId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, previousHash CHAR(64) NULL, recordHash CHAR(64) NOT NULL);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_CalcRun_plant') CREATE INDEX IX_CalcRun_plant ON dbo.CalcRun(plantId, periodStart DESC);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_Outbox_pending') CREATE INDEX IX_Outbox_pending ON dbo.PublicationOutbox(state, createdAt);
GO
-- 모의 계수·방법론 등록(공식 계수 아님). 값은 calc/core.py와 동일해야 하며 digest는 앱이 시작 시 대조한다.
GO
IF NOT EXISTS (SELECT 1 FROM dbo.MethodologyVersion WHERE methodologyId='AMA-S12-ENERGY-V1' AND version='1') INSERT dbo.MethodologyVersion(methodologyId,version,formula,rounding,contentDigest,approvalRef) VALUES ('AMA-S12-ENERGY-V1','1',N'scope2 = Σ(grid_kW × interval_h) × EF_grid ; scope1 = Σ(gas_Nm3/h × interval_h) × EF_gas ; cost = kWh × tariff','ROUND_HALF_EVEN-3','00c29d0bebb5b6ed687ceba0a20344834666d18e7bcf684aac8fe5e5a7a90a0a','MOCK(승인 근거 없음)');
GO
IF NOT EXISTS (SELECT 1 FROM dbo.FactorVersionRef WHERE factorId='MOCK-EF-GRID-KR' AND version='1') INSERT dbo.FactorVersionRef(factorId,version,value,unit,validFrom,validTo,origin,contentDigest) VALUES ('MOCK-EF-GRID-KR','1','0.4594','kgCO2e/kWh','2026-01-01','2027-01-01',N'MOCK(공식 계수 아님)','781a7b88069a8ef1230120d73723146f432b0cc5279539ca912b83f616064093');
GO
IF NOT EXISTS (SELECT 1 FROM dbo.FactorVersionRef WHERE factorId='MOCK-EF-GAS' AND version='1') INSERT dbo.FactorVersionRef(factorId,version,value,unit,validFrom,validTo,origin,contentDigest) VALUES ('MOCK-EF-GAS','1','2.10','kgCO2e/Nm3','2026-01-01','2027-01-01',N'MOCK(공식 계수 아님)','681177ee1bf3682d232d071cf26675d03e3ddc1558f9c5d99a847d7443b84153');
GO
IF NOT EXISTS (SELECT 1 FROM dbo.FactorVersionRef WHERE factorId='MOCK-EF-001' AND version='1') INSERT dbo.FactorVersionRef(factorId,version,value,unit,validFrom,validTo,origin,contentDigest) VALUES ('MOCK-EF-001','1','0.5','kgCO2e/kWh','2026-01-01','2027-01-01',N'정본 fixture','7703fa7300377e4d04537e9408f669b4f75814acd29fd6dfe3c18485f3e24071');
GO
IF NOT EXISTS (SELECT 1 FROM dbo.FactorVersionRef WHERE factorId='MOCK-TARIFF-001' AND version='1') INSERT dbo.FactorVersionRef(factorId,version,value,unit,validFrom,validTo,origin,contentDigest) VALUES ('MOCK-TARIFF-001','1','100','KRW/kWh','2026-01-01','2027-01-01',N'정본 fixture','6dca220254ce04b833fb7c8ee716d5c92f0ea5de7cdf2fe1394f984aeadcf41f');
GO
