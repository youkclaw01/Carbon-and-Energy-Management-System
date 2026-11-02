-- DB06 증빙·감사 근거(sqldb-cems-prd-krc-evidence-01) — 체크리스트 2-3. 설계: design/services/S06 §4·6·7.3.
-- 원본/패키지 바이트는 Blob(현지), DB에는 메타데이터·참조·해시·상태만 둔다. 봉인 본체는 수정하지 않고 처리 상태행만 CAS로 바꾼다. 식별자는 NVARCHAR(36) 문자열.
IF OBJECT_ID('dbo.EvidenceRequest') IS NULL CREATE TABLE dbo.EvidenceRequest (
  requestId NVARCHAR(36) NOT NULL CONSTRAINT PK_EvReq PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, plantId NVARCHAR(32) NOT NULL, principal NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL,
  requestDigest CHAR(64) NOT NULL, sourceKind NVARCHAR(12) NOT NULL, sourceRef NVARCHAR(80) NOT NULL, purpose NVARCHAR(40) NOT NULL, recipientScope NVARCHAR(40) NOT NULL, manifestId NVARCHAR(36) NOT NULL, manifestVersion INT NOT NULL,
  generationState NVARCHAR(30) NOT NULL, stateVersion INT NOT NULL, leaseEpoch INT NOT NULL CONSTRAINT DF_EvReq_le DEFAULT 0, failReason NVARCHAR(300) NULL, correlationId NVARCHAR(80) NULL, createdAt DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_EvReq_idem UNIQUE (country, orgId, principal, idemKey), CONSTRAINT UQ_EvReq_manifest UNIQUE (manifestId, manifestVersion),
  CONSTRAINT CK_EvReq_state CHECK (generationState IN ('REQUESTED','ASSEMBLING','SEALED_DRAFT','PACKAGE_READY','LOCAL_UNSIGNED_DRAFT_READY','PARTIAL','BLOCKED','FAILED','UNKNOWN')), CONSTRAINT CK_EvReq_kind CHECK (sourceKind IN ('run','release')));
GO
IF OBJECT_ID('dbo.EvidenceManifest') IS NULL CREATE TABLE dbo.EvidenceManifest (
  country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, manifestId NVARCHAR(36) NOT NULL, manifestVersion INT NOT NULL, plantId NVARCHAR(32) NOT NULL, sourceBinding NVARCHAR(MAX) NOT NULL, snapshotId NVARCHAR(80) NOT NULL,
  periodStart DATETIME2(3) NOT NULL, periodEnd DATETIME2(3) NOT NULL, timeZone NVARCHAR(40) NOT NULL, purpose NVARCHAR(40) NOT NULL, recipientScope NVARCHAR(40) NOT NULL, inputDigest CHAR(64) NOT NULL, manifestHash CHAR(64) NOT NULL,
  supersedesRef NVARCHAR(80) NULL, mode NVARCHAR(12) NOT NULL, classification NVARCHAR(24) NOT NULL, schemaVersion NVARCHAR(24) NOT NULL, bodyJson NVARCHAR(MAX) NOT NULL, createdBy NVARCHAR(120) NOT NULL, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_EvManifest PRIMARY KEY (country, orgId, manifestId, manifestVersion));
GO
IF OBJECT_ID('dbo.EvidenceItemRef') IS NULL CREATE TABLE dbo.EvidenceItemRef (
  manifestId NVARCHAR(36) NOT NULL, manifestVersion INT NOT NULL, itemId NVARCHAR(40) NOT NULL, ownerService NVARCHAR(8) NOT NULL, sourceRef NVARCHAR(200) NOT NULL, sourceVersion NVARCHAR(80) NULL, byteHash CHAR(64) NOT NULL, byteSize INT NOT NULL,
  mediaType NVARCHAR(60) NOT NULL, inclusionStatus NVARCHAR(16) NOT NULL, inclusionReason NVARCHAR(200) NULL, factRef NVARCHAR(MAX) NULL, CONSTRAINT PK_EvItem PRIMARY KEY (manifestId, manifestVersion, itemId),
  CONSTRAINT CK_EvItem_inc CHECK (inclusionStatus IN ('INCLUDED','EXCLUDED','MISSING')));
