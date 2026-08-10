# ADR-003 — PostgreSQL + PostGIS as the System of Record

**Status:** Accepted  
**Date:** 2026-01-15  
**Authors:** @will-tech-lead, @will-backend-core-1  
**Reviewers:** @will-compliance-officer

---

## Context

Track data is geospatial, time-series, and must be queryable by classification level and tenant. The platform must support 10 000 sensor updates per second at p99 < 500 ms (Phase 5 KPI). Storage must be ORNISS-accreditable (Romanian classified information law, HG 585/2002).

## Decision

**PostgreSQL 16 + PostGIS 3.4** as the single system of record, with:
- **Patroni** (3-node HA) in production profiles; single node in dev/edge
- **Flyway** for migration management (all DDL versioned in `/core/migrations/`)
- **GIST index** on `position GEOGRAPHY(POINT, 4326)` for sub-millisecond radius queries
- Row-level security (RLS) policies keyed on `tenant_id` enforced at the database layer
- **TimescaleDB** hypertables planned for Sprint 5 when track volume exceeds 10M rows/day

## Consequences

- **Positive:** Mature ACID guarantees; PostGIS is NATO-programme proven (used in multiple national C2 systems).
- **Positive:** RLS means a misconfigured application cannot leak cross-tenant tracks.
- **Negative:** Single write master (Patroni primary) is a bottleneck. Mitigated by event-sourcing writes through EMQX and batch-inserting via COPY.
- **Compliance:** All `raw_payload JSONB` columns containing PII or classified metadata are encrypted at rest via PostgreSQL pgcrypto (Sprint 10).

## Schema Summary

```sql
tracks        -- raw sensor reports (one row per observation)
fused_tracks  -- Kalman-fused unique track objects (populated Sprint 6)
```

Both tables carry `classification_level` enum aligned with STANAG 4774 levels.
