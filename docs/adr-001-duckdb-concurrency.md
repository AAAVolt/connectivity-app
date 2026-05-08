# ADR-001 — DuckDB concurrency model

**Status:** Accepted (deferred). Re-evaluate when load testing shows contention.
**Date:** 2026-05-08
**Context:** Wave 4 follow-up to the audit recommendation in `docs/runbook.md`.

## Decision

We keep the current single-connection + `threading.Lock` model in `backend/src/backend/db.py` instead of introducing a connection pool.

API endpoints in `cells.py` are now `async def` and dispatch DuckDB queries via `fastapi.concurrency.run_in_threadpool`. Other routers (dashboard, boundaries, …) remain sync `def`; FastAPI runs them in anyio's threadpool, which is fine.

The lock serialises all queries through a single connection. We accept this until measured load shows it actually hurts.

## What we considered

### Option A — Status quo (chosen)

```python
_conn = duckdb.connect()      # one in-memory DB
_conn_lock = threading.Lock()  # serialises every query
```

- Simple, well-tested, already shipping.
- DuckDB Python connections are thread-safe but **serialise** — multiple threads sharing one connection don't run queries in parallel.
- Throughput ≈ `1 / mean_query_latency`. With p95 ≈ 200 ms and p50 ≈ 30 ms, single-instance throughput sits at ~30 QPS sustained.
- Cloud Run scales to 5 instances, so headroom is ~150 QPS before any contention shows up at the lock layer.

### Option B — Cursor-per-request (rejected)

```python
def execute(self, sql, params):
    cur = self._conn.cursor()  # one cursor per request, no lock
    cur.execute(sql, params)
    ...
```

The DuckDB Python docs are explicit: connections are thread-safe by **serialising** internally; cursors of the same connection do **not** unlock parallel reads. Removing the lock just moves the serialisation one layer deeper. No throughput gain. Worse, removing the lock would also remove the protection around the `_conn` variable replacement in `init_db()` / `reload_db()`, which would race with in-flight requests.

### Option C — File-backed read pool (deferred)

```python
# At init: write the in-memory DB to a parquet-backed file
_db_path = Path(tempfile.mkdtemp()) / "bizkaia.duckdb"
_master_conn = duckdb.connect(_db_path)
# ... load all parquet …
_master_conn.close()

# Per request: open a fresh read-only connection, no lock
def get_db():
    yield duckdb.connect(_db_path, read_only=True)
```

Multiple connections to the same file in **read-only** mode genuinely run queries in parallel. This is the only option that actually scales single-instance concurrency.

Costs:

1. **Disk I/O on cold start.** Every Cloud Run instance has to materialise the in-memory DB to disk before serving. We already pay this for parquet download from GCS; adding a write-to-disk step roughly doubles cold-start time.
2. **`/admin/reload` becomes harder.** The reload pattern today re-creates `_conn` while the lock is held. With N read-only connections in flight, you have to drain them, swap the file, then re-open. Either we tolerate stale reads during reload, or we coordinate with a barrier.
3. **Schema-contract validation runs on the master connection only.** Currently the lock guarantees no read sees a half-loaded table; with a pool we have to guarantee `init_db()` finishes before any pool connection is opened (an init-flag suffices but adds state).

### Option D — Multiple in-memory connections (rejected)

You can't share an in-memory DuckDB across connections. Each call to `duckdb.connect(":memory:")` produces an isolated database. Only file-backed DBs can be shared. So this collapses into Option C.

## When to revisit

Trigger one of these and re-open this ADR:

- Cloud Run metrics show **`request_latencies` p95 > 1 s** sustained and the slow requests are dominated by DB time (not network/JSON serialisation).
- **`instance_count` > 4 for >10 min** while CPU per instance is < 50%. That pattern means we're scaling out to dodge lock contention rather than to handle CPU work.
- A load-test rig (`make loadtest`, hypothetical) shows the lock is the binding constraint at the QPS we want to support.

If any of these fire, implement Option C. The cells.py endpoints are already `async def` with `run_in_threadpool`, so the migration is mostly contained to `db.py` (init_db, reload_db, close_db, get_db) and a `_DB_READY` event that reload coordinates against.

## Cross-references

- Wave 2 audit (item 9): "Async-ify backend endpoints" — partly executed, this ADR captures why we stopped where we did.
- `backend/src/backend/db.py:`90 — `DuckDBSession` and the lock.
- `backend/src/backend/api/cells.py:` — already async-ready.
- `docs/runbook.md` §4 — what to watch.
