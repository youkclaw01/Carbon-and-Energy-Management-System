-- DB01(ingest) 접수 메타데이터 — S01 설계(04·06절) 기반 최소 구현. 원문은 SQL에 두지 않는다(Bronze Blob에 보존). 모든 문장은 반복 실행해도 안전하다.
IF OBJECT_ID('dbo.SourceRegistry') IS NULL CREATE TABLE dbo.SourceRegistry(
  sourceId NVARCHAR(64) NOT NULL CONSTRAINT PK_SourceRegistry PRIMARY KEY, plantId NVARCHAR(32) NOT NULL, sourceKind NVARCHAR(32) NOT NULL,
  boundPrincipal NVARCHAR(64) NOT NULL, allowedSchemaVersions NVARCHAR(128) NOT NULL, environmentId NVARCHAR(16) NOT NULL, mode NVARCHAR(16) NOT NULL,
  status NVARCHAR(16) NOT NULL, registryVersion INT NOT NULL, credentialRef NVARCHAR(160) NULL, updatedAt DATETIME2(3) NOT NULL CONSTRAINT DF_SourceRegistry_u DEFAULT SYSUTCDATETIME());
GO
IF OBJECT_ID('dbo.IngestionBatch') IS NULL CREATE TABLE dbo.IngestionBatch(
  batchId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_IngestionBatch PRIMARY KEY, sourceId NVARCHAR(64) NOT NULL, sourceEventId NVARCHAR(160) NOT NULL,
  requestDigest CHAR(64) NOT NULL, digestVersion TINYINT NOT NULL, rawDigest CHAR(64) NOT NULL, schemaVersion NVARCHAR(32) NOT NULL,
  epoch NVARCHAR(64) NOT NULL, firstSeq BIGINT NOT NULL, lastSeq BIGINT NOT NULL, eventCount INT NOT NULL, duplicateCount INT NOT NULL CONSTRAINT DF_IB_dup DEFAULT 0, rejectedCount INT NOT NULL CONSTRAINT DF_IB_rej DEFAULT 0,
  eventTime DATETIME2(3) NULL, receivedAt DATETIME2(3) NOT NULL, environmentId NVARCHAR(16) NOT NULL, mode NVARCHAR(16) NOT NULL, sourceRegistryVersion INT NOT NULL,
  rawRef NVARCHAR(260) NULL, status NVARCHAR(24) NOT NULL, reasonCode NVARCHAR(64) NULL, rowVersion INT NOT NULL CONSTRAINT DF_IB_rv DEFAULT 1,
  CONSTRAINT FK_IB_Source FOREIGN KEY(sourceId) REFERENCES dbo.SourceRegistry(sourceId),
  CONSTRAINT CK_IB_Status CHECK (status IN ('RECEIVING','LANDED','QUARANTINED','REJECTED','LANDING_UNKNOWN')));
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_IB_Source_Event') CREATE UNIQUE INDEX UX_IB_Source_Event ON dbo.IngestionBatch(sourceId, sourceEventId);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_IB_Source_Time') CREATE INDEX IX_IB_Source_Time ON dbo.IngestionBatch(sourceId, receivedAt DESC) INCLUDE(status, eventCount, firstSeq, lastSeq);
GO
IF OBJECT_ID('dbo.IngestionOutbox') IS NULL CREATE TABLE dbo.IngestionOutbox(
  eventId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_IngestionOutbox PRIMARY KEY, batchId UNIQUEIDENTIFIER NOT NULL, type NVARCHAR(64) NOT NULL, schemaVersion NVARCHAR(32) NOT NULL,
  digest CHAR(64) NOT NULL, payloadRef NVARCHAR(260) NULL, deliveryState NVARCHAR(16) NOT NULL CONSTRAINT DF_OB_state DEFAULT 'PENDING', attempt INT NOT NULL CONSTRAINT DF_OB_att DEFAULT 0,
  nextAttemptAt DATETIME2(3) NOT NULL CONSTRAINT DF_OB_next DEFAULT SYSUTCDATETIME(), createdAt DATETIME2(3) NOT NULL CONSTRAINT DF_OB_c DEFAULT SYSUTCDATETIME(), sentAt DATETIME2(3) NULL,
  CONSTRAINT FK_OB_Batch FOREIGN KEY(batchId) REFERENCES dbo.IngestionBatch(batchId), CONSTRAINT CK_OB_State CHECK (deliveryState IN ('PENDING','SENDING','SENT','FAILED')));
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_OB_Pending') CREATE INDEX IX_OB_Pending ON dbo.IngestionOutbox(deliveryState, nextAttemptAt);
GO
IF OBJECT_ID('dbo.IngestionAudit') IS NULL CREATE TABLE dbo.IngestionAudit(
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_IngestionAudit PRIMARY KEY, actor NVARCHAR(64) NULL, action NVARCHAR(48) NOT NULL, sourceId NVARCHAR(64) NULL, batchId UNIQUEIDENTIFIER NULL,
  beforeVersion INT NULL, afterVersion INT NULL, reason NVARCHAR(200) NULL, traceId NVARCHAR(64) NULL, at DATETIME2(3) NOT NULL CONSTRAINT DF_AU_at DEFAULT SYSUTCDATETIME(),
  previousHash CHAR(64) NULL, recordHash CHAR(64) NOT NULL);
GO
-- 시작 등록: 모의 공장 원천 12개(한국 5·일본 4·싱가포르 3)(SIMULATED 전용 등록. 운영 mode 어휘는 설계상 미결이라 만들지 않는다)
MERGE dbo.SourceRegistry AS t USING (VALUES
 ('src-kr01-vm01','KR-01','kr01-k1'),('src-kr02-vm01','KR-02','kr02-k1'),('src-kr03-vm01','KR-03','kr03-k1'),('src-kr04-vm01','KR-04','kr04-k1'),('src-kr05-vm01','KR-05','kr05-k1'),('src-jp01-vm01','JP-01','jp01-k1'),('src-jp02-vm01','JP-02','jp02-k1'),('src-jp03-vm01','JP-03','jp03-k1'),('src-jp04-vm01','JP-04','jp04-k1'),('src-sg01-vm01','SG-01','sg01-k1'),('src-sg02-vm01','SG-02','sg02-k1'),('src-sg03-vm01','SG-03','sg03-k1')) AS s(sourceId,plantId,boundPrincipal)
 ON t.sourceId = s.sourceId WHEN NOT MATCHED THEN INSERT(sourceId,plantId,sourceKind,boundPrincipal,allowedSchemaVersions,environmentId,mode,status,registryVersion,credentialRef)
 VALUES(s.sourceId,s.plantId,'factory-vm',s.boundPrincipal,'ama.factory.v1','prd','SIMULATED','ACTIVE',1,'kv:factory-keys#'+s.boundPrincipal);
GO
