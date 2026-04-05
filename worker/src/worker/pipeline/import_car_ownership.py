"""Import car ownership data per municipality from UDALMAP / Open Data Euskadi.

Source: UDALMAP indicator 102 -- vehicles per inhabitant per municipality.
Clean CSV: semicolon-delimited, decimal comma, 2003-2023.

URL: https://opendata.euskadi.eus/contenidos/estadistica/udalmap_indicador_102/es_def/adjuntos/indicator.csv

Output: municipality_car_ownership.parquet in the serving directory.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import structlog

logger = structlog.get_logger()

BIZKAIA_PREFIX = "48"

UDALMAP_URL = (
    "https://opendata.euskadi.eus/contenidos/estadistica/"
    "udalmap_indicador_102/es_def/adjuntos/indicator.csv"
)


def _parse_car_csv(content: str) -> dict[str, dict[int, float]]:
    """Parse UDALMAP car ownership CSV.

    Returns {muni_code: {year: vehicles_per_inhabitant}}.
    """
    lines = content.strip().splitlines()
    if not lines:
        return {}

    # Find header row -- must contain both a label AND year columns (4-digit numbers)
    header_idx = 0
    for i, line in enumerate(lines):
        parts = line.split(";")
        has_years = any(
            p.strip().strip('"').isdigit() and len(p.strip().strip('"')) == 4
            for p in parts
        )
        has_label = "Municipio" in line or "municipio" in line or "Codigo" in line
        if has_label and has_years:
            header_idx = i
            break

    header = lines[header_idx].split(";")
    year_cols: list[tuple[int, int]] = []
    for ci, col in enumerate(header):
        col = col.strip().strip('"')
        if col.isdigit() and len(col) == 4:
            year_cols.append((ci, int(col)))

    result: dict[str, dict[int, float]] = {}

    for line in lines[header_idx + 1 :]:
        parts = line.split(";")
        if len(parts) < 3:
            continue

        code = parts[0].strip().strip('"')
        if not code.startswith(BIZKAIA_PREFIX) or len(code) != 5:
            continue

        year_values: dict[int, float] = {}
        for ci, yr in year_cols:
            if ci < len(parts):
                val_str = parts[ci].strip().strip('"').replace(",", ".")
                if val_str and val_str not in ("..", "-", ""):
                    try:
                        year_values[yr] = float(val_str)
                    except ValueError:
                        pass

        if year_values:
            result[code] = year_values

    return result


def import_car_ownership(
    serving_dir: str | Path,
    csv_path: Path | None = None,
    *,
    download: bool = True,
) -> dict[str, object]:
    """Download and import UDALMAP car ownership data for Bizkaia.

    Args:
        serving_dir: Output directory for Parquet files.
        csv_path: Path to local CSV. If None and download=True, fetches from web.
        download: Whether to download if csv_path is None.

    Writes municipality_car_ownership.parquet.
    """
    serving = Path(serving_dir)
    log = logger.bind(source="udalmap_cars")

    if csv_path and csv_path.exists():
        content = csv_path.read_text(encoding="utf-8-sig")
    elif download:
        log.info("car_ownership_downloading")
        with httpx.Client(timeout=60) as client:
            resp = client.get(UDALMAP_URL)
            resp.raise_for_status()
            content = resp.text
    else:
        raise FileNotFoundError("No car ownership CSV and download disabled")

    parsed = _parse_car_csv(content)
    log.info("car_ownership_parsed", municipalities=len(parsed))

    if not parsed:
        return {"inserted": 0, "municipalities": 0, "years": []}

    # Build records
    all_years: set[int] = set()
    records: list[dict[str, object]] = []

    for muni_code, yr_vals in sorted(parsed.items()):
        for year, veh_per_inhab in sorted(yr_vals.items()):
            all_years.add(year)
            records.append({
                "muni_code": muni_code,
                "year": year,
                "vehicles_per_inhab": veh_per_inhab,
            })

    # Write Parquet
    inserted = len(records)
    if records:
        df = pd.DataFrame(records)
        out_path = serving / "municipality_car_ownership.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, index=False)

    log.info("car_ownership_imported", inserted=inserted)

    return {
        "inserted": inserted,
        "municipalities": len(parsed),
        "years": sorted(all_years),
    }
