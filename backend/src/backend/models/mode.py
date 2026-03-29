"""Transport mode lookup model."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Mode(Base):
    __tablename__ = "modes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
