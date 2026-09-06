"""Tests for Docker security configuration."""

import pytest
from app.security.docker_security import DockerSecurityConfig, validate_docker_config


class TestDockerSecurity:
    """Test Docker security configuration."""

    def test_forbidden_flags_exist(self):
        """Forbidden flags must be defined."""
        config = DockerSecurityConfig()
        assert "--privileged" in config.FORBIDDEN_FLAGS
        assert "--pid=host" in config.FORBIDDEN_FLAGS
        assert "--network=host" in config.FORBIDDEN_FLAGS

    def test_forbidden_mounts_exist(self):
        """Forbidden mounts must be defined."""
        config = DockerSecurityConfig()
        assert "/var/run/docker.sock" in config.FORBIDDEN_MOUNTS
        assert "/proc" in config.FORBIDDEN_MOUNTS
        assert "/sys" in config.FORBIDDEN_MOUNTS
        assert "/" in config.FORBIDDEN_MOUNTS

    def test_required_security_opts_exist(self):
        """Required security options must be defined."""
        config = DockerSecurityConfig()
        assert "no-new-privileges:true" in config.REQUIRED_SECURITY_OPTS

    def test_forbidden_users_exist(self):
        """Forbidden users must be defined."""
        config = DockerSecurityConfig()
        assert "root" in config.FORBIDDEN_USERS
        assert "0" in config.FORBIDDEN_USERS
        assert "0:0" in config.FORBIDDEN_USERS

    def test_validate_blocks_privileged(self):
        """Must reject --privileged flag."""
        config = {"command": ["--privileged", "run"]}
        violations = validate_docker_config(config)
        assert any("--privileged" in v for v in violations)

    def test_validate_blocks_host_network(self):
        """Must reject --network=host."""
        config = {"command": ["--network=host"], "network_mode": "host"}
        violations = validate_docker_config(config)
        assert any("host" in v for v in violations)

    def test_validate_blocks_docker_socket(self):
        """Must reject Docker socket mount."""
        config = {"volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}
        violations = validate_docker_config(config)
        assert any("docker.sock" in v for v in violations)

    def test_validate_blocks_proc_mount(self):
        """Must reject /proc mount."""
        config = {"volumes": ["/proc:/host/proc"]}
        violations = validate_docker_config(config)
        assert any("/proc" in v for v in violations)

    def test_validate_blocks_sys_mount(self):
        """Must reject /sys mount."""
        config = {"volumes": ["/sys:/host/sys"]}
        violations = validate_docker_config(config)
        assert any("/sys" in v for v in violations)

    def test_validate_blocks_root_mount(self):
        """Must reject / mount."""
        config = {"volumes": ["/:/host"]}
        violations = validate_docker_config(config)
        assert any("/" in v for v in violations)

    def test_validate_blocks_root_user(self):
        """Must reject root user."""
        config = {"user": "root"}
        violations = validate_docker_config(config)
        assert any("root" in v for v in violations)

    def test_validate_blocks_0_user(self):
        """Must reject 0 user."""
        config = {"user": "0"}
        violations = validate_docker_config(config)
        assert any("0" in v for v in violations)

    def test_validate_blocks_pid_host(self):
        """Must reject PID mode host."""
        config = {"pid_mode": "host"}
        violations = validate_docker_config(config)
        assert any("PID" in v for v in violations)

    def test_validate_blocks_ipc_host(self):
        """Must reject IPC mode host."""
        config = {"ipc_mode": "host"}
        violations = validate_docker_config(config)
        assert any("IPC" in v for v in violations)

    def test_validate_blocks_missing_security_opt(self):
        """Must reject missing security options."""
        config = {"security_opt": []}
        violations = validate_docker_config(config)
        assert any("security option" in v for v in violations)

    def test_validate_allows_valid_config(self):
        """Valid config must pass validation."""
        config = {
            "command": ["run"],
            "user": "1000:1000",
            "network_mode": "bridge",
            "security_opt": ["no-new-privileges:true"],
            "volumes": [],
        }
        violations = validate_docker_config(config)
        assert len(violations) == 0

    def test_config_is_frozen(self):
        """DockerSecurityConfig must be immutable."""
        config = DockerSecurityConfig()
        with pytest.raises(AttributeError):
            config.FORBIDDEN_FLAGS = ()
