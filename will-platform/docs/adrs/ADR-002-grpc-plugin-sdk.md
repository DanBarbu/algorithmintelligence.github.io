# ADR-002 — gRPC as the Plugin SDK Transport

**Status:** Accepted  
**Date:** 2026-01-15  
**Authors:** @will-tech-lead, @will-backend-plugins-1  
**Reviewers:** @will-security-engineer

---

## Context

The HAL (Hardware Abstraction Layer) requires a versioned, language-agnostic contract between the core and sensor plugins. Plugins ship as separate signed container images; they must be upgradeable independently of the core.

## Decision

Use **gRPC** with Protocol Buffers v3 as the Plugin SDK transport. The canonical contract is defined in `/proto/plugin/v1/plugin.proto` and versioned as a first-class repository artefact committed before any implementation.

The Plugin SDK lifecycle:
1. Plugin registers via `PluginService.Register(PluginInfo)`
2. Core streams normalised `TrackEvent` messages to plugins via `PluginService.StreamTracks`
3. Plugins emit sensor data via `SensorService.Ingest(SensorReport)`

Backwards-compatibility window: current major + previous major, minimum 3 years.

## Consequences

- **Positive:** Strongly typed cross-language contract; generated client SDKs for Go, Python, C++.
- **Positive:** mTLS at the gRPC layer provides per-plugin identity without additional middleware.
- **Negative:** Proto schema evolution requires discipline (no field removal, use `reserved`).
- **Tooling:** `buf lint` + `buf breaking` run in CI against the previous released schema.

## Alternatives Rejected

| Option | Reason |
|--------|--------|
| REST/OpenAPI | No streaming; SDK generation less ergonomic for binary sensor data |
| MQTT only | No request/reply; hard to enforce typed contracts |
| Unix sockets | Cannot span container boundaries without shared volumes |
