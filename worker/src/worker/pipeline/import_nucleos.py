"""Import EUSTAT núcleo polygons for dasymetric population masking.

Núcleos are concentrated settlement areas.  Rows with NUC_NUCD = '99'
are *diseminado* (dispersed rural) and are stored but flagged so they
can be excluded during population disaggregation.

Data source:
  https://www.geo.euskadi.eus/cartografia/DatosDescarga/Limites/Unidades_estadisticas/NUCLEOS_EUSTAT_5000_ETRS89.zip
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import structlog
from shapely.geometry import MultiPolygon, Polygon
from sqlalchemy import text
from sqlalchemy.orm import Session

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
    session: Session,
    tenant_id: str,
    shp_path: Path,
    *,
    clear_existing: bool = True,
) -> dict[str, object]:
    """Import EUSTAT núcleo polygons filtered to Bizkaia.

    Returns statistics about imported records.
    """
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

    if clear_existing:
        deleted = session.execute(
            text("DELETE FROM nucleos WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).rowcount
        if deleted:
            log.info("import_nucleos_cleared", deleted=deleted)

    insert_sql = text("""
        INSERT INTO nucleos (tenant_id, code, nucleo_num, name,
                             entity_name, muni_code, muni_name, geom)
        VALUES (:tid, :code, :nnum, :name, :entity, :muni_code, :muni_name,
                ST_Multi(ST_MakeValid(ST_SetSRID(ST_GeomFromText(:wkt), :srid))))
    """)

    nucleo_count = 0
    diseminado_count = 0

    for _, row in biz.iterrows():
        nuc_num = str(row["NUC_NUCD"]).strip()
        session.execute(insert_sql, {
            "tid": tenant_id,
            "code": str(row["NUC_CL"]),
            "nnum": nuc_num,
            "name": str(row["NUC_DS_O"]),
            "entity": str(row.get("NUC_ENTI_D", "")),
            "muni_code": str(row["NUC_MUNI"]),
            "muni_name": str(row["NUC_MUNI_D"]),
            "wkt": row.geometry.wkt,
            "srid": STORAGE_SRID,
        })

        if nuc_num == "99":
            diseminado_count += 1
        else:
            nucleo_count += 1

    session.commit()

    stats: dict[str, object] = {
        "total": nucleo_count + diseminado_count,
        "nucleos": nucleo_count,
        "diseminados": diseminado_count,
    }
    log.info("import_nucleos_complete", **stats)
    return stats
