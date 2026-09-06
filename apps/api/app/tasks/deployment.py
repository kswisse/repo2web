import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.services.deployment import DeploymentServiceSync
from app.services.deployment_metrics import DeploymentMetricsServiceSync
from app.services.deployment_health import DeploymentHealthServiceSync
from app.orchestrator.orchestrator import DeploymentOrchestrator
from app.orchestrator.states import DeploymentState

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=1,
    soft_time_limit=600,  # 10 minutes
    time_limit=660,
    acks_late=True,
)
def execute_deployment(self, deployment_id: str):
    """Execute a deployment asynchronously.
    
    This task:
    1. Loads deployment from database
    2. Checks if already running (idempotency)
    3. Calls orchestrator to execute pipeline
    4. Updates deployment state
    5. Handles cleanup on failure
    """
    service = DeploymentServiceSync()
    metrics_service = DeploymentMetricsServiceSync()
    health_service = DeploymentHealthServiceSync()
    
    try:
        # 1. Load deployment from database
        deployment = service.get(deployment_id)
        
        # 2. Check if already running (idempotency)
        if deployment.state != "queued":
            logger.info(
                f"Deployment {deployment_id} already in state {deployment.state}, skipping"
            )
            return {
                "deployment_id": deployment_id,
                "status": "skipped",
                "reason": f"Deployment already in state: {deployment.state}",
            }
        
        # 3. Update state to cloning
        service.update_state(deployment_id, "cloning")
        
        # 4. Run orchestrator
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
            
            # 5. Update deployment with result
            service.update_from_result(deployment_id, result)
            
            # 5b. Persist health check record if available
            if result.health_status:
                try:
                    from app.runtime.health import HealthCheckResult
                    health_result = HealthCheckResult(
                        status=result.health_status,
                        response_time_ms=result.health_response_time_ms,
                        status_code=200 if result.health_status == "healthy" else None,
                        attempts=1,
                    )
                    health_service.record_health_check(
                        deployment_id,
                        health_result,
                        is_final=True,
                    )
                except Exception as health_error:
                    logger.warning(f"Failed to persist health check: {health_error}")
            
            # 5c. Persist resource metrics if available
            if result.resource_metrics:
                try:
                    metrics_service.record_metrics(
                        deployment_id,
                        result.resource_metrics,
                    )
                except Exception as metrics_error:
                    logger.warning(f"Failed to persist metrics: {metrics_error}")
            
            logger.info(
                f"Deployment {deployment_id} completed with state {result.state.value}"
            )
            
            return {
                "deployment_id": deployment_id,
                "status": result.state.value,
                "framework": result.framework,
                "port": result.port,
            }
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Deployment {deployment_id} failed: {e}", exc_info=True)
        
        # 6. Update state on failure
        try:
            service.update_state(
                deployment_id, "build_failed", str(e)
            )
        except Exception as update_error:
            logger.error(f"Failed to update deployment state: {update_error}")
        
        raise
    finally:
        service.close()
        metrics_service.close()
        health_service.close()