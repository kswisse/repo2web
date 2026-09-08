import re
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment_log import DeploymentLog

# Maximum allowed log message length to prevent database exhaustion
MAX_LOG_MESSAGE_LENGTH = 10000

# ANSI escape sequence pattern
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-9;]*[a-zA-Z]|\x1B\].*?\x07")

# Control characters to strip (except newline and tab)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def sanitize_log_message(message: str) -> str:
    """
    Sanitize a log message for safe storage.
    
    - Strips ANSI escape sequences
    - Strips dangerous control characters
    - Truncates to maximum length
    - Preserves newlines and tabs for readability
    """
    if not message:
        return ""
    
    # Strip ANSI escape sequences
    message = ANSI_ESCAPE_PATTERN.sub("", message)
    
    # Strip dangerous control characters (keep \n and \t)
    message = CONTROL_CHAR_PATTERN.sub("", message)
    
    # Truncate to maximum length
    if len(message) > MAX_LOG_MESSAGE_LENGTH:
        message = message[:MAX_LOG_MESSAGE_LENGTH] + "\n[TRUNCATED]"
    
    return message


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
        """Persist a deployment log entry with sanitization."""
        # Sanitize the message
        message = sanitize_log_message(message)
        
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