"""Grid cell model."""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Float, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class GridCell(Base):
    __tablename__ = "grid_cells"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    cell_code: Mapped[str] = mapped_column(String, nullable=False)
    geom = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    centroid = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    population: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0")
    )
    muni_code: Mapped[str | None] = mapped_column(String, nullable=True)
