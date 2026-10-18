"""Tests for SSRF protection."""

import pytest
from unittest.mock import patch, MagicMock
from app.security.ssrf import (
    validate_url_ssrf,
    is_ip_blocked,
    resolve_hostname,
    is_trusted_deployment_endpoint,
    BLOCKED_IP_RANGES,
    BLOCKED_HOSTS,
    ALLOWED_HOSTS,
)


class TestSSRFProtection:
    """Test SSRF protection functions."""

    def test_blocked_ip_ranges_exist(self):
        """Blocked IP ranges must be defined."""
        assert len(BLOCKED_IP_RANGES) > 0

    def test_blocked_hosts_exist(self):
        """Blocked hosts must be defined."""
        assert "localhost" in BLOCKED_HOSTS
        assert "127.0.0.1" in BLOCKED_HOSTS
        assert "169.254.169.254" in BLOCKED_HOSTS

    def test_allowed_hosts_exist(self):
        """Allowed hosts must be defined."""
        assert "github.com" in ALLOWED_HOSTS

    def test_is_ip_blocked_localhost(self):
        """Localhost must be blocked."""
        assert is_ip_blocked("127.0.0.1") is True
        assert is_ip_blocked("127.0.0.2") is True

    def test_is_ip_blocked_private_ranges(self):
        """Private IP ranges must be blocked."""
        assert is_ip_blocked("10.0.0.1") is True
        assert is_ip_blocked("172.16.0.1") is True
        assert is_ip_blocked("192.168.0.1") is True

    def test_is_ip_blocked_metadata(self):
        """Cloud metadata endpoint must be blocked."""
        assert is_ip_blocked("169.254.169.254") is True

    def test_is_ip_blocked_ipv6_loopback(self):
        """IPv6 loopback must be blocked."""
        assert is_ip_blocked("::1") is True

    def test_is_ip_blocked_ipv6_ula(self):
        """IPv6 ULA must be blocked."""
        assert is_ip_blocked("fd00::1") is True

    def test_is_ip_allowed_public(self):
        """Public IPs must be allowed."""
        assert is_ip_blocked("8.8.8.8") is False
        assert is_ip_blocked("1.1.1.1") is False

    def test_validate_url_ssrf_blocks_http(self):
        """HTTP URLs must be blocked."""
        is_safe, reason = validate_url_ssrf("http://github.com/user/repo")
        assert is_safe is False
        assert "https" in reason.lower()

    def test_validate_url_ssrf_blocks_localhost(self):
        """URLs pointing to localhost must be blocked."""
        is_safe, reason = validate_url_ssrf("https://localhost/repo")
        assert is_safe is False
        assert "blocked" in reason.lower()

    def test_validate_url_ssrf_blocks_127_0_0_1(self):
        """URLs pointing to 127.0.0.1 must be blocked."""
        is_safe, reason = validate_url_ssrf("https://127.0.0.1/repo")
        assert is_safe is False

    def test_validate_url_ssrf_blocks_metadata(self):
        """URLs pointing to cloud metadata must be blocked."""
        is_safe, reason = validate_url_ssrf("https://169.254.169.254/latest/meta-data/")
        assert is_safe is False

    def test_validate_url_ssrf_blocks_private_ip(self):
        """URLs pointing to private IPs must be blocked."""
        is_safe, reason = validate_url_ssrf("https://10.0.0.1/repo")
        assert is_safe is False

    def test_validate_url_ssrf_blocks_non_github(self):
        """Non-GitHub URLs must be blocked."""
        is_safe, reason = validate_url_ssrf("https://evil.com/user/repo")
        assert is_safe is False
        assert "allowed" in reason.lower()

    def test_validate_url_ssrf_allows_github(self):
        """GitHub URLs must be allowed."""
        is_safe, reason = validate_url_ssrf("https://github.com/user/repo")
        assert is_safe is True
        assert reason is None

    def test_validate_url_ssrf_blocks_invalid_format(self):
        """Invalid URL format must be blocked."""
        is_safe, reason = validate_url_ssrf("not-a-url")
        assert is_safe is False

    def test_validate_url_ssrf_blocks_resolved_private_ip(self):
        """URLs resolving to private IPs must be blocked."""
        with patch("app.security.ssrf.resolve_hostname", return_value=["10.0.0.1"]):
            is_safe, reason = validate_url_ssrf("https://github.com/user/repo")
            assert is_safe is False
            assert "blocked ip" in reason.lower()

    def test_validate_url_ssrf_allows_resolved_public_ip(self):
        """URLs resolving to public IPs must be allowed."""
        with patch("app.security.ssrf.resolve_hostname", return_value=["140.82.121.3"]):
            is_safe, reason = validate_url_ssrf("https://github.com/user/repo")
            assert is_safe is True

    def test_validate_url_ssrf_handles_unresolvable_host(self):
        """Unresolvable hostnames must be blocked."""
        with patch("app.security.ssrf.resolve_hostname", return_value=[]):
            is_safe, reason = validate_url_ssrf("https://github.com/user/repo")
            assert is_safe is False
            assert "resolve" in reason.lower()


