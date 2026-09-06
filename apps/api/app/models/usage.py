import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class UsageRecord(UUIDMixin, Base):
    __tablename__ = "usage_records"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("deployments.id"), nullable=False, index=True
    )
    cpu_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    memory_mb_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    storage_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    network_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
