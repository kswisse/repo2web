"""
Container runtime exceptions.
"""


class ContainerRuntimeError(Exception):
    """Base exception for container runtime errors."""
    pass


class ContainerCreateError(ContainerRuntimeError):
    """Exception raised when container creation fails."""
    pass


class ContainerStartError(ContainerRuntimeError):
    """Exception raised when container start fails."""
    pass


class ContainerStopError(ContainerRuntimeError):
    """Exception raised when container stop fails."""
    pass


class ContainerExecError(ContainerRuntimeError):
    """Exception raised when command execution in container fails."""
    pass


class ContainerTimeoutError(ContainerRuntimeError):
    """Exception raised when container operation times out."""
    pass


class ContainerResourceLimitError(ContainerRuntimeError):
    """Exception raised when container exceeds resource limits."""
    pass


class SecurityPolicyViolationError(ContainerRuntimeError):
    """Exception raised when security policy is violated."""
    pass