GO
IF OBJECT_ID('dbo.LineageRef') IS NULL CREATE TABLE dbo.LineageRef (
  manifestId NVARCHAR(36) NOT NULL, manifestVersion INT NOT NULL, edgeId NVARCHAR(40) NOT NULL, fromRef NVARCHAR(200) NOT NULL, toRef NVARCHAR(200) NOT NULL, method NVARCHAR(200) NOT NULL, CONSTRAINT PK_EvLineage PRIMARY KEY (manifestId, manifestVersion, edgeId));
GO
IF OBJECT_ID('dbo.SignatureRef') IS NULL CREATE TABLE dbo.SignatureRef (
  manifestId NVARCHAR(36) NOT NULL, manifestVersion INT NOT NULL, signatureId NVARCHAR(40) NOT NULL, signedDigest CHAR(64) NULL, signingProfileVersion NVARCHAR(24) NULL, algorithm NVARCHAR(24) NULL, keyRef NVARCHAR(200) NULL,
  signedAt DATETIME2(3) NULL, verificationStatus NVARCHAR(24) NOT NULL, CONSTRAINT PK_EvSig PRIMARY KEY (manifestId, manifestVersion, signatureId));
GO
IF OBJECT_ID('dbo.AuditPackage') IS NULL CREATE TABLE dbo.AuditPackage (
  manifestId NVARCHAR(36) NOT NULL, manifestVersion INT NOT NULL, packageId NVARCHAR(40) NOT NULL, blobRef NVARCHAR(300) NOT NULL, artifactHash CHAR(64) NOT NULL, byteSize INT NOT NULL, templateVersion NVARCHAR(16) NOT NULL,
  generationState NVARCHAR(30) NOT NULL, signingState NVARCHAR(16) NOT NULL, reviewState NVARCHAR(16) NOT NULL CONSTRAINT DF_EvPkg_rv DEFAULT 'PENDING', externalVerificationState NVARCHAR(16) NOT NULL CONSTRAINT DF_EvPkg_ev DEFAULT 'NOT_VERIFIED',
  localOnly BIT NOT NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT PK_EvPkg PRIMARY KEY (manifestId, manifestVersion, packageId));
GO
IF OBJECT_ID('dbo.EvidenceAccessAudit') IS NULL CREATE TABLE dbo.EvidenceAccessAudit (
  auditSeq BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_EvAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, targetHash CHAR(64) NULL, purpose NVARCHAR(40) NULL,
  decision NVARCHAR(16) NOT NULL, reason NVARCHAR(300) NULL, correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, entryHash CHAR(64) NOT NULL);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_EvReq_plant') CREATE INDEX IX_EvReq_plant ON dbo.EvidenceRequest(plantId, createdAt DESC);
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID('dbo.EvidenceRequest') AND name='generationState' AND max_length < 60)
BEGIN
  ALTER TABLE dbo.EvidenceRequest DROP CONSTRAINT CK_EvReq_state;
  ALTER TABLE dbo.EvidenceRequest ALTER COLUMN generationState NVARCHAR(30) NOT NULL;
  ALTER TABLE dbo.EvidenceRequest ADD CONSTRAINT CK_EvReq_state CHECK (generationState IN ('REQUESTED','ASSEMBLING','SEALED_DRAFT','PACKAGE_READY','LOCAL_UNSIGNED_DRAFT_READY','PARTIAL','BLOCKED','FAILED','UNKNOWN'));
END
GO
GO
IF OBJECT_ID('dbo.SigningKeyStatus') IS NULL CREATE TABLE dbo.SigningKeyStatus (keyRef NVARCHAR(300) NOT NULL CONSTRAINT PK_SigningKeyStatus PRIMARY KEY, status NVARCHAR(10) NOT NULL CONSTRAINT DF_SigKey_st DEFAULT 'active', reason NVARCHAR(300) NULL, changedAt DATETIME2(3) NOT NULL, changedBy NVARCHAR(120) NOT NULL, CONSTRAINT CK_SigKey_st CHECK (status IN ('active','retired','revoked')));
GO
