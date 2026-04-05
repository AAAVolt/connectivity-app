"""Import EUSTAT nucleo polygons for dasymetric population masking.

Nucleos are concentrated settlement areas.  Rows with NUC_NUCD = '99'
are *diseminado* (dispersed rural) and are stored but flagged so they
can be excluded during population disaggregation.

Output: nucleos.parquet (GeoParquet) in the serving directory.

Data source:
  https://www.geo.euskadi.eus/cartografia/DatosDescarga/Limites/Unidades_estadisticas/NUCLEOS_EUSTAT_5000_ETRS89.zip
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import structlog
from shapely.geometry import MultiPolygon, Polygon

logger = structlog.get_logger()

STORAGE_SRID = 4326
BIZKAIA_PROV = "48"


def _ensure_multi(geom: object) -> MultiPolygon:
    """Promote Polygon to MultiPolygon; extract polygons from GeometryCollection."""
    if geom is None:
        return MultiPolygon()
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom  # type: ignore[return-value]
    polys: list[Polygon] = []
    for g in getattr(geom, "geoms", []):
        if isinstance(g, Polygon):
            polys.append(g)
        elif isinstance(g, MultiPolygon):
            polys.extend(g.geoms)
    return MultiPolygon(polys) if polys else MultiPolygon()


def import_nucleos(
    tenant_id: str,
    serving_dir: str | Path,
    shp_path: Path,
) -> dict[str, object]:
    """Import EUSTAT nucleo polygons filtered to Bizkaia.

    Writes nucleos.parquet as GeoParquet.
    Returns statistics about imported records.
    """
    serving = Path(serving_dir)
    log = logger.bind(tenant_id=tenant_id, shp=str(shp_path))
    log.info("import_nucleos_start")

    gdf = gpd.read_file(shp_path)
    biz = gdf[gdf["NUC_PROV"] == BIZKAIA_PROV].copy()

    if biz.empty:
        raise ValueError(f"No Bizkaia records (NUC_PROV={BIZKAIA_PROV}) in {shp_path}")

    # Fix invalid geometries and ensure MultiPolygon
    biz["geometry"] = biz.geometry.make_valid()
    biz["geometry"] = biz.geometry.apply(_ensure_multi)

    # Reproject to WGS84
    if biz.crs and biz.crs.to_epsg() != STORAGE_SRID:
        biz = biz.to_crs(epsg=STORAGE_SRID)

    # Build output records
    records: list[dict[str, object]] = []
    geometries: list[MultiPolygon] = []
    nucleo_count = 0
    diseminado_count = 0

    for _, row in biz.iterrows():
        nuc_num = str(row["NUC_NUCD"]).strip()
        records.append({
            "tenant_id": tenant_id,
            "code": str(row["NUC_CL"]),
            "nucleo_num": nuc_num,
            "name": str(row["NUC_DS_O"]),
            "entity_name": str(row.get("NUC_ENTI_D", "")),
            "muni_code": str(row["NUC_MUNI"]),
            "muni_name": str(row["NUC_MUNI_D"]),
        })
        geometries.append(row.geometry)

        if nuc_num == "99":
            diseminado_count += 1
        else:
            nucleo_count += 1

    out_gdf = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
    out_path = serving / "nucleos.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_gdf.to_parquet(out_path)

    stats: dict[str, object] = {
        "total": nucleo_count + diseminado_count,
        "nucleos": nucleo_count,
        "diseminados": diseminado_count,
    }
    log.info("import_nucleos_complete", **stats)
    return stats
