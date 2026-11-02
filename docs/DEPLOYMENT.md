# Deployment notes

These notes describe the shape of the deployment; the snapshot does not include the private operations scripts.

- **Compute**: one container app per service in a Korea Central environment (Japan East and Southeast Asia host only the regional ingestion and storage pieces). Images are built in a container registry, with immutable tags per version.
- **Data**: one SQL database per service. Schema files in `services/db/` are applied in order by `services/db/runner.py`; permissions come from `grants.json` / `grants.sql.tpl`.
- **Identity**: user-assigned managed identity per service. Grant access by role at resource-group scope, never with shared keys.
- **Secrets**: Key Vault only. No keys in images, environment dumps or this repository.
- **Edge**: application gateway with WAF; the portal container app is the only public backend.
- **Operations**: nightly stop and morning start of non-production compute, alert rules with 15-minute auto-recovery, budget alerts with e-mail notification.
- **Rollback**: previous image tags stay available; deployments are done one service at a time and verified through the portal route before the next.
