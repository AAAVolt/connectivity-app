"""Atomic file-write utilities for the data pipeline.

Ensures that concurrent workers (or crashes mid-write) never leave a
half-written Parquet file in the serving directory.

Pattern: write to a temporary file in the same directory, then
``os.replace()`` atomically.  On POSIX systems this is guaranteed to be
atomic when source and destination are on the same filesystem.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import geopandas as gpd
    import pandas as pd

logger = structlog.get_logger()


def atomic_write_parquet(
    df: "pd.DataFrame | gpd.GeoDataFrame",
    dest: Path,
    *,
    index: bool = False,
) -> None:
    """Write a DataFrame/GeoDataFrame to Parquet atomically.

    Creates a temporary file in the same directory as *dest*, writes the
    data, then uses ``os.replace()`` to move it into place.  This
    guarantees that *dest* is never in a half-written state — readers
    will see either the old file or the new file, never a partial one.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # tempfile in the same directory so os.replace is atomic
    fd, tmp_path = tempfile.mkstemp(
        dir=dest.parent,
        prefix=f".{dest.stem}_",
        suffix=".parquet.tmp",
    )
    try:
        os.close(fd)
        df.to_parquet(tmp_path, index=index)
        os.replace(tmp_path, dest)
        logger.debug("atomic_write_ok", path=str(dest), rows=len(df))
    except BaseException:
        # Clean up temp file on any failure (including KeyboardInterrupt)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
