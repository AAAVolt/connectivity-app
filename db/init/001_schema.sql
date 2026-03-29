-- Bizkaia Connectivity MVP – Database Schema
-- PostGIS + multi-tenant tables, all geometries in SRID 4326.
--
-- Grid generation and area calculations use ST_Transform to
-- EPSG:25830 (ETRS89 / UTM 30N) at query time for metric accuracy.

-- ============================================================
-- Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- LOOKUP TABLES (global, not tenant-scoped)
-- ============================================================

-- Transport modes
CREATE TABLE modes (
    id      SERIAL PRIMARY KEY,
    code    TEXT NOT NULL UNIQUE,
    label   TEXT NOT NULL
);

-- Destination / purpose types
CREATE TABLE destination_types (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    description TEXT
);

-- ============================================================
-- TENANTS
-- ============================================================
CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    config      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TENANT-SCOPED TABLES
-- ============================================================

-- Region boundaries (defines the area to grid)
CREATE TABLE boundaries (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    boundary_type   TEXT NOT NULL DEFAULT 'region',
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_boundaries_geom   ON boundaries USING GIST (geom);
CREATE INDEX idx_boundaries_tenant ON boundaries (tenant_id);

-- Municipalities within a tenant's region
CREATE TABLE municipalities (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    muni_code   TEXT NOT NULL,
    name        TEXT NOT NULL,
    geom        GEOMETRY(MultiPolygon, 4326) NOT NULL,
    UNIQUE (tenant_id, muni_code)
);

CREATE INDEX idx_municipalities_geom   ON municipalities USING GIST (geom);
CREATE INDEX idx_municipalities_tenant ON municipalities (tenant_id);

-- 100 m grid cells
CREATE TABLE grid_cells (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cell_code   TEXT NOT NULL,
    geom        GEOMETRY(Polygon, 4326) NOT NULL,
    centroid    GEOMETRY(Point, 4326) NOT NULL,
    population  REAL NOT NULL DEFAULT 0,
    muni_code   TEXT,
    UNIQUE (tenant_id, cell_code)
);

CREATE INDEX idx_grid_cells_geom   ON grid_cells USING GIST (geom);
CREATE INDEX idx_grid_cells_tenant ON grid_cells (tenant_id);
CREATE INDEX idx_grid_cells_muni   ON grid_cells (tenant_id, muni_code);

-- Population source polygons (núcleos, census tracts, etc.)
CREATE TABLE population_sources (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT,
    population  REAL NOT NULL DEFAULT 0,
    geom        GEOMETRY(Polygon, 4326) NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_pop_sources_geom   ON population_sources USING GIST (geom);
CREATE INDEX idx_pop_sources_tenant ON population_sources (tenant_id);

-- Destination locations (POIs)
CREATE TABLE destinations (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type_id     INT NOT NULL REFERENCES destination_types(id),
    name        TEXT,
    geom        GEOMETRY(Point, 4326) NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0,
    metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_destinations_geom        ON destinations USING GIST (geom);
CREATE INDEX idx_destinations_tenant_type ON destinations (tenant_id, type_id);

-- Travel time matrices
-- NOTE: For full-scale runs, the OD matrix may be stored as Parquet
-- files and processed by the worker. This table handles manageable
-- subsets or pre-aggregated data.
CREATE TABLE travel_times (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    origin_cell_id      BIGINT NOT NULL REFERENCES grid_cells(id) ON DELETE CASCADE,
    destination_id      BIGINT NOT NULL REFERENCES destinations(id) ON DELETE CASCADE,
    mode                TEXT NOT NULL,
    departure_time      TIMESTAMPTZ,
    travel_time_minutes REAL NOT NULL,
    UNIQUE (tenant_id, origin_cell_id, destination_id, mode)
);

CREATE INDEX idx_travel_times_origin ON travel_times (tenant_id, origin_cell_id, mode);
CREATE INDEX idx_travel_times_dest   ON travel_times (tenant_id, destination_id, mode);

-- Connectivity scores per cell / mode / purpose
CREATE TABLE connectivity_scores (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cell_id             BIGINT NOT NULL REFERENCES grid_cells(id) ON DELETE CASCADE,
    mode                TEXT NOT NULL,
    purpose             TEXT NOT NULL,
    score               REAL NOT NULL,
    score_normalized    REAL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cell_id, mode, purpose)
);

CREATE INDEX idx_scores_cell         ON connectivity_scores (tenant_id, cell_id);
CREATE INDEX idx_scores_mode_purpose ON connectivity_scores (tenant_id, mode, purpose);

-- Combined / overall score per cell
CREATE TABLE combined_scores (
    id                          BIGSERIAL PRIMARY KEY,
    tenant_id                   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cell_id                     BIGINT NOT NULL REFERENCES grid_cells(id) ON DELETE CASCADE,
    combined_score              REAL NOT NULL,
    combined_score_normalized   REAL,
    weights                     JSONB NOT NULL DEFAULT '{}',
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cell_id)
);

CREATE INDEX idx_combined_scores_cell ON combined_scores (tenant_id, cell_id);
