"""Tests for NetworkPolicy security configuration."""

import pytest
from app.security.network import (
    NetworkPolicy,
    NetworkRule,
    Protocol,
    Direction,
    BUILD_NETWORK_POLICY,
    RUNTIME_NETWORK_POLICY,
    generate_iptables_rules,
)


class TestNetworkPolicy:
    """Test NetworkPolicy configuration."""

    def test_blocked_cidrs_include_private_ranges(self):
        """All private IP ranges must be blocked."""
        policy = NetworkPolicy(name="test")
        assert "10.0.0.0/8" in policy.BLOCKED_CIDRS
        assert "172.16.0.0/12" in policy.BLOCKED_CIDRS
        assert "192.168.0.0/16" in policy.BLOCKED_CIDRS

    def test_blocked_cidrs_include_metadata(self):
        """Cloud metadata endpoint must be blocked."""
        policy = NetworkPolicy(name="test")
        assert "169.254.0.0/16" in policy.BLOCKED_CIDRS
        assert "127.0.0.0/8" in policy.BLOCKED_CIDRS

    def test_blocked_cidrs_include_ipv6(self):
        """IPv6 loopback and ULA must be blocked."""
        policy = NetworkPolicy(name="test")
        assert "::1/128" in policy.BLOCKED_CIDRS
        assert "fc00::/7" in policy.BLOCKED_CIDRS

    def test_blocked_hosts_include_localhost(self):
        """Localhost must be blocked."""
        policy = NetworkPolicy(name="test")
        assert "localhost" in policy.BLOCKED_HOSTS
        assert "127.0.0.1" in policy.BLOCKED_HOSTS
        assert "169.254.169.254" in policy.BLOCKED_HOSTS

    def test_blocked_ports_include_dangerous_ports(self):
        """Dangerous ports must be blocked."""
        policy = NetworkPolicy(name="test")
        assert 22 in policy.BLOCKED_PORTS  # SSH
        assert 23 in policy.BLOCKED_PORTS  # Telnet
        assert 25 in policy.BLOCKED_PORTS  # SMTP
        assert 4444 in policy.BLOCKED_PORTS  # Metasploit
        assert 5555 in policy.BLOCKED_PORTS  # Reverse shell

    def test_build_policy_allows_http(self):
        """Build policy must allow outbound HTTP."""
        policy = BUILD_NETWORK_POLICY
        assert any(
            r.direction == Direction.EGRESS and r.port == 80
            for r in policy.rules
        )

    def test_build_policy_allows_https(self):
        """Build policy must allow outbound HTTPS."""
        policy = BUILD_NETWORK_POLICY
        assert any(
            r.direction == Direction.EGRESS and r.port == 443
            for r in policy.rules
        )

    def test_build_policy_allows_dns(self):
        """Build policy must allow DNS."""
        policy = BUILD_NETWORK_POLICY
        assert any(
            r.direction == Direction.EGRESS and r.protocol == Protocol.UDP and r.port == 53
            for r in policy.rules
        )

    def test_build_policy_denies_ingress(self):
        """Build policy must deny ingress."""
        policy = BUILD_NETWORK_POLICY
        assert any(
            r.direction == Direction.INGRESS and r.action == "deny"
            for r in policy.rules
        )

    def test_runtime_policy_allows_http(self):
        """Runtime policy must allow outbound HTTP."""
        policy = RUNTIME_NETWORK_POLICY
        assert any(
            r.direction == Direction.EGRESS and r.port == 80
            for r in policy.rules
        )

    def test_runtime_policy_allows_https(self):
        """Runtime policy must allow outbound HTTPS."""
        policy = RUNTIME_NETWORK_POLICY
        assert any(
            r.direction == Direction.EGRESS and r.port == 443
            for r in policy.rules
        )

    def test_runtime_policy_denies_ingress(self):
        """Runtime policy must deny ingress."""
        policy = RUNTIME_NETWORK_POLICY
        assert any(
            r.direction == Direction.INGRESS and r.action == "deny"
            for r in policy.rules
        )

    def test_network_rule_is_frozen(self):
        """NetworkRule must be immutable."""
        rule = NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=80,
        )
        with pytest.raises(AttributeError):
            rule.port = 443

    def test_generate_iptables_rules(self):
        """Must generate valid iptables rules."""
        policy = BUILD_NETWORK_POLICY
        rules = generate_iptables_rules(policy, "172.21.0.0/16")
        assert len(rules) > 0
        # Check that DROP rule for forwarded traffic exists
        assert any(
            "DROP" in rule and "FORWARD" in rule
            for rule in rules
        )
