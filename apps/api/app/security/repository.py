"""
Repository ingestion policy — what we accept and how we process it.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RepositoryPolicy:
    """Immutable policy for repository ingestion."""

    # --- URL Validation ---
    allowed_url_pattern: str = r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?$"
    require_https: bool = True
    require_github: bool = True

    # --- Size Limits ---
    max_repository_size_mb: int = 50
    max_file_size_mb: int = 10
    max_total_files: int = 10_000

    # --- Git Configuration ---
    shallow_clone: bool = True
    clone_timeout_seconds: int = 120
    disable_hooks: bool = True
    disable_fsmonitor: bool = True
    disable_untracked_cache: bool = True

    # --- Submodule Policy ---
    allow_submodules: bool = False
    delete_gitmodules: bool = True

    # --- Symlink Policy ---
    allow_symlinks: bool = False

    # --- Git LFS Policy ---
    allow_lfs: bool = False

    # --- Branch/Commit Policy ---
    require_immutable_commit: bool = True
    allowed_branches: Optional[list] = None
    validate_commit_sha: bool = True

    # --- File Type Restrictions ---
    blocked_extensions: tuple = (
        ".exe", ".dll", ".so", ".dylib",
        ".bin", ".dat",
    )

    # --- Content Validation ---
    scan_for_secrets: bool = True
    block_private_keys: bool = True
    block_dockerfiles: bool = True


# Default policy
DEFAULT_REPO_POLICY = RepositoryPolicy()


def validate_commit_sha(sha: str) -> bool:
    """Validate that a commit SHA is a valid 40-character hex string."""
    return bool(re.match(r"^[0-9a-f]{40}$", sha))


def validate_short_sha(sha: str) -> bool:
    """Validate that a short SHA is at least 7 characters of hex."""
    return bool(re.match(r"^[0-9a-f]{7,40}$", sha))


def validate_url(url: str, policy: RepositoryPolicy | None = None) -> tuple[bool, str | None]:
    """
    Validate repository URL against policy.
    Returns (is_valid, reason_if_invalid).
    """
    policy = policy or DEFAULT_REPO_POLICY

    # Check HTTPS requirement
    if policy.require_https and not url.startswith("https://"):
        return False, "URL must use HTTPS"

    # Check GitHub requirement
    if policy.require_github and not re.match(policy.allowed_url_pattern, url):
        return False, "URL must be a valid GitHub repository URL"

    return True, None
