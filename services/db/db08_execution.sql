-- DB08 제한 실행(sqldb-cems-prd-krc-execution-01) — 체크리스트 2-11. 설계: design/services/S08 §3. 실거래·외부 송신 없음(sim-provider만). permit이 없어 실행 행은 만들어지지 않는다.
IF OBJECT_ID('dbo.ExecutionIntentRef') IS NULL CREATE TABLE dbo.ExecutionIntentRef (
  executionId NVARCHAR(36) NOT NULL CONSTRAINT PK_ExecIntent PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, plantId NVARCHAR(32) NOT NULL, permitId NVARCHAR(36) NOT NULL, sourceService NVARCHAR(8) NOT NULL, businessOperationId NVARCHAR(100) NOT NULL,
  intentId NVARCHAR(60) NOT NULL, intentVersion INT NOT NULL, intentDigest CHAR(64) NOT NULL, canonicalizationVersion NVARCHAR(40) NOT NULL, digestAlgorithm NVARCHAR(16) NOT NULL, executionState NVARCHAR(16) NOT NULL, rowVersion INT NOT NULL, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_ExecIntent_permit UNIQUE (permitId), CONSTRAINT UQ_ExecIntent_op UNIQUE (country, sourceService, businessOperationId), CONSTRAINT CK_ExecIntent_state CHECK (executionState IN ('accepted','sending','executed','unknown','partial','rejected','reconciling','review-required')));
GO
IF OBJECT_ID('dbo.ExecutionAttempt') IS NULL CREATE TABLE dbo.ExecutionAttempt (
  attemptId NVARCHAR(36) NOT NULL CONSTRAINT PK_ExecAttempt PRIMARY KEY, executionId NVARCHAR(36) NOT NULL, attemptNo INT NOT NULL, executionEpoch INT NOT NULL, claimId NVARCHAR(36) NULL, authorityVersion INT NULL, sendState NVARCHAR(16) NOT NULL, startedAt DATETIME2(3) NOT NULL, deadline DATETIME2(3) NOT NULL, lastCheckedAt DATETIME2(3) NULL,
  CONSTRAINT UQ_ExecAttempt UNIQUE (executionId, attemptNo), CONSTRAINT FK_ExecAttempt_ex FOREIGN KEY (executionId) REFERENCES dbo.ExecutionIntentRef(executionId));
GO
IF OBJECT_ID('dbo.ExternalReceipt') IS NULL CREATE TABLE dbo.ExternalReceipt (
  receiptObservationId NVARCHAR(36) NOT NULL CONSTRAINT PK_ExtReceipt PRIMARY KEY, executionId NVARCHAR(36) NOT NULL, attemptId NVARCHAR(36) NOT NULL, providerId NVARCHAR(40) NOT NULL, externalReceiptId NVARCHAR(100) NOT NULL, receiptVersion INT NOT NULL, payloadDigest CHAR(64) NOT NULL,
  verified BIT NOT NULL, observedAt DATETIME2(3) NOT NULL, ownerEffectId NVARCHAR(60) NOT NULL, effectVersion INT NOT NULL, quantityStatus NVARCHAR(16) NOT NULL, quantityValue NVARCHAR(40) NULL, quantityUnit NVARCHAR(16) NULL,
  CONSTRAINT UQ_ExtReceipt UNIQUE (providerId, externalReceiptId, receiptVersion), CONSTRAINT CK_ExtReceipt_q CHECK ((quantityStatus='CONFIRMED' AND quantityValue IS NOT NULL AND quantityUnit IS NOT NULL) OR (quantityStatus IN ('UNCONFIRMED','NOT_APPLICABLE') AND quantityValue IS NULL)));
GO
IF OBJECT_ID('dbo.PermitGate') IS NULL CREATE TABLE dbo.PermitGate (permitId NVARCHAR(36) NOT NULL CONSTRAINT PK_PermitGate PRIMARY KEY, blocked BIT NOT NULL CONSTRAINT DF_PG_b DEFAULT 0, blockVersion INT NOT NULL CONSTRAINT DF_PG_v DEFAULT 0, executionEpoch INT NOT NULL CONSTRAINT DF_PG_e DEFAULT 0, dispatchStartedCount INT NOT NULL CONSTRAINT DF_PG_d DEFAULT 0);
GO
IF OBJECT_ID('dbo.ExecutionAudit') IS NULL CREATE TABLE dbo.ExecutionAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ExecAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
