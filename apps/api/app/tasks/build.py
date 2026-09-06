import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, time_limit=600)
def build_repository_task(self, deployment_id: str, repo_url: str, commit_sha: str, plan: dict, build_dir: str):
    """
    Build repository in a container.
    
    Args:
        deployment_id: Deployment ID
        repo_url: Repository URL
        commit_sha: Commit SHA
        plan: Execution plan
        build_dir: Path to cloned repository
    """
    try:
        from app.services.build import BuildService
        
        build_service = BuildService()
        
        # Run async build in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                build_service.execute_build(
                    deployment_id=deployment_id,
                    repo_url=repo_url,
                    commit_sha=commit_sha,
                    execution_plan=plan,
                    build_dir=build_dir,
                )
            )
            
            return {
                "deployment_id": deployment_id,
                "status": "completed" if result.success else "failed",
                "message": "Build completed successfully" if result.success else result.error,
                "container_id": result.container_id,
                "duration_seconds": result.duration_seconds,
                "security_violations": result.security_violations,
            }
        finally:
            loop.close()
            
    except Exception as e:
        return {
            "deployment_id": deployment_id,
            "status": "failed",
            "error": str(e),
        }
