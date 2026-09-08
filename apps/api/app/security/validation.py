"""
Security validation functions — input validation, path traversal prevention, etc.
"""

import re
from pathlib import Path

# Maximum allowed URL length to prevent memory exhaustion
MAX_URL_LENGTH = 2048

# Characters that are never valid in GitHub owner/repo names
INVALID_URL_CHARS = re.compile(r"[;<>(){}|`$!&\n\r\t\x00]")

# Shell metacharacters that must never appear in commands from repository data
SHELL_METACHARACTERS = re.compile(r"[;&|`$!(){}<>\"'\\]")


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
    Only allows: https://github.com/{owner}/{repo} with optional tree/blob/commit paths.
    Rejects path traversal, shell metacharacters, and non-GitHub hosts.
    Returns (is_valid, reason_if_invalid).
    """
    # Enforce URL length limit
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL exceeds maximum length of {MAX_URL_LENGTH}"

    # Reject URL-encoded traversal attempts early
    if "%2e" in url.lower() or "%2f" in url.lower():
        return False, "URL contains encoded path traversal"

    # Reject shell metacharacters in URL
    if INVALID_URL_CHARS.search(url):
        return False, "URL contains invalid characters"

    # Strict pattern: owner/repo with optional valid GitHub path suffixes
    # Only allows /tree/{branch}, /blob/{branch}, /commit/{sha}, or /releases
    pattern = (
        r"^https://github\.com/"
        r"[a-zA-Z0-9_.-]+/"  # owner
        r"[a-zA-Z0-9_.-]+"   # repo
        r"(/tree/[a-zA-Z0-9_./-]+)?"  # optional /tree/branch
        r"(/blob/[a-zA-Z0-9_./-]+)?"  # optional /blob/path
        r"(/commit/[a-f0-9]+)?"        # optional /commit/sha
        r"(/releases.*)?$"              # optional /releases
    )
    if not re.match(pattern, url):
        return False, "Invalid GitHub URL format"

    # Block encoded traversal sequences
    if "\\.." in url or "/../" in url or "\\..\\" in url:
        return False, "URL contains path traversal"

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


def sanitize_shell_argument(arg: str) -> str:
    """
    Sanitize a string for safe use as a shell argument.
    Blocks arguments containing shell metacharacters.
    Returns the argument if safe, raises ValueError if not.
    """
    if SHELL_METACHARACTERS.search(arg):
        raise ValueError(f"Argument contains shell metacharacters: {arg!r}")
    return arg
