# postgis-legacy (frozen)

This is the **pre-DuckDB** schema. It is no longer executed anywhere in the
running system.

In April 2026 the project migrated from PostGIS (Cloud SQL) to DuckDB +
Parquet on GCS to drop hosting cost from ~$30–50/mo to ~$5–15/mo. The backend
now reads Parquet files directly into an in-memory DuckDB at startup; no
relational database is ever started.

These files are kept only for historical reference of the original schema:

- `init/001_schema.sql` — original normalized PostGIS schema (tenants, modes,
  destinations, grid_cells, connectivity_scores, …)
- `init/002_seed_demo.sql` — demo seed
- `init/003..007_*.sql` — additive migrations applied during the PostGIS era

**Do not run these against any live database.** The current source of truth
for table contents is the worker pipeline (`worker/`), which writes Parquet
files to `data/serving/`. See `deployment.md` for the current data flow.
