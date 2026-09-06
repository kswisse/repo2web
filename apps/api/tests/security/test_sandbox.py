"""Tests for SandboxConfig security validation."""

import pytest
from app.security.sandbox import SandboxConfig, ContainerType, NetworkMode


class TestSandboxConfig:
    """Test SandboxConfig dataclass and validation."""

    def test_default_config_has_resource_limits(self):
        """Default config must have resource limits."""
        config = SandboxConfig()
        assert config.cpu_limit == 1.0
        assert config.memory_limit == "512m"
        assert config.pids_limit == 50

    def test_for_build_has_higher_limits(self):
        """Build sandbox must have higher resource limits."""
        config = SandboxConfig.for_build()
        assert config.cpu_limit == 2.0
        assert config.memory_limit == "1g"
        assert config.pids_limit == 100
        assert config.disk_limit == "1g"

    def test_for_runtime_has_lower_limits(self):
        """Runtime sandbox must have lower resource limits."""
        config = SandboxConfig.for_runtime()
        assert config.cpu_limit == 1.0
        assert config.memory_limit == "512m"
        assert config.pids_limit == 50

    def test_config_is_frozen(self):
        """Config must be immutable."""
        config = SandboxConfig()
        with pytest.raises(AttributeError):
            config.cpu_limit = 2.0

    def test_blocks_root_user(self):
        """Containers must not run as root."""
        config = SandboxConfig(user="root")
        violations = config.validate()
        assert any("root" in v for v in violations)

    def test_blocks_root_uid(self):
        """Containers must not run as root UID."""
        config = SandboxConfig(user="0:0")
        violations = config.validate()
        assert any("root" in v for v in violations)

    def test_allows_non_root_user(self):
        """Non-root user must be allowed."""
        config = SandboxConfig(user="1000:1000")
        violations = config.validate()
        assert not any("root" in v for v in violations)

    def test_drops_all_capabilities(self):
        """ALL capabilities must be dropped."""
        config = SandboxConfig()
        assert "ALL" in config.cap_drop

    def test_blocks_cap_add(self):
        """Must not add capabilities."""
        config = SandboxConfig(cap_add=["NET_ADMIN"])
        violations = config.validate()
        assert any("capabilities" in v for v in violations)

    def test_requires_no_new_privileges(self):
        """no-new-privileges must be enabled."""
        config = SandboxConfig(no_new_privileges=False)
        violations = config.validate()
        assert any("no-new-privileges" in v for v in violations)

    def test_blocks_host_volumes(self):
        """No host volumes must be mounted."""
        config = SandboxConfig(volumes=["/host:/container"])
        violations = config.validate()
        assert any("volumes" in v for v in violations)

    def test_blocks_internal_network(self):
        """Untrusted code must not use internal network."""
        config = SandboxConfig(network_mode=NetworkMode.INTERNAL)
        violations = config.validate()
        assert any("internal network" in v for v in violations)

    def test_allows_isolated_network(self):
        """Isolated network must be allowed."""
        config = SandboxConfig(network_mode=NetworkMode.ISOLATED)
        violations = config.validate()
        assert not any("internal network" in v for v in violations)

    def test_requires_dns_servers(self):
        """Must configure DNS servers."""
        config = SandboxConfig(dns_servers=[])
        violations = config.validate()
        assert any("DNS" in v for v in violations)

    def test_blocks_custom_dns(self):
        """Custom DNS servers must be blocked."""
        config = SandboxConfig(dns_servers=["10.0.0.1"])
        violations = config.validate()
        assert any("DNS" in v for v in violations)

    def test_allows_public_dns(self):
        """Public DNS servers must be allowed."""
        config = SandboxConfig(dns_servers=["8.8.8.8", "1.1.1.1"])
        violations = config.validate()
        assert not any("DNS" in v for v in violations)

    def test_runtime_has_read_only_rootfs(self):
        """Runtime must have read-only root filesystem."""
        config = SandboxConfig.for_runtime()
        assert config.read_only_rootfs is True

    def test_build_has_writable_rootfs(self):
        """Build must have writable root filesystem."""
        config = SandboxConfig.for_build()
        assert config.read_only_rootfs is False

    def test_to_docker_run_args(self):
        """Must generate valid Docker run arguments."""
        config = SandboxConfig.for_runtime()
        args = config.to_docker_run_args(
            image="python:3.11-slim",
            command=["python", "app.py"],
            env_vars={"PORT": "8080"},
            name="test-container",
        )
        assert args["image"] == "python:3.11-slim"
        assert args["user"] == "1000:1000"
        assert args["mem_limit"] == "512m"
        assert args["pids_limit"] == 50
        assert "no-new-privileges:true" in args["security_opt"]
