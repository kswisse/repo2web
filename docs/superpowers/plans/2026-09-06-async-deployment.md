# Async Deployment Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert deployment execution from synchronous to asynchronous using Celery + Redis + PostgreSQL

**Architecture:** API returns 202 immediately with QUEUED state, Celery worker executes deployment pipeline, PostgreSQL is source of truth for state, Redis is job infrastructure only

**Tech Stack:** FastAPI, SQLAlchemy async, Celery with Redis broker, PostgreSQL

## Global Constraints

- PostgreSQL is authoritative for state
- Redis/Celery is job infrastructure only
- No AI repair implementation
- No production deployment implementation
- No public URLs implementation
- No WebSocket (use polling)
- No billing/auth additions
- Do NOT hold database transactions across long-running work
- Design for at-least-once task delivery
- Celery worker must not bypass sandbox controls
- Repository code executes only in containers
- No host execution
- Cleanup on all failure paths
- No secrets logged

## File Structure

- Create: `apps/api/app/models/deployment_log.py` - DeploymentLog model
- Create: `apps/api/app/services/deployment_log.py` - DeploymentLog service
- Modify: `apps/api/app/models/deployment.py` - Add container/snapshot fields, relax FK constraints
- Create: `apps/api/app/tasks/deployment.py` - Celery task for async execution
- Modify: `apps/api/app/services/deployment.py` - Add URL-based deployment methods
- Modify: `apps/api/app/orchestrator/orchestrator.py` - Accept deployment_id, persist state/logs
- Modify: `apps/api/app/api/v1/deployments.py` - Update endpoints for async flow
- Create: `apps/api/tests/test_async_deployment.py` - Async deployment tests

## Tasks

### Task 1: Create DeploymentLog Model

**Files:**
- Create: `apps/api/app/models/deployment_log.py`
- Modify: `apps/api/app/models/__init__.py`

**Interfaces:**
- Produces: `DeploymentLog` SQLAlchemy model

- [ ] **Step 1: Create the DeploymentLog model**

```python
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
```

- [ ] **Step 2: Update models __init__.py**

Add `DeploymentLog` to exports.

- [ ] **Step 3: Commit**

### Task 2: Create DeploymentLog Service

**Files:**
- Create: `apps/api/app/services/deployment_log.py`
- Modify: `apps/api/app/services/__init__.py`

**Interfaces:**
- Consumes: `DeploymentLog` model
- Produces: `DeploymentLogService` class with `log()`, `get_logs()`, `get_logs_by_stage()` methods

- [ ] **Step 1: Create the DeploymentLogService**

```python
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
```

- [ ] **Step 2: Update services __init__.py**

Add `DeploymentLogService` to exports.

- [ ] **Step 3: Commit**

### Task 3: Update Deployment Model

**Files:**
- Modify: `apps/api/app/models/deployment.py`
- Modify: `apps/api/app/schemas/deployment.py`

**Interfaces:**
- Consumes: Existing Deployment model
- Produces: Updated model with container tracking fields and relaxed FK constraints

- [ ] **Step 1: Update Deployment model**

Add fields:
- `container_id` (String(100), nullable) - runtime container ID
- `build_container_id` (String(100), nullable) - build container ID  
- `snapshot_path` (String(500), nullable) - local clone path
- Make `repository_id`, `snapshot_id`, `user_id` nullable
- Add `celery_task_id` (String(36), nullable) - for task tracking

- [ ] **Step 2: Update DeploymentResponse schema**

Add new fields to response schema.

- [ ] **Step 3: Commit**

### Task 4: Create Celery Deployment Task

**Files:**
- Create: `apps/api/app/tasks/deployment.py`
- Modify: `apps/api/app/tasks/__init__.py`

**Interfaces:**
- Consumes: `DeploymentOrchestrator`, `DeploymentService`, `DeploymentLogService`
- Produces: `execute_deployment` Celery task

- [ ] **Step 1: Create the Celery task**

```python
import asyncio
from app.tasks.celery_app import celery_app
from app.core.database import get_sync_db
from app.services.deployment import DeploymentService
from app.services.deployment_log import DeploymentLogService
from app.orchestrator.orchestrator import DeploymentOrchestrator


@celery_app.task(
    bind=True,
    max_retries=1,
    soft_time_limit=600,  # 10 minutes
    time_limit=660,
    acks_late=True,
)
def execute_deployment(self, deployment_id: str):
    """Execute a deployment asynchronously."""
    db = get_sync_db()
    try:
        # 1. Check if already running (idempotency)
        service = DeploymentService(db)
        deployment = service.get_sync(deployment_id)
        
        if deployment.state != "queued":
            return {
                "deployment_id": deployment_id,
                "status": "skipped",
                "reason": f"Deployment already in state: {deployment.state}",
            }
        
        # 2. Update state to cloning
        service.update_state_sync(deployment_id, "cloning")
        
        # 3. Run orchestrator
        orchestrator = DeploymentOrchestrator()
        
        # Run async orchestrator in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                orchestrator.deploy(
                    deployment_id=deployment_id,
                    repository_url=deployment.repository_url,
                )
            )
            
            # 4. Update deployment with result
            service.update_from_result_sync(deployment_id, result)
            
            return {
                "deployment_id": deployment_id,
                "status": result.state.value,
                "framework": result.framework,
                "port": result.port,
            }
        finally:
            loop.close()
            
    except Exception as e:
        # 5. Update state on failure
        try:
            service.update_state_sync(
                deployment_id, "build_failed", str(e)
            )
        except Exception:
            pass
        raise
    finally:
        db.close()
```

