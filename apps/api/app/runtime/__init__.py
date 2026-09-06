"""
Container runtime abstraction for Repo2Web.

Provides secure container execution with security policy enforcement.
"""

from .base import ContainerRuntime, ContainerConfig, ContainerStatus, ExecResult
from .docker import DockerContainerRuntime
from .executor import BuildExecutor, RuntimeExecutor, BuildResult, RuntimeInstance
from .health import HealthChecker, HealthCheckResult
from .cleanup import ContainerCleanup
from .exceptions import (
    ContainerRuntimeError,
    ContainerCreateError,
    ContainerStartError,
    ContainerStopError,
    ContainerExecError,
    ContainerTimeoutError,
    ContainerResourceLimitError,
    SecurityPolicyViolationError,
)

__all__ = [
    "ContainerRuntime",
    "ContainerConfig",
    "ContainerStatus",
    "ExecResult",
    "DockerContainerRuntime",
    "BuildExecutor",
    "RuntimeExecutor",
    "BuildResult",
    "RuntimeInstance",
    "HealthChecker",
    "HealthCheckResult",
    "ContainerCleanup",
    "ContainerRuntimeError",
    "ContainerCreateError",
    "ContainerStartError",
    "ContainerStopError",
    "ContainerExecError",
    "ContainerTimeoutError",
    "ContainerResourceLimitError",
    "SecurityPolicyViolationError",
]
