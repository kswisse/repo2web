"""
Repository-related exceptions.

All exceptions are specific and provide actionable error messages.
"""


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class RepositoryCloneError(RepositoryError):
    """Raised when repository cloning fails."""
    
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to clone {url}: {reason}")


class RepositoryValidationError(RepositoryError):
    """Raised when repository URL validation fails."""
    
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Invalid repository URL {url}: {reason}")


class RepositoryTimeoutError(RepositoryError):
    """Raised when repository operation times out."""
    
    def __init__(self, url: str, timeout: int):
        self.url = url
        self.timeout = timeout
        super().__init__(f"Repository operation timed out after {timeout}s for {url}")


class RepositoryCleanupError(RepositoryError):
    """Raised when cleanup of repository artifacts fails."""
    
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to cleanup {path}: {reason}")
