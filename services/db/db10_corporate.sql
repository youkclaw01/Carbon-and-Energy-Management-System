-- DB10 중앙 업무·허용 자료(sqldb-cems-prd-krc-corporate-01) — 체크리스트 2-7. 설계: design/services/S10 §4. AppAccessGrant 원장은 만들지 않는다(권한 출처 미결, S10 §2).
IF OBJECT_ID('dbo.FederationInbox') IS NULL CREATE TABLE dbo.FederationInbox (
  country CHAR(2) NOT NULL, senderId NVARCHAR(60) NOT NULL, exportId NVARCHAR(36) NOT NULL, envelopeHash CHAR(64) NOT NULL, schemaVersion NVARCHAR(40) NOT NULL, receivedSourceVersions NVARCHAR(MAX) NOT NULL, receivedAt DATETIME2(3) NOT NULL, ackId NVARCHAR(60) NOT NULL,
  outcome NVARCHAR(16) NOT NULL, ackBody NVARCHAR(MAX) NOT NULL, CONSTRAINT PK_FedInbox PRIMARY KEY (country, senderId, exportId), CONSTRAINT CK_FedInbox_o CHECK (outcome IN ('applied','recorded_stale')));
GO
IF OBJECT_ID('dbo.AuthorityState') IS NULL CREATE TABLE dbo.AuthorityState (
  country CHAR(2) NOT NULL, authority NVARCHAR(8) NOT NULL, objectId NVARCHAR(80) NOT NULL, revision INT NOT NULL, statusVersion INT NOT NULL, status NVARCHAR(24) NOT NULL, digest CHAR(64) NOT NULL, verifiedAt DATETIME2(3) NOT NULL, validUntil DATETIME2(3) NULL,
  tombstone BIT NOT NULL CONSTRAINT DF_AuthState_t DEFAULT 0, provenanceRef NVARCHAR(120) NULL, CONSTRAINT PK_AuthState PRIMARY KEY (country, authority, objectId));
GO
IF OBJECT_ID('dbo.PortfolioProjection') IS NULL CREATE TABLE dbo.PortfolioProjection (
  projectionKey NVARCHAR(160) NOT NULL CONSTRAINT PK_PortProj PRIMARY KEY, orgId NVARCHAR(40) NOT NULL, country CHAR(2) NOT NULL, plantScope NVARCHAR(32) NOT NULL, periodStart DATETIME2(3) NOT NULL, periodEnd DATETIME2(3) NOT NULL, boundaryRef NVARCHAR(40) NOT NULL,
  metric NVARCHAR(60) NOT NULL, unit NVARCHAR(24) NOT NULL, currency CHAR(3) NULL, valueDecimal NVARCHAR(40) NOT NULL, sourceRefs NVARCHAR(MAX) NOT NULL, sourceAsOf DATETIME2(3) NOT NULL, lastVerifiedAt DATETIME2(3) NOT NULL, validUntil DATETIME2(3) NOT NULL, rowVersion INT NOT NULL);
GO
IF OBJECT_ID('dbo.CentralReadAudit') IS NULL CREATE TABLE dbo.CentralReadAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_CReadAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
