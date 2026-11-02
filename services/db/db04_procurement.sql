-- DB04 조달 포지셔닝(sqldb-cems-prd-krc-procurement-01) — 체크리스트 2-10. 설계: design/services/S04 §4. 의도는 초안/모의 전용(propose-only): intentDigest·정규화 규약은 합의 전이라 NULL·bindingState=UNRESOLVED.
IF OBJECT_ID('dbo.BusinessOperation') IS NULL CREATE TABLE dbo.BusinessOperation (
  country CHAR(2) NOT NULL, sourceService NVARCHAR(8) NOT NULL, businessOperationId NVARCHAR(36) NOT NULL, orgId NVARCHAR(40) NOT NULL, businessRequestRef NVARCHAR(100) NOT NULL, rootIntentId NVARCHAR(36) NOT NULL, activeIntentVersion INT NOT NULL, holdState NVARCHAR(12) NOT NULL CONSTRAINT DF_BO_h DEFAULT 'none', rowVersion INT NOT NULL,
  CONSTRAINT PK_BusinessOp PRIMARY KEY (country, sourceService, businessOperationId), CONSTRAINT UQ_BusinessOp_ref UNIQUE (country, orgId, businessRequestRef));
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UQ_BusinessOp_id') ALTER TABLE dbo.BusinessOperation ADD CONSTRAINT UQ_BusinessOp_id UNIQUE (country, orgId, businessOperationId);
GO
IF OBJECT_ID('dbo.ProcurementIntent') IS NULL CREATE TABLE dbo.ProcurementIntent (
  intentId NVARCHAR(36) NOT NULL, intentVersion INT NOT NULL, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, businessOperationId NVARCHAR(36) NOT NULL, plantId NVARCHAR(32) NOT NULL, mode NVARCHAR(12) NOT NULL, principalRef NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  instrumentType NVARCHAR(20) NOT NULL, purpose NVARCHAR(40) NOT NULL, quantityValue NVARCHAR(40) NOT NULL, quantityUnit NVARCHAR(16) NOT NULL, currency CHAR(3) NOT NULL, priceCapMinorText NVARCHAR(40) NULL, deliveryStart DATETIME2(3) NOT NULL, deliveryEnd DATETIME2(3) NOT NULL,
  scenarioRef NVARCHAR(MAX) NOT NULL, assumption NVARCHAR(MAX) NOT NULL, intentDigest CHAR(64) NULL, canonicalizationVersion NVARCHAR(40) NULL, digestAlgorithm NVARCHAR(16) NULL, bindingState NVARCHAR(12) NOT NULL, state NVARCHAR(16) NOT NULL, blockers NVARCHAR(MAX) NOT NULL, rowVersion INT NOT NULL, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_ProcIntent PRIMARY KEY (intentId, intentVersion), CONSTRAINT UQ_ProcIntent_idem UNIQUE (country, orgId, principalRef, idemKey), CONSTRAINT CK_ProcIntent_mode CHECK (mode = 'SIMULATED'), CONSTRAINT CK_ProcIntent_state CHECK (state IN ('DRAFT','POLICY_PENDING','CANCELLED')),
  CONSTRAINT CK_ProcIntent_bind2 CHECK ((bindingState = 'UNRESOLVED' AND intentDigest IS NULL) OR (bindingState = 'BOUND' AND intentDigest IS NOT NULL AND canonicalizationVersion IS NOT NULL AND digestAlgorithm IS NOT NULL)), CONSTRAINT FK_ProcIntent_bo FOREIGN KEY (country, orgId, businessOperationId) REFERENCES dbo.BusinessOperation(country, orgId, businessOperationId));
GO
IF OBJECT_ID('dbo.PositionSnapshot') IS NULL CREATE TABLE dbo.PositionSnapshot (
  country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, positionKey NVARCHAR(160) NOT NULL, version INT NOT NULL, mode NVARCHAR(12) NOT NULL, contractedQty NVARCHAR(40) NOT NULL, deliveredQty NVARCHAR(40) NOT NULL, retiredQty NVARCHAR(40) NOT NULL, pendingQty NVARCHAR(40) NOT NULL, unknownExposure NVARCHAR(40) NOT NULL,
  asOf DATETIME2(3) NOT NULL, quality NVARCHAR(16) NOT NULL, CONSTRAINT PK_PosSnap PRIMARY KEY (country, orgId, positionKey, version));
GO
IF OBJECT_ID('dbo.ProcurementAudit') IS NULL CREATE TABLE dbo.ProcurementAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProcAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
GO
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_ProcIntent_bind') ALTER TABLE dbo.ProcurementIntent DROP CONSTRAINT CK_ProcIntent_bind;
GO
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_ProcIntent_bind2') ALTER TABLE dbo.ProcurementIntent ADD CONSTRAINT CK_ProcIntent_bind2 CHECK ((bindingState = 'UNRESOLVED' AND intentDigest IS NULL) OR (bindingState = 'BOUND' AND intentDigest IS NOT NULL AND canonicalizationVersion IS NOT NULL AND digestAlgorithm IS NOT NULL));
