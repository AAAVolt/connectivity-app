"""Destination models."""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class DestinationType(Base):
    __tablename__ = "destination_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("destination_types.id"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("1.0")
    )
    extra: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
