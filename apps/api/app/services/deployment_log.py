from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment_log import DeploymentLog


class DeploymentLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self, 
        deployment_id: str, 
        stage: str, 
        level: str, 
        message: str,
    ) -> DeploymentLog:
        """Persist a deployment log entry."""
        # Get next sequence number
        result = await self.db.execute(
            select(func.coalesce(func.max(DeploymentLog.sequence), 0))
            .where(DeploymentLog.deployment_id == deployment_id)
        )
        max_seq = result.scalar() or 0
        
        log_entry = DeploymentLog(
            deployment_id=deployment_id,
            stage=stage,
            level=level,
            message=message,
            timestamp=datetime.now(timezone.utc),
            sequence=max_seq + 1,
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

    async def get_logs(
        self, deployment_id: str, limit: int = 100
    ) -> list[DeploymentLog]:
        """Get deployment logs ordered by sequence."""
        result = await self.db.execute(
            select(DeploymentLog)
            .where(DeploymentLog.deployment_id == deployment_id)
            .order_by(DeploymentLog.sequence)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_logs_by_stage(
        self, deployment_id: str, stage: str
    ) -> list[DeploymentLog]:
        """Get logs for a specific stage."""
        result = await self.db.execute(
            select(DeploymentLog)
            .where(
                DeploymentLog.deployment_id == deployment_id,
                DeploymentLog.stage == stage,
            )
            .order_by(DeploymentLog.sequence)
        )
        return list(result.scalars().all())