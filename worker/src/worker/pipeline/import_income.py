"""Import income data per municipality from UDALMAP / Open Data Euskadi.

Primary source: UDALMAP indicator 167 (renta personal disponible, index CAE=100)
Secondary: UDALMAP indicators 184/185 (mean personal income by sex, EUR)

These are clean CSVs with municipality rows and year columns.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()

BIZKAIA_PREFIX = "48"

# UDALMAP indicator URLs
INDICATORS = {
    "renta_index": {
        "url": "https://opendata.euskadi.eus/contenidos/estadistica/udalmap_indicador_167/es_def/adjuntos/indicator.csv",
        "field": "renta_index",
    },
    "renta_personal_total": {
        "url": "https://opendata.euskadi.eus/contenidos/estadistica/udalmap_indicador_185/es_def/adjuntos/indicator.csv",
        "field": "renta_personal_media",
    },
    "renta_disponible": {
        "url": "https://opendata.euskadi.eus/contenidos/estadistica/udalmap_indicador_186/es_def/adjuntos/indicator.csv",
        "field": "renta_disponible_media",
    },
}


def _parse_udalmap_csv(
    content: str,
) -> dict[str, dict[int, float]]:
    """Parse UDALMAP CSV: municipality code → {year: value}.

    Format: semicolon-delimited, decimal comma.
    Header row has: Código municipio; Municipio; 2023; 2022; ...
    Province/comarca summary rows are filtered out (we only keep 48xxx codes).
    """
    lines = content.strip().splitlines()
    if not lines:
        return {}

    # Find header row — must contain both a label AND year columns (4-digit numbers)
    header_idx = 0
    for i, line in enumerate(lines):
        parts = line.split(";")
        has_years = any(
            p.strip().strip('"').isdigit() and len(p.strip().strip('"')) == 4
            for p in parts
        )
        has_label = "Municipio" in line or "municipio" in line or "Código" in line
        if has_label and has_years:
            header_idx = i
            break

    header = lines[header_idx].split(";")
    # Extract year columns (those that look like 4-digit years)
    year_cols: list[tuple[int, int]] = []  # (col_index, year)
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
        # Only keep individual Bizkaia municipalities (5-digit codes starting with 48)
        if not code.startswith(BIZKAIA_PREFIX) or len(code) != 5:
            continue

        year_values: dict[int, float] = {}
        for ci, yr in year_cols:
            if ci < len(parts):
                val_str = parts[ci].strip().strip('"').replace(",", ".")
                if val_str and val_str != ".." and val_str != "-":
                    try:
                        year_values[yr] = float(val_str)
                    except ValueError:
                        pass

        if year_values:
            result[code] = year_values

    return result


def import_income(
    session: Session,
    csv_dir: Path | None = None,
    *,
    download: bool = True,
) -> dict[str, object]:
    """Download and import UDALMAP income indicators for Bizkaia municipalities.

    If csv_dir is provided, reads from local files named
    renta_index.csv, renta_personal_total.csv, renta_disponible.csv.
    Otherwise downloads from Open Data Euskadi.
    """
    log = logger.bind(source="udalmap_income")

    # Download or read each indicator
    indicator_data: dict[str, dict[str, dict[int, float]]] = {}

    for name, info in INDICATORS.items():
        if csv_dir and (csv_dir / f"{name}.csv").exists():
            content = (csv_dir / f"{name}.csv").read_text(encoding="utf-8-sig")
        elif download:
            log.info("income_downloading", indicator=name)
            with httpx.Client(timeout=60) as client:
                resp = client.get(info["url"])
                resp.raise_for_status()
                content = resp.text
        else:
            continue

        parsed = _parse_udalmap_csv(content)
        indicator_data[name] = parsed
        log.info("income_parsed", indicator=name, municipalities=len(parsed))

    # Merge indicators and find the latest year available
    all_munis: set[str] = set()
    all_years: set[int] = set()
    for parsed in indicator_data.values():
        for code, yr_vals in parsed.items():
            all_munis.add(code)
            all_years.update(yr_vals.keys())

    if not all_years:
        log.warning("income_no_data")
        return {"inserted": 0}

    # Insert per (muni, year) — but only years with data
    inserted = 0
    for muni_code in sorted(all_munis):
        for year in sorted(all_years):
            renta_index = indicator_data.get("renta_index", {}).get(muni_code, {}).get(year)
            renta_personal = indicator_data.get("renta_personal_total", {}).get(muni_code, {}).get(year)
            renta_disponible = indicator_data.get("renta_disponible", {}).get(muni_code, {}).get(year)

            if renta_index is None and renta_personal is None and renta_disponible is None:
                continue

            session.execute(
                text("""
                    INSERT INTO municipality_income
                        (muni_code, year, renta_personal_media, renta_disponible_media, renta_index)
                    VALUES (:muni_code, :year, :renta_personal, :renta_disponible, :renta_index)
                    ON CONFLICT (muni_code, year) DO UPDATE SET
                        renta_personal_media = COALESCE(EXCLUDED.renta_personal_media, municipality_income.renta_personal_media),
                        renta_disponible_media = COALESCE(EXCLUDED.renta_disponible_media, municipality_income.renta_disponible_media),
                        renta_index = COALESCE(EXCLUDED.renta_index, municipality_income.renta_index)
                """),
                {
                    "muni_code": muni_code,
                    "year": year,
                    "renta_personal": renta_personal,
                    "renta_disponible": renta_disponible,
                    "renta_index": renta_index,
                },
            )
            inserted += 1

    session.commit()
    log.info("income_imported", inserted=inserted, municipalities=len(all_munis))

    return {
        "inserted": inserted,
        "municipalities": len(all_munis),
        "years": sorted(all_years),
    }
