-- Sociodemographic enrichment tables: demographics, income, car ownership,
-- transit frequency.  All keyed by municipality code for join with
-- municipalities table.

-- ============================================================
-- Demographics (age groups per municipality)
-- ============================================================
CREATE TABLE IF NOT EXISTS municipality_demographics (
    id          BIGSERIAL PRIMARY KEY,
    muni_code   TEXT NOT NULL,
    year        INT NOT NULL,
    pop_total   INT NOT NULL DEFAULT 0,
    pop_0_17    INT NOT NULL DEFAULT 0,
    pop_18_25   INT NOT NULL DEFAULT 0,
    pop_26_64   INT NOT NULL DEFAULT 0,
    pop_65_plus INT NOT NULL DEFAULT 0,
    pct_0_17    REAL GENERATED ALWAYS AS (
        CASE WHEN pop_total > 0 THEN pop_0_17::REAL / pop_total * 100 ELSE 0 END
    ) STORED,
    pct_18_25   REAL GENERATED ALWAYS AS (
        CASE WHEN pop_total > 0 THEN pop_18_25::REAL / pop_total * 100 ELSE 0 END
    ) STORED,
    pct_65_plus REAL GENERATED ALWAYS AS (
        CASE WHEN pop_total > 0 THEN pop_65_plus::REAL / pop_total * 100 ELSE 0 END
    ) STORED,
    UNIQUE (muni_code, year)
);

CREATE INDEX idx_demographics_muni ON municipality_demographics (muni_code);

-- ============================================================
-- Income (per municipality)
-- ============================================================
CREATE TABLE IF NOT EXISTS municipality_income (
    id                      BIGSERIAL PRIMARY KEY,
    muni_code               TEXT NOT NULL,
    year                    INT NOT NULL,
    renta_personal_media    REAL,          -- EUR, mean personal income
    renta_disponible_media  REAL,          -- EUR, mean disposable income
    renta_index             REAL,          -- index vs CAE=100
    UNIQUE (muni_code, year)
);

CREATE INDEX idx_income_muni ON municipality_income (muni_code);

-- ============================================================
-- Car ownership (per municipality)
-- ============================================================
CREATE TABLE IF NOT EXISTS municipality_car_ownership (
    id                  BIGSERIAL PRIMARY KEY,
    muni_code           TEXT NOT NULL,
    year                INT NOT NULL,
    vehicles_per_inhab  REAL NOT NULL,    -- vehicles / inhabitant
    UNIQUE (muni_code, year)
);

CREATE INDEX idx_car_ownership_muni ON municipality_car_ownership (muni_code);

-- ============================================================
-- Transit frequency (departures per hour per stop)
-- ============================================================
CREATE TABLE IF NOT EXISTS stop_frequency (
    id                  BIGSERIAL PRIMARY KEY,
    operator            TEXT NOT NULL,
    stop_id             TEXT NOT NULL,
    stop_name           TEXT,
    time_window         TEXT NOT NULL DEFAULT '07:00-09:00',
    departures          INT NOT NULL DEFAULT 0,
    departures_per_hour REAL NOT NULL DEFAULT 0,
    geom                GEOMETRY(Point, 4326),
    UNIQUE (operator, stop_id, time_window)
);

CREATE INDEX idx_stop_freq_geom ON stop_frequency USING GIST (geom);
CREATE INDEX idx_stop_freq_operator ON stop_frequency (operator);
