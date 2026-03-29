"""Population source model."""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Float, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class PopulationSource(Base):
    __tablename__ = "population_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    population: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0")
    )
    geom = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
