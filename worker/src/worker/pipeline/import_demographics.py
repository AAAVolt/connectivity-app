"""Import age-group demographics per municipality from EUSTAT.

Reads census-section CSV, aggregates to municipality, writes Parquet.

Source: EUSTAT table PX_010154_cepv1_ep10b.px -- population by municipality,
year of birth, and sex.  We request all Bizkaia municipalities (code prefix 48)
and derive custom age groups: 0-17, 18-25, 26-64, 65+.

Fallback: EUSTAT census-section CSV with broad age bands (0-19, 20-64, 65+),
aggregated to municipality level.

Output: municipality_demographics.parquet in the serving directory.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd
import structlog

logger = structlog.get_logger()

# EUSTAT PX-Web API -- population by broad age groups per municipality
EUSTAT_API_URL = (
    "https://www.eustat.eus/bankupx/api/v1/es/DB/"
    "PX_010154_cepv1_ep06b.px"
)

# Direct CSV with census-section-level age percentages (fallback)
EUSTAT_CSV_URL = "https://www.eustat.eus/elem/xls0011435_c.csv"

BIZKAIA_PREFIX = "48"

# Year of the latest available data -- override via argument
DEFAULT_PERIOD = "20250101"


def _fetch_eustat_broad_ages(period: str = DEFAULT_PERIOD) -> list[dict[str, object]]:
    """Fetch population by broad age group per municipality from EUSTAT API.

    Returns list of dicts with keys: muni_code, value.
    """
    log = logger.bind(source="eustat_api")

    # First, get the metadata to discover municipality codes
    with httpx.Client(timeout=60) as client:
        meta_resp = client.get(EUSTAT_API_URL)
        meta_resp.raise_for_status()
        meta = meta_resp.json()

    # Find municipality variable values (codes starting with "48")
    muni_values: list[str] = []
    for var in meta.get("variables", []):
        if "territorial" in var.get("code", "").lower() or "ambitos" in var.get("code", "").lower():
            for val in var.get("values", []):
                if val.startswith(BIZKAIA_PREFIX) and len(val) == 5:
                    muni_values.append(val)
            break

    if not muni_values:
        log.warning("eustat_api_no_municipalities_found")
        return []

    log.info("eustat_api_fetching", municipalities=len(muni_values))

    # Build query -- request all Bizkaia municipalities, all age groups, total sex
    query = {
        "query": [
            {
                "code": meta["variables"][0]["code"],
                "selection": {"filter": "item", "values": muni_values},
            },
            {
                "code": next(
                    v["code"]
                    for v in meta["variables"]
                    if "sexo" in v.get("code", "").lower() or "sex" in v.get("code", "").lower()
                ),
                "selection": {"filter": "item", "values": ["Total"]},
            },
            {
                "code": next(
                    v["code"]
                    for v in meta["variables"]
                    if "periodo" in v.get("code", "").lower() or "period" in v.get("code", "").lower()
                ),
                "selection": {"filter": "item", "values": [period]},
            },
        ],
        "response": {"format": "json"},
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(EUSTAT_API_URL, json=query)
        resp.raise_for_status()
        data = resp.json()

    # Parse the JSON-stat-like response
    results: list[dict[str, object]] = []
    for record in data.get("data", []):
        key = record.get("key", [])
        values = record.get("values", [])
        if len(key) >= 1 and len(values) >= 1:
            muni_code = key[0]
            results.append({
                "muni_code": muni_code,
                "value": float(values[0]) if values[0] else 0,
            })

    return results


def import_demographics_from_csv(
    serving_dir: str | Path,
    csv_path: Path | None = None,
    year: int = 2025,
    *,
    download: bool = True,
) -> dict[str, object]:
    """Import demographics from EUSTAT census-section CSV, aggregated to municipality.

    The CSV has columns: muni_code, muni_name, district, section,
    total_pop, men, women, sex_ratio, pct_0_19, pct_20_64, pct_65_plus, ...

    We aggregate sections to municipality and approximate age groups:
    - 0-17 ~ pct_0_19 * 0.9 (rough: 18 out of 20 years in 0-19 band)
    - 18-25 ~ pct_0_19 * 0.1 + pct_20_64 * 0.14 (8 years out of 45)
    - 26-64 ~ pct_20_64 * 0.86
    - 65+ = pct_65_plus

    Writes municipality_demographics.parquet.
    """
    serving = Path(serving_dir)
    log = logger.bind(year=year)

    downloaded_tmp: Path | None = None
    if csv_path is None and download:
        log.info("demographics_downloading_csv")
        csv_path = Path("/tmp/eustat_demographics.csv")
        with httpx.Client(timeout=60) as client:
            resp = client.get(EUSTAT_CSV_URL)
            resp.raise_for_status()
            csv_path.write_bytes(resp.content)
        downloaded_tmp = csv_path

    if csv_path is None or not csv_path.exists():
        raise FileNotFoundError(f"Demographics CSV not found: {csv_path}")

    try:
        raw = csv_path.read_text(encoding="utf-8-sig")
        lines = raw.splitlines()

        # Parse -- semicolon-delimited, header on row 6 (0-indexed), data from row 7
        # Columns: muni_code; muni_name; district; section; total; men; women;
        #          sex_ratio; pct_0_19; pct_20_64; pct_65+; ...
        muni_data: dict[str, dict[str, float]] = {}
        current_muni: str | None = None

        for line in lines[6:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(";")
            if len(parts) < 11:
                continue

            code = parts[0].strip('"').strip()
            section = parts[3].strip('"').strip()
            pop_str = parts[4].strip('"').replace(".", "").strip()

            if code:
                current_muni = code

            # Skip district/municipality totals (section "000" or empty)
            if not section or section == "000" or current_muni is None:
                continue

            try:
                pop = int(pop_str)
            except ValueError:
                continue

            # Parse percentage columns -- use comma as decimal separator
            def parse_pct(s: str) -> float:
                s = s.strip('"').strip().replace(",", ".")
                try:
                    return float(s)
                except ValueError:
                    return 0.0

            pct_0_19 = parse_pct(parts[8])
            pct_20_64 = parse_pct(parts[9])
            pct_65 = parse_pct(parts[10])

            # Aggregate to municipality
            if current_muni not in muni_data:
                muni_data[current_muni] = {
                    "pop_total": 0,
                    "pop_0_19_weighted": 0,
                    "pop_20_64_weighted": 0,
                    "pop_65_weighted": 0,
                }

            m = muni_data[current_muni]
            m["pop_total"] += pop
            m["pop_0_19_weighted"] += pop * pct_0_19 / 100
            m["pop_20_64_weighted"] += pop * pct_20_64 / 100
            m["pop_65_weighted"] += pop * pct_65 / 100

        log.info("demographics_parsed", municipalities=len(muni_data))

        # Build records
        records: list[dict[str, object]] = []

        for muni_code, m in muni_data.items():
            pop_total = int(m["pop_total"])
            if pop_total == 0:
                continue

            # Approximate age groups from broad bands
            pop_0_19 = m["pop_0_19_weighted"]
            pop_20_64 = m["pop_20_64_weighted"]
            pop_65 = m["pop_65_weighted"]

            # Split 0-19 into 0-17 and 18-19 (approx 90% / 10%)
            pop_0_17 = int(pop_0_19 * 0.9)
            pop_18_19 = pop_0_19 - pop_0_17

            # Split 20-64 to extract 20-25 (6 years out of 45)
            pop_20_25 = int(pop_20_64 * 6 / 45)
            pop_26_64 = int(pop_20_64 - pop_20_25)

            pop_18_25 = int(pop_18_19 + pop_20_25)
            pop_65_plus = int(pop_65)

            full_muni_code = f"{BIZKAIA_PREFIX}{muni_code}" if len(muni_code) == 3 else muni_code

            records.append({
                "muni_code": full_muni_code,
                "year": year,
                "pop_total": pop_total,
                "pop_0_17": pop_0_17,
                "pop_18_25": pop_18_25,
                "pop_26_64": pop_26_64,
                "pop_65_plus": pop_65_plus,
                "pct_0_17": round(pop_0_17 / pop_total * 100, 2),
                "pct_18_25": round(pop_18_25 / pop_total * 100, 2),
                "pct_65_plus": round(pop_65_plus / pop_total * 100, 2),
            })

        # Write Parquet
        if records:
            df = pd.DataFrame(records)
            out_path = serving / "municipality_demographics.parquet"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(out_path, index=False)

        inserted = len(records)
        log.info("demographics_imported", inserted=inserted)

        return {"municipalities": inserted, "year": year, "source": "eustat_csv"}
    finally:
        if downloaded_tmp and downloaded_tmp.exists():
            downloaded_tmp.unlink()
            log.info("demographics_temp_file_cleaned", path=str(downloaded_tmp))
