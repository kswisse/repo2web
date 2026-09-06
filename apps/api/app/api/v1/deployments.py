from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user_id
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentLogsResponse,
    DeploymentLogEntry,
    CreateDeploymentRequest,
    ResourceMetricsResponse,
)
from app.services.deployment import DeploymentService
from app.services.deployment_log import DeploymentLogService
from app.services.deployment_metrics import DeploymentMetricsService
from app.services.deployment_health import DeploymentHealthService
from app.tasks.deployment import execute_deployment

router = APIRouter()


@router.post("", response_model=DeploymentResponse, status_code=202)
async def create_deployment(
    request: CreateDeploymentRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create a deployment (async).
    
    This endpoint:
    1. Creates a deployment record in QUEUED state
    2. Enqueues a Celery task for async execution
    3. Returns immediately with 202 and deployment_id
    
    The deployment will be processed asynchronously by a Celery worker.
    Poll the GET endpoint to check status.
    """
    # Create deployment record
    service = DeploymentService(db)
    deployment = await service.create_from_url(
        repository_url=request.repository_url,
        user_id=user_id,
    )
    await db.commit()
    
    # Enqueue Celery task
    task = execute_deployment.delay(deployment.id)
    
    # Update deployment with task ID
    deployment.celery_task_id = task.id
    await db.commit()
    
    return deployment


@router.post("/legacy", response_model=DeploymentResponse)
async def create_deployment_legacy(
    request: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create a deployment (legacy endpoint)."""
    service = DeploymentService(db)
    deployment = await service.create(
        repository_id=request.repository_id,
        snapshot_id=request.snapshot_id,
        user_id=user_id,
    )
    await db.commit()
    return deployment


@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get deployment status with metrics."""
    service = DeploymentService(db)
    deployment = await service.get(deployment_id)
    
    # Attach latest resource metrics if available
    resource_metrics = None
    try:
        metrics_service = DeploymentMetricsService(db)
        latest_metrics = await metrics_service.get_latest_metrics(deployment_id)
        if latest_metrics:
            resource_metrics = ResourceMetricsResponse(
                cpu_usage_percent=latest_metrics.cpu_usage_percent,
                memory_usage_bytes=latest_metrics.memory_usage_bytes,
                memory_limit_bytes=latest_metrics.memory_limit_bytes,
                memory_percent=latest_metrics.memory_percent,
                network_rx_bytes=latest_metrics.network_rx_bytes,
                network_tx_bytes=latest_metrics.network_tx_bytes,
                container_status=latest_metrics.container_status,
                uptime_seconds=latest_metrics.uptime_seconds,
                timestamp=latest_metrics.timestamp,
            )
    except Exception:
        # Metrics are optional; don't fail the endpoint
        pass
    
    return DeploymentDetailResponse(
        id=str(deployment.id),
        repository_id=str(deployment.repository_id) if deployment.repository_id else None,
        snapshot_id=str(deployment.snapshot_id) if deployment.snapshot_id else None,
        state=deployment.state,
        repository_url=deployment.repository_url,
        commit_sha=deployment.commit_sha,
        framework=deployment.framework,
        port=deployment.port,
        start_command=deployment.start_command,
        error_message=deployment.error_message,
        error_stage=deployment.error_stage,
        container_id=deployment.container_id,
        build_container_id=deployment.build_container_id,
        snapshot_path=deployment.snapshot_path,
        celery_task_id=deployment.celery_task_id,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        completed_at=deployment.completed_at,
        cloned_at=deployment.cloned_at,
        analyzed_at=deployment.analyzed_at,
        plan_generated_at=deployment.plan_generated_at,
        build_started_at=deployment.build_started_at,
        build_completed_at=deployment.build_completed_at,
        runtime_started_at=deployment.runtime_started_at,
        health_checked_at=deployment.health_checked_at,
        health_status=deployment.health_status,
        health_response_time_ms=deployment.health_response_time_ms,
        last_health_check_at=deployment.last_health_check_at,
        resource_metrics=resource_metrics,
    )


@router.get("/{deployment_id}/logs", response_model=DeploymentLogsResponse)
async def get_deployment_logs(
    deployment_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get deployment logs."""
    service = DeploymentService(db)
    deployment = await service.get(deployment_id)
    
    log_service = DeploymentLogService(db)
    logs = await log_service.get_logs(deployment_id, limit=limit)
    
    log_entries = [
        DeploymentLogEntry(
            id=str(log.id),
            deployment_id=str(log.deployment_id),
            stage=log.stage,
            level=log.level,
            message=log.message,
            timestamp=log.timestamp,
            sequence=log.sequence,
        )
        for log in logs
    ]
    
    return DeploymentLogsResponse(
        logs=log_entries,
        total=len(log_entries),
    )


@router.delete("/{deployment_id}", response_model=DeploymentResponse)
async def cancel_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Cancel a running deployment."""
    service = DeploymentService(db)
    deployment = await service.get(deployment_id)
    
    # Check if deployment can be cancelled
    from app.services.deployment import TERMINAL_STATES
    if deployment.state in TERMINAL_STATES:
        return deployment
    
    # Update state to cancelled
    await service.update_state(deployment_id, "cancelled")
    
    # If there's a Celery task, revoke it
    if deployment.celery_task_id:
        from app.tasks.celery_app import celery_app
        celery_app.control.revoke(
            deployment.celery_task_id,
            terminate=True,
            signal='SIGTERM',
        )
    
    # If there's a running container, stop it
    if deployment.container_id:
        from app.runtime.docker import DockerContainerRuntime
        runtime = DockerContainerRuntime()
        try:
            await runtime.stop_container(deployment.container_id)
        except Exception:
            pass
    
    await db.commit()
    
    # Refresh to get updated state
    deployment = await service.get(deployment_id)
    return deployment