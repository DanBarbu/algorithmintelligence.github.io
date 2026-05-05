# ADR-001 — Adopt Mythic as the C2 Core

**Status:** Accepted  
**Date:** 2026-01-15  
**Authors:** @will-tech-lead  
**Reviewers:** @will-security-engineer, @will-product-owner

---

## Context

WILL Romania needs a C2 core that is:
- Open-source and auditable (no binary blobs)
- Extensible via plugins without touching core logic
- Actively maintained and community-vetted

Evaluated options: Mythic (BSD-3), OpenC2 reference implementation (LGPL), and a fully bespoke gRPC core.

## Decision

Adopt **Mythic v3.3.x** (BSD-3 licensed) as the WILL C2 core, forked as `will-mythic`, with all red-team agent modules stripped from the distribution build. The fork is maintained as a thin patch set on top of upstream Mythic releases.

## Consequences

- **Positive:** Mature task-dispatch, operator collaboration, and web UI with minimal build cost. Upstream CVE fixes can be cherry-picked.
- **Positive:** Plugin SDK wraps Mythic's C2 profile API; operators never interact with raw Mythic surfaces.
- **Negative:** Fork maintenance burden. Mitigated by limiting patch surface to module removal and configuration only.
- **Compliance note:** Red-team module removal is a contractual requirement and is verified in CI by Trivy SBOM diffing against a known-clean manifest.

## Alternatives Rejected

| Option | Reason |
|--------|--------|
| OpenC2 reference impl | Immature deployment tooling; no built-in multi-tenancy |
| Bespoke gRPC core | 6–9 months build time; unacceptable schedule risk for Sprint 0 |
