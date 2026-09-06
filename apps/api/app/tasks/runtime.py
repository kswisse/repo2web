import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, time_limit=300)
def start_runtime_task(self, deployment_id: str, build_image: str, plan: dict, port: int = 8000):
    """
    Start runtime container.
    
    Args:
        deployment_id: Deployment ID
        build_image: Docker image from build
        plan: Execution plan
        port: Port to expose
    """
    try:
        from app.runtime.docker import DockerContainerRuntime
        from app.runtime.executor import RuntimeExecutor
        from app.core.config import get_settings
        
        settings = get_settings()
        
        # Initialize runtime
        runtime = DockerContainerRuntime(base_url=settings.DOCKER_SOCKET)
        executor = RuntimeExecutor(runtime)
        
        # Run async start in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                executor.start_runtime(
                    deployment_id=deployment_id,
                    build_image=build_image,
                    execution_plan=plan,
                    port=port,
                )
            )
            
            return {
                "deployment_id": deployment_id,
                "status": result.status,
                "container_id": result.container_id,
                "port": result.port,
                "internal_url": result.internal_url,
            }
        finally:
            loop.close()
            
    except Exception as e:
        return {
            "deployment_id": deployment_id,
            "status": "failed",
            "error": str(e),
        }
