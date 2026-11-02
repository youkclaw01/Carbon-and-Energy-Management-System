# Topology application

A separate read-only, administrator-only container app that draws the live Azure estate.

- **Source**: Azure Resource Graph queries (read-only). It never creates, changes or deletes anything.
- **Views**: resources by relationship, network configuration, service boxes (grouped by service), service-flow application map, impact range, path finding between two resources.
- **Icons**: official Azure icon set. Layout: layered (ELK-style), orthogonal lines.
- **Selection**: choosing a resource lights up only its neighbors; flowing dots animate on the selected links only. Collapsed groups expand automatically.
- **Load balancers and gateways** (v1.9+): relations are derived from structure, because Resource Graph properties carry no resource IDs for these links:
  1. an environment's internal load balancer lives in the environment's managed infrastructure resource group; it connects to the environment and to its apps with external ingress;
  2. an application gateway listener host → backend pool FQDN → the container app with the same FQDN → that app's environment load balancer.
  Unresolved pools produce no edge (no guessing).
- **Telemetry**: Korean services only (Application Insights); other regions are excluded for data residency.
- **Tests**: `services/tests/test_topo.py` (46 checks, including the load-balancer rules).
