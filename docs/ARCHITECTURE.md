# Architecture

## Goals
1. A believable end-to-end carbon and energy workflow for a customer demo.
2. Strict human control: no AI or service can approve its own action.
3. Data residency: telemetry and personal/business data stay in the Korean region; Japan and Southeast Asia nodes only send signed, minimal batches.
4. Everything traceable: each result links to its inputs, policy version and evidence.

## Regions and layout
- **Korea Central**: the main region. Web tier, business services, SQL databases, search, AI, observability.
- **Japan East** and **Southeast Asia (Singapore)**: regional factory ingestion and regional medallion (bronze/silver/gold) storage; they forward signed summaries to Korea.
- Each region follows a **Hub/Spoke** network design: shared edge services (firewall, application gateway with WAF) in the Hub, workloads in Spoke subnets. A global front door sits outside the virtual networks.

## Layers
1. **Edge**: application gateway + WAF terminates TLS and forwards to the portal container app.
2. **Portal**: a static single-page app served by nginx. It talks to services through same-origin `/api/<service>/` routes only; services are never exposed directly.
3. **Business services** (container apps, one per service, one managed identity each): see [SERVICES.md](SERVICES.md).
4. **Data**: one Azure SQL database per service (no cross-service database access), blob/lake storage for the medallion layers, a search index for law and history retrieval.
5. **AI**: a dedicated Foundry resource with a chat model and an embedding model. The agent service is the only caller.
6. **Security**: Key Vault (signing keys, sender authentication), managed identities, RBAC at resource-group scope.
7. **Observability**: Log Analytics, Application Insights (Korean services only), alert rules with an auto-recovery runbook, budget alerts.

## Data flow
```
Factory sim (1 s samples) --60 s signed batch--> ingest-api --> outbox/relay --> queue --> lake (bronze)
   bronze -> silver -> gold (hourly) --> calc-api (Scope 1/2, run + data-quality flags)
   calc-api --> plan-api (energy-cost scenarios) --> proc-api (procurement intent draft + digest)
   proc-api --> approval-api (human decision, permit) --> exec-api (simulated dispatch + reconcile)
   every step --> evid-api (detached signature in Key Vault) --> audit trail in the portal
   agent-api reads computed facts and retrieval results, answers questions, proposes explanations (read-only)
```

## Design rules that shape the code
- **Landing before acknowledgement**: a batch is acknowledged to the sender only after it is durably stored.
- **Numbers are never invented**: if a source (for example a certified calculation run) is missing, the API answers `waiting_source` or `BLOCKED_DEPENDENCY` instead of producing a value.
- **Idempotency**: requests carry keys; the same key returns the same result, a conflicting payload is rejected.
- **Least privilege**: each service has its own identity and its own database grants (`services/db/grants.json`).
- **Simulation boundary**: the only provider in the execution service is a simulator. Permits are one-time, signed and claim-checked.
