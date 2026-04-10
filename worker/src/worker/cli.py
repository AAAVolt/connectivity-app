"""Bizkaia Connectivity data pipeline CLI.

All pipeline modules now read/write Parquet files instead of PostgreSQL.
"""

from pathlib import Path
from typing import Optional

import structlog
import typer

from worker.config import get_settings

logger = structlog.get_logger()

app = typer.Typer(
    name="bizkaia-worker",
    help="Bizkaia Connectivity data pipeline (Parquet-based).",
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
    cell_size: int = typer.Option(250, help="Grid cell size in metres"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Generate a 250 m grid over the tenant's boundary."""
    from worker.pipeline.grid import build_grid as _build_grid

    sd = str(serving_dir or get_settings().serving_dir)
    count = _build_grid(tenant, sd, cell_size_m=cell_size)
    typer.echo(f"Grid built: {count} cells created.")


@app.command()
def disaggregate_population(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    no_nucleos: bool = typer.Option(
        False, "--no-nucleos",
        help="Disable dasymetric masking",
    ),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Disaggregate population from source polygons to grid cells."""
    from worker.pipeline.population import disaggregate_population as _disaggregate

    sd = str(serving_dir or get_settings().serving_dir)
    stats = _disaggregate(tenant, sd, use_nucleos=not no_nucleos)
    mode = "dasymetric" if stats.get("dasymetric") else "areal weighting"
    typer.echo(f"Population disaggregated ({mode}):")
    typer.echo(f"  Source population:     {stats['source_population']:.0f}")
    typer.echo(f"  Allocated population:  {stats['allocated_population']:.0f}")
    typer.echo(f"  Cells with population: {stats['cells_with_population']}")
    typer.echo(f"  Total cells:           {stats['total_cells']}")
    if "loss_pct" in stats:
        typer.echo(f"  Loss:                  {stats['loss_pct']:.2f}%")


@app.command()
def export_r5r(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    output_dir: Path = typer.Option("/data/network", help="Output dir for R5R CSVs"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Export grid-cell origins and destinations as CSV for R5R routing."""
    from worker.pipeline.export_r5r import export_r5r_inputs

    sd = str(serving_dir or get_settings().serving_dir)
    stats = export_r5r_inputs(tenant, sd, output_dir)
    typer.echo(f"R5R inputs exported: {stats['origins']} origins, {stats['destinations']} destinations")


@app.command()
def import_travel_times(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    input_dir: Path = typer.Option("/data/output", help="Dir with R5R ttm_*.parquet"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import R5R Parquet travel-time matrices."""
    from worker.pipeline.travel_times import import_travel_times as _import

    sd = str(serving_dir or get_settings().serving_dir)
    stats = _import(tenant, sd, input_dir)
    typer.echo(f"Travel times imported: {stats['rows_imported']:,} rows")


@app.command()
def seed_demo(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    cell_size: int = typer.Option(250, help="Grid cell size in metres"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Seed with synthetic data for local development."""
    from worker.pipeline.grid import build_grid as _build_grid
    from worker.pipeline.population import disaggregate_population as _disaggregate
    from worker.pipeline.seed_demo import seed_destinations, seed_travel_times
    from worker.scoring.compute_scores import compute_scores as _compute

    sd = str(serving_dir or get_settings().serving_dir)

    typer.echo("Step 1/5: Building grid...")
    cell_count = _build_grid(tenant, sd, cell_size_m=cell_size)
    typer.echo(f"  -> {cell_count} cells created")

    typer.echo("Step 2/5: Disaggregating population...")
    pop_stats = _disaggregate(tenant, sd)
    typer.echo(f"  -> {pop_stats['cells_with_population']} cells with population")

    typer.echo("Step 3/5: Seeding destinations...")
    dest_count = seed_destinations(tenant, sd)
    typer.echo(f"  -> {dest_count} destinations created")

    typer.echo("Step 4/5: Generating travel times...")
    tt_counts = seed_travel_times(tenant, sd)
    typer.echo(f"  -> TRANSIT: {tt_counts['TRANSIT']} travel times")

    typer.echo("Step 5/5: Computing scores...")
    score_stats = _compute(tenant, sd)
    typer.echo(f"  -> {score_stats['scores_written']} connectivity scores")
    typer.echo(f"  -> {score_stats['combined_written']} combined scores")

    typer.echo("\nDemo data seeded successfully!")


@app.command()
def run_pipeline(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    cell_size: int = typer.Option(250, help="Grid cell size in metres"),
    r5r_output: Path = typer.Option("/data/output", help="Dir with R5R ttm_*.parquet"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Run the full pipeline: grid -> population -> travel times -> scores."""
    from worker.pipeline.grid import build_grid as _build_grid
    from worker.pipeline.population import disaggregate_population as _disaggregate
    from worker.pipeline.travel_times import import_travel_times as _import_tt
    from worker.scoring.compute_scores import compute_scores as _compute

    sd = str(serving_dir or get_settings().serving_dir)

    typer.echo(f"Step 1/4: Building {cell_size}m grid...")
    cell_count = _build_grid(tenant, sd, cell_size_m=cell_size)
    typer.echo(f"  -> {cell_count} cells created")

    typer.echo("Step 2/4: Disaggregating population...")
    pop_stats = _disaggregate(tenant, sd)
    typer.echo(f"  -> {pop_stats['cells_with_population']} cells with population")

    typer.echo("Step 3/4: Importing R5R travel times...")
    tt_stats = _import_tt(tenant, sd, r5r_output)
    typer.echo(f"  -> {tt_stats['rows_imported']:,} rows imported")

    typer.echo("Step 4/4: Computing scores...")
    score_stats = _compute(tenant, sd)
    typer.echo(f"  -> {score_stats['scores_written']:,} connectivity scores")
    typer.echo(f"  -> {score_stats['combined_written']:,} combined scores")

    typer.echo("\nPipeline complete!")


@app.command()
def compute_scores(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    config_path: Optional[Path] = typer.Option(None, help="Path to scoring YAML"),
    departure_time: Optional[str] = typer.Option(None, help="Single departure time (HH:MM)"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Compute connectivity and combined scores for all grid cells."""
    from worker.scoring.compute_scores import compute_scores as _compute
    from worker.scoring.config import load_scoring_config

    sd = str(serving_dir or get_settings().serving_dir)
    scoring_config = load_scoring_config(config_path) if config_path else None
    stats = _compute(tenant, sd, config=scoring_config, departure_time=departure_time)
    typer.echo(f"Scores computed: {stats['scores_written']} connectivity, {stats['combined_written']} combined")


@app.command()
def import_pois(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    pois_dir: Path = typer.Option("/data/pois", help="Dir with POI CSV files"),
    clear_existing: bool = typer.Option(False, "--clear-existing", help="Delete existing destinations per type before inserting"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import custom POIs from CSV files."""
    from worker.pipeline.import_pois import import_pois_from_csv

    sd = str(serving_dir or get_settings().serving_dir)
    results = import_pois_from_csv(tenant, sd, pois_dir, clear_existing=clear_existing)
    if not results:
        typer.echo("No CSV files found in " + str(pois_dir))
        return
    total = sum(results.values())
    typer.echo(f"POIs imported: {total} destinations")


@app.command()
def import_population(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    shp_path: Path = typer.Option(
        "/data/raw/secciones/SECCIONES_EUSTAT_5000_ETRS89.shp",
        help="EUSTAT secciones shapefile",
    ),
    csv_path: Path = typer.Option(
        "/data/raw/population/bizkaia_population_sections.csv",
        help="EUSTAT population CSV",
    ),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import EUSTAT census sections as population sources."""
    from worker.pipeline.import_population import import_secciones

    sd = str(serving_dir or get_settings().serving_dir)
    stats = import_secciones(tenant, sd, shp_path, csv_path)
    typer.echo(f"Population imported: {stats['matched']} sections, {stats['csv_total_population']:,.0f} people")


@app.command()
def import_nucleos(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    shp_path: Path = typer.Option(
        "/data/raw/nucleos/NUCLEOS_EUSTAT_5000_ETRS89.shp",
        help="EUSTAT nucleos shapefile",
    ),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import EUSTAT nucleo polygons for dasymetric masking."""
    from worker.pipeline.import_nucleos import import_nucleos as _import

    sd = str(serving_dir or get_settings().serving_dir)
    stats = _import(tenant, sd, shp_path)
    typer.echo(f"Nucleos imported: {stats['total']} ({stats['nucleos']} nucleos, {stats['diseminados']} diseminados)")


@app.command()
def import_geoeuskadi(
    tenant: str = typer.Option(DEMO_TENANT_ID, help="Tenant ID"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import real Bizkaia data from GeoEuskadi ArcGIS REST services."""
    from worker.pipeline.geoeuskadi import (
        import_bizkaia_boundary,
        import_comarcas,
        import_municipalities,
        seed_tenants_and_modes,
    )

    sd = str(serving_dir or get_settings().serving_dir)

    typer.echo("Seeding tenants, modes, and destination types...")
    seed_tenants_and_modes(sd)

    typer.echo("Importing Bizkaia boundary...")
    import_bizkaia_boundary(tenant, sd)
    typer.echo("  -> boundary imported")

    typer.echo("Importing municipalities...")
    n = import_municipalities(tenant, sd)
    typer.echo(f"  -> {n} municipalities")

    typer.echo("Importing comarcas...")
    n = import_comarcas(tenant, sd)
    typer.echo(f"  -> {n} comarcas")

    typer.echo("\nGeoEuskadi import complete!")


@app.command()
def download_gtfs(
    output_dir: Path = typer.Option("/data/gtfs", help="Output dir for GTFS zips"),
) -> None:
    """Download GTFS feeds for all Bizkaia transit operators."""
    from worker.pipeline.gtfs_download import download_gtfs_feeds

    typer.echo(f"Downloading GTFS feeds to {output_dir}...")
    results = download_gtfs_feeds(output_dir)
    for operator, status in results.items():
        typer.echo(f"  {operator}: {status}")


@app.command()
def import_gtfs_shapes(
    gtfs_dir: Path = typer.Option("/data/gtfs", help="Dir with .gtfs.zip files"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import route shapes and stops from GTFS feeds."""
    from worker.pipeline.gtfs_import import import_gtfs_to_db

    sd = str(serving_dir or get_settings().serving_dir)
    results = import_gtfs_to_db(sd, gtfs_dir)
    for operator, stats in results.items():
        typer.echo(f"  {operator}: {stats.get('routes', 0)} routes, {stats.get('stops', 0)} stops")


@app.command()
def import_demographics(
    csv_path: Optional[Path] = typer.Option(None, help="EUSTAT demographics CSV"),
    year: int = typer.Option(2025, help="Reference year"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import age-group demographics per municipality."""
    from worker.pipeline.import_demographics import import_demographics_from_csv

    sd = str(serving_dir or get_settings().serving_dir)
    stats = import_demographics_from_csv(sd, csv_path=csv_path, year=year)
    typer.echo(f"Demographics imported: {stats['municipalities']} municipalities")


@app.command()
def import_income(
    csv_dir: Optional[Path] = typer.Option(None, help="Dir with income CSVs"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import income data per municipality from UDALMAP."""
    from worker.pipeline.import_income import import_income as _import

    sd = str(serving_dir or get_settings().serving_dir)
    stats = _import(sd, csv_dir=csv_dir)
    typer.echo(f"Income imported: {stats['inserted']} records")


@app.command()
def import_car_ownership(
    csv_path: Optional[Path] = typer.Option(None, help="UDALMAP car ownership CSV"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Import car ownership per municipality from UDALMAP."""
    from worker.pipeline.import_car_ownership import import_car_ownership as _import

    sd = str(serving_dir or get_settings().serving_dir)
    stats = _import(sd, csv_path=csv_path)
    typer.echo(f"Car ownership imported: {stats['inserted']} records")


@app.command()
def compute_frequency(
    gtfs_dir: Path = typer.Option("/data/gtfs", help="Dir with .gtfs.zip files"),
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
) -> None:
    """Compute transit frequency per stop from GTFS data."""
    from worker.pipeline.compute_frequency import compute_transit_frequency

    sd = str(serving_dir or get_settings().serving_dir)
    stats = compute_transit_frequency(sd, gtfs_dir)
    typer.echo(f"Frequency computed: {stats['total_records']} records")


@app.command()
def upload_gcs(
    serving_dir: Path = typer.Option(None, help="Serving data directory"),
    bucket: str = typer.Option(None, help="GCS bucket name"),
    prefix: str = typer.Option("serving", help="GCS prefix"),
) -> None:
    """Upload serving Parquet files to Google Cloud Storage."""
    from worker.pipeline.export_gcs import upload_serving_to_gcs

    settings = get_settings()
    sd = str(serving_dir or settings.serving_dir)
    bkt = bucket or settings.gcs_bucket
    results = upload_serving_to_gcs(sd, bkt, prefix)
    for filename, status in results.items():
        typer.echo(f"  {filename}: {status}")
    typer.echo("\nUpload complete!")


if __name__ == "__main__":
    app()
