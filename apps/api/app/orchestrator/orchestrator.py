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

Phase 2.9 adds:
- Bounded repair loop for supported deployment failures
- Deterministic repair proposals validated before execution
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.analyzer import analyze_repository
from app.analyzer.types import (
    ApplicationInfo,
    BuildInfo,
    CompatibilityResult,
    ExecutionPlan,
    RuntimeInfo,
)
from app.repository.fetcher import RepositoryFetcher
from app.repository.snapshot import RepositorySnapshot
from app.repair.deterministic import DeterministicRepairProvider
from app.repair.loop import RepairLoop
from app.repair.types import RepairContext, RepairType
from app.repair.validator import validate_repair_proposal
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

    # Repair tracking
    repair_attempted: bool = False
    repair_attempts: int = 0
    repair_proposal_type: Optional[str] = None
    repair_final_result: Optional[str] = None  # "repaired", "rejected", "exhausted", "failed"


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
        
        # Initialize repair loop (Phase 2.9)
        self.repair_loop = RepairLoop(DeterministicRepairProvider())
        
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
        build_image: Optional[str] = None
        execution_plan: Optional[ExecutionPlan] = None
        file_names: list[str] = []
        
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
            
            # Capture file names for repair context
            try:
                from app.analyzer.file_inventory import scan_repository
                from pathlib import Path as _Path
                inv = scan_repository(snapshot.local_path)
                file_names = [_Path(f).name for f in inv.files[:50]]
            except Exception:
                file_names = []
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
                # Phase 2.9: Attempt repair for supported failures
                repaired_plan = await self._attempt_build_repair(
                    deployment_id=deployment_id,
                    execution_plan=execution_plan,
                    build_error=build_result.error or "Build failed",
                    file_names=file_names,
                    result=result,
                    snapshot=snapshot,
                    start_time=start_time,
                )
                
                if repaired_plan is not None:
                    # Repair succeeded — retry build with repaired plan
                    execution_plan = repaired_plan
                    result.framework = repaired_plan.application.framework
                    result.port = repaired_plan.runtime.port
                    result.state = DeploymentState.BUILDING
                    
                    plan_dict = {
                        "framework": repaired_plan.application.framework,
                        "install_steps": [{"command": repaired_plan.build.install_command}] if repaired_plan.build.install_command else [],
                        "build_steps": [{"command": repaired_plan.build.build_command}] if repaired_plan.build.build_command else [],
                        "run_command": repaired_plan.runtime.start_command,
                        "port": repaired_plan.runtime.port,
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
                        result.repair_final_result = "failed"
                        return result
                else:
                    # No repair possible or all attempts exhausted
                    result.state = DeploymentState.BUILD_FAILED
                    result.error_message = build_result.error
                    result.error_stage = "building"
                    if result.repair_final_result is None:
                        result.repair_final_result = "unsupported"
                    return result
                
            result.build_container_id = build_result.container_id
            result.build_completed_at = datetime.now(timezone.utc)
            build_image = build_result.image
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
                # Phase 2.9: Attempt repair for health check failures
                repaired_plan = await self._attempt_health_repair(
                    deployment_id=deployment_id,
                    execution_plan=execution_plan,
                    health_error=health_result.error or "Health check failed",
                    file_names=file_names,
                    result=result,
                )
                
                if repaired_plan is not None:
                    # Repair succeeded — retry with repaired plan
                    execution_plan = repaired_plan
                    result.framework = repaired_plan.application.framework
                    result.port = repaired_plan.runtime.port
                    
                    # Retry health check with repaired path
                    health_result = await self.health_checker.check_health(
                        container_id=container_id,
                        port=result.port,
                        path=repaired_plan.runtime.health_check_path,
                        timeout=30,
                    )
                    
                    result.health_status = health_result.status
                    result.health_response_time_ms = health_result.response_time_ms
                    result.last_health_check_at = datetime.now(timezone.utc)
                    
                    if health_result.status != "healthy":
                        result.state = DeploymentState.HEALTH_CHECK_FAILED
                        result.error_message = health_result.error or "Health check failed after repair"
                        result.error_stage = "health_checking"
                        result.repair_final_result = "failed"
                        return result
                else:
                    # No repair possible or all attempts exhausted
                    result.state = DeploymentState.HEALTH_CHECK_FAILED
                    result.error_message = health_result.error or "Health check failed"
                    result.error_stage = "health_checking"
                    if result.repair_final_result is None:
                        result.repair_final_result = "unsupported"
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
            # Note: build_image is NOT cleaned up here - it persists while runtime runs.
            # The image is referenced by the runtime container and will be cleaned up
            # when the container is destroyed.
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

    # ---- Phase 2.9: Repair Integration ----

    def _build_repair_context(
        self,
        execution_plan: ExecutionPlan,
        failure_stage: str,
        failure_error: str,
        file_names: list[str],
    ) -> RepairContext:
        """Create a bounded RepairContext from an ExecutionPlan and failure info.

        Only exposes information permitted for repair analysis.
        Never exposes secrets, credentials, or internal paths.

        Args:
            execution_plan: The current execution plan.
            failure_stage: The stage where deployment failed.
            failure_error: The error message from the failure.
            file_names: Key file names in the repository.

        Returns:
            RepairContext with bounded information.
        """
        return RepairContext(
            framework=execution_plan.application.framework,
            language=execution_plan.application.language,
            package_manager=execution_plan.build.package_manager,
            start_command=execution_plan.runtime.start_command,
            health_check_path=execution_plan.runtime.health_check_path,
            port=execution_plan.runtime.port,
            install_command=execution_plan.build.install_command,
            build_command=execution_plan.build.build_command,
            failure_stage=failure_stage,
            failure_error=failure_error[:500],  # Bounded error message
            repository_url=execution_plan.repository.url,
            evidence_summary=[e.value for e in execution_plan.evidence[:10]],
            file_names=file_names[:50],  # Bounded file list
        )

    def _apply_repair_proposal(
        self,
        execution_plan: ExecutionPlan,
        proposal,
    ) -> ExecutionPlan:
        """Apply a validated repair proposal to an ExecutionPlan.

        Creates a new immutable ExecutionPlan with the repaired values.
        The original plan is never modified.

        Args:
            execution_plan: The original execution plan.
            proposal: The validated repair proposal.

        Returns:
            New ExecutionPlan with repaired values.
        """
        # Build new application info if framework changed
        application = execution_plan.application
        if proposal.repair_type == RepairType.FRAMEWORK_DETECTION:
            application = ApplicationInfo(
                language=execution_plan.application.language,
                framework=proposal.proposed_value,
                framework_version=execution_plan.application.framework_version,
                confidence="HIGH",
            )

        # Build new build info if install/build command changed
        build = execution_plan.build
        if proposal.repair_type == RepairType.INSTALL_COMMAND:
            build = BuildInfo(
                package_manager=execution_plan.build.package_manager,
                install_command=proposal.proposed_value,
                build_command=execution_plan.build.build_command,
                working_directory=execution_plan.build.working_directory,
            )
        elif proposal.repair_type == RepairType.BUILD_COMMAND:
            build = BuildInfo(
                package_manager=execution_plan.build.package_manager,
                install_command=execution_plan.build.install_command,
                build_command=proposal.proposed_value,
                working_directory=execution_plan.build.working_directory,
            )
        elif proposal.repair_type == RepairType.PACKAGE_MANAGER:
            build = BuildInfo(
                package_manager=proposal.proposed_value,
                install_command=execution_plan.build.install_command,
                build_command=execution_plan.build.build_command,
                working_directory=execution_plan.build.working_directory,
            )

        # Build new runtime info if start command/port/health path changed
        runtime = execution_plan.runtime
        if proposal.repair_type == RepairType.START_COMMAND:
            runtime = RuntimeInfo(
                start_command=proposal.proposed_value,
                port=execution_plan.runtime.port,
                host=execution_plan.runtime.host,
                health_check_path=execution_plan.runtime.health_check_path,
            )
        elif proposal.repair_type == RepairType.PORT:
            runtime = RuntimeInfo(
                start_command=execution_plan.runtime.start_command,
                port=int(proposal.proposed_value),
                host=execution_plan.runtime.host,
                health_check_path=execution_plan.runtime.health_check_path,
            )
        elif proposal.repair_type == RepairType.HEALTH_CHECK_PATH:
            runtime = RuntimeInfo(
                start_command=execution_plan.runtime.start_command,
                port=execution_plan.runtime.port,
                host=execution_plan.runtime.host,
                health_check_path=proposal.proposed_value,
            )

        # Validate the repaired plan
        from app.analyzer.plan_validator import validate_plan
        repaired_plan = ExecutionPlan(
            repository=execution_plan.repository,
            application=application,
            build=build,
            runtime=runtime,
            environment=execution_plan.environment,
            services=execution_plan.services,
            compatibility=execution_plan.compatibility,
            evidence=execution_plan.evidence,
            created_at=execution_plan.created_at,
        )

        validation = validate_plan(repaired_plan)
        if not validation.valid:
            logger.warning(
                "repair.repaired_plan_invalid",
                extra={"errors": validation.errors},
            )
            # Return original plan if repaired plan is invalid
            return execution_plan

        return repaired_plan

    async def _attempt_build_repair(
        self,
        deployment_id: str,
        execution_plan: ExecutionPlan,
        build_error: str,
        file_names: list[str],
        result: DeploymentResult,
        snapshot: RepositorySnapshot,
        start_time: datetime,
    ) -> Optional[ExecutionPlan]:
        """Attempt to repair a build failure.

        Args:
            deployment_id: Deployment identifier.
            execution_plan: The failed execution plan.
            build_error: The build error message.
            file_names: Key file names in the repo.
            result: The deployment result to update.
            snapshot: Repository snapshot for retry.
            start_time: Deployment start time.

        Returns:
            Repaired ExecutionPlan if repair succeeded, None otherwise.
        """
        if not self.repair_loop.can_repair("build"):
            return None

        repair_context = self._build_repair_context(
            execution_plan=execution_plan,
            failure_stage="build",
            failure_error=build_error,
            file_names=file_names,
        )

        for attempt in range(self.repair_loop.max_attempts()):
            result.repair_attempted = True
            result.repair_attempts = attempt + 1

            self._log_stage_start(deployment_id, "repairing", {
                "attempt": attempt,
                "failure_stage": "build",
            })

            repair_result = self.repair_loop.attempt_repair(repair_context, attempt)

            if repair_result.proposal is None:
                # No proposal — either unsupported or engine error
                result.repair_final_result = "no_proposal"
                self._log_stage_complete(deployment_id, "repairing", {
                    "attempt": attempt,
                    "result": "no_proposal",
                    "error": repair_result.error,
                })
                break

            if not repair_result.accepted:
                # Proposal rejected by validator
                result.repair_proposal_type = repair_result.proposal.repair_type.value
                result.repair_final_result = "rejected"
                self._log_stage_complete(deployment_id, "repairing", {
                    "attempt": attempt,
                    "result": "rejected",
                    "repair_type": repair_result.proposal.repair_type.value,
                    "reject_reason": repair_result.reject_reason,
                })
                break

            # Proposal accepted — apply it
            result.repair_proposal_type = repair_result.proposal.repair_type.value
            repaired_plan = self._apply_repair_proposal(execution_plan, repair_result.proposal)

            self._log_stage_complete(deployment_id, "repairing", {
                "attempt": attempt,
                "result": "accepted",
                "repair_type": repair_result.proposal.repair_type.value,
                "target": repair_result.proposal.target,
                "proposed_value": repair_result.proposal.proposed_value,
            })

            # Return the repaired plan for retry
            return repaired_plan

        # All attempts exhausted or no repair possible
        if result.repair_final_result is None:
            result.repair_final_result = "exhausted"
        return None

    async def _attempt_health_repair(
        self,
        deployment_id: str,
        execution_plan: ExecutionPlan,
        health_error: str,
        file_names: list[str],
        result: DeploymentResult,
    ) -> Optional[ExecutionPlan]:
        """Attempt to repair a health check failure.

        Args:
            deployment_id: Deployment identifier.
            execution_plan: The failed execution plan.
            health_error: The health check error message.
            file_names: Key file names in the repo.
            result: The deployment result to update.

        Returns:
            Repaired ExecutionPlan if repair succeeded, None otherwise.
        """
        if not self.repair_loop.can_repair("health_checking"):
            return None

        repair_context = self._build_repair_context(
            execution_plan=execution_plan,
            failure_stage="health_checking",
            failure_error=health_error,
            file_names=file_names,
        )

        for attempt in range(self.repair_loop.max_attempts()):
            result.repair_attempted = True
            result.repair_attempts = attempt + 1

            self._log_stage_start(deployment_id, "repairing", {
                "attempt": attempt,
                "failure_stage": "health_checking",
            })

            repair_result = self.repair_loop.attempt_repair(repair_context, attempt)

            if repair_result.proposal is None:
                result.repair_final_result = "no_proposal"
                self._log_stage_complete(deployment_id, "repairing", {
                    "attempt": attempt,
                    "result": "no_proposal",
                    "error": repair_result.error,
                })
                break

            if not repair_result.accepted:
                result.repair_proposal_type = repair_result.proposal.repair_type.value
                result.repair_final_result = "rejected"
                self._log_stage_complete(deployment_id, "repairing", {
                    "attempt": attempt,
                    "result": "rejected",
                    "repair_type": repair_result.proposal.repair_type.value,
                    "reject_reason": repair_result.reject_reason,
                })
                break

            # Proposal accepted — apply it
            result.repair_proposal_type = repair_result.proposal.repair_type.value
            repaired_plan = self._apply_repair_proposal(execution_plan, repair_result.proposal)

            self._log_stage_complete(deployment_id, "repairing", {
                "attempt": attempt,
                "result": "accepted",
                "repair_type": repair_result.proposal.repair_type.value,
                "target": repair_result.proposal.target,
                "proposed_value": repair_result.proposal.proposed_value,
            })

            return repaired_plan

        if result.repair_final_result is None:
            result.repair_final_result = "exhausted"
        return None