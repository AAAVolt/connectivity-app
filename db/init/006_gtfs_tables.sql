-- GTFS route shapes and stops for transit network visualisation.
-- Populated by the worker import-gtfs-shapes command.

CREATE TABLE IF NOT EXISTS gtfs_routes (
    id          BIGSERIAL PRIMARY KEY,
    operator    TEXT NOT NULL,
    route_id    TEXT NOT NULL,
    route_name  TEXT,
    route_type  INT NOT NULL DEFAULT 3,
    route_color TEXT,
    geom        GEOMETRY(MultiLineString, 4326),
    UNIQUE (operator, route_id)
);

CREATE INDEX IF NOT EXISTS idx_gtfs_routes_geom ON gtfs_routes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_gtfs_routes_operator ON gtfs_routes (operator);

CREATE TABLE IF NOT EXISTS gtfs_stops (
    id          BIGSERIAL PRIMARY KEY,
    operator    TEXT NOT NULL,
    stop_id     TEXT NOT NULL,
    stop_name   TEXT,
    geom        GEOMETRY(Point, 4326) NOT NULL,
    UNIQUE (operator, stop_id)
);

CREATE INDEX IF NOT EXISTS idx_gtfs_stops_geom ON gtfs_stops USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_gtfs_stops_operator ON gtfs_stops (operator);
