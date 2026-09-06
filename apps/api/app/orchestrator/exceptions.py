"""
Orchestration exceptions.

Exceptions specific to the deployment pipeline orchestration.
"""


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""
    pass


class DeploymentError(OrchestrationError):
    """Raised when deployment operation fails."""
    
    def __init__(self, deployment_id: str, message: str, stage: str = None):
        self.deployment_id = deployment_id
        self.stage = stage
        super().__init__(f"Deployment {deployment_id} failed: {message}")


class PipelineError(OrchestrationError):
    """Raised when pipeline step fails."""
    
    def __init__(self, stage: str, message: str, details: dict = None):
        self.stage = stage
        self.details = details or {}
        super().__init__(f"Pipeline stage '{stage}' failed: {message}")


class CleanupError(OrchestrationError):
    """Raised when cleanup operation fails."""
    
    def __init__(self, resource: str, message: str):
        self.resource = resource
        super().__init__(f"Cleanup failed for {resource}: {message}")
