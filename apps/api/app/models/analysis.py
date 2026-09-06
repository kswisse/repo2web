import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin


class AnalysisResult(UUIDMixin, Base):
    __tablename__ = "analysis_results"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("repository_snapshots.id"),
        unique=True, nullable=False, index=True
    )
    detected_languages: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    framework: Mapped[str | None] = mapped_column(String(100), nullable=True)
    package_manager: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entrypoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    install_command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    build_command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    run_command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expected_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    environment_variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    warnings: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    unsupported_requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    snapshot: Mapped["RepositorySnapshot"] = relationship(back_populates="analysis")
    execution_plan: Mapped["ExecutionPlan"] = relationship(
        back_populates="analysis", uselist=False
    )


class ExecutionPlan(UUIDMixin, Base):
    __tablename__ = "execution_plans"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("analysis_results.id"),
        unique=True, nullable=False, index=True
    )
    runtime: Mapped[str] = mapped_column(String(50), nullable=False, default="docker")
    framework: Mapped[str] = mapped_column(String(100), nullable=False)
    install_steps: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    build_steps: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    run_command: Mapped[str] = mapped_column(String(500), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=3000)
    environment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resource_requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    network_requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped["AnalysisResult"] = relationship(back_populates="execution_plan")
