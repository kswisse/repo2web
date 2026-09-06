"""
Repository fetcher for cloning GitHub repositories.

Provides secure repository cloning with:
- URL validation (GitHub HTTPS only)
- Timeout enforcement
- Commit SHA pinning
- Cleanup on failure
- No code execution
"""

import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .snapshot import RepositorySnapshot
from .exceptions import (
    RepositoryCloneError,
    RepositoryValidationError,
    RepositoryTimeoutError,
    RepositoryCleanupError,
)

logger = logging.getLogger(__name__)

# GitHub HTTPS URL pattern
GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?$"
)

# Blocked patterns for security
BLOCKED_PATTERNS = [
    r"^file://",
    r"^ssh://",
    r"^git://",
    r"^http://(?!localhost)",  # Non-HTTPS (except localhost for dev)
    r"@[a-zA-Z0-9]",  # Embedded credentials
    r"localhost",
    r"127\.",
    r"0\.0\.0\.0",
    r"10\.",
    r"172\.(1[6-9]|2[0-9]|3[01])\.",
    r"192\.168\.",
]


class RepositoryFetcher:
    """Fetches and clones GitHub repositories.
    
    This class handles:
    - URL validation
    - Repository cloning (shallow clone)
    - Commit SHA resolution
    - Temporary directory management
    - Cleanup on failure
    
    Security:
    - Only allows GitHub HTTPS URLs
    - Blocks internal IPs and localhost
    - Never executes repository code
    - Enforces timeouts
    - Cleans up on all failure paths
    """
    
    def __init__(self, timeout: int = 60, base_dir: Optional[str] = None):
        """Initialize the repository fetcher.
        
        Args:
            timeout: Clone timeout in seconds (default: 60)
            base_dir: Base directory for clones (default: system temp dir)
        """
        self.timeout = timeout
        self.base_dir = base_dir or tempfile.gettempdir()
        
    async def fetch(
        self,
        url: str,
        target_dir: Optional[str] = None,
    ) -> RepositorySnapshot:
        """Fetch a repository and create a snapshot.
        
        Args:
            url: GitHub repository URL
            target_dir: Optional target directory (auto-generated if None)
            
        Returns:
            RepositorySnapshot with clone information
            
        Raises:
            RepositoryValidationError: If URL is invalid
            RepositoryCloneError: If clone fails
            RepositoryTimeoutError: If operation times out
        """
        # 1. Validate URL
        self._validate_url(url)
        
        # 2. Extract owner and repo
        owner, repo = self._extract_owner_repo(url)
        
        # 3. Create target directory
        if target_dir is None:
            target_dir = self._create_target_dir(owner, repo)
        
        try:
            # 4. Clone repository
            await self._clone_repository(url, target_dir)
            
            # 5. Resolve commit SHA
            commit_sha = await self._resolve_commit_sha(target_dir)
            
            # 6. Create snapshot
            snapshot = RepositorySnapshot.create(
                repository_url=url,
                owner=owner,
                repository=repo,
                commit_sha=commit_sha,
                local_path=target_dir,
            )
            
            logger.info(
                "repository.clone.completed",
                extra={
                    "url": url,
                    "commit_sha": commit_sha,
                    "local_path": target_dir,
                },
            )
            
            return snapshot
            
        except Exception as e:
            # Cleanup on failure
            await self._cleanup_on_failure(target_dir)
            raise
            
    def _validate_url(self, url: str) -> None:
        """Validate repository URL.
        
        Args:
            url: Repository URL to validate
            
        Raises:
            RepositoryValidationError: If URL is invalid
        """
        if not url:
            raise RepositoryValidationError(url, "URL is empty")
            
        # Check GitHub HTTPS pattern
        if not GITHUB_URL_PATTERN.match(url):
            raise RepositoryValidationError(
                url,
                "Must be a valid GitHub HTTPS URL: https://github.com/owner/repo"
            )
            
        # Check blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                raise RepositoryValidationError(
                    url,
                    f"URL matches blocked pattern: {pattern}"
                )
                
    def _extract_owner_repo(self, url: str) -> tuple[str, str]:
        """Extract owner and repository name from URL.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repository)
        """
        parts = url.rstrip("/").split("/")
        owner = parts[-2]
        repo = parts[-1].removesuffix(".git")
        return owner, repo
        
    def _create_target_dir(self, owner: str, repo: str) -> str:
        """Create target directory for clone.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Path to created directory
        """
        # Create unique directory name
        import uuid
        dir_name = f"{owner}_{repo}_{uuid.uuid4().hex[:8]}"
        target_dir = os.path.join(self.base_dir, dir_name)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir
        
    async def _clone_repository(self, url: str, target_dir: str) -> None:
        """Clone repository with shallow clone.
        
        Args:
            url: Repository URL
            target_dir: Target directory
            
        Raises:
            RepositoryCloneError: If clone fails
            RepositoryTimeoutError: If clone times out
        """
        cmd = ["git", "clone", "--depth", "1", url, target_dir]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RepositoryTimeoutError(url, self.timeout)
                
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RepositoryCloneError(url, error_msg)
                
        except asyncio.TimeoutError:
            raise RepositoryTimeoutError(url, self.timeout)
        except RepositoryCloneError:
            raise
        except Exception as e:
            raise RepositoryCloneError(url, str(e))
            
    async def _resolve_commit_sha(self, repo_path: str) -> str:
        """Resolve commit SHA of cloned repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Commit SHA string
            
        Raises:
            RepositoryCloneError: If SHA resolution fails
        """
        cmd = ["git", "rev-parse", "HEAD"]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10,
            )
            
            if process.returncode != 0:
                raise RepositoryCloneError(
                    repo_path,
                    f"Failed to resolve commit SHA: {stderr.decode().strip()}"
                )
                
            sha = stdout.decode().strip()
            if not sha or len(sha) != 40:
                raise RepositoryCloneError(
                    repo_path,
                    f"Invalid commit SHA: {sha}"
                )
                
            return sha
            
        except asyncio.TimeoutError:
            raise RepositoryCloneError(
                repo_path,
                "Timeout resolving commit SHA"
            )
        except Exception as e:
            raise RepositoryCloneError(repo_path, str(e))
            
    async def _cleanup_on_failure(self, path: str) -> None:
        """Cleanup directory on failure.
        
        Args:
            path: Directory to cleanup
        """
        if not path or not os.path.exists(path):
            return
            
        try:
            # Use asyncio to run shutil.rmtree in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._rmtree_force, path)
            logger.debug(f"Cleaned up directory: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup directory {path}: {e}")
            
    async def cleanup(self, snapshot: RepositorySnapshot) -> None:
        """Cleanup repository snapshot.
        
        Args:
            snapshot: Repository snapshot to cleanup
            
        Raises:
            RepositoryCleanupError: If cleanup fails
        """
        if not os.path.exists(snapshot.local_path):
            return
            
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._rmtree_force, snapshot.local_path
            )
            logger.info(
                "repository.cleanup.completed",
                extra={"local_path": snapshot.local_path},
            )
        except Exception as e:
            logger.error(f"Failed to cleanup snapshot: {e}")
            raise RepositoryCleanupError(snapshot.local_path, str(e))
            
    @staticmethod
    def _rmtree_force(path: str) -> None:
        """Remove directory tree, handling read-only files on Windows.
        
        Args:
            path: Directory to remove
        """
        import stat
        
        def handle_remove_readonly(func, path, exc_info):
            """Handle read-only files by clearing the read-only bit."""
            if func in (os.unlink, os.rmdir) and exc_info[0] == PermissionError:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            else:
                raise exc_info[1]
                
        shutil.rmtree(path, onerror=handle_remove_readonly)
