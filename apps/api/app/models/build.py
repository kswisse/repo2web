import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin


class BuildJob(UUIDMixin, Base):
    __tablename__ = "build_jobs"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("execution_plans.id"), nullable=False, index=True
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("deployments.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["BuildStep"]] = relationship(
        back_populates="build_job", cascade="all, delete-orphan"
    )


class BuildStep(UUIDMixin, Base):
    __tablename__ = "build_steps"

    build_job_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("build_jobs.id"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    command: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    build_job: Mapped["BuildJob"] = relationship(back_populates="steps")
    logs: Mapped[list["BuildLog"]] = relationship(
        back_populates="build_step", cascade="all, delete-orphan"
    )


class BuildLog(UUIDMixin, Base):
    __tablename__ = "build_logs"

    build_step_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("build_steps.id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    build_step: Mapped["BuildStep"] = relationship(back_populates="logs")
