"""Connectivity score models."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ConnectivityScore(Base):
    __tablename__ = "connectivity_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    cell_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grid_cells.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_normalized: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CombinedScore(Base):
    __tablename__ = "combined_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    cell_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grid_cells.id", ondelete="CASCADE"), nullable=False
    )
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)
    combined_score_normalized: Mapped[float | None] = mapped_column(Float, nullable=True)
    weights: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
