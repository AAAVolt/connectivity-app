"""Download GTFS feeds for all Bizkaia transit operators from Moveuskadi.

Source: https://www.geo.euskadi.eus/cartografia/DatosDescarga/Transporte/Moveuskadi/
All feeds are public, updated daily, standard GTFS format.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger()

MOVEUSKADI_BASE = "https://www.geo.euskadi.eus/cartografia/DatosDescarga/Transporte/Moveuskadi"

# Operators relevant to Bizkaia, ordered by importance
BIZKAIA_OPERATORS: list[tuple[str, str]] = [
    ("Bizkaibus", "Intercity bus network"),
    ("Bilbobus", "Bilbao urban bus"),
    ("MetroBilbao", "Metro system"),
    ("Euskotren", "Tram and commuter rail"),
    ("Renfe_Cercanias", "Renfe commuter rail"),
    ("La_Union", "Bilbao tram"),
    ("FunicularArtxanda", "Artxanda funicular"),
]

TIMEOUT_S = 120


def download_gtfs_feeds(
    output_dir: Path,
    *,
    operators: list[str] | None = None,
) -> dict[str, str]:
    """Download GTFS feeds for Bizkaia transit operators.

    Args:
        output_dir: Directory to save the .zip files.
        operators: Optional list of operator names to download.
            Defaults to all Bizkaia operators.

    Returns:
        Dict mapping operator name to download status.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if operators:
        targets = [(op, "") for op in operators]
    else:
        targets = BIZKAIA_OPERATORS

    results: dict[str, str] = {}

    with httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, verify=False) as client:
        for operator, description in targets:
            url = f"{MOVEUSKADI_BASE}/{operator}/google_transit.zip"
            dest = output_dir / f"{operator}.gtfs.zip"
            log = logger.bind(operator=operator, url=url)

            try:
                log.info("gtfs_download_start", description=description)
                resp = client.get(url)
                resp.raise_for_status()

                dest.write_bytes(resp.content)
                size_mb = len(resp.content) / (1024 * 1024)
                results[operator] = f"OK ({size_mb:.1f} MB)"
                log.info("gtfs_download_complete", size_mb=f"{size_mb:.1f}")

            except httpx.HTTPStatusError as exc:
                results[operator] = f"HTTP {exc.response.status_code}"
                log.warning("gtfs_download_failed", status=exc.response.status_code)
            except httpx.RequestError as exc:
                results[operator] = f"Error: {exc}"
                log.warning("gtfs_download_error", error=str(exc))

    return results
