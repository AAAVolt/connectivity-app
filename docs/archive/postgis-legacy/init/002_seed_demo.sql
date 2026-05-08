-- Seed data for local development
-- ============================================================

-- Transport modes (global lookup)
INSERT INTO modes (code, label) VALUES
    ('TRANSIT', 'Public Transport')
ON CONFLICT (code) DO NOTHING;

-- Destination / purpose types (from all_pois.csv POI categories)
INSERT INTO destination_types (code, label, description) VALUES
    ('aeropuerto',       'Aeropuerto',       'Airports'),
    ('bachiller',        'Bachiller',        'Secondary / vocational schools (BHI)'),
    ('centro_educativo', 'Centro Educativo', 'Education centres'),
    ('centro_urbano',    'Centro Urbano',    'Urban centres'),
    ('consulta_general', 'Consulta General', 'GP / general health consultations'),
    ('hacienda',         'Hacienda',         'Government tax / finance offices'),
    ('hospital',         'Hospital',         'Hospitals'),
    ('osakidetza',       'Osakidetza',       'Osakidetza health service locations'),
    ('residencia',       'Residencia',       'Residential care facilities'),
    ('universidad',      'Universidad',      'Universities')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- Demo tenant
-- ============================================================
INSERT INTO tenants (id, name, slug, config)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Bizkaia Demo',
    'bizkaia-demo',
    '{"region": "bizkaia", "crs_projected": 25830}'::jsonb
) ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- Demo boundary: ~5 km × 5 km around central Bilbao
-- For development/testing only. Replace with real Bizkaia boundary
-- from official data (Eustat, INE, or OpenStreetMap extract).
-- ============================================================
INSERT INTO boundaries (tenant_id, name, boundary_type, geom)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Bilbao Demo Area',
    'region',
    ST_Multi(ST_SetSRID(ST_GeomFromText(
        'POLYGON((-2.97 43.24, -2.97 43.29, -2.90 43.29, -2.90 43.24, -2.97 43.24))'
    ), 4326))
);

-- ============================================================
-- Sample population sources (placeholder núcleos around Bilbao)
-- These represent small areas with known population figures.
-- Real data would come from INE census or Eustat population grid.
-- ============================================================
INSERT INTO population_sources (tenant_id, name, population, geom) VALUES
(
    '00000000-0000-0000-0000-000000000001',
    'Casco Viejo',
    12000,
    ST_Multi(ST_SetSRID(ST_GeomFromText(
        'POLYGON((-2.925 43.258, -2.925 43.263, -2.918 43.263, -2.918 43.258, -2.925 43.258))'
    ), 4326))
),
(
    '00000000-0000-0000-0000-000000000001',
    'Abando',
    25000,
    ST_Multi(ST_SetSRID(ST_GeomFromText(
        'POLYGON((-2.945 43.260, -2.945 43.268, -2.930 43.268, -2.930 43.260, -2.945 43.260))'
    ), 4326))
),
(
    '00000000-0000-0000-0000-000000000001',
    'Deusto',
    18000,
    ST_Multi(ST_SetSRID(ST_GeomFromText(
        'POLYGON((-2.960 43.270, -2.960 43.280, -2.940 43.280, -2.940 43.270, -2.960 43.270))'
    ), 4326))
);
