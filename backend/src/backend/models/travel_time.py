"""Travel time model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class TravelTime(Base):
    __tablename__ = "travel_times"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    origin_cell_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grid_cells.id", ondelete="CASCADE"), nullable=False
    )
    destination_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    departure_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    travel_time_minutes: Mapped[float] = mapped_column(Float, nullable=False)
