"""
Deployment health check persistence model.

Stores health check results for deployment containers.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class DeploymentHealth(UUIDMixin, Base):
    """Stores health check results for a deployment."""
    __tablename__ = "deployment_health"

    deployment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pending, healthy, unhealthy, timeout
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