class TestTrustedDeploymentEndpoint:
    """Test is_trusted_deployment_endpoint for health check authorization."""

    def test_trusted_runtime_container(self):
        """Valid runtime container with deployment_id label must be trusted."""
        labels = {
            "deployment_id": "validate-flask-minimal-abc123",
            "type": "runtime",
        }
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is True

    def test_trusted_build_container(self):
        """Valid build container with deployment_id label must be trusted."""
        labels = {
            "deployment_id": "validate-flask-minimal-abc123",
            "type": "build",
        }
        assert is_trusted_deployment_endpoint("172.18.0.3", labels) is True

    def test_rejected_no_labels(self):
        """Container without labels must NOT be trusted."""
        assert is_trusted_deployment_endpoint("172.18.0.2", None) is False
        assert is_trusted_deployment_endpoint("172.18.0.2", {}) is False

    def test_rejected_no_deployment_id(self):
        """Container without deployment_id label must NOT be trusted."""
        labels = {"type": "runtime"}
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is False

    def test_rejected_no_type(self):
        """Container without type label must NOT be trusted."""
        labels = {"deployment_id": "test-123"}
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is False

    def test_rejected_invalid_type(self):
        """Container with invalid type label must NOT be trusted."""
        labels = {
            "deployment_id": "test-123",
            "type": "unknown",
        }
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is False

    def test_rejected_invalid_deployment_id_format(self):
        """Container with invalid deployment_id format must NOT be trusted."""
        labels = {
            "deployment_id": "",  # empty
            "type": "runtime",
        }
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is False

    def test_rejected_deployment_id_too_long(self):
        """Container with very long deployment_id must NOT be trusted."""
        labels = {
            "deployment_id": "x" * 200,  # > 128 chars
            "type": "runtime",
        }
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is False

    def test_rejected_deployment_id_special_chars(self):
        """Container with special characters in deployment_id must NOT be trusted."""
        labels = {
            "deployment_id": "test; rm -rf /",
            "type": "runtime",
        }
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is False

    def test_rejected_invalid_ip(self):
        """Container with invalid IP must NOT be trusted."""
        labels = {
            "deployment_id": "test-123",
            "type": "runtime",
        }
        assert is_trusted_deployment_endpoint("not-an-ip", labels) is False

    def test_rejected_loopback_ip_even_with_valid_labels(self):
        """Container with loopback IP must NOT be trusted even with valid labels."""
        labels = {
            "deployment_id": "test-123",
            "type": "runtime",
        }
        # Defense-in-depth: loopback should never be a deployment endpoint
        assert is_trusted_deployment_endpoint("127.0.0.1", labels) is False
        assert is_trusted_deployment_endpoint("127.0.0.2", labels) is False

    def test_rejected_link_local_ip_even_with_valid_labels(self):
        """Container with link-local IP must NOT be trusted even with valid labels."""
        labels = {
            "deployment_id": "test-123",
            "type": "runtime",
        }
        # Defense-in-depth: link-local should never be a deployment endpoint
        assert is_trusted_deployment_endpoint("169.254.1.1", labels) is False

    def test_allows_docker_bridge_ip_with_valid_labels(self):
        """Docker bridge IP (172.18.x.x) must be allowed with valid labels."""
        labels = {
            "deployment_id": "validate-flask-minimal",
            "type": "runtime",
        }
        # Docker typically assigns IPs from 172.16.0.0/12 range
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is True
        assert is_trusted_deployment_endpoint("172.19.0.5", labels) is True

    def test_allows_docker_custom_network_ip(self):
        """Custom Docker network IP must be allowed with valid labels."""
        labels = {
            "deployment_id": "test-deployment",
            "type": "runtime",
        }
        # Could be any private IP assigned by Docker
        assert is_trusted_deployment_endpoint("10.0.0.5", labels) is True
        assert is_trusted_deployment_endpoint("192.168.1.100", labels) is True

    def test_does_not_weaken_general_ssrf_protection(self):
        """General SSRF protection must remain intact.

        The is_trusted_deployment_endpoint function only allows specific
        containers with valid labels. It does NOT whitelist private CIDRs.
        Containers without labels are still rejected.
        """
        # Private IPs without labels must still be blocked
        assert is_trusted_deployment_endpoint("172.18.0.2", None) is False
        assert is_trusted_deployment_endpoint("10.0.0.1", None) is False
        assert is_trusted_deployment_endpoint("192.168.1.1", None) is False

    def test_deployment_id_with_valid_special_characters(self):
        """deployment_id with hyphens and underscores must be allowed."""
        labels = {
            "deployment_id": "validate-my-repo_abc123",
            "type": "runtime",
        }
        assert is_trusted_deployment_endpoint("172.18.0.2", labels) is True
