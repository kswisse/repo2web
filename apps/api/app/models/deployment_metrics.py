"""
Deployment metrics persistence model.

Stores resource usage snapshots for deployment containers.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class DeploymentMetrics(UUIDMixin, Base):
    """Stores resource metrics snapshots for a deployment container."""
    __tablename__ = "deployment_metrics"

    deployment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cpu_usage_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_usage_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_limit_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    network_rx_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    network_tx_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
