# Carbon and Energy Management System (CEMS)

A cloud-native control platform for **carbon-allowance procurement and trading**, built as a customer demo on Azure.
The core story is a single, auditable chain:

> **collect → calculate → AI judgment → per-case human approval → simulated execution → evidence**

> **Status: demonstration system. All factory data is synthetic. No real trading is performed; execution is simulated only.**
> Every execution needs a separate approval by an authorized reviewer. The AI assistant never approves or rejects.

This repository is a *sanitized public snapshot* of a private working project (codename "AMA").
Subscription IDs, domains, e-mail addresses, secrets and internal corpora have been removed or replaced by placeholders.
Resource names are illustrative (`cems-prd-<region>-...`).

## What it does

- **Collects** minute-level energy and process data from simulated factories in three regions (Korea, Japan, Singapore). Each factory samples every second and sends a signed batch every minute.
- **Calculates** Scope 1 and Scope 2 emissions, an hourly "gold" table, and energy-cost scenarios.
- **Judges** allowance positions with a rule engine and an AI assistant grounded only on computed facts and a legal / history corpus (retrieval-augmented).
- **Requires human approval** for every procurement intent. Intents carry a cryptographic digest; approvals issue signed one-time permits.
- **Executes in simulation** (no market connectivity) and **records evidence** with detached signatures from a key vault.
- Shows an **Azure resource topology** (read-only) with service-flow, network and load-balancer-to-backend views.

## Repository layout

| Path | Content |
|---|---|
| `services/` | Python services (one folder per business service), SQL schema (`db/`), simulators (`factory/`), tests (`tests/`) |
| `portal/` | Single-page web portal (vanilla JS, multiple skins, i18n ko/en), nginx config, market-data and report helpers |
| `docs/` | Architecture, services, security model, approval flow, topology app, development and deployment guides |
| `journal/` | "Living Only for Today", the public developer diary (Jekyll) |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Services S01–S12](docs/SERVICES.md)
- [Security and approval model](docs/SECURITY.md)
- [Topology application](docs/TOPOLOGY.md)
- [Development and testing](docs/DEVELOPMENT.md)
- [Deployment notes](docs/DEPLOYMENT.md)
- [Demo scenario](docs/DEMO.md)
- [Limitations and open decisions](docs/LIMITATIONS.md)
- [Release v2](docs/RELEASE-V2.md)

## License

No license has been granted yet. Until the owner chooses one, all rights are reserved.
