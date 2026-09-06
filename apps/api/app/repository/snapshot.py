"""
Repository snapshot dataclass.

Represents a cloned repository at a specific commit.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RepositorySnapshot:
    """Immutable snapshot of a cloned repository.
    
    Attributes:
        repository_url: Original GitHub URL
        owner: Repository owner
        repository: Repository name
        commit_sha: Pinned commit SHA
        local_path: Path to local clone
        created_at: ISO timestamp of snapshot creation
    """
    repository_url: str
    owner: str
    repository: str
    commit_sha: str
    local_path: str
    created_at: str

    def __post_init__(self):
        """Validate snapshot data."""
        if not self.repository_url:
            raise ValueError("repository_url is required")
        if not self.owner:
            raise ValueError("owner is required")
        if not self.repository:
            raise ValueError("repository is required")
        if not self.commit_sha:
            raise ValueError("commit_sha is required")
        if not self.local_path:
            raise ValueError("local_path is required")
        if not self.created_at:
            raise ValueError("created_at is required")

    @classmethod
    def create(
        cls,
        repository_url: str,
        owner: str,
        repository: str,
        commit_sha: str,
        local_path: str,
    ) -> "RepositorySnapshot":
        """Create a new snapshot with current timestamp.
        
        Args:
            repository_url: Original GitHub URL
            owner: Repository owner
            repository: Repository name
            commit_sha: Pinned commit SHA
            local_path: Path to local clone
            
        Returns:
            New RepositorySnapshot instance
        """
        return cls(
            repository_url=repository_url,
            owner=owner,
            repository=repository,
            commit_sha=commit_sha,
            local_path=local_path,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
