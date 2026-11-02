-- DB09 국가 반출 심사(sqldb-cems-prd-krc-export-01) — 체크리스트 2-6. 설계: design/services/S09 §4·5. 활성 정책이 없으면 ALLOW 불가 → outbox·ack는 비어 있다.
IF OBJECT_ID('dbo.ExportRelease') IS NULL CREATE TABLE dbo.ExportRelease (
  country CHAR(2) NOT NULL, exportId NVARCHAR(36) NOT NULL, requesterPrincipal NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL, sourceOwner NVARCHAR(8) NOT NULL, senderId NVARCHAR(60) NOT NULL, operation NVARCHAR(12) NOT NULL,
  sourceProjectionRef NVARCHAR(MAX) NOT NULL, sourceRefs NVARCHAR(MAX) NOT NULL, schemaRef NVARCHAR(80) NOT NULL, policyDecisionRef NVARCHAR(100) NULL, policyVersion NVARCHAR(24) NULL, purpose NVARCHAR(40) NOT NULL, recipientScope NVARCHAR(40) NOT NULL, destination NVARCHAR(60) NOT NULL,
  targetExportId NVARCHAR(36) NULL, replacesExportId NVARCHAR(36) NULL, envelopeHash CHAR(64) NULL, eligibility NVARCHAR(12) NOT NULL, reasonCode NVARCHAR(60) NOT NULL, rowVersion INT NOT NULL, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_ExportRelease PRIMARY KEY (country, exportId), CONSTRAINT UQ_ExportRelease_idem UNIQUE (country, requesterPrincipal, idemKey), CONSTRAINT CK_ExportRelease_op CHECK (operation IN ('snapshot','correction','withdrawal','status')),
  CONSTRAINT CK_ExportRelease_elig CHECK (eligibility IN ('ALLOW','BLOCK','UNKNOWN')), CONSTRAINT CK_ExportRelease_env CHECK (eligibility <> 'ALLOW' OR envelopeHash IS NOT NULL));
GO
IF OBJECT_ID('dbo.DataPolicyVersion') IS NULL CREATE TABLE dbo.DataPolicyVersion (
  policyId NVARCHAR(40) NOT NULL, version NVARCHAR(16) NOT NULL, policyDigest CHAR(64) NOT NULL, fieldAllowlist NVARCHAR(MAX) NOT NULL, classification NVARCHAR(24) NOT NULL, scopeConditions NVARCHAR(MAX) NOT NULL, legalEvidenceRef NVARCHAR(200) NOT NULL, securityEvidenceRef NVARCHAR(200) NOT NULL,
  authorId NVARCHAR(120) NOT NULL, activationApproverId NVARCHAR(120) NULL, status NVARCHAR(12) NOT NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT PK_DataPolicy PRIMARY KEY (policyId, version), CONSTRAINT CK_DataPolicy_st CHECK (status IN ('draft','active','revoked')),
  CONSTRAINT CK_DataPolicy_sep CHECK (activationApproverId IS NULL OR activationApproverId <> authorId));
GO
IF OBJECT_ID('dbo.ExportOutbox') IS NULL CREATE TABLE dbo.ExportOutbox (
  country CHAR(2) NOT NULL, exportId NVARCHAR(36) NOT NULL, destination NVARCHAR(60) NOT NULL, envelopeJson NVARCHAR(MAX) NOT NULL, deliveryState NVARCHAR(14) NOT NULL, attemptId NVARCHAR(36) NULL, leaseEpoch INT NOT NULL CONSTRAINT DF_ExpOut_le DEFAULT 0, nextCheckAt DATETIME2(3) NULL, rowVersion INT NOT NULL,
  CONSTRAINT PK_ExportOutbox PRIMARY KEY (country, exportId, destination), CONSTRAINT CK_ExpOut_st CHECK (deliveryState IN ('PENDING','SENDING','ACKED','AWAIT_ACK','UNKNOWN','QUARANTINED')),
  CONSTRAINT FK_ExpOut_rel FOREIGN KEY (country, exportId) REFERENCES dbo.ExportRelease(country, exportId));
GO
IF OBJECT_ID('dbo.ExportAck') IS NULL CREATE TABLE dbo.ExportAck (
  country CHAR(2) NOT NULL, exportId NVARCHAR(36) NOT NULL, destination NVARCHAR(60) NOT NULL, ackId NVARCHAR(60) NOT NULL, envelopeHash CHAR(64) NOT NULL, outcome NVARCHAR(16) NOT NULL, projectionRevision NVARCHAR(40) NULL, receivedAt DATETIME2(3) NOT NULL, receiverPrincipal NVARCHAR(120) NOT NULL, verifiedAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_ExportAck PRIMARY KEY (country, exportId, destination), CONSTRAINT CK_ExpAck_o CHECK (outcome IN ('applied','recorded_stale')));
GO
IF OBJECT_ID('dbo.ExportAudit') IS NULL CREATE TABLE dbo.ExportAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ExpAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
