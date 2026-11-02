# Services

Twelve business services (S01–S12) plus supporting apps. Every service is a small Python HTTP app with its own tests.

| ID | Service | Folder | Purpose |
|---|---|---|---|
| S01 | Ingestion and field integration | `ingestapi/`, `ingest/`, `relay/` | Receives signed factory batches, validates, stores before acknowledging, tracks gaps, retries and quarantine; relay forwards the outbox to a queue |
| S02 | Carbon calculation | `calcapi/`, `calc/` | Scope 1 / Scope 2 runs from gold data with data-quality flags; certified releases |
| S03 | Cost planning | `planapi/` | Energy-cost scenarios (currently energy cost only) |
| S04 | Procurement positioning | `procapi/` | Allowance positions, rule-based judgment, procurement *intent* drafts with a canonical digest |
| S05 | Quote and shipment carbon information | `fpapi/` | Product footprint answers; refuses to invent a number if no certified source exists |
| S06 | Evidence | `evidapi/` | Evidence bundles, detached signatures with a Key Vault EC P-256 key, key status and rotation |
| S07 | Approval, policy and limits | `approvalapi/` | Own login (scrypt), MFA/TOTP, passkeys, sign-up with admin approval, grades, approval workflow, permits |
| S08 | Restricted execution | `execapi/` | Simulated dispatcher and reconciler; execution only with a valid, claimed permit |
| S09 | Export boundary | `exportapi/` | Controls what may leave the Korean region; blocked until a data policy is active |
| S10 | Central query | `cqapi/` | Portfolio views and a signed receiver for regional snapshots |
| S11 | Business AI | `agentapi/` | Read-only agent tasks (explain a calculation, answer questions on a procurement case, search law and history) |
| S12 | Long-running jobs | `wfapi/` | Job engine for calculation, evidence assembly and follow-up (manual tick, no auto-start) |

## Supporting apps
- `factory/`: factory simulator (1 s collection, 60 s batch send, multi-instance per region, 5-year synthetic history for 12 plants).
- `topoapi/`: read-only Azure topology viewer, see [TOPOLOGY.md](TOPOLOGY.md).
- `common/`: shared service helpers and telemetry.
- `db/`: schema files per service database and a migration runner.
- `calc/`, `medallion/`, `data/`: calculation core, medallion layout and synthetic data.

## Common contract (summary)
- JSON over HTTPS, versioned paths (`/v1/...`), problem-style error bodies.
- State-changing calls are idempotent by key.
- Every service exposes `/health`; the portal reaches services only through same-origin routes.
- Status words such as `DRAFT-SIMULATED`, `waiting_source`, `BLOCKED_DEPENDENCY`, `ALREADY_CLAIMED` are part of the contract.
