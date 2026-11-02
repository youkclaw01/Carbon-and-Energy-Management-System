-- DB11 업무 Agent(sqldb-cems-prd-krc-agents-01) — 체크리스트 2-12. 설계: design/services/S11 §4. 비밀·위임 토큰·permit 원문은 저장하지 않는다.
IF OBJECT_ID('dbo.AgentRun') IS NULL CREATE TABLE dbo.AgentRun (
  agentRunId NVARCHAR(36) NOT NULL CONSTRAINT PK_AgentRun PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, agentId NVARCHAR(8) NOT NULL, task NVARCHAR(40) NOT NULL, subjectRef NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  purpose NVARCHAR(40) NOT NULL, plantScope NVARCHAR(32) NOT NULL, contextRefs NVARCHAR(MAX) NOT NULL, modelPolicyRef NVARCHAR(80) NOT NULL, promptVersion NVARCHAR(20) NOT NULL, toolSchemaVersion NVARCHAR(20) NOT NULL, state NVARCHAR(16) NOT NULL, version INT NOT NULL, blockedReason NVARCHAR(200) NULL,
  createdAt DATETIME2(3) NOT NULL, deadline DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL, CONSTRAINT UQ_AgentRun_idem UNIQUE (country, orgId, subjectRef, idemKey), CONSTRAINT CK_AgentRun_state CHECK (state IN ('ACCEPTED','RUNNING','DRAFT','BLOCKED','FAILED','STOP_REQUESTED','STOPPED')));
GO
IF OBJECT_ID('dbo.ToolCallAudit') IS NULL CREATE TABLE dbo.ToolCallAudit (
  agentRunId NVARCHAR(36) NOT NULL, toolCallId NVARCHAR(36) NOT NULL, auditSequence INT NOT NULL, toolId NVARCHAR(20) NOT NULL, requestDigest CHAR(64) NOT NULL, resultDigest CHAR(64) NULL, effectClass NVARCHAR(12) NOT NULL, phase NVARCHAR(16) NOT NULL, status NVARCHAR(16) NOT NULL, recordedAt DATETIME2(3) NOT NULL,
  CONSTRAINT PK_ToolCall PRIMARY KEY (agentRunId, toolCallId, auditSequence), CONSTRAINT CK_ToolCall_eff CHECK (effectClass = 'READ'), CONSTRAINT FK_ToolCall_run FOREIGN KEY (agentRunId) REFERENCES dbo.AgentRun(agentRunId));
GO
IF OBJECT_ID('dbo.EvaluationRef') IS NULL CREATE TABLE dbo.EvaluationRef (
  agentRunId NVARCHAR(36) NOT NULL, evaluationId NVARCHAR(36) NOT NULL, evaluatorVersion NVARCHAR(20) NOT NULL, sourceVersions NVARCHAR(MAX) NOT NULL, numericResult NVARCHAR(12) NOT NULL, citationResult NVARCHAR(12) NOT NULL, schemaResult NVARCHAR(12) NOT NULL, detail NVARCHAR(MAX) NULL,
  CONSTRAINT PK_EvalRef PRIMARY KEY (agentRunId, evaluationId), CONSTRAINT FK_EvalRef_run FOREIGN KEY (agentRunId) REFERENCES dbo.AgentRun(agentRunId), CONSTRAINT CK_EvalRef_n CHECK (numericResult IN ('passed','failed','not_run')));
GO
IF OBJECT_ID('dbo.DraftArtifact') IS NULL CREATE TABLE dbo.DraftArtifact (
  agentRunId NVARCHAR(36) NOT NULL, artifactId NVARCHAR(36) NOT NULL, facts NVARCHAR(MAX) NOT NULL, citations NVARCHAR(MAX) NOT NULL, draftText NVARCHAR(MAX) NOT NULL, sourceVersions NVARCHAR(MAX) NOT NULL, classification NVARCHAR(24) NOT NULL, modelDeployment NVARCHAR(40) NOT NULL, responseModel NVARCHAR(60) NULL,
  responseId NVARCHAR(80) NULL, usage NVARCHAR(MAX) NULL, status NVARCHAR(12) NOT NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT PK_Draft PRIMARY KEY (agentRunId, artifactId), CONSTRAINT FK_Draft_run FOREIGN KEY (agentRunId) REFERENCES dbo.AgentRun(agentRunId), CONSTRAINT CK_Draft_st CHECK (status IN ('DRAFT','INVALIDATED')));
GO
IF OBJECT_ID('dbo.RunAudit') IS NULL CREATE TABLE dbo.RunAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RunAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL, reason NVARCHAR(300) NULL,
  correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
