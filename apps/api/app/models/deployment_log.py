import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class DeploymentLog(UUIDMixin, Base):
    __tablename__ = "deployment_logs"
    
    deployment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="INFO"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)