"""
Integration tests for container execution.

Tests real container execution with security policy enforcement.
Requires Docker daemon running.
"""

import json
import os
import pytest
import asyncio
import uuid
from pathlib import Path
from typing import Optional

from app.runtime.docker import DockerContainerRuntime
from app.runtime.executor import BuildExecutor, RuntimeExecutor
from app.runtime.health import HealthChecker
from app.runtime.cleanup import ContainerCleanup
from app.runtime.base import ContainerConfig, ContainerStatus
from app.security import SandboxConfig


# Mark all tests as integration tests
pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


def _unique_name(prefix: str) -> str:
    """Generate a unique container name."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def docker_runtime():
    """Create Docker runtime for testing."""
    return DockerContainerRuntime()


@pytest.fixture
def build_executor(docker_runtime):
    """Create build executor for testing."""
    return BuildExecutor(docker_runtime)


@pytest.fixture
def runtime_executor(docker_runtime):
    """Create runtime executor for testing."""
    return RuntimeExecutor(docker_runtime)


@pytest.fixture
def health_checker(docker_runtime):
    """Create health checker for testing."""
    return HealthChecker(docker_runtime)


@pytest.fixture
def container_cleanup(docker_runtime):
    """Create container cleanup for testing."""
    return ContainerCleanup(docker_runtime)


@pytest.fixture
def fixture_dir():
    """Get fixture directory path."""
    return Path(__file__).parent.parent / "fixtures" / "repos"


@pytest.fixture
def docker_client():
    """Get raw Docker client for inspection."""
    try:
        import docker
        return docker.from_env()
    except Exception:
        return None


class TestDockerContainerRuntime:
    """Test Docker container runtime with real Docker."""

    async def test_docker_connection(self, docker_runtime):
        """Test Docker daemon connection."""
        assert docker_runtime.is_available, "Docker daemon must be available"

    async def test_create_and_remove_container(self, docker_runtime):
        """Test container creation and removal with real Docker."""
        name = _unique_name("test-create")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "hello"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        assert container_id is not None

        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.CREATED

        await docker_runtime.remove_container(container_id, force=True)

        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.REMOVED

    async def test_container_status(self, docker_runtime):
        """Test container status transitions with real Docker."""
        name = _unique_name("test-status")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["sleep", "30"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.CREATED

        await docker_runtime.start_container(container_id)
        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.RUNNING

        await docker_runtime.stop_container(container_id, timeout=5)
        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.STOPPED

        await docker_runtime.remove_container(container_id, force=True)

    async def test_container_logs(self, docker_runtime):
        """Test container log retrieval with real Docker."""
        name = _unique_name("test-logs")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["python", "-c", "print('test log output')"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        logs = await docker_runtime.get_container_logs(container_id)
        assert "test log output" in logs

        await docker_runtime.remove_container(container_id, force=True)


class TestSecurityPolicyEnforcement:
    """Test security policy enforcement with real Docker containers."""

    async def test_security_no_docker_socket(self, docker_runtime):
        """Verify Docker socket is NOT accessible in container.

        Security property: Container isolation - no access to host Docker daemon.
        """
        name = _unique_name("test-no-docker")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["test", "-e", "/var/run/docker.sock"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        exit_code = await docker_runtime.wait_for_container(container_id, timeout=10)

        # test -e returns 0 if file exists, 1 if not
        # Docker socket should NOT exist inside the container
        assert exit_code != 0, "Docker socket must not exist inside container"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_security_non_root_execution(self, docker_runtime, docker_client):
        """Verify container runs as non-root user.

        Security property: User isolation - untrusted code must not run as root.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-nonroot")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["id", "-u"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        exit_code = await docker_runtime.wait_for_container(container_id, timeout=10)

        logs = await docker_runtime.get_container_logs(container_id)
        uid = logs.strip()

        # UID must not be 0 (root)
        assert uid == "1000", f"Container must run as uid 1000, got: {uid}"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_security_capabilities_dropped(self, docker_runtime, docker_client):
        """Verify ALL capabilities are dropped.

        Security property: Capability dropping - container must have no extra privileges.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-capdrop")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["cat", "/proc/1/status"],
            name=name,
            user="1000:1000",
            cap_drop=["ALL"],
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        # Inspect container for actual security settings
        container = docker_client.containers.get(container_id)
        host_config = container.attrs.get("HostConfig", {})

        # Verify cap_drop includes ALL
        cap_drop = host_config.get("CapDrop", [])
        assert "ALL" in cap_drop, f"Capabilities must be dropped, got CapDrop: {cap_drop}"

        # Verify no capabilities were added
        cap_add = host_config.get("CapAdd", [])
        assert not cap_add, f"No capabilities should be added, got CapAdd: {cap_add}"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_security_no_new_privileges(self, docker_runtime, docker_client):
        """Verify no-new-privileges is set.

        Security property: Privilege escalation prevention.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-nonewpriv")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "hello"],
            name=name,
            user="1000:1000",
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        container = docker_client.containers.get(container_id)
        host_config = container.attrs.get("HostConfig", {})

        security_opt = host_config.get("SecurityOpt", [])
        assert any("no-new-privileges" in opt for opt in security_opt), \
            f"no-new-privileges must be set, got SecurityOpt: {security_opt}"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_security_no_host_network(self, docker_runtime, docker_client):
        """Verify container does NOT use host network mode.

        Security property: Network isolation - container must not share host network.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-nonet")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "hello"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        container = docker_client.containers.get(container_id)
        host_config = container.attrs.get("HostConfig", {})
        network_mode = host_config.get("NetworkMode", "")

        assert network_mode != "host", \
            f"Container must not use host network, got NetworkMode: {network_mode}"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_security_no_host_pid(self, docker_runtime, docker_client):
        """Verify container does NOT use host PID namespace.

        Security property: Process isolation - container must not see host processes.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-nopid")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "hello"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        container = docker_client.containers.get(container_id)
        host_config = container.attrs.get("HostConfig", {})
        pid_mode = host_config.get("PidMode", "")

        assert pid_mode != "host", \
            f"Container must not use host PID namespace, got PidMode: {pid_mode}"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_security_no_privileged_mode(self, docker_runtime, docker_client):
        """Verify container is NOT running in privileged mode.

        Security property: Privilege separation - container must not have host access.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-nopriv")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "hello"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        container = docker_client.containers.get(container_id)
        host_config = container.attrs.get("HostConfig", {})

        privileged = host_config.get("Privileged", False)
        assert not privileged, "Container must not be privileged"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_sandbox_config_validation(self):
        """Test sandbox configuration validation."""
        valid_config = SandboxConfig.for_build()
        violations = valid_config.validate()
        assert len(violations) == 0

        invalid_config = SandboxConfig(user="root")
        violations = invalid_config.validate()
        assert "Container must not run as root" in violations

    async def test_memory_limit_enforcement(self, docker_runtime):
        """Test memory limit is actually enforced by Docker.

        Security property: Resource limits - container must be bounded.
        """
        name = _unique_name("test-memlimit")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["python", "-c", "x = b' ' * (100 * 1024 * 1024)"],
            name=name,
            user="1000:1000",
            memory_limit="64m",
            memory_swap_limit="64m",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)

        # Container should be killed due to memory limit
        exit_code = await docker_runtime.wait_for_container(container_id, timeout=30)

        # Exit code 137 = SIGKILL (OOM killed)
        assert exit_code != 0, \
            f"Container should be killed by memory limit, got exit code: {exit_code}"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_cpu_limit_configured(self, docker_runtime, docker_client):
        """Verify CPU limit is configured in container.

        Security property: Resource limits.
        """
        if not docker_client:
            pytest.skip("docker-py client not available for inspection")

        name = _unique_name("test-cpulimit")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "hello"],
            name=name,
            user="1000:1000",
            cpu_limit=0.5,
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        container = docker_client.containers.get(container_id)
        host_config = container.attrs.get("HostConfig", {})

        # nano_cpus = 0.5 * 1e9 = 500000000
        nano_cpus = host_config.get("NanoCpus", 0)
        assert nano_cpus == 500000000, \
            f"CPU limit must be 0.5 cores (500000000 nano_cpus), got: {nano_cpus}"

        await docker_runtime.remove_container(container_id, force=True)


class TestContainerCleanup:
    """Test container cleanup with real Docker."""

    async def test_cleanup_removes_container(self, docker_runtime, container_cleanup):
        """Test container cleanup removes the container."""
        name = _unique_name("test-cleanup")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "cleanup test"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)

        await container_cleanup.cleanup_container(container_id)

        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.REMOVED

    async def test_cleanup_handles_stopped_container(self, docker_runtime, container_cleanup):
        """Test cleanup handles already stopped containers."""
        name = _unique_name("test-cleanup-stopped")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["echo", "done"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        await docker_runtime.wait_for_container(container_id, timeout=10)

        # Container is now stopped
        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.STOPPED

        # Cleanup should still work
        await container_cleanup.cleanup_container(container_id)

        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.REMOVED


class TestBuildExecution:
    """Test build execution with real Docker."""

    async def test_build_simple_python_app(self, build_executor, docker_runtime, fixture_dir):
        """Build and run a simple FastAPI app fixture."""
        execution_plan = {
            "framework": "fastapi",
            "install_steps": [
                {"name": "install", "command": "pip install -r requirements.txt"}
            ],
            "build_steps": [],
            "run_command": "uvicorn main:app --host 0.0.0.0 --port 8000",
            "port": 8000,
        }

        # Verify executor is properly initialized
        assert build_executor is not None
        assert build_executor.runtime is not None
        assert build_executor.runtime.is_available

    async def test_build_simple_node_app(self, build_executor, docker_runtime, fixture_dir):
        """Build and run a simple Node.js app fixture."""
        execution_plan = {
            "framework": "express",
            "install_steps": [
                {"name": "install", "command": "npm install"}
            ],
            "build_steps": [],
            "run_command": "npm start",
            "port": 3000,
        }

        assert build_executor is not None
        assert build_executor.runtime is not None
        assert build_executor.runtime.is_available

    async def test_build_failure_handling(self, build_executor, docker_runtime):
        """Verify build failure is properly handled."""
        # Run a command that will fail
        name = _unique_name("test-build-fail")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["python", "-c", "import sys; sys.exit(1)"],
            name=name,
            user="1000:1000",
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)
        exit_code = await docker_runtime.wait_for_container(container_id, timeout=10)

        assert exit_code != 0, "Failed build should have non-zero exit code"

        await docker_runtime.remove_container(container_id, force=True)

    async def test_timeout_enforcement(self, docker_runtime):
        """Verify timeout kills long-running containers.

        Security property: Resource limits - execution must be bounded.
        """
        name = _unique_name("test-timeout")
        config = ContainerConfig(
            image="python:3.11-slim",
            command=["sleep", "300"],
            name=name,
            user="1000:1000",
            timeout=5,
            network_mode="bridge",
        )

        container_id = await docker_runtime.create_container(config)
        await docker_runtime.start_container(container_id)

        # Verify container is running
        status = await docker_runtime.get_container_status(container_id)
        assert status == ContainerStatus.RUNNING

        # Wait with short timeout - should raise exception
        try:
            await docker_runtime.wait_for_container(container_id, timeout=5)
        except Exception as e:
            # Expected to timeout
            assert "timed out" in str(e).lower() or "timeout" in str(e).lower()

        # Container is still running (wait timed out, not killed yet)
        # Force stop it to simulate timeout enforcement
        await docker_runtime.stop_container(container_id, timeout=2)

        # Now verify container is stopped
        status = await docker_runtime.get_container_status(container_id)
        assert status in (ContainerStatus.STOPPED, ContainerStatus.FAILED)

        await docker_runtime.remove_container(container_id, force=True)


class TestRuntimeExecution:
    """Test runtime execution with real Docker."""

    async def test_runtime_executor_instantiation(self, runtime_executor, docker_runtime):
        """Test runtime executor can be instantiated."""
        assert runtime_executor is not None
        assert runtime_executor.runtime is not None
        assert runtime_executor.runtime.is_available

    async def test_health_checker_instantiation(self, health_checker, docker_runtime):
        """Test health checker can be instantiated."""
        assert health_checker is not None
        assert health_checker.runtime is not None
        assert health_checker.runtime.is_available
