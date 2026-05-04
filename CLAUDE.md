# WILL Platform – Romania Edition
## Claude Code Project Brief

**What this is:** WILL (White-Label Lattice) is a modular, open-core command and control fabric
for the Romanian defence ecosystem, aligned with NATO and EU interoperability requirements.
It is delivered as a Helm-deployable, Terraform-provisioned, FIPS-validated, ORNISS-accreditable
C2 platform. Codebase lives in the `will-platform` private repository.

---

## Architecture Principles (non-negotiable)

1. **Plugins-first.** New capabilities ship as plugins, never as core changes.
2. **Contracts before implementations.** gRPC / OpenAPI specs are versioned artefacts committed before any implementation.
3. **Immutable infrastructure.** Terraform-provisioned, Helm-deployed; pods replaced, not patched.
4. **Offline by default.** Every service tolerates partition; outbox + sync are first-class.
5. **Classification-aware.** Every track, command, and log carries a STANAG 4774 metadata label end-to-end.
6. **Observability is not optional.** No service ships without Prometheus metrics, OpenTelemetry traces, and Loki logs.

---

## Logical Layers

```
Physical Hardware  →  sensors, radars, drones, IoT nodes
HAL / Plugin SDK   →  gRPC contract; signed plugin images; plugin loader
Edge Runtime       →  K3s on rugged hardware; SQLite cache; outbox; NanoMQ
Core Services      →  Mythic-derived C2 core; EMQX bus; PostgreSQL/PostGIS; fusion engine; identity; audit
API / Access       →  REST + gRPC + WebSocket; OIDC/SAML; ZPR network policies
UX / Tenancy       →  React 18 + CesiumJS; APP-6D symbology; white-label theming; feature toggles; RBAC
Cross-cutting      →  Observability; security scanning; audit trail; classification metadata
```

---

## Technology Stack

| Layer | Component | Licence |
|---|---|---|
| C2 Core | Mythic (forked, red-team modules removed) | BSD-3 |
| Message Bus | EMQX (open edition) / NanoMQ on edge | Apache 2.0 |
| Database | PostgreSQL 16 + PostGIS, Patroni HA, Flyway migrations | PostgreSQL Licence |
| Sensor Fusion | libRSF + GTSAM, Drools rule engine | BSD / MIT |
| Frontend | React 18 + CesiumJS + APP-6D symbol library | Apache 2.0 |
| Mobile Bridge | ATAK-CIV plugin bridge (CoT XML) | Apache 2.0 |
| Identity | Keycloak (OIDC/SAML; bridges to NPKI and RO-PKI) | Apache 2.0 |
| Authorisation | Ory Keto + CASBIN (RBAC/ABAC) | Apache 2.0 |
| Mesh Networking | Meshtastic (runtime only, not linked to core) | GPL-3 |
| Orchestration | K3s (edge), Kubernetes/OKE (core) | Apache 2.0 |
| Observability | Prometheus + Grafana + Loki + OpenTelemetry + Jaeger | Apache 2.0 |
| Secrets | HashiCorp Vault (FIPS-validated build) | BUSL |
| Image Signing | Sigstore Cosign (required on all production images) | Apache 2.0 |
| Policy | OPA Gatekeeper (cluster admission) | Apache 2.0 |
| CI/CD | GitLab Runner + Trivy + Grype + Kube-bench + OpenSCAP | MIT / Apache 2.0 |
| IaC | Terraform + Helm + Ansible | MPL / Apache 2.0 |
| TDL Gateways | Custom Go: Link-16 (STANAG 5516), Link-22 (STANAG 5522), VMF, CoT, MIP 4 | Proprietary |

---

## Squads & Agents

