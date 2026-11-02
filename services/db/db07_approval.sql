-- DB07 승인·정책·한도(sqldb-cems-prd-krc-approval-01) — 체크리스트 2-4. 설계: design/services/S07 §4·6. 식별자는 NVARCHAR(36). 금액은 통화별 최소단위 정수(BIGINT)+통화(부동소수 금지).
IF OBJECT_ID('dbo.PolicyEvaluation') IS NULL CREATE TABLE dbo.PolicyEvaluation (
  evaluationId NVARCHAR(36) NOT NULL CONSTRAINT PK_PolEval PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, principal NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  action NVARCHAR(60) NOT NULL, resource NVARCHAR(120) NOT NULL, purpose NVARCHAR(40) NOT NULL, operationKey NVARCHAR(160) NOT NULL, intentDigest CHAR(64) NOT NULL, canonicalizationVersion NVARCHAR(40) NOT NULL, digestAlgorithmId NVARCHAR(20) NOT NULL,
  amountMinor BIGINT NULL, currency CHAR(3) NULL, decision NVARCHAR(20) NOT NULL, reasonCode NVARCHAR(40) NOT NULL, policyVersion NVARCHAR(20) NOT NULL, proposeOnly BIT NOT NULL, createdAt DATETIME2(3) NOT NULL, expiresAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_PolEval_idem UNIQUE (country, orgId, principal, idemKey), CONSTRAINT CK_PolEval_dec CHECK (decision IN ('allow','deny','needs-approval')), CONSTRAINT CK_PolEval_amt CHECK (amountMinor IS NULL OR amountMinor >= 0));
GO
IF OBJECT_ID('dbo.ApprovalRequest') IS NULL CREATE TABLE dbo.ApprovalRequest (
  requestId NVARCHAR(36) NOT NULL CONSTRAINT PK_ApprReq PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, evaluationId NVARCHAR(36) NOT NULL, requester NVARCHAR(120) NOT NULL, idemKey NVARCHAR(100) NOT NULL, requestDigest CHAR(64) NOT NULL,
  operationKey NVARCHAR(160) NOT NULL, intentRevision INT NOT NULL, intentDigest CHAR(64) NOT NULL, digestVerified BIT NOT NULL CONSTRAINT DF_ApprReq_dv DEFAULT 0, action NVARCHAR(60) NOT NULL, purpose NVARCHAR(40) NOT NULL, amountMinor BIGINT NULL, currency CHAR(3) NULL,
  state NVARCHAR(12) NOT NULL, rev INT NOT NULL, approvalVersion INT NOT NULL CONSTRAINT DF_ApprReq_av DEFAULT 0, expiresAt DATETIME2(3) NOT NULL, createdAt DATETIME2(3) NOT NULL, updatedAt DATETIME2(3) NOT NULL,
  CONSTRAINT UQ_ApprReq_idem UNIQUE (country, orgId, requester, idemKey), CONSTRAINT CK_ApprReq_state CHECK (state IN ('pending','approved','rejected','cancelled','expired')), CONSTRAINT FK_ApprReq_eval FOREIGN KEY (evaluationId) REFERENCES dbo.PolicyEvaluation(evaluationId));
GO
IF OBJECT_ID('dbo.ApprovalDecision') IS NULL CREATE TABLE dbo.ApprovalDecision (
  decisionId NVARCHAR(36) NOT NULL CONSTRAINT PK_ApprDec PRIMARY KEY, requestId NVARCHAR(36) NOT NULL, actor NVARCHAR(120) NOT NULL, mfaEvidenceRef NVARCHAR(200) NOT NULL, decision NVARCHAR(10) NOT NULL, reasonCode NVARCHAR(60) NULL,
  approvalVersion INT NOT NULL, decidedAt DATETIME2(3) NOT NULL, CONSTRAINT CK_ApprDec_d CHECK (decision IN ('approve','reject','cancel')), CONSTRAINT FK_ApprDec_req FOREIGN KEY (requestId) REFERENCES dbo.ApprovalRequest(requestId));
GO
IF OBJECT_ID('dbo.LimitAccount') IS NULL CREATE TABLE dbo.LimitAccount (
  accountId NVARCHAR(36) NOT NULL CONSTRAINT PK_LimAcc PRIMARY KEY, country CHAR(2) NOT NULL, orgId NVARCHAR(40) NOT NULL, principalScope NVARCHAR(120) NOT NULL, action NVARCHAR(60) NOT NULL, currency CHAR(3) NOT NULL, periodStart DATETIME2(3) NOT NULL, periodEnd DATETIME2(3) NOT NULL,
  capMinor BIGINT NOT NULL, heldMinor BIGINT NOT NULL CONSTRAINT DF_LimAcc_h DEFAULT 0, settledMinor BIGINT NOT NULL CONSTRAINT DF_LimAcc_s DEFAULT 0, rev INT NOT NULL CONSTRAINT DF_LimAcc_r DEFAULT 1,
  CONSTRAINT CK_LimAcc_inv CHECK (capMinor >= 0 AND heldMinor >= 0 AND settledMinor >= 0 AND capMinor >= heldMinor + settledMinor), CONSTRAINT CK_LimAcc_per CHECK (periodStart < periodEnd));
