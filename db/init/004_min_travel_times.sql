-- Minimum travel time from each cell to the nearest destination per mode/purpose.
-- Complements connectivity_scores with an intuitive "minutes to nearest" metric.

CREATE TABLE min_travel_times (
    id                      BIGSERIAL PRIMARY KEY,
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cell_id                 BIGINT NOT NULL REFERENCES grid_cells(id) ON DELETE CASCADE,
    mode                    TEXT NOT NULL,
    purpose                 TEXT NOT NULL,
    min_travel_time_minutes REAL NOT NULL,
    nearest_destination_id  BIGINT REFERENCES destinations(id) ON DELETE SET NULL,
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, cell_id, mode, purpose)
);

CREATE INDEX idx_min_travel_times_cell ON min_travel_times (tenant_id, cell_id, mode, purpose);
