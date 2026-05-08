-- Núcleo (concentrated settlement) polygons from EUSTAT.
-- Used as a dasymetric mask in population disaggregation: only grid cells
-- that overlap a núcleo receive population.  Diseminado (dispersed) areas
-- are excluded so population concentrates where people actually live.

CREATE TABLE IF NOT EXISTS nucleos (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        TEXT NOT NULL,           -- NUC_CL
    nucleo_num  TEXT NOT NULL,           -- NUC_NUCD (01-N = núcleo, 99 = diseminado)
    name        TEXT NOT NULL,           -- NUC_DS_O
    entity_name TEXT,                    -- NUC_ENTI_D
    muni_code   TEXT,                    -- NUC_MUNI
    muni_name   TEXT,                    -- NUC_MUNI_D
    geom        GEOMETRY(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nucleos_geom   ON nucleos USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_nucleos_tenant ON nucleos (tenant_id);
CREATE INDEX IF NOT EXISTS idx_nucleos_type   ON nucleos (tenant_id, nucleo_num);
