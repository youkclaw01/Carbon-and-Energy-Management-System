# Security and approval model

## Identity
- The portal uses its **own login** (not a corporate directory): scrypt password hashes, server-side sessions with hashed tokens, TOTP MFA, optional passkeys.
- Public registration is closed by default; sign-up requests need administrator approval. Accounts have grades (for example operator, approver, administrator).
- Service-to-service access uses **managed identities**. Each service has its own identity and database grants.

## Approval (decision D12)
- Every execution needs a **separate human approval per case**. Nobody approves on behalf of another person; the AI assistant has no approve or reject tool.
- Segregation of duties: a requester cannot approve their own request, with one explicit exception for the administrator grade (recorded in the audit trail).
- A request must contain a requester-written **reason** (10–500 characters). The reason is shown as a claim, never as evidence; the AI treats it as a claim too.
- The decision is guarded: if the reason or intent changed after the approver opened it, the decision is rejected (`REASON_CHANGED`) and must be reviewed again.
- Rejecting or approving requires MFA.

## Intent digest and permits
- A procurement intent is serialized canonically (JCS-style, `intent.v1`) and hashed (SHA-256). The approval verifies the digest again.
- Approval issues a **signed, one-time permit**. The execution service verifies it, claims it (`active → claimed`) and refuses replays from another claimant.

## Signing and evidence
- Evidence and permits are signed with Key Vault keys (EC P-256). Keys can be retired or revoked; a rotation runbook exists.
- Regional senders authenticate with Key Vault ES256 signatures; factory batches carry per-site keys and signatures.

## Network
- Hub/Spoke design, application gateway with WAF at the edge, private endpoints for data services (design target), no direct public access to services.
- Security controls are never bypassed for convenience; blocked paths are fixed, not worked around.

## AI safety
- The agent answers only from computed FACTS and retrieved documents. Numbers not present in FACTS cause the answer to be blocked.
- No state-changing tool is exposed to the agent. Outputs are labeled `DRAFT-SIMULATED`.
- Prompts avoid anthropomorphic wording: the acting party is always named "administrator or reviewer".

## Data policy
- All factory data is synthetic. Telemetry stays in the Korean region; Japan and Southeast Asia send only signed summaries.
