"""Boundary model for tenant regions."""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Boundary(Base):
    __tablename__ = "boundaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    boundary_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'region'")
    )
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
