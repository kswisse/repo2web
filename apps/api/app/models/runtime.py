import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin


class RuntimeInstance(UUIDMixin, Base):
    __tablename__ = "runtime_instances"

    build_job_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("build_jobs.id"),
        unique=True, nullable=False, index=True
    )
    container_id: Mapped[str] = mapped_column(String(100), nullable=False)
    internal_url: Mapped[str] = mapped_column(String(500), nullable=False)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="starting")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    health_checks: Mapped[list["HealthCheck"]] = relationship(
        back_populates="runtime", cascade="all, delete-orphan"
    )


class HealthCheck(UUIDMixin, Base):
    __tablename__ = "health_checks"

    runtime_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("runtime_instances.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    runtime: Mapped["RuntimeInstance"] = relationship(back_populates="health_checks")
