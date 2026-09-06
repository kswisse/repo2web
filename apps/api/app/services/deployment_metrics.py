"""
Deployment metrics service.

Persists resource usage metrics for deployment containers.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment_metrics import DeploymentMetrics
from app.runtime.metrics import ContainerMetrics


# Maximum number of metric snapshots to keep per deployment
MAX_METRICS_HISTORY = 60


class DeploymentMetricsService:
    """Service for persisting and querying deployment resource metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_metrics(
        self, deployment_id: str, metrics: ContainerMetrics
    ) -> DeploymentMetrics:
        """Record resource metrics for a deployment."""
        record = DeploymentMetrics(
            deployment_id=deployment_id,
            timestamp=metrics.timestamp,
            cpu_usage_percent=metrics.cpu_usage_percent,
            memory_usage_bytes=metrics.memory_usage_bytes,
            memory_limit_bytes=metrics.memory_limit_bytes,
            memory_percent=metrics.memory_percent,
            network_rx_bytes=metrics.network_rx_bytes,
            network_tx_bytes=metrics.network_tx_bytes,
            container_status=metrics.status,
            exit_code=metrics.exit_code,
            uptime_seconds=metrics.uptime_seconds,
        )
        self.db.add(record)
        await self.db.flush()

        # Prune old metrics beyond retention limit
        await self._prune_old_metrics(deployment_id)

        return record

    async def get_latest_metrics(
        self, deployment_id: str
    ) -> Optional[DeploymentMetrics]:
        """Get the most recent metrics for a deployment."""
        result = await self.db.execute(
            select(DeploymentMetrics)
            .where(DeploymentMetrics.deployment_id == deployment_id)
            .order_by(DeploymentMetrics.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_metrics_history(
        self, deployment_id: str, limit: int = MAX_METRICS_HISTORY
    ) -> list[DeploymentMetrics]:
        """Get metrics history for a deployment, ordered by timestamp."""
        result = await self.db.execute(
            select(DeploymentMetrics)
            .where(DeploymentMetrics.deployment_id == deployment_id)
            .order_by(DeploymentMetrics.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _prune_old_metrics(self, deployment_id: str) -> None:
        """Remove old metric snapshots beyond retention limit."""
        # Find the ID of the N-th oldest record
        subquery = (
            select(DeploymentMetrics.id)
            .where(DeploymentMetrics.deployment_id == deployment_id)
            .order_by(DeploymentMetrics.timestamp.desc())
            .offset(MAX_METRICS_HISTORY)
            .limit(1)
            .scalar_subquery()
        )

        # Delete records older than the retention limit
        from sqlalchemy import delete

        await self.db.execute(
            delete(DeploymentMetrics).where(
                DeploymentMetrics.deployment_id == deployment_id,
                DeploymentMetrics.id <= subquery,
            )
        )


# Synchronous version for Celery tasks
class DeploymentMetricsServiceSync:
    """Synchronous metrics service for Celery tasks."""

    def __init__(self):
        from app.services.deployment import _get_sync_session
        self.db = _get_sync_session()

    def record_metrics(
        self, deployment_id: str, metrics: ContainerMetrics
    ) -> Optional[DeploymentMetrics]:
        """Record resource metrics for a deployment."""
        try:
            record = DeploymentMetrics(
                deployment_id=deployment_id,
                timestamp=metrics.timestamp,
                cpu_usage_percent=metrics.cpu_usage_percent,
                memory_usage_bytes=metrics.memory_usage_bytes,
                memory_limit_bytes=metrics.memory_limit_bytes,
                memory_percent=metrics.memory_percent,
                network_rx_bytes=metrics.network_rx_bytes,
                network_tx_bytes=metrics.network_tx_bytes,
                container_status=metrics.status,
                exit_code=metrics.exit_code,
                uptime_seconds=metrics.uptime_seconds,
            )
            self.db.add(record)
            self.db.commit()
            return record
        except Exception:
            self.db.rollback()
            return None

    def get_latest_metrics(
        self, deployment_id: str
    ) -> Optional[DeploymentMetrics]:
        """Get the most recent metrics for a deployment."""
        result = self.db.execute(
            select(DeploymentMetrics)
            .where(DeploymentMetrics.deployment_id == deployment_id)
            .order_by(DeploymentMetrics.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def close(self):
        self.db.close()
