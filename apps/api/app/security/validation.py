"""
Security validation functions — input validation, path traversal prevention, etc.
"""

import re
from pathlib import Path


def validate_file_path(path: str, base_dir: str | None = None) -> bool:
    """
    Validate that a file path is safe (no traversal, no absolute paths).
    Returns True if safe, False if potentially malicious.
    """
    # Block absolute paths
    if path.startswith("/") or path.startswith("\\"):
        return False

    # Block path traversal
    if ".." in path:
        return False

    # Normalize and check
    normalized = Path(path).parts
    if any(part.startswith("/") or part.startswith("\\") for part in normalized):
        return False

    # If base_dir specified, ensure path stays within it
    if base_dir:
        try:
            base = Path(base_dir).resolve()
            target = (base / path).resolve()
            if not str(target).startswith(str(base)):
                return False
        except Exception:
            return False

    return True


def validate_branch_name(name: str) -> bool:
    """
    Validate that a branch name is safe.
    Returns True if safe, False if potentially malicious.
    """
    # Block empty names
    if not name or not name.strip():
        return False

    # Block names with traversal
    if ".." in name or "/" in name or "\\" in name:
        return False

    # Block names with shell metacharacters
    dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "{", "}", "<", ">", "!", "\n", "\r"]
    for char in dangerous_chars:
        if char in name:
            return False

    # Block names starting with dash (could be interpreted as flags)
    if name.startswith("-"):
        return False

    return True


def validate_commit_sha(sha: str) -> bool:
    """Validate that a commit SHA is a valid hex string (7-40 chars)."""
    return bool(re.match(r"^[0-9a-f]{7,40}$", sha))


def validate_github_url(url: str) -> tuple[bool, str | None]:
    """
    Validate GitHub URL format.
    Returns (is_valid, reason_if_invalid).
    """
    pattern = r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?$"
    if not re.match(pattern, url):
        return False, "Invalid GitHub URL format"
    return True, None


def validate_docker_image(image: str) -> tuple[bool, str | None]:
    """
    Validate Docker image name against security policy.
    Returns (is_valid, reason_if_invalid).
    """
    # Block images with tags that could be exploits
    if ";" in image or "|" in image or "`" in image:
        return False, "Image name contains dangerous characters"

    # Block images from untrusted registries
    blocked_registries = ["docker.io/", "ghcr.io/", "quay.io/"]
    for registry in blocked_registries:
        if image.startswith(registry):
            return False, f"Registry {registry} not allowed"

    return True, None
