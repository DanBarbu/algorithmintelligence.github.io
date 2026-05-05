-- WILL Platform — Sprint 0 (S0-03)
-- Track storage schema with PostGIS geometry index.
-- Flyway migration: V1__create_tracks_schema.sql

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Classification enum (STANAG 4774 levels; crypto-binding added in Sprint 9)
CREATE TYPE classification_level AS ENUM (
    'UNCLASSIFIED',
    'NATO_RESTRICTED',
    'NATO_CONFIDENTIAL',
    'NATO_SECRET'
);

-- Raw track events (one row per sensor report)
CREATE TABLE tracks (
    id              UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    track_id        TEXT              NOT NULL,
    source          TEXT              NOT NULL,
    position        GEOGRAPHY(POINT, 4326) NOT NULL,
    altitude_m      DOUBLE PRECISION,
    speed_ms        DOUBLE PRECISION,
    heading_deg     DOUBLE PRECISION,
    classification  classification_level NOT NULL DEFAULT 'UNCLASSIFIED',
    label_xml       TEXT,                        -- STANAG 4774 label (Sprint 9)
    tenant_id       UUID,
    observed_at     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    ingested_at     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    raw_payload     JSONB
);

CREATE INDEX idx_tracks_position ON tracks USING GIST(position);
CREATE INDEX idx_tracks_track_id ON tracks(track_id);
CREATE INDEX idx_tracks_observed ON tracks(observed_at DESC);
CREATE INDEX idx_tracks_tenant   ON tracks(tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX idx_tracks_source   ON tracks(source);

-- Fused track table (populated by fusion engine in Sprint 6)
CREATE TABLE fused_tracks (
    id                UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    track_id          TEXT              NOT NULL UNIQUE,
    position          GEOGRAPHY(POINT, 4326) NOT NULL,
    altitude_m        DOUBLE PRECISION,
    speed_ms          DOUBLE PRECISION,
    heading_deg       DOUBLE PRECISION,
    confidence        DOUBLE PRECISION  CHECK (confidence BETWEEN 0 AND 1),
    classification    classification_level NOT NULL DEFAULT 'UNCLASSIFIED',
    label_xml         TEXT,
    tenant_id         UUID,
    source_track_ids  TEXT[],
    first_observed_at TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    last_updated_at   TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    raw_payload       JSONB
);

CREATE INDEX idx_fused_position ON fused_tracks USING GIST(position);
CREATE INDEX idx_fused_track_id ON fused_tracks(track_id);
CREATE INDEX idx_fused_tenant   ON fused_tracks(tenant_id) WHERE tenant_id IS NOT NULL;

COMMENT ON TABLE tracks       IS 'Raw sensor reports — one row per observation';
COMMENT ON TABLE fused_tracks IS 'Kalman-fused tracks — one row per unique track object (Sprint 6+)';
