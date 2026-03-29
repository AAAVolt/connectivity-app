-- Add departure_time (time-of-day) dimension to all score/travel-time tables.
-- Stores "HH:MM" strings (e.g. "08:00", "23:30") — day-agnostic.
-- Existing rows default to '08:00' (the original AM-peak window).

-- ── travel_times ──
ALTER TABLE travel_times
    ADD COLUMN IF NOT EXISTS departure_time TEXT NOT NULL DEFAULT '08:00';

ALTER TABLE travel_times
    DROP CONSTRAINT IF EXISTS travel_times_tenant_id_origin_cell_id_destination_id_mode_key;

ALTER TABLE travel_times
    ADD CONSTRAINT travel_times_tenant_origin_dest_mode_deptime_key
        UNIQUE (tenant_id, origin_cell_id, destination_id, mode, departure_time);

-- ── connectivity_scores ──
ALTER TABLE connectivity_scores
    ADD COLUMN IF NOT EXISTS departure_time TEXT NOT NULL DEFAULT '08:00';

ALTER TABLE connectivity_scores
    DROP CONSTRAINT IF EXISTS connectivity_scores_tenant_id_cell_id_mode_purpose_key;

ALTER TABLE connectivity_scores
    ADD CONSTRAINT connectivity_scores_tenant_cell_mode_purpose_deptime_key
        UNIQUE (tenant_id, cell_id, mode, purpose, departure_time);

-- ── combined_scores ──
ALTER TABLE combined_scores
    ADD COLUMN IF NOT EXISTS departure_time TEXT NOT NULL DEFAULT '08:00';

ALTER TABLE combined_scores
    DROP CONSTRAINT IF EXISTS combined_scores_tenant_id_cell_id_key;

ALTER TABLE combined_scores
    ADD CONSTRAINT combined_scores_tenant_cell_deptime_key
        UNIQUE (tenant_id, cell_id, departure_time);

-- ── min_travel_times ──
ALTER TABLE min_travel_times
    ADD COLUMN IF NOT EXISTS departure_time TEXT NOT NULL DEFAULT '08:00';

ALTER TABLE min_travel_times
    DROP CONSTRAINT IF EXISTS min_travel_times_tenant_id_cell_id_mode_purpose_key;

ALTER TABLE min_travel_times
    ADD CONSTRAINT min_travel_times_tenant_cell_mode_purpose_deptime_key
        UNIQUE (tenant_id, cell_id, mode, purpose, departure_time);

-- Update indexes for queries that filter by departure_time
CREATE INDEX IF NOT EXISTS idx_scores_deptime
    ON connectivity_scores (tenant_id, mode, purpose, departure_time);

CREATE INDEX IF NOT EXISTS idx_combined_deptime
    ON combined_scores (tenant_id, departure_time);

CREATE INDEX IF NOT EXISTS idx_min_tt_deptime
    ON min_travel_times (tenant_id, cell_id, mode, purpose, departure_time);

CREATE INDEX IF NOT EXISTS idx_travel_times_deptime
    ON travel_times (tenant_id, origin_cell_id, mode, departure_time);
