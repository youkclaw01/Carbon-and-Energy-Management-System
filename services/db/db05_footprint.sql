-- DB05 견적·출하 탄소정보(sqldb-cems-prd-krc-footprint-01) — 체크리스트 2-5. 설계: design/services/S05 §4·6. 수치 레코드는 S02 release 근거가 있을 때만 생성(현재 release 없음 → 비어 있음).
IF OBJECT_ID('dbo.CustomerRequest') IS NULL CREATE TABLE dbo.CustomerRequest (
  requestId NVARCHAR(36) NOT NULL CONSTRAINT PK_CustReq PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, plantId NVARCHAR(32) NOT NULL, principal NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  kind NVARCHAR(10) NOT NULL, quoteId NVARCHAR(80) NULL, shipmentId NVARCHAR(80) NULL, productId NVARCHAR(80) NOT NULL, batchRefs NVARCHAR(MAX) NOT NULL, quantityValue NVARCHAR(40) NOT NULL, quantityUnit NVARCHAR(16) NOT NULL, declaredUnit NVARCHAR(MAX) NOT NULL,
  boundary NVARCHAR(MAX) NOT NULL, periodStart DATETIME2(3) NOT NULL, periodEnd DATETIME2(3) NOT NULL, recipientScope NVARCHAR(40) NOT NULL, purpose NVARCHAR(40) NOT NULL, schemaVersion NVARCHAR(24) NOT NULL, releaseRef NVARCHAR(MAX) NULL, sourceVersion NVARCHAR(80) NULL, assumptionRef NVARCHAR(80) NULL,
  requestState NVARCHAR(16) NOT NULL, waitReason NVARCHAR(200) NULL, footprintStatus NVARCHAR(16) NOT NULL, rev INT NOT NULL, correlationId NVARCHAR(80) NULL, createdAt DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_CustReq_idem UNIQUE (country, orgId, principal, idemKey), CONSTRAINT CK_CustReq_kind CHECK (kind IN ('quote','shipment') AND ((kind='quote' AND quoteId IS NOT NULL AND shipmentId IS NULL) OR (kind='shipment' AND shipmentId IS NOT NULL AND quoteId IS NULL))),
  CONSTRAINT CK_CustReq_state CHECK (requestState IN ('received','waiting_source','ready','rejected')), CONSTRAINT CK_CustReq_fs CHECK (footprintStatus IN ('none','provisional','estimated','certified')));
GO
IF OBJECT_ID('dbo.QuoteFootprint') IS NULL CREATE TABLE dbo.QuoteFootprint (
  footprintId NVARCHAR(36) NOT NULL, revision INT NOT NULL, requestId NVARCHAR(36) NOT NULL, sourceRefs NVARCHAR(MAX) NOT NULL, valueDecimal NVARCHAR(40) NOT NULL, unit NVARCHAR(24) NOT NULL, metricKind NVARCHAR(20) NOT NULL, declaredUnit NVARCHAR(MAX) NOT NULL,
  boundary NVARCHAR(MAX) NOT NULL, coverage NVARCHAR(24) NOT NULL, exclusions NVARCHAR(MAX) NOT NULL, methodologyVersion NVARCHAR(40) NOT NULL, factorVersion NVARCHAR(40) NOT NULL, allocationVersion NVARCHAR(40) NOT NULL, footprintStatus NVARCHAR(16) NOT NULL,
  createdAt DATETIME2(3) NOT NULL, CONSTRAINT PK_QuoteFp PRIMARY KEY (footprintId, revision), CONSTRAINT FK_QuoteFp_req FOREIGN KEY (requestId) REFERENCES dbo.CustomerRequest(requestId));
GO
IF OBJECT_ID('dbo.DisclosureRelease') IS NULL CREATE TABLE dbo.DisclosureRelease (
  disclosureId NVARCHAR(36) NOT NULL, revision INT NOT NULL, footprintId NVARCHAR(36) NOT NULL, footprintRevision INT NOT NULL, recipientScope NVARCHAR(40) NOT NULL, purpose NVARCHAR(40) NOT NULL, allowedFields NVARCHAR(MAX) NOT NULL, validUntil DATETIME2(3) NOT NULL,
  policyDecisionRef NVARCHAR(100) NULL, policyVersion NVARCHAR(24) NULL, contentHash CHAR(64) NOT NULL, supersedesRef NVARCHAR(80) NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT PK_DiscRel PRIMARY KEY (disclosureId, revision),
  CONSTRAINT FK_DiscRel_fp FOREIGN KEY (footprintId, footprintRevision) REFERENCES dbo.QuoteFootprint(footprintId, revision));
GO
IF OBJECT_ID('dbo.DisclosureHead') IS NULL CREATE TABLE dbo.DisclosureHead (
  scopeKey NVARCHAR(200) NOT NULL CONSTRAINT PK_DiscHead PRIMARY KEY, currentDisclosureId NVARCHAR(36) NOT NULL, currentRevision INT NOT NULL, disclosureState NVARCHAR(20) NOT NULL, disclosureStatusVersion INT NOT NULL, rowVersion INT NOT NULL, denyReasons NVARCHAR(400) NULL,
  CONSTRAINT CK_DiscHead_st CHECK (disclosureState IN ('draft','policy_pending','disclosable','published','corrected','withdrawn')));
GO
IF OBJECT_ID('dbo.Revocation') IS NULL CREATE TABLE dbo.Revocation (
  revocationId NVARCHAR(36) NOT NULL CONSTRAINT PK_Revocation PRIMARY KEY, targetDisclosureId NVARCHAR(36) NOT NULL, targetRevision INT NOT NULL, reasonCode NVARCHAR(40) NOT NULL, reason NVARCHAR(300) NOT NULL, decisionActor NVARCHAR(120) NOT NULL, decidedAt DATETIME2(3) NOT NULL,
  disclosureStatusVersion INT NOT NULL, replacementRef NVARCHAR(80) NULL);
GO
IF OBJECT_ID('dbo.SourceStateProjection') IS NULL CREATE TABLE dbo.SourceStateProjection (
  authority NVARCHAR(8) NOT NULL, sourceId NVARCHAR(80) NOT NULL, sourceRevision INT NULL, sourceStatusVersion INT NULL, status NVARCHAR(24) NOT NULL, checkedAt DATETIME2(3) NOT NULL, digest CHAR(64) NULL, CONSTRAINT PK_SrcState PRIMARY KEY (authority, sourceId));
GO
IF OBJECT_ID('dbo.FootprintAudit') IS NULL CREATE TABLE dbo.FootprintAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_FpAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_CustReq_ship') CREATE INDEX IX_CustReq_ship ON dbo.CustomerRequest(shipmentId, createdAt DESC);
GO