| Squad | Owns | Agents |
|---|---|---|
| **Alpha** (Core & TDL) | Mythic C2 core, TDL gateways, EMQX bus, audit | `@will-backend-core-1`, `@will-backend-core-2`, `@will-backend-tdl`, `@will-scrum-master-alpha` |
| **Bravo** (HAL, Plugins, Edge) | Plugin SDK, HAL, edge runtime, mesh | `@will-backend-plugins-1`, `@will-backend-plugins-2`, `@will-edge-engineer`, `@will-scrum-master-bravo` |
| **Charlie** (UX, Multi-tenancy) | React/CesiumJS frontend, theming, RBAC | `@will-frontend-app6d`, `@will-frontend-cesium`, `@will-frontend-tenant-ux`, `@will-fusion-engineer` |
| **Cross-cutting** | Architecture, security, compliance, QA, docs | `@will-tech-lead`, `@will-product-owner`, `@will-programme-manager`, `@will-security-engineer`, `@will-compliance-officer`, `@will-devops-cloud`, `@will-devops-onprem`, `@will-qa-automation`, `@will-qa-hil`, `@will-tech-writer` |

---

## Architectural Decision Records (ADRs 001–008)

| ADR | Decision |
|---|---|
| ADR-001 | Adopt Mythic as the C2 core (forked; red-team modules stripped) |
| ADR-002 | gRPC as the Plugin SDK transport |
| ADR-003 | PostgreSQL + PostGIS as the system of record |
| ADR-004 | Helm + Terraform as the deployment toolchain |
| ADR-005 | STANAG 4774 as the canonical classification metadata standard |
| ADR-006 | Cosign as the mandatory image-signing standard |
| ADR-007 | Bilingual UI (RO/EN) from Sprint 0 — no retrofitting of i18n later |
| ADR-008 | Three deployment profiles (EU Sovereign Cloud, CPG/STS, On-prem) sharing one Helm chart |

---

## Deployment Profiles (all use the same Helm chart)

| Profile | Hosting | Classification level |
|---|---|---|
| EU Sovereign Cloud | OCI Madrid or Frankfurt | Unclassified / NATO RESTRICTED |
| Government Private Cloud (CPG/STS) | STS-operated, ORNISS-accredited | Secret de Serviciu / Secret |
| On-Premises / Air-Gapped | K3s on rugged hardware, HSM on-site | NATO SECRET |

Parameterised via `deployment_profile` Helm variable.

---

## Programme Roadmap (18 months, 16 sprints)

| Phase | Sprints | Theme | Key exit criterion |
|---|---|---|---|
| 0 – Foundation | 0a, 0b | Dev env, core demo | `docker compose up` → moving APP-6D icon on CesiumJS, bilingual login |
| 1 – HAL & Multi-tenancy | 1–4 | Plugin SDK; first 3 real sensors | ATAK-MIL, MAVLink, STANAG 4607 onboarded; tenant isolation working |
| 2 – Edge & AI Fusion | 5–8 | Offline mesh; Kalman fusion; track prediction | Disconnected demo; fused tracks with confidence scores |
| 3 – Compliance & Hardening | 9–11 | Classification, FIPS, audit, ORNISS pack | ORNISS pre-accreditation file submitted; FIPS modules in place |
| 4 – Ecosystem & Marketplace | 12–14 | Plugin registry, versioned API, certification kit | Public plugin registry live; AQAP 2110 documentation pack |
| 5 – Scale & Pilot Prep | 15 | Stress tests, chaos, Helm chart | 10k sensors @ 1 Hz, p99 < 500 ms; chaos recovery < 30 s |
| Pilot | +8 weeks | Live RO unit deployment | Go/No-Go report at Day 60 |

---

## Sprint 0 Goals & Acceptance Criteria

