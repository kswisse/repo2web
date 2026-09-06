"""Tests for RepositoryPolicy security configuration."""

import pytest
from app.security.repository import (
    RepositoryPolicy,
    DEFAULT_REPO_POLICY,
    validate_commit_sha,
    validate_short_sha,
    validate_url,
)


class TestRepositoryPolicy:
    """Test RepositoryPolicy configuration."""

    def test_default_policy_blocks_submodules(self):
        """Submodules must be blocked by default."""
        policy = RepositoryPolicy()
        assert policy.allow_submodules is False

    def test_default_policy_blocks_symlinks(self):
        """Symlinks must be blocked by default."""
        policy = RepositoryPolicy()
        assert policy.allow_symlinks is False

    def test_default_policy_blocks_lfs(self):
        """Git LFS must be blocked by default."""
        policy = RepositoryPolicy()
        assert policy.allow_lfs is False

    def test_default_policy_enforces_size_limit(self):
        """Repository size limit must be enforced."""
        policy = RepositoryPolicy()
        assert policy.max_repository_size_mb == 50

    def test_default_policy_enforces_file_size_limit(self):
        """Individual file size limit must be enforced."""
        policy = RepositoryPolicy()
        assert policy.max_file_size_mb == 10

    def test_default_policy_blocks_binaries(self):
        """Binary files must be blocked."""
        policy = RepositoryPolicy()
        assert ".exe" in policy.blocked_extensions
        assert ".dll" in policy.blocked_extensions
        assert ".so" in policy.blocked_extensions

    def test_default_policy_requires_https(self):
        """HTTPS must be required by default."""
        policy = RepositoryPolicy()
        assert policy.require_https is True

    def test_default_policy_requires_github(self):
        """GitHub must be required by default."""
        policy = RepositoryPolicy()
        assert policy.require_github is True

    def test_default_policy_disables_hooks(self):
        """Git hooks must be disabled by default."""
        policy = RepositoryPolicy()
        assert policy.disable_hooks is True

    def test_default_policy_shallow_clone(self):
        """Shallow clone must be enabled by default."""
        policy = RepositoryPolicy()
        assert policy.shallow_clone is True

    def test_default_policy_deletes_gitmodules(self):
        """.gitmodules must be deleted by default."""
        policy = RepositoryPolicy()
        assert policy.delete_gitmodules is True

    def test_validate_commit_sha_valid(self):
        """Valid commit SHA must be accepted."""
        sha = "a" * 40
        assert validate_commit_sha(sha) is True

    def test_validate_commit_sha_lowercase_hex(self):
        """Lowercase hex must be accepted."""
        sha = "0123456789abcdef" * 2 + "0123456789abcdef"[:8]
        assert validate_commit_sha(sha) is True

    def test_validate_commit_sha_invalid_chars(self):
        """Non-hex characters must be rejected."""
        sha = "g" * 40
        assert validate_commit_sha(sha) is False

    def test_validate_commit_sha_wrong_length(self):
        """Wrong length must be rejected."""
        sha = "a" * 39
        assert validate_commit_sha(sha) is False
        sha = "a" * 41
        assert validate_commit_sha(sha) is False

    def test_validate_short_sha_valid(self):
        """Valid short SHA must be accepted."""
        sha = "a" * 7
        assert validate_short_sha(sha) is True

    def test_validate_short_sha_long(self):
        """Long SHA must be accepted."""
        sha = "a" * 40
        assert validate_short_sha(sha) is True

    def test_validate_short_sha_too_short(self):
        """Too short SHA must be rejected."""
        sha = "a" * 6
        assert validate_short_sha(sha) is False

    def test_validate_url_valid_github(self):
        """Valid GitHub URL must be accepted."""
        url = "https://github.com/user/repo"
        is_valid, reason = validate_url(url)
        assert is_valid is True
        assert reason is None

    def test_validate_url_blocks_http(self):
        """HTTP URLs must be rejected."""
        url = "http://github.com/user/repo"
        is_valid, reason = validate_url(url)
        assert is_valid is False
        assert "https" in reason.lower()

    def test_validate_url_blocks_non_github(self):
        """Non-GitHub URLs must be rejected."""
        url = "https://gitlab.com/user/repo"
        is_valid, reason = validate_url(url)
        assert is_valid is False
        assert "github" in reason.lower()

    def test_validate_url_blocks_invalid_format(self):
        """Invalid URL format must be rejected."""
        url = "https://github.com/"
        is_valid, reason = validate_url(url)
        assert is_valid is False

    def test_default_policy_is_frozen(self):
        """Default policy must be immutable."""
        policy = RepositoryPolicy()
        with pytest.raises(AttributeError):
            policy.max_repository_size_mb = 100
