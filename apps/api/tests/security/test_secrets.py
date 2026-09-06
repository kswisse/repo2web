"""Tests for Secret Isolation security controls."""

import pytest
from app.security.secrets import (
    is_secret_env_var,
    validate_container_env,
    redact_secrets,
    scan_build_output,
    FORBIDDEN_ENV_PATTERNS,
)


class TestSecretIsolation:
    """Test secret isolation functions."""

    def test_forbidden_patterns_exist(self):
        """Forbidden patterns must be defined."""
        assert len(FORBIDDEN_ENV_PATTERNS) > 0

    def test_is_secret_env_var_password(self):
        """Password env vars must be detected."""
        assert is_secret_env_var("DATABASE_PASSWORD") is True
        assert is_secret_env_var("DB_PASSWORD") is True
        assert is_secret_env_var("MY_PASSWORD") is True

    def test_is_secret_env_var_secret(self):
        """Secret env vars must be detected."""
        assert is_secret_env_var("SECRET_KEY") is True
        assert is_secret_env_var("JWT_SECRET") is True
        assert is_secret_env_var("MY_SECRET") is True

    def test_is_secret_env_var_token(self):
        """Token env vars must be detected."""
        assert is_secret_env_var("GITHUB_TOKEN") is True
        assert is_secret_env_var("API_TOKEN") is True
        assert is_secret_env_var("MY_TOKEN") is True

    def test_is_secret_env_var_key(self):
        """Key env vars must be detected."""
        assert is_secret_env_var("API_KEY") is True
        assert is_secret_env_var("SECRET_KEY") is True
        assert is_secret_env_var("PRIVATE_KEY") is True

    def test_is_secret_env_var_database_url(self):
        """DATABASE_URL must be detected."""
        assert is_secret_env_var("DATABASE_URL") is True

    def test_is_secret_env_var_redis_url(self):
        """REDIS_URL must be detected."""
        assert is_secret_env_var("REDIS_URL") is True

    def test_is_secret_env_var_allowed(self):
        """Allowed env vars must not be detected."""
        assert is_secret_env_var("PORT") is False
        assert is_secret_env_var("NODE_ENV") is False
        assert is_secret_env_var("BUILD_ID") is False
        assert is_secret_env_var("REPO_URL") is False

    def test_validate_container_env_blocks_secrets(self):
        """Secrets in container env must be blocked."""
        env = {
            "PORT": "8080",
            "DATABASE_URL": "postgresql://user:pass@host/db",
            "SECRET_KEY": "supersecret",
        }
        forbidden = validate_container_env(env)
        assert "DATABASE_URL" in forbidden
        assert "SECRET_KEY" in forbidden
        assert "PORT" not in forbidden

    def test_validate_container_env_with_allowed_list(self):
        """Only allowed env vars must be permitted."""
        env = {
            "PORT": "8080",
            "NODE_ENV": "production",
            "CUSTOM_VAR": "value",
        }
        allowed = {"PORT": "8080", "NODE_ENV": "production"}
        forbidden = validate_container_env(env, allowed_vars=allowed)
        assert "CUSTOM_VAR" in forbidden
        assert "PORT" not in forbidden
        assert "NODE_ENV" not in forbidden

    def test_redact_secrets(self):
        """Secrets must be redacted from text."""
        text = "password=secret123 token=abc123"
        redacted = redact_secrets(text)
        assert "secret123" not in redacted
        assert "abc123" not in redacted
        assert "[REDACTED]" in redacted

    def test_scan_build_output_detects_secrets(self):
        """Build output with secrets must be detected."""
        output = "Installing dependencies... DATABASE_URL=postgresql://user:pass@host/db"
        detected = scan_build_output(output)
        assert len(detected) > 0

    def test_scan_build_output_clean(self):
        """Clean build output must not be detected."""
        output = "Installing dependencies... npm install complete"
        detected = scan_build_output(output)
        assert len(detected) == 0

    def test_validate_container_env_empty(self):
        """Empty env must be valid."""
        forbidden = validate_container_env({})
        assert len(forbidden) == 0
