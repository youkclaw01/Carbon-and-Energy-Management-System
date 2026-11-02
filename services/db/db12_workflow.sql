-- DB12 장기 작업(sqldb-cems-prd-krc-workflow-01) — 체크리스트 2-8. 설계: design/services/S12 §4. 시각 UTC, 식별자 NVARCHAR(36), CAS=revision.
IF OBJECT_ID('dbo.Job') IS NULL CREATE TABLE dbo.Job (
  jobId NVARCHAR(36) NOT NULL CONSTRAINT PK_Job PRIMARY KEY, country CHAR(2) NOT NULL, environment NVARCHAR(8) NOT NULL, orgId NVARCHAR(40) NOT NULL, plantId NVARCHAR(32) NULL, principal NVARCHAR(120) NOT NULL, jobKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  ownerService NVARCHAR(8) NOT NULL, workflowType NVARCHAR(60) NOT NULL, definitionVersion NVARCHAR(16) NOT NULL, inputRef NVARCHAR(200) NOT NULL, inputDigest CHAR(64) NOT NULL, runKey CHAR(64) NULL, state NVARCHAR(20) NOT NULL, waitingReason NVARCHAR(120) NULL, revision INT NOT NULL,
  leaseEpoch INT NOT NULL CONSTRAINT DF_Job_le DEFAULT 0, leaseOwner NVARCHAR(60) NULL, leaseUntil DATETIME2(3) NULL, deadlineAt DATETIME2(3) NOT NULL, retryPolicyVersion NVARCHAR(16) NOT NULL, createdAt DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_Job_key UNIQUE (country, orgId, principal, jobKey), CONSTRAINT CK_Job_state CHECK (state IN ('PENDING','READY','RUNNING','WAITING_SOURCE','WAITING_APPROVAL','SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')),
  CONSTRAINT CK_Job_lease CHECK (state <> 'RUNNING' OR (leaseOwner IS NOT NULL AND leaseUntil IS NOT NULL)));
GO
IF OBJECT_ID('dbo.StepAttempt') IS NULL CREATE TABLE dbo.StepAttempt (
  jobId NVARCHAR(36) NOT NULL, stepId NVARCHAR(40) NOT NULL, attemptNo INT NOT NULL, operationKey NVARCHAR(160) NOT NULL, targetService NVARCHAR(8) NOT NULL, taskType NVARCHAR(60) NOT NULL, targetRef NVARCHAR(200) NULL, expectedTargetVersion NVARCHAR(40) NULL,
  dispatchState NVARCHAR(16) NOT NULL, outcome NVARCHAR(24) NULL, epoch INT NOT NULL, providerJobRef NVARCHAR(120) NULL, observedAt DATETIME2(3) NULL, CONSTRAINT PK_StepAttempt PRIMARY KEY (jobId, stepId, attemptNo), CONSTRAINT FK_Step_job FOREIGN KEY (jobId) REFERENCES dbo.Job(jobId));
GO
IF OBJECT_ID('dbo.Timer') IS NULL CREATE TABLE dbo.Timer (jobId NVARCHAR(36) NOT NULL, timerId NVARCHAR(40) NOT NULL, dueAt DATETIME2(3) NOT NULL, purpose NVARCHAR(40) NOT NULL, expectedRevision INT NOT NULL, consumedAt DATETIME2(3) NULL, CONSTRAINT PK_Timer PRIMARY KEY (jobId, timerId), CONSTRAINT FK_Timer_job FOREIGN KEY (jobId) REFERENCES dbo.Job(jobId));
GO
IF OBJECT_ID('dbo.Checkpoint') IS NULL CREATE TABLE dbo.[Checkpoint] (jobId NVARCHAR(36) NOT NULL, checkpointNo INT NOT NULL, definitionVersion NVARCHAR(16) NOT NULL, lastCommittedStep NVARCHAR(40) NOT NULL, sourceRefs NVARCHAR(MAX) NULL, digest CHAR(64) NOT NULL, revision INT NOT NULL, epoch INT NOT NULL,
  CONSTRAINT PK_Checkpoint PRIMARY KEY (jobId, checkpointNo), CONSTRAINT FK_Chk_job FOREIGN KEY (jobId) REFERENCES dbo.Job(jobId));
GO
IF OBJECT_ID('dbo.TransitionAudit') IS NULL CREATE TABLE dbo.TransitionAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_TransAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
