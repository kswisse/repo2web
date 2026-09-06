"""Tests for Security Validation functions."""

import pytest
from app.security.validation import (
    validate_file_path,
    validate_branch_name,
    validate_commit_sha,
    validate_github_url,
    validate_docker_image,
)


class TestSecurityValidation:
    """Test security validation functions."""

    def test_validate_file_path_blocks_traversal(self):
        """Path traversal must be blocked."""
        assert validate_file_path("../../../etc/passwd") is False

    def test_validate_file_path_blocks_absolute(self):
        """Absolute paths must be blocked."""
        assert validate_file_path("/etc/passwd") is False
        assert validate_file_path("\\windows\\system32") is False

    def test_validate_file_path_allows_relative(self):
        """Relative paths within base must be allowed."""
        assert validate_file_path("src/main.py") is True
        assert validate_file_path("app/config.json") is True

    def test_validate_file_path_with_base_dir(self):
        """Paths must stay within base directory."""
        assert validate_file_path("src/main.py", base_dir="/app") is True
        assert validate_file_path("../../../etc/passwd", base_dir="/app") is False

    def test_validate_branch_name_blocks_traversal(self):
        """Branch names with traversal must be blocked."""
        assert validate_branch_name("../../etc") is False

    def test_validate_branch_name_blocks_special_chars(self):
        """Branch names with special chars must be blocked."""
        assert validate_branch_name("branch;rm -rf /") is False
        assert validate_branch_name("branch|cat /etc/passwd") is False
        assert validate_branch_name("branch`whoami`") is False
        assert validate_branch_name("branch$(whoami)") is False

    def test_validate_branch_name_blocks_empty(self):
        """Empty branch names must be blocked."""
        assert validate_branch_name("") is False
        assert validate_branch_name("   ") is False

    def test_validate_branch_name_blocks_dash(self):
        """Branch names starting with dash must be blocked."""
        assert validate_branch_name("-flag") is False

    def test_validate_branch_name_allows_valid(self):
        """Valid branch names must be allowed."""
        assert validate_branch_name("main") is True
        assert validate_branch_name("feature/my-feature") is False  # Has /
        assert validate_branch_name("release-1.0") is True

    def test_validate_commit_sha_valid(self):
        """Valid commit SHA must be accepted."""
        sha = "a" * 40
        assert validate_commit_sha(sha) is True

    def test_validate_commit_sha_short(self):
        """Short SHA must be accepted."""
        sha = "a" * 7
        assert validate_commit_sha(sha) is True

    def test_validate_commit_sha_invalid(self):
        """Invalid SHA must be rejected."""
        assert validate_commit_sha("g" * 40) is False
        assert validate_commit_sha("a" * 6) is False
        assert validate_commit_sha("a" * 41) is False

    def test_validate_github_url_valid(self):
        """Valid GitHub URL must be accepted."""
        url = "https://github.com/user/repo"
        is_valid, reason = validate_github_url(url)
        assert is_valid is True
        assert reason is None

    def test_validate_github_url_with_path(self):
        """GitHub URL with path must be accepted."""
        url = "https://github.com/user/repo/tree/main/src"
        is_valid, reason = validate_github_url(url)
        assert is_valid is True

    def test_validate_github_url_invalid(self):
        """Invalid GitHub URL must be rejected."""
        url = "https://gitlab.com/user/repo"
        is_valid, reason = validate_github_url(url)
        assert is_valid is False

    def test_validate_github_url_http(self):
        """HTTP GitHub URL must be rejected."""
        url = "http://github.com/user/repo"
        is_valid, reason = validate_github_url(url)
        assert is_valid is False

    def test_validate_docker_image_valid(self):
        """Valid Docker image must be accepted."""
        image = "python:3.11-slim"
        is_valid, reason = validate_docker_image(image)
        assert is_valid is True
        assert reason is None

    def test_validate_docker_image_dangerous_chars(self):
        """Docker image with dangerous chars must be rejected."""
        image = "python:3.11;rm -rf /"
        is_valid, reason = validate_docker_image(image)
        assert is_valid is False

    def test_validate_docker_image_blocked_registry(self):
        """Docker image from blocked registry must be rejected."""
        image = "docker.io/python:3.11-slim"
        is_valid, reason = validate_docker_image(image)
        assert is_valid is False
