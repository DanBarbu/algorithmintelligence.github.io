# ADR-004 — Helm + Terraform as the Deployment Toolchain

**Status:** Accepted  
**Date:** 2026-01-15  
**Authors:** @will-devops-cloud, @will-devops-onprem  
**Reviewers:** @will-tech-lead, @will-compliance-officer

---

## Context

WILL must deploy to three distinct environments (EU Sovereign Cloud / OCI, Government Private Cloud / CPG-STS, On-premises air-gapped K3s) from a single, auditable source of truth.

## Decision

Use **Terraform** for infrastructure provisioning and **Helm** for application deployment, sharing a single Helm chart parameterised by the `deployment_profile` variable (`cloud`, `cpg`, `onprem`).

Toolchain:
- Terraform modules: `modules/networking`, `modules/k8s-cluster`, `modules/vault`, `modules/observability`
- Helm chart: `helm/will-platform/` with `values-cloud.yaml`, `values-cpg.yaml`, `values-onprem.yaml`
- OPA Gatekeeper policies enforced at cluster admission for all three profiles
- Cosign image verification as a Kyverno policy (Sprint 3)
- Air-gapped profile uses a local Helm repository mirrored by GitLab Package Registry

## Consequences

- **Positive:** One chart, three profiles — no drift between environments.
- **Positive:** Terraform state in OCI Object Storage (cloud) or local encrypted volume (onprem); no shared mutable state.
- **Negative:** Helm chart complexity grows with profile count. Mitigated by Helm library chart for shared templates.
- **Tooling gate:** `helm lint` + `helm template | conftest` run in CI before any push to main.

## Alternatives Rejected

| Option | Reason |
|--------|--------|
| Kustomize only | Weaker templating for multi-profile value injection |
| Ansible only | Not idempotent at infrastructure layer; no state tracking |
| Crossplane | Immature for air-gapped; steep learning curve for CPG ops team |
