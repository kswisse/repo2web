import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.models.deployment import Deployment
from app.models.repository import Repository, RepositorySnapshot


VALID_STATES = {
    "queued", "cloning", "analyzing", "planning", "building",
    "starting", "health_checking", "running",
    "clone_failed", "analysis_failed", "plan_failed",
    "build_failed", "start_failed", "health_check_failed",
    "security_blocked", "timeout", "cancelled",
}

TRANSITIONS = {
    "queued": {"cloning", "cancelled"},
    "cloning": {"analyzing", "clone_failed"},
    "analyzing": {"planning", "analysis_failed"},
    "planning": {"building", "plan_failed"},
    "building": {"starting", "build_failed", "security_blocked"},
    "starting": {"health_checking", "start_failed"},
    "health_checking": {"running", "health_check_failed", "timeout"},
}

TERMINAL_STATES = {
    "running", "clone_failed", "analysis_failed", "plan_failed",
    "build_failed", "start_failed", "health_check_failed",
    "security_blocked", "timeout", "cancelled",
}


class DeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, repository_id: str, snapshot_id: str, user_id: str
    ) -> Deployment:
        repo = await self.db.get(Repository, repository_id)
        if not repo:
            raise NotFoundException("Repository", repository_id)

        snapshot = await self.db.get(RepositorySnapshot, snapshot_id)
        if not snapshot:
            raise NotFoundException("RepositorySnapshot", snapshot_id)

        deployment = Deployment(
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            user_id=user_id,
            state="queued",
        )
        self.db.add(deployment)
        await self.db.flush()
        return deployment

    async def create_from_url(
        self, repository_url: str, user_id: str
    ) -> Deployment:
        """Create a deployment from a GitHub URL (async flow)."""
        deployment = Deployment(
            id=str(uuid.uuid4()),
            repository_url=repository_url,
            user_id=user_id,
            state="queued",
        )
        self.db.add(deployment)
        await self.db.flush()
        return deployment

    async def get(self, deployment_id: str) -> Deployment:
        result = await self.db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise NotFoundException("Deployment", deployment_id)
        return deployment

    async def update_state(self, deployment_id: str, new_state: str, error: str = None) -> Deployment:
        if new_state not in VALID_STATES:
            raise ValidationException(f"Invalid state: {new_state}")

        deployment = await self.get(deployment_id)

        allowed = TRANSITIONS.get(deployment.state, set())
        if new_state not in allowed and new_state != "cancelled":
            raise ValidationException(
                f"Cannot transition from {deployment.state} to {new_state}"
            )

        deployment.state = new_state
        if new_state in TERMINAL_STATES:
            deployment.completed_at = datetime.now(timezone.utc)
        if error:
            deployment.error_message = error
            deployment.error_stage = new_state

        await self.db.flush()
        return deployment

    async def update_from_result(self, deployment_id: str, result) -> Deployment:
        """Update deployment from DeploymentResult."""
        deployment = await self.get(deployment_id)
        
        deployment.state = result.state.value
        deployment.commit_sha = result.commit_sha
        deployment.framework = result.framework
        deployment.port = result.port
        deployment.internal_url = getattr(result, 'internal_url', None)
        deployment.error_message = result.error_message
        deployment.error_stage = result.error_stage
        deployment.cloned_at = result.cloned_at
        deployment.analyzed_at = result.analyzed_at
        deployment.plan_generated_at = result.plan_generated_at
        deployment.build_started_at = result.build_started_at
        deployment.build_completed_at = result.build_completed_at
        deployment.runtime_started_at = result.runtime_started_at
        deployment.health_checked_at = result.health_checked_at
        deployment.completed_at = result.completed_at
        
        # Health and observability fields
        deployment.health_status = getattr(result, 'health_status', None)
        deployment.health_response_time_ms = getattr(result, 'health_response_time_ms', None)
        deployment.last_health_check_at = getattr(result, 'last_health_check_at', None)
        
        await self.db.flush()
        return deployment

    async def list_by_user(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Deployment], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(Deployment).where(Deployment.user_id == user_id)
        )
        total = count_result.scalar()

        result = await self.db.execute(
            select(Deployment)
            .where(Deployment.user_id == user_id)
            .order_by(Deployment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


# Synchronous versions for Celery tasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings


def _get_sync_session():
    settings = get_settings()
    engine = create_engine(
        settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"),
        echo=False,
        pool_size=5,
        max_overflow=5,
    )
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


class DeploymentServiceSync:
    """Synchronous deployment service for Celery tasks."""
    
    def __init__(self):
        self.db = _get_sync_session()

    def get(self, deployment_id: str) -> Deployment:
        result = self.db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        if not deployment:
            raise NotFoundException("Deployment", deployment_id)
        return deployment

    def update_state(self, deployment_id: str, new_state: str, error: str = None) -> Deployment:
        if new_state not in VALID_STATES:
            raise ValidationException(f"Invalid state: {new_state}")

        deployment = self.get(deployment_id)

        allowed = TRANSITIONS.get(deployment.state, set())
        if new_state not in allowed and new_state != "cancelled":
            raise ValidationException(
                f"Cannot transition from {deployment.state} to {new_state}"
            )

        deployment.state = new_state
        if new_state in TERMINAL_STATES:
            deployment.completed_at = datetime.now(timezone.utc)
        if error:
            deployment.error_message = error
            deployment.error_stage = new_state

        self.db.commit()
        return deployment

    def update_from_result(self, deployment_id: str, result) -> Deployment:
        """Update deployment from DeploymentResult."""
        deployment = self.get(deployment_id)
        
        deployment.state = result.state.value
        deployment.commit_sha = result.commit_sha
        deployment.framework = result.framework
        deployment.port = result.port
        deployment.internal_url = getattr(result, 'internal_url', None)
        deployment.error_message = result.error_message
        deployment.error_stage = result.error_stage
        deployment.cloned_at = result.cloned_at
        deployment.analyzed_at = result.analyzed_at
        deployment.plan_generated_at = result.plan_generated_at
        deployment.build_started_at = result.build_started_at
        deployment.build_completed_at = result.build_completed_at
        deployment.runtime_started_at = result.runtime_started_at
        deployment.health_checked_at = result.health_checked_at
        deployment.completed_at = result.completed_at
        
        # Health and observability fields
        deployment.health_status = getattr(result, 'health_status', None)
        deployment.health_response_time_ms = getattr(result, 'health_response_time_ms', None)
        deployment.last_health_check_at = getattr(result, 'last_health_check_at', None)
        
        self.db.commit()
        return deployment

    def close(self):
        self.db.close()
