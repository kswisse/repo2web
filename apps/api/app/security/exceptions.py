"""
Security exceptions for Repo2Web.

All security-related errors inherit from SecurityException for consistent handling.
"""


class SecurityException(Exception):
    """Base exception for all security violations."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class SandboxViolationException(SecurityException):
    """Raised when sandbox configuration violates security policy."""

    pass


class NetworkPolicyViolationException(SecurityException):
    """Raised when network configuration violates security policy."""

    pass


class SSRFBlockedException(SecurityException):
    """Raised when a URL resolves to a blocked IP range."""

    pass


class SecretLeakException(SecurityException):
    """Raised when secrets are detected in container environment."""

    pass


class RepositoryPolicyException(SecurityException):
    """Raised when repository violates ingestion policy."""

    pass


class ContainerEscapeException(SecurityException):
    """Raised when container escape is detected or suspected."""

    pass


class ResourceLimitException(SecurityException):
    """Raised when resource limits are exceeded or violated."""

    pass


class AuditLogException(SecurityException):
    """Raised when audit logging fails (critical — system must not continue)."""

    pass
