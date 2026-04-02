"""Bizkaia Connectivity data pipeline CLI."""

from pathlib import Path
from typing import Optional

import structlog
import typer

from worker.db import get_session

logger = structlog.get_logger()

app = typer.Typer(
    name="bizkaia-worker",
    help="Bizkaia Connectivity data pipeline.",
)

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@app.command()
def hello(
    name: str = typer.Option("world", help="Name to greet"),
) -> None:
    """Say hello – verifies the CLI works."""
    logger.info("hello_command", name=name)
    typer.echo(f"Hello, {name}! The worker pipeline is ready.")


@app.command()
def build_grid(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    cell_size: int = typer.Option(100, help="Grid cell size in metres"),
) -> None:
    """Generate a 100 m grid over the tenant's boundary."""
    from worker.pipeline.grid import build_grid as _build_grid

    session = get_session()
    try:
        count = _build_grid(session, tenant, cell_size_m=cell_size)
        typer.echo(f"Grid built: {count} cells created.")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def disaggregate_population(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    no_nucleos: bool = typer.Option(
        False, "--no-nucleos",
        help="Disable dasymetric masking (spread population uniformly, ignoring núcleos)",
    ),
) -> None:
    """Disaggregate population from source polygons to grid cells.

    By default uses núcleo polygons (if imported) as a dasymetric mask:
    only cells overlapping concentrated settlements receive population.
    Pass --no-nucleos to fall back to plain areal weighting.
    """
    from worker.pipeline.population import disaggregate_population as _disaggregate

    session = get_session()
    try:
        stats = _disaggregate(session, tenant, use_nucleos=not no_nucleos)
        mode = "dasymetric (núcleos)" if stats.get("dasymetric") else "areal weighting"
        typer.echo(f"Population disaggregated ({mode}):")
        typer.echo(f"  Source population:     {stats['source_population']:.0f}")
        typer.echo(f"  Allocated population:  {stats['allocated_population']:.0f}")
        typer.echo(f"  Cells with population: {stats['cells_with_population']}")
        typer.echo(f"  Total cells:           {stats['total_cells']}")
        if "loss_pct" in stats:
            typer.echo(f"  Loss:                  {stats['loss_pct']:.2f}%")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def export_r5r(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    output_dir: Path = typer.Option(
        "/data/network", help="Output directory for origins.csv and destinations.csv"
    ),
) -> None:
    """Export grid-cell origins and destinations as CSV for R5R routing.

    Run this after build-grid and import-geoeuskadi, before running
    the R5R Docker container.
    """
    from worker.pipeline.export_r5r import export_r5r_inputs

    session = get_session()
    try:
        stats = export_r5r_inputs(session, tenant, output_dir)
        typer.echo("R5R inputs exported:")
        typer.echo(f"  Origins:      {stats['origins']}")
        typer.echo(f"  Destinations: {stats['destinations']}")
        typer.echo(f"  Output dir:   {output_dir}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def import_travel_times(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    input_dir: Path = typer.Option(
        "/data/output", help="Directory containing R5R ttm_*.parquet files"
    ),
) -> None:
    """Import R5R Parquet travel-time matrices into the database.

    Reads ttm_*.parquet files produced by the R5R container.
    Mode is inferred from filename (e.g. ttm_transit.parquet → TRANSIT).
    """
    from worker.pipeline.travel_times import import_travel_times as _import

    session = get_session()
    try:
        stats = _import(session, tenant, input_dir)
        typer.echo("Travel times imported:")
        typer.echo(f"  Files processed: {stats['files_processed']}")
        typer.echo(f"  Rows imported:   {stats['rows_imported']}")
        typer.echo(f"  Rows skipped:    {stats['rows_skipped']}")
        mode_counts = stats.get("mode_counts", {})
        for mode, count in sorted(mode_counts.items()):
            typer.echo(f"  {mode}: {count:,} rows")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def seed_demo(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    cell_size: int = typer.Option(100, help="Grid cell size in metres"),
) -> None:
    """Seed the database with synthetic data for local development.

    Runs the full pipeline: grid → population → destinations →
    travel times → scores, using synthetic destinations and
    distance-based travel times (no OSM/GTFS/R5R required).
    """
    from worker.pipeline.grid import build_grid as _build_grid
    from worker.pipeline.population import disaggregate_population as _disaggregate
    from worker.pipeline.seed_demo import seed_destinations, seed_travel_times
    from worker.scoring.compute_scores import compute_scores as _compute

    session = get_session()
    try:
        typer.echo("Step 1/5: Building grid...")
        cell_count = _build_grid(session, tenant, cell_size_m=cell_size)
        typer.echo(f"  → {cell_count} cells created")

        typer.echo("Step 2/5: Disaggregating population...")
        pop_stats = _disaggregate(session, tenant)
        typer.echo(f"  → {pop_stats['cells_with_population']} cells with population")

        typer.echo("Step 3/5: Seeding destinations...")
        dest_count = seed_destinations(session, tenant)
        typer.echo(f"  → {dest_count} destinations created")

        typer.echo("Step 4/5: Generating travel times...")
        tt_counts = seed_travel_times(session, tenant)
        typer.echo(f"  → WALK: {tt_counts['WALK']}, TRANSIT: {tt_counts['TRANSIT']}")

        typer.echo("Step 5/5: Computing scores...")
        score_stats = _compute(session, tenant)
        typer.echo(f"  → {score_stats['scores_written']} connectivity scores")
        typer.echo(f"  → {score_stats['combined_written']} combined scores")

        typer.echo("\nDemo data seeded successfully!")
        typer.echo("Start the backend and frontend to explore the data.")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def run_pipeline(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    cell_size: int = typer.Option(100, help="Grid cell size in metres"),
    r5r_output: Path = typer.Option(
        "/data/output", help="Directory with R5R ttm_*.parquet files"
    ),
) -> None:
    """Run the full pipeline using R5R-routed travel times.

    Steps:
      1. Build grid
      2. Disaggregate population
      3. Import R5R travel-time matrices (parquet)
      4. Compute scores

    Prerequisites:
      - Boundary + destinations imported (run import-geoeuskadi first)
      - R5R travel times computed (run export-r5r, then the R5R container)
    """
    from worker.pipeline.grid import build_grid as _build_grid
    from worker.pipeline.population import disaggregate_population as _disaggregate
    from worker.pipeline.travel_times import import_travel_times as _import_tt
    from worker.scoring.compute_scores import compute_scores as _compute

    session = get_session()
    try:
        typer.echo(f"Step 1/4: Building {cell_size}m grid over boundary...")
        cell_count = _build_grid(session, tenant, cell_size_m=cell_size)
        typer.echo(f"  → {cell_count} cells created")

        typer.echo("Step 2/4: Disaggregating population...")
        pop_stats = _disaggregate(session, tenant)
        typer.echo(f"  → {pop_stats['cells_with_population']} cells with population")

        typer.echo("Step 3/4: Importing R5R travel times...")
        tt_stats = _import_tt(session, tenant, r5r_output)
        typer.echo(f"  → {tt_stats['rows_imported']:,} travel time rows imported")
        for mode, count in sorted(tt_stats.get("mode_counts", {}).items()):
            typer.echo(f"     {mode}: {count:,}")

        typer.echo("Step 4/4: Computing scores...")
        score_stats = _compute(session, tenant)
        typer.echo(f"  → {score_stats['scores_written']:,} connectivity scores")
        typer.echo(f"  → {score_stats['combined_written']:,} combined scores")

        typer.echo("\nPipeline complete!")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def compute_scores(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    config_path: Optional[Path] = typer.Option(
        None, help="Path to scoring YAML config (default: worker/config/scoring.yaml)"
    ),
    departure_time: Optional[str] = typer.Option(
        None,
        help="Compute for a single departure time slot (HH:MM). "
        "If omitted, computes for all slots found in travel_times.",
    ),
) -> None:
    """Compute connectivity and combined scores for all grid cells.

    By default computes scores for every departure_time slot present in
    the travel_times table.  Pass --departure-time to process a single slot.
    """
    from worker.scoring.compute_scores import compute_scores as _compute
    from worker.scoring.config import load_scoring_config

    scoring_config = load_scoring_config(config_path) if config_path else None
    session = get_session()
    try:
        stats = _compute(
            session, tenant, config=scoring_config, departure_time=departure_time
        )
        typer.echo("Scores computed:")
        typer.echo(f"  Connectivity scores: {stats['scores_written']}")
        typer.echo(f"  Combined scores:     {stats['combined_written']}")
        dep_times = stats.get("departure_times", [])
        typer.echo(f"  Departure slots:     {len(dep_times)}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def import_pois(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    pois_dir: Path = typer.Option(
        "/data/pois", help="Directory containing POI CSV files"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Delete existing destinations for each type before importing"
    ),
) -> None:
    """Import custom POIs from CSV files in data/pois/.

    Each CSV file becomes a destination type (filename = type code).
    Required columns: name, lon, lat. Optional: weight (default 1.0).
    """
    from worker.pipeline.import_pois import import_pois_from_csv

    session = get_session()
    try:
        results = import_pois_from_csv(
            session, tenant, pois_dir, clear_existing=clear
        )
        if not results:
            typer.echo("No CSV files found in " + str(pois_dir))
            return
        typer.echo("POI import results:")
        total = 0
        for type_code, count in sorted(results.items()):
            typer.echo(f"  {type_code}: {count} destinations")
            total += count
        typer.echo(f"  Total: {total} destinations imported")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def import_population(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    shp_path: Path = typer.Option(
        "/data/raw/secciones/SECCIONES_EUSTAT_5000_ETRS89.shp",
        help="Path to EUSTAT secciones shapefile (.shp)",
    ),
    csv_path: Path = typer.Option(
        "/data/raw/population/bizkaia_population_sections.csv",
        help="Path to EUSTAT population CSV",
    ),
    no_clear: bool = typer.Option(
        False, "--no-clear", help="Keep existing population sources"
    ),
) -> None:
    """Import EUSTAT census sections as population sources.

    Reads the secciones censales shapefile and population CSV, joins
    them by section code, and inserts into population_sources.
    Then runs disaggregation to distribute to grid cells.
    """
    from worker.pipeline.import_population import import_secciones

    session = get_session()
    try:
        typer.echo("Importing census sections...")
        stats = import_secciones(
            session, tenant, shp_path, csv_path,
            clear_existing=not no_clear,
        )
        typer.echo(f"  CSV sections:     {stats['csv_sections']}")
        typer.echo(f"  SHP sections:     {stats['shp_sections']}")
        typer.echo(f"  Matched:          {stats['matched']}")
        typer.echo(f"  Unmatched CSV:    {stats['unmatched_csv']}")
        typer.echo(f"  CSV population:   {stats['csv_total_population']:,.0f}")
        typer.echo(f"  DB population:    {stats['db_total_population']:,.0f}")
        typer.echo(f"  Loss:             {stats['loss_pct']:.4f}%")

        if stats["loss_pct"] > 0.1:
            typer.echo(
                "WARNING: Population loss exceeds 0.1%!",
                err=True,
            )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def import_nucleos(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    shp_path: Path = typer.Option(
        "/data/raw/nucleos/NUCLEOS_EUSTAT_5000_ETRS89.shp",
        help="Path to EUSTAT nucleos shapefile (.shp)",
    ),
    no_clear: bool = typer.Option(
        False, "--no-clear", help="Keep existing nucleos"
    ),
) -> None:
    """Import EUSTAT núcleo polygons for dasymetric population masking.

    Filters to Bizkaia and stores both núcleos (concentrated settlements)
    and diseminados (dispersed).  During disaggregate-population, only
    cells overlapping núcleos (not diseminados) receive population.
    """
    from worker.pipeline.import_nucleos import import_nucleos as _import

    session = get_session()
    try:
        typer.echo("Importing núcleos...")
        stats = _import(
            session, tenant, shp_path,
            clear_existing=not no_clear,
        )
        typer.echo(f"  Total:       {stats['total']}")
        typer.echo(f"  Núcleos:     {stats['nucleos']}")
        typer.echo(f"  Diseminados: {stats['diseminados']}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def import_geoeuskadi(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
) -> None:
    """Import real Bizkaia data from GeoEuskadi ArcGIS REST services.

    Downloads and imports:
      - Bizkaia territory boundary
      - 114 municipality boundaries
      - Schools, health centres, supermarkets, employment zones
    """
    from worker.pipeline.geoeuskadi import (
        import_bizkaia_boundary,
        import_comarcas,
        import_health,
        import_jobs,
        import_municipalities,
        import_schools,
        import_supermarkets,
    )

    session = get_session()
    try:
        typer.echo("Importing Bizkaia boundary...")
        import_bizkaia_boundary(session, tenant)
        typer.echo("  → Bizkaia boundary imported")

        typer.echo("Importing municipalities...")
        n = import_municipalities(session, tenant)
        typer.echo(f"  → {n} municipalities imported")

        typer.echo("Importing comarcas...")
        n = import_comarcas(session, tenant)
        typer.echo(f"  → {n} comarcas imported")

        typer.echo("Importing schools...")
        n = import_schools(session, tenant)
        typer.echo(f"  → {n} schools imported")

        typer.echo("Importing health centres & pharmacies...")
        n = import_health(session, tenant)
        typer.echo(f"  → {n} health facilities imported")

        typer.echo("Importing supermarkets...")
        n = import_supermarkets(session, tenant)
        typer.echo(f"  → {n} supermarkets imported")

        typer.echo("Importing employment zones...")
        n = import_jobs(session, tenant)
        typer.echo(f"  → {n} employment zones imported")

        typer.echo("\nGeoEuskadi import complete!")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@app.command()