GO
IF OBJECT_ID('dbo.LimitReservation') IS NULL CREATE TABLE dbo.LimitReservation (
  reservationId NVARCHAR(36) NOT NULL CONSTRAINT PK_LimRes PRIMARY KEY, requestId NVARCHAR(36) NOT NULL, permitId NVARCHAR(36) NULL, accountId NVARCHAR(36) NOT NULL, intentDigest CHAR(64) NOT NULL, reservedMinor BIGINT NOT NULL,
  state NVARCHAR(16) NOT NULL, expiresAt DATETIME2(3) NOT NULL, reconciliationVersion INT NOT NULL CONSTRAINT DF_LimRes_rv DEFAULT 0, proofRef NVARCHAR(200) NULL, rev INT NOT NULL CONSTRAINT DF_LimRes_r DEFAULT 1,
  CONSTRAINT CK_LimRes_state CHECK (state IN ('held','settled','released','review-required')), CONSTRAINT CK_LimRes_amt CHECK (reservedMinor >= 0), CONSTRAINT UQ_LimRes_permit UNIQUE (permitId, accountId),
  CONSTRAINT FK_LimRes_acc FOREIGN KEY (accountId) REFERENCES dbo.LimitAccount(accountId), CONSTRAINT FK_LimRes_req FOREIGN KEY (requestId) REFERENCES dbo.ApprovalRequest(requestId));
GO
IF OBJECT_ID('dbo.ExecutionPermit') IS NULL CREATE TABLE dbo.ExecutionPermit (
  permitId NVARCHAR(36) NOT NULL CONSTRAINT PK_Permit PRIMARY KEY, operationKey NVARCHAR(160) NOT NULL, requestId NVARCHAR(36) NOT NULL, reservationId NVARCHAR(36) NULL, intentDigest CHAR(64) NOT NULL, state NVARCHAR(16) NOT NULL,
  useProhibited BIT NOT NULL CONSTRAINT DF_Permit_up DEFAULT 1, operationHold BIT NOT NULL CONSTRAINT DF_Permit_oh DEFAULT 0, authorityVersion INT NOT NULL CONSTRAINT DF_Permit_av DEFAULT 1, createdAt DATETIME2(3) NOT NULL,
  CONSTRAINT CK_Permit_state CHECK (state IN ('signing','active','claimed','block_pending','blocked','expired')));
GO
IF OBJECT_ID('dbo.ApprovalAudit') IS NULL CREATE TABLE dbo.ApprovalAudit (
  auditId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ApprAudit PRIMARY KEY, actor NVARCHAR(120) NOT NULL, action NVARCHAR(40) NOT NULL, target NVARCHAR(120) NULL, beforeVersion NVARCHAR(40) NULL, afterVersion NVARCHAR(40) NULL,
  reason NVARCHAR(300) NULL, correlationId NVARCHAR(80) NULL, at DATETIME2(3) NOT NULL, prevHash CHAR(64) NULL, hash CHAR(64) NOT NULL);
GO
GO
IF OBJECT_ID('dbo.AppUser') IS NULL CREATE TABLE dbo.AppUser (
  userId NVARCHAR(36) NOT NULL CONSTRAINT PK_AppUser PRIMARY KEY, username NVARCHAR(40) NOT NULL CONSTRAINT UQ_AppUser_name UNIQUE, pwHash NVARCHAR(64) NOT NULL, pwSalt NVARCHAR(32) NOT NULL, status NVARCHAR(10) NOT NULL CONSTRAINT DF_AppUser_st DEFAULT 'active',
  isAdmin BIT NOT NULL CONSTRAINT DF_AppUser_adm DEFAULT 0, mfaSecretEnc NVARCHAR(200) NULL, mfaEnrolled BIT NOT NULL CONSTRAINT DF_AppUser_mfa DEFAULT 0, mfaLastStep BIGINT NOT NULL CONSTRAINT DF_AppUser_ls DEFAULT 0,
  failCount INT NOT NULL CONSTRAINT DF_AppUser_fc DEFAULT 0, lockedUntil DATETIME2(3) NULL, createdAt DATETIME2(3) NOT NULL, CONSTRAINT CK_AppUser_st CHECK (status IN ('active','disabled')));
GO
IF OBJECT_ID('dbo.AppSession') IS NULL CREATE TABLE dbo.AppSession (
  tokenHash CHAR(64) NOT NULL CONSTRAINT PK_AppSession PRIMARY KEY, userId NVARCHAR(36) NOT NULL, mfaVerified BIT NOT NULL, createdAt DATETIME2(3) NOT NULL, expiresAt DATETIME2(3) NOT NULL, revokedAt DATETIME2(3) NULL,
  CONSTRAINT FK_AppSession_user FOREIGN KEY (userId) REFERENCES dbo.AppUser(userId));