| ID | Story | Acceptance |
|---|---|---|
| S0-01 | One-command stack startup | All containers healthy in < 60 s |
| S0-02 | Mythic core + DB + broker | Mythic UI reachable at `https://localhost:7443` |
| S0-03 | PostGIS schema for tracks | `tracks` table with geometry index |
| S0-04 | Simulated GPS plugin (Python) | Publishes lat/lon at 1 Hz on `telemetry/gps/sim01` |
| S0-05 | WebSocket bridge | Subscribes EMQX → emits JSON on `ws://localhost:7000/tracks` |
| S0-06 | CesiumJS dashboard + APP-6D icon | Blue rectangle moves on the globe in real time |
| S0-07 | Bilingual i18n login (RO/EN) | Language toggle switches all visible strings |
| S0-08 | GitLab CI with Trivy + Grype | Pipeline fails on a deliberately vulnerable image |
| S0-09 | ADR repo | First five ADRs written and reviewed |

---

## Definition of Done (every PBI)

- [ ] Code reviewed by at least one peer not on the original pair
- [ ] Unit + integration + (where applicable) contract tests passing in CI
- [ ] Static analysis clean: `golangci-lint` / `ruff` / `eslint`
- [ ] Security scan clean (Trivy, Grype): no Critical, no unjustified High
- [ ] SBOM regenerated (CycloneDX) for any new container
- [ ] Documentation updated in the same merge request
- [ ] Acceptance criteria signed off by Product Owner
- [ ] Classification metadata reviewed by Compliance Officer if the change touches data flows

**Extra gate for changes touching identity, crypto, classification, or audit:**
Security Engineer is a required reviewer.

---

## Coding Standards

**Go** — `golangci-lint` clean; Effective Go style; no `panic` in library code; context propagation mandatory; Conventional Commits.

**Python** — `ruff` + `mypy --strict`; type hints everywhere; no implicit `Any`.

**TypeScript** — strict mode; ESLint Airbnb base; no `any`; prefer functional components.

**C/C++** — `clang-tidy` baseline; AddressSanitizer in CI; bounds-checked containers.

**SQL** — all migrations via Flyway; reversible where reasonable; explicit transactions.

**All languages** — each PR links to a GitLab/Jira issue and to relevant ADRs; backwards-compatibility window for Plugin SDK is current + previous major (minimum 3 years).

---

## Key Standards & Compliance References

| Standard | Purpose | Sprint |
|---|---|---|
| STANAG 4774 / 4778 | Classification metadata labels + crypto binding | Sprint 9 |
| STANAG 5516 | Link-16 message standard | Sprint 1 |
| STANAG 5522 | Link-22 message standard | Sprint 8 |
| STANAG 4607 | GMTI (ground moving target indicator) | Sprint 3 |
| STANAG 4586 | UAV control & interoperability | Sprint 1 |
| APP-6D | Joint military symbology | Sprint 0 |
| FMN Spiral 4/5 | Federated mission networking | Sprint 12–14 |
| FIPS 140-3 | Cryptographic module validation | Sprint 10 |
| AQAP 2110 | NATO software quality assurance | Continuous |
| Law 58/2023 (NIS2) | Romanian cybersecurity mandate | Sprint 0 |
| Law 182/2002 + HG 585/2002 | Romanian classified information | Sprint 9 |
| ORNISS accreditation | National security accreditation | Sprint 0 → pilot |

---

## Engineering KPIs

| KPI | Target |
|---|---|
| Sprint commitment completion | ≥ 85 % |
| Lead time (commit → staging) | < 20 minutes |
| Change failure rate | < 15 % |
| MTTR (production) | < 30 minutes |
| Test coverage (unit + integration) | ≥ 75 % |
| Critical CVEs in production images | 0 |
| End-to-end track latency (sensor → UI) | < 500 ms p99 |
| Time to integrate a new sensor (skilled dev) | < 4 hours |

---

## Data Flow (track lifecycle)

1. Sensor → Plugin SDK (normalise + STANAG 4774 label) → EMQX `telemetry/<type>/<id>`
2. Correlation service → assigns track ID
3. Fusion engine (libRSF/Kalman) → emits fused track + confidence
4. Persists to PostGIS `fused_tracks`; broadcasts on WebSocket bus
5. Frontend renders with APP-6D symbology + classification banner
6. Audit service → append-only log (Loki + WORM MinIO, 7-year retention)
