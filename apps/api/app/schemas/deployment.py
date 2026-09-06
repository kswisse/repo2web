from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.build import BuildJobResponse
from app.schemas.analysis import AnalysisResultResponse


class DeploymentCreate(BaseModel):
    """Request to create a deployment."""
    repository_url: str = Field(..., description="GitHub repository URL")
    # Keep old fields for backward compatibility
    repository_id: Optional[str] = None
    snapshot_id: Optional[str] = None


class DeploymentResponse(BaseModel):
    """Response for deployment operations."""
    id: str
    repository_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    state: str
    repository_url: Optional[str] = None
    commit_sha: Optional[str] = None
    framework: Optional[str] = None
    port: Optional[int] = None
    start_command: Optional[str] = None
    error_message: Optional[str] = None
    error_stage: Optional[str] = None
    container_id: Optional[str] = None
    build_container_id: Optional[str] = None
    snapshot_path: Optional[str] = None
    celery_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    # Stage timestamps
    cloned_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    plan_generated_at: Optional[datetime] = None
    build_started_at: Optional[datetime] = None
    build_completed_at: Optional[datetime] = None
    runtime_started_at: Optional[datetime] = None
    health_checked_at: Optional[datetime] = None

    # Health and observability
    health_status: Optional[str] = None
    health_response_time_ms: Optional[int] = None
    last_health_check_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeploymentDetailResponse(DeploymentResponse):
    """Detailed deployment response with related objects."""
    build_job: Optional[BuildJobResponse] = None
    analysis: Optional[AnalysisResultResponse] = None
    resource_metrics: Optional["ResourceMetricsResponse"] = None


class ResourceMetricsResponse(BaseModel):
    """Resource metrics snapshot response."""
    cpu_usage_percent: Optional[float] = None
    memory_usage_bytes: Optional[int] = None
    memory_limit_bytes: Optional[int] = None
    memory_percent: Optional[float] = None
    network_rx_bytes: Optional[int] = None
    network_tx_bytes: Optional[int] = None
    container_status: Optional[str] = None
    uptime_seconds: Optional[int] = None
    timestamp: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeploymentLogEntry(BaseModel):
    """Single deployment log entry."""
    id: str
    deployment_id: str
    stage: str
    level: str
    message: str
    timestamp: datetime
    sequence: int

    model_config = {"from_attributes": True}


class DeploymentLogsResponse(BaseModel):
    """Deployment logs response."""
    logs: list[DeploymentLogEntry]
    total: int


class CreateDeploymentRequest(BaseModel):
    """Request to create a deployment from URL."""
    repository_url: str = Field(..., description="GitHub repository URL")