GO
IF OBJECT_ID('dbo.UserGrant') IS NULL CREATE TABLE dbo.UserGrant (
  grantId NVARCHAR(36) NOT NULL CONSTRAINT PK_UserGrant PRIMARY KEY, userId NVARCHAR(36) NOT NULL, action NVARCHAR(40) NOT NULL, grantedBy NVARCHAR(40) NOT NULL, validFrom DATETIME2(3) NOT NULL, validTo DATETIME2(3) NULL, revokedAt DATETIME2(3) NULL,
  CONSTRAINT FK_UserGrant_user FOREIGN KEY (userId) REFERENCES dbo.AppUser(userId), CONSTRAINT CK_UserGrant_act CHECK (action IN ('request','approve','permit.issue','admin')));
GO
IF COL_LENGTH('dbo.AppUser','email') IS NULL ALTER TABLE dbo.AppUser ADD email NVARCHAR(120) NULL, displayName NVARCHAR(60) NULL, grade NVARCHAR(16) NULL, decidedBy NVARCHAR(40) NULL, decidedAt DATETIME2(3) NULL;
GO
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name='CK_AppUser_st') ALTER TABLE dbo.AppUser DROP CONSTRAINT CK_AppUser_st;
GO
ALTER TABLE dbo.AppUser ADD CONSTRAINT CK_AppUser_st CHECK (status IN ('active','disabled','pending','rejected'));
GO
IF OBJECT_ID('dbo.AppSetting') IS NULL CREATE TABLE dbo.AppSetting (settingKey NVARCHAR(60) NOT NULL CONSTRAINT PK_AppSetting PRIMARY KEY, settingValue NVARCHAR(400) NOT NULL, updatedBy NVARCHAR(40) NOT NULL, updatedAt DATETIME2(3) NOT NULL);
GO
IF OBJECT_ID('dbo.MailOutbox') IS NULL CREATE TABLE dbo.MailOutbox (mailId NVARCHAR(36) NOT NULL CONSTRAINT PK_MailOutbox PRIMARY KEY, kind NVARCHAR(30) NOT NULL, toEmail NVARCHAR(120) NOT NULL, subject NVARCHAR(160) NOT NULL, body NVARCHAR(1000) NOT NULL,
  state NVARCHAR(10) NOT NULL CONSTRAINT DF_Mail_st DEFAULT 'pending', attempts INT NOT NULL CONSTRAINT DF_Mail_at DEFAULT 0, createdAt DATETIME2(3) NOT NULL, sentAt DATETIME2(3) NULL, lastError NVARCHAR(200) NULL, CONSTRAINT CK_Mail_st CHECK (state IN ('pending','sent','failed')));
GO
IF OBJECT_ID('dbo.PasskeyCredential') IS NULL CREATE TABLE dbo.PasskeyCredential (
  credId NVARCHAR(400) NOT NULL CONSTRAINT PK_Passkey PRIMARY KEY, userId NVARCHAR(36) NOT NULL, publicKey NVARCHAR(200) NOT NULL, signCount BIGINT NOT NULL CONSTRAINT DF_Pk_sc DEFAULT 0, label NVARCHAR(60) NULL, createdAt DATETIME2(3) NOT NULL, lastUsedAt DATETIME2(3) NULL, revokedAt DATETIME2(3) NULL,
  CONSTRAINT FK_Passkey_user FOREIGN KEY (userId) REFERENCES dbo.AppUser(userId));
GO
IF OBJECT_ID('dbo.PasskeyChallenge') IS NULL CREATE TABLE dbo.PasskeyChallenge (
  challengeHash CHAR(64) NOT NULL CONSTRAINT PK_PkChallenge PRIMARY KEY, purpose NVARCHAR(10) NOT NULL, userId NVARCHAR(36) NULL, createdAt DATETIME2(3) NOT NULL, expiresAt DATETIME2(3) NOT NULL, usedAt DATETIME2(3) NULL);
GO
IF COL_LENGTH('dbo.ApprovalRequest','intentRef') IS NULL ALTER TABLE dbo.ApprovalRequest ADD intentRef NVARCHAR(120) NULL;
GO
IF COL_LENGTH('dbo.ExecutionPermit','signature') IS NULL ALTER TABLE dbo.ExecutionPermit ADD signature NVARCHAR(160) NULL, keyRef NVARCHAR(200) NULL, signedDigest CHAR(64) NULL, expiresAt DATETIME2(3) NULL;
GO
IF COL_LENGTH('dbo.ExecutionPermit','claimedBy') IS NULL ALTER TABLE dbo.ExecutionPermit ADD claimedBy NVARCHAR(60) NULL, claimedAt DATETIME2(3) NULL;
GO
IF COL_LENGTH('dbo.ApprovalRequest','requestReason') IS NULL ALTER TABLE dbo.ApprovalRequest ADD requestReason NVARCHAR(500) NULL, reasonUpdatedAt DATETIME2(3) NULL;