- [ ] **Step 2: Update tasks __init__.py**

Add `execute_deployment` to exports.

- [ ] **Step 3: Commit**

### Task 5: Update Deployment Service

**Files:**
- Modify: `apps/api/app/services/deployment.py`

**Interfaces:**
- Consumes: `Deployment` model
- Produces: `create_from_url()`, `get_sync()`, `update_state_sync()`, `update_from_result_sync()` methods

- [ ] **Step 1: Add URL-based deployment methods**

Add methods:
- `create_from_url(repository_url: str, user_id: str) -> Deployment`
- `get_sync(deployment_id: str) -> Deployment` (synchronous version for Celery)
- `update_state_sync(deployment_id: str, new_state: str, error: str = None) -> Deployment`
- `update_from_result_sync(deployment_id: str, result: DeploymentResult) -> Deployment`

- [ ] **Step 2: Commit**

### Task 6: Update Orchestrator

**Files:**
- Modify: `apps/api/app/orchestrator/orchestrator.py`

**Interfaces:**
- Consumes: `DeploymentLogService`
- Produces: Updated orchestrator with state persistence and logging

- [ ] **Step 1: Update orchestrator to persist state**

Modify `deploy()` method to:
- Accept `db` parameter for database session
- Create `DeploymentLogService` instance
- Log at each stage transition
- Update deployment state at each transition
- Store container IDs and snapshot path
- Handle cleanup on all failure paths

- [ ] **Step 2: Commit**

### Task 7: Update API Endpoints

**Files:**
- Modify: `apps/api/app/api/v1/deployments.py`

**Interfaces:**
- Consumes: `DeploymentService`, `execute_deployment` task
- Produces: Updated API endpoints

- [ ] **Step 1: Update create_deployment endpoint**

Change to:
- Accept `CreateDeploymentRequest`
- Create deployment record with QUEUED state
- Enqueue Celery task
- Return 202 with deployment_id

- [ ] **Step 2: Update get_deployment endpoint**

Keep as is (polling endpoint).

- [ ] **Step 3: Update get_deployment_logs endpoint**

Implement log retrieval from database.

- [ ] **Step 4: Update cancel_deployment endpoint**

Implement cancellation logic.

- [ ] **Step 5: Commit**

### Task 8: Create Database Migration

**Files:**
- Create: `apps/api/alembic/versions/002_async_deployment.py`

**Interfaces:**
- Consumes: Existing database schema
- Produces: Updated schema with new tables and columns

- [ ] **Step 1: Create migration**

Add:
- `deployment_logs` table
- New columns to `deployments` table
- Make `repository_id`, `snapshot_id`, `user_id` nullable

- [ ] **Step 2: Commit**

### Task 9: Write Tests

**Files:**
- Create: `apps/api/tests/test_async_deployment.py`

**Interfaces:**
- Consumes: All implemented components
- Produces: Comprehensive test coverage

- [ ] **Step 1: Write test for POST returns 202**

```python
@pytest.mark.anyio
async def test_create_deployment_returns_202(client):
    response = await client.post(
        "/api/v1/deployments",
        json={"repository_url": "https://github.com/test/repo"},
    )
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["state"] == "queued"
```

- [ ] **Step 2: Write test for deployment state transitions**

- [ ] **Step 3: Write test for status endpoint**

- [ ] **Step 4: Write test for logs endpoint**

- [ ] **Step 5: Write test for cancellation**

- [ ] **Step 6: Write test for idempotency**

- [ ] **Step 7: Write test for timeout handling**

- [ ] **Step 8: Write test for failure state persistence**

- [ ] **Step 9: Commit**

### Task 10: Run All Tests

- [ ] **Step 1: Run existing tests**

```bash
cd apps/api
pytest tests/ -v
```

- [ ] **Step 2: Run new tests**

```bash
pytest tests/test_async_deployment.py -v
```

- [ ] **Step 3: Verify all tests pass**

### Task 11: Security Verification

- [ ] **Step 1: Verify Celery worker does not bypass sandbox**

- [ ] **Step 2: Verify repository code executes only in containers**

- [ ] **Step 3: Verify no host execution**

- [ ] **Step 4: Verify cleanup on all failure paths**

- [ ] **Step 5: Verify no secrets logged**

### Task 12: Final Commit

- [ ] **Step 1: Create final commit with all changes**
