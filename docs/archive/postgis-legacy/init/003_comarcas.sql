-- Comarcas table (administrative level between municipality and territory)
CREATE TABLE IF NOT EXISTS comarcas (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    comarca_code TEXT NOT NULL,
    name        TEXT NOT NULL,
    geom        GEOMETRY(MultiPolygon, 4326) NOT NULL,
    UNIQUE (tenant_id, comarca_code)
);

CREATE INDEX IF NOT EXISTS idx_comarcas_geom   ON comarcas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_comarcas_tenant ON comarcas (tenant_id);
