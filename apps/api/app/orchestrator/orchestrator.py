"""
Deployment orchestrator.

Coordinates the full deployment pipeline:
1. Validate repository URL
2. Clone repository
3. Analyze repository
4. Generate execution plan
5. Build application
6. Start runtime
7. Health check
8. Return result
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.analyzer import analyze_repository
from app.analyzer.types import ExecutionPlan
from app.repository.fetcher import RepositoryFetcher
from app.repository.snapshot import RepositorySnapshot
from app.runtime.executor import BuildExecutor, RuntimeExecutor, BuildResult, RuntimeInstance
from app.runtime.health import HealthChecker, HealthCheckResult
from app.runtime.cleanup import ContainerCleanup
from app.runtime.docker import DockerContainerRuntime
from app.runtime.metrics import ContainerMetrics

from .states import DeploymentState
from .exceptions import DeploymentError, PipelineError, CleanupError

logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    
    deployment_id: str
    state: DeploymentState
    repository_url: str
    commit_sha: Optional[str] = None
    framework: Optional[str] = None
    port: Optional[int] = None
    internal_url: Optional[str] = None
    external_url: Optional[str] = None
    error_message: Optional[str] = None
    error_stage: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Stage timestamps
    cloned_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    plan_generated_at: Optional[datetime] = None
    build_started_at: Optional[datetime] = None
    build_completed_at: Optional[datetime] = None
    runtime_started_at: Optional[datetime] = None
    health_checked_at: Optional[datetime] = None
    
    # Container tracking
    container_id: Optional[str] = None
    build_container_id: Optional[str] = None
    snapshot_path: Optional[str] = None

    # Health and observability
    health_status: Optional[str] = None  # pending, healthy, unhealthy, timeout
    health_response_time_ms: Optional[int] = None
    last_health_check_at: Optional[datetime] = None
    resource_metrics: Optional[ContainerMetrics] = None


class DeploymentOrchestrator:
    """Orchestrates the full deployment pipeline.
    
    This class coordinates:
    - Repository fetching
    - Repository analysis
    - Execution plan generation
    - Build execution
    - Runtime startup
    - Health checking
    - Cleanup
    
    All operations are logged and audited for security.
    """
    
    def __init__(
        self,
        fetcher: Optional[RepositoryFetcher] = None,
        runtime: Optional[DockerContainerRuntime] = None,
        cleanup: Optional[ContainerCleanup] = None,
    ):
        """Initialize the orchestrator.
        
        Args:
            fetcher: Repository fetcher (auto-created if None)
            runtime: Docker container runtime (auto-created if None)
            cleanup: Container cleanup service (auto-created if None)
        """
        self.fetcher = fetcher or RepositoryFetcher()
        self.runtime = runtime or DockerContainerRuntime()
        self.cleanup = cleanup or ContainerCleanup(self.runtime)
        
        # Initialize executors
        self.build_executor = BuildExecutor(self.runtime, self.cleanup)
        self.runtime_executor = RuntimeExecutor(self.runtime, self.cleanup)
        self.health_checker = HealthChecker(self.runtime)
        
    async def deploy(
        self,
        deployment_id: str,
        repository_url: str,
        db: Optional[AsyncSession] = None,
    ) -> DeploymentResult:
        """Execute the full deployment pipeline.
        
        Args:
            deployment_id: Unique deployment identifier
            repository_url: GitHub repository URL
            db: Optional database session for state persistence
            
        Returns:
            DeploymentResult with final state and details
        """
        start_time = datetime.now(timezone.utc)
        result = DeploymentResult(
            deployment_id=deployment_id,
            state=DeploymentState.QUEUED,
            repository_url=repository_url,
            started_at=start_time,
        )
        
        snapshot: Optional[RepositorySnapshot] = None
        container_id: Optional[str] = None
        
        try:
            # 1. Validate URL
            result.state = DeploymentState.CLONING
            self._log_stage_start(deployment_id, "cloning", {"url": repository_url})
            
            # 2. Clone repository
            snapshot = await self.fetcher.fetch(repository_url)
            result.commit_sha = snapshot.commit_sha
            result.snapshot_path = snapshot.local_path
            result.cloned_at = datetime.now(timezone.utc)
            self._log_stage_complete(deployment_id, "cloning", {
                "commit_sha": snapshot.commit_sha,
                "duration": (result.cloned_at - start_time).total_seconds(),
            })
            
            # 3. Analyze repository
            result.state = DeploymentState.ANALYZING
            analysis_start = datetime.now(timezone.utc)
            self._log_stage_start(deployment_id, "analyzing", {
                "local_path": snapshot.local_path,
            })
            
            execution_plan = analyze_repository(
                repo_path=snapshot.local_path,
                url=repository_url,
                commit_sha=snapshot.commit_sha,
                owner=snapshot.owner,
                repo=snapshot.repository,
            )
            result.framework = execution_plan.application.framework
            result.port = execution_plan.runtime.port
            result.analyzed_at = datetime.now(timezone.utc)
            self._log_stage_complete(deployment_id, "analyzing", {
                "framework": result.framework,
                "port": result.port,
                "duration": (result.analyzed_at - analysis_start).total_seconds(),
            })
            
            # 4. Generate execution plan (already done in step 3)
            result.state = DeploymentState.PLANNING
            result.plan_generated_at = datetime.now(timezone.utc)
            self._log_stage_complete(deployment_id, "planning", {
                "plan_valid": True,
            })
            
            # 5. Build application
            result.state = DeploymentState.BUILDING
            build_start = datetime.now(timezone.utc)
            result.build_started_at = build_start
            self._log_stage_start(deployment_id, "building", {
                "framework": result.framework,
            })
            
            # Convert ExecutionPlan to dict for BuildExecutor
            plan_dict = {
                "framework": execution_plan.application.framework,
                "install_steps": [{"command": execution_plan.build.install_command}] if execution_plan.build.install_command else [],
                "build_steps": [{"command": execution_plan.build.build_command}] if execution_plan.build.build_command else [],
                "run_command": execution_plan.runtime.start_command,
                "port": execution_plan.runtime.port,
            }
            
            build_result = await self.build_executor.execute_build(
                deployment_id=deployment_id,
                repo_url=repository_url,
                commit_sha=snapshot.commit_sha,
                execution_plan=plan_dict,
                build_dir=snapshot.local_path,
            )
            
            if not build_result.success:
                result.state = DeploymentState.BUILD_FAILED
                result.error_message = build_result.error
                result.error_stage = "building"
                return result
                
            result.build_container_id = build_result.container_id
            result.build_completed_at = datetime.now(timezone.utc)
            self._log_stage_complete(deployment_id, "building", {
                "image": build_result.image,
                "duration": (result.build_completed_at - build_start).total_seconds(),
            })
            
            # 6. Start runtime
            result.state = DeploymentState.STARTING
            start_runtime_start = datetime.now(timezone.utc)
            result.runtime_started_at = start_runtime_start
            self._log_stage_start(deployment_id, "starting", {
                "image": build_result.image,
                "port": result.port,
            })
            
            runtime_instance = await self.runtime_executor.start_runtime(
                deployment_id=deployment_id,
                build_image=build_result.image,
                execution_plan=plan_dict,
                port=result.port,
            )
            
            container_id = runtime_instance.container_id
            result.container_id = container_id
            result.internal_url = runtime_instance.internal_url
            result.completed_at = datetime.now(timezone.utc)
            self._log_stage_complete(deployment_id, "starting", {
                "container_id": container_id,
                "internal_url": result.internal_url,
                "duration": (result.completed_at - start_runtime_start).total_seconds(),
            })
            
            # 7. Health check
            result.state = DeploymentState.HEALTH_CHECKING
            health_start = datetime.now(timezone.utc)
            result.health_checked_at = health_start
            self._log_stage_start(deployment_id, "health_checking", {
                "container_id": container_id,
            })
            
            health_result = await self.health_checker.check_health(
                container_id=container_id,
                port=result.port,
                path="/",
                timeout=30,
            )
            
            # Record health status on result
            result.health_status = health_result.status
            result.health_response_time_ms = health_result.response_time_ms
            result.last_health_check_at = datetime.now(timezone.utc)
            
            if health_result.status != "healthy":
                result.state = DeploymentState.HEALTH_CHECK_FAILED
                result.error_message = health_result.error or "Health check failed"
                result.error_stage = "health_checking"
                return result
                
            self._log_stage_complete(deployment_id, "health_checking", {
                "healthy": True,
                "response_time_ms": health_result.response_time_ms,
                "duration": (datetime.now(timezone.utc) - health_start).total_seconds(),
            })
            
            # 7b. Collect resource metrics (best-effort)
            try:
                from app.infrastructure.docker_metrics import DockerResourceCollector
                collector = DockerResourceCollector()
                metrics = await collector.collect_metrics(container_id)
                if metrics:
                    result.resource_metrics = metrics
                    self._log_stage_complete(deployment_id, "metrics_collected", {
                        "cpu_percent": metrics.cpu_usage_percent,
                        "memory_percent": metrics.memory_percent,
                    })
            except Exception as metrics_error:
                logger.warning(f"Failed to collect resource metrics: {metrics_error}")
            
            # 8. Success
            result.state = DeploymentState.RUNNING
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - start_time).total_seconds()
            
            self._log_deployment_complete(deployment_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}", exc_info=True)
            
            # Determine appropriate failure state
            if result.state == DeploymentState.CLONING:
                result.state = DeploymentState.CLONE_FAILED
            elif result.state == DeploymentState.ANALYZING:
                result.state = DeploymentState.ANALYSIS_FAILED
            elif result.state == DeploymentState.PLANNING:
                result.state = DeploymentState.PLAN_FAILED
            elif result.state == DeploymentState.BUILDING:
                result.state = DeploymentState.BUILD_FAILED
            elif result.state == DeploymentState.STARTING:
                result.state = DeploymentState.START_FAILED
            elif result.state == DeploymentState.HEALTH_CHECKING:
                result.state = DeploymentState.HEALTH_CHECK_FAILED
            else:
                result.state = DeploymentState.BUILD_FAILED
                
            result.error_message = str(e)
            result.error_stage = result.state.value
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.completed_at - start_time).total_seconds()
            
            return result
            
        finally:
            # Cleanup on all paths
            await self._cleanup_resources(snapshot, container_id)
            
    async def cancel(self, deployment_id: str, container_id: Optional[str] = None) -> DeploymentResult:
        """Cancel a running deployment.
        
        Args:
            deployment_id: Deployment to cancel
            container_id: Optional container ID to stop
            
        Returns:
            DeploymentResult with cancelled state
        """
        logger.info(
            "deployment.cancelled",
            extra={"deployment_id": deployment_id},
        )
        
        # Stop container if provided
        if container_id:
            try:
                await self.runtime.stop_container(container_id)
            except Exception as e:
                logger.warning(f"Failed to stop container: {e}")
                
        return DeploymentResult(
            deployment_id=deployment_id,
            state=DeploymentState.CANCELLED,
            repository_url="",
            completed_at=datetime.now(timezone.utc),
        )
        
    async def _cleanup_resources(
        self,
        snapshot: Optional[RepositorySnapshot],
        container_id: Optional[str],
    ) -> None:
        """Cleanup all resources.
        
        Args:
            snapshot: Repository snapshot to cleanup
            container_id: Container ID to cleanup
        """
        # Cleanup repository snapshot
        if snapshot:
            try:
                await self.fetcher.cleanup(snapshot)
            except Exception as e:
                logger.warning(f"Failed to cleanup snapshot: {e}")
                
        # Container cleanup is handled by BuildExecutor/RuntimeExecutor
        
    def _log_stage_start(
        self,
        deployment_id: str,
        stage: str,
        details: dict,
    ) -> None:
        """Log stage start."""
        logger.info(
            f"deployment.{stage}.started",
            extra={
                "deployment_id": deployment_id,
                "stage": stage,
                **details,
            },
        )
        
    def _log_stage_complete(
        self,
        deployment_id: str,
        stage: str,
        details: dict,
    ) -> None:
        """Log stage completion."""
        logger.info(
            f"deployment.{stage}.completed",
            extra={
                "deployment_id": deployment_id,
                "stage": stage,
                **details,
            },
        )
        
    def _log_deployment_complete(
        self,
        deployment_id: str,
        result: DeploymentResult,
    ) -> None:
        """Log deployment completion."""
        logger.info(
            "deployment.completed",
            extra={
                "state": result.state.value,
                "duration_seconds": result.duration_seconds,
                "framework": result.framework,
                "port": result.port,
            },
        )