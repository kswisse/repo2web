import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Repository(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "repositories"

    url: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )

    snapshots: Mapped[list["RepositorySnapshot"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class RepositorySnapshot(UUIDMixin, Base):
    __tablename__ = "repository_snapshots"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("repositories.id"), nullable=False, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    cloned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    repository: Mapped["Repository"] = relationship(back_populates="snapshots")
    analysis: Mapped["AnalysisResult"] = relationship(
        back_populates="snapshot", uselist=False
    )
