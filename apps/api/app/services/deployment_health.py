"""
Deployment health check service.

Persists health check results for deployment containers.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment_health import DeploymentHealth
from app.runtime.health import HealthCheckResult


class DeploymentHealthService:
    """Service for persisting and querying deployment health checks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_health_check(
        self,
        deployment_id: str,
        result: HealthCheckResult,
        is_final: bool = False,
    ) -> DeploymentHealth:
        """Record a health check result."""
        record = DeploymentHealth(
            deployment_id=deployment_id,
            status=result.status,
            response_time_ms=result.response_time_ms,
            status_code=result.status_code,
            error_message=result.error,
            attempt_number=result.attempts,
            checked_at=datetime.now(timezone.utc),
            is_final=is_final,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_health_status(
        self, deployment_id: str
    ) -> Optional[DeploymentHealth]:
        """Get the current (final) health status for a deployment."""
        result = await self.db.execute(
            select(DeploymentHealth)
            .where(
                DeploymentHealth.deployment_id == deployment_id,
                DeploymentHealth.is_final == True,  # noqa: E712
            )
            .order_by(DeploymentHealth.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_health_check(
        self, deployment_id: str
    ) -> Optional[DeploymentHealth]:
        """Get the most recent health check for a deployment."""
        result = await self.db.execute(
            select(DeploymentHealth)
            .where(DeploymentHealth.deployment_id == deployment_id)
            .order_by(DeploymentHealth.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_health_history(
        self, deployment_id: str, limit: int = 20
    ) -> list[DeploymentHealth]:
        """Get health check history for a deployment."""
        result = await self.db.execute(
            select(DeploymentHealth)
            .where(DeploymentHealth.deployment_id == deployment_id)
            .order_by(DeploymentHealth.checked_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# Synchronous version for Celery tasks
class DeploymentHealthServiceSync:
    """Synchronous health service for Celery tasks."""

    def __init__(self):
        from app.services.deployment import _get_sync_session
        self.db = _get_sync_session()

    def record_health_check(
        self,
        deployment_id: str,
        result: HealthCheckResult,
        is_final: bool = False,
    ) -> Optional[DeploymentHealth]:
        """Record a health check result."""
        try:
            record = DeploymentHealth(
                deployment_id=deployment_id,
                status=result.status,
                response_time_ms=result.response_time_ms,
                status_code=result.status_code,
                error_message=result.error,
                attempt_number=result.attempts,
                checked_at=datetime.now(timezone.utc),
                is_final=is_final,
            )
            self.db.add(record)
            self.db.commit()
            return record
        except Exception:
            self.db.rollback()
            return None

    def get_health_status(
        self, deployment_id: str
    ) -> Optional[DeploymentHealth]:
        """Get the current (final) health status for a deployment."""
        result = self.db.execute(
            select(DeploymentHealth)
            .where(
                DeploymentHealth.deployment_id == deployment_id,
                DeploymentHealth.is_final == True,  # noqa: E712
            )
            .order_by(DeploymentHealth.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def close(self):
        self.db.close()
