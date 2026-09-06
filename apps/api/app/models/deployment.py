import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Deployment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deployments"

    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36), ForeignKey("repositories.id"), nullable=True, index=True
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36), ForeignKey("repository_snapshots.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    
    # Repository information
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    
    # Application information
    framework: Mapped[str | None] = mapped_column(String(50), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Error information
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Container tracking for cleanup
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    build_container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Celery task tracking
    celery_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    
    # Timestamps for each stage
    cloned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    build_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    build_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    runtime_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Health and observability fields
    health_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="pending"
    )  # pending, healthy, unhealthy, timeout
    health_response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped["Repository"] = relationship()
    snapshot: Mapped["RepositorySnapshot"] = relationship()
    build_job: Mapped["BuildJob"] = relationship(uselist=False)