def download_gtfs(
    output_dir: Path = typer.Option(
        "/data/gtfs", help="Output directory for GTFS zip files"
    ),
) -> None:
    """Download GTFS feeds for all Bizkaia transit operators.

    Downloads from Moveuskadi (geo.euskadi.eus), updated daily.
    Operators: Bizkaibus, Bilbobus, MetroBilbao, Euskotren,
    Renfe_Cercanias, La_Union, FunicularArtxanda, Transbordador_Vizcaya.
    """
    from worker.pipeline.gtfs_download import download_gtfs_feeds

    typer.echo(f"Downloading GTFS feeds to {output_dir}...")
    results = download_gtfs_feeds(output_dir)
    for operator, status in results.items():
        typer.echo(f"  {operator}: {status}")
    typer.echo("\nGTFS download complete!")
    typer.echo("Place these files in /data/network/ for R5R routing.")


@app.command()
def import_gtfs_shapes(
    gtfs_dir: Path = typer.Option(
        "/data/gtfs", help="Directory containing .gtfs.zip files"
    ),
) -> None:
    """Import route shapes and stops from downloaded GTFS feeds into the DB.

    Parses shapes.txt, routes.txt, trips.txt, and stops.txt from each
    operator's GTFS zip and writes them as PostGIS geometries.
    """
    from worker.pipeline.gtfs_import import import_gtfs_to_db

    session = get_session()
    try:
        results = import_gtfs_to_db(session, gtfs_dir)
        typer.echo("GTFS import results:")
        for operator, stats in results.items():
            typer.echo(f"  {operator}: {stats.get('routes', 0)} routes, {stats.get('stops', 0)} stops")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


if __name__ == "__main__":
    app()
