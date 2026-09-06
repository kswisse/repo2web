"""
Security interfaces for Repo2Web.

All security controls are defined as interfaces (protocols/ABCs)
to enable testing and future implementation swaps.
"""

from .sandbox import SandboxConfig, ContainerType, NetworkMode
from .network import (
    NetworkPolicy, NetworkRule, Protocol, Direction,
    BUILD_NETWORK_POLICY, RUNTIME_NETWORK_POLICY,
    generate_iptables_rules,
)
from .repository import RepositoryPolicy, DEFAULT_REPO_POLICY, validate_commit_sha, validate_short_sha, validate_url
from .docker_security import DockerSecurityConfig, validate_docker_config
from .audit import SecurityEvent, SecurityEventType, SecurityAuditLogger, audit_logger, redact_sensitive
from .validation import (
    validate_file_path,
    validate_branch_name,
    validate_commit_sha as validate_commit_sha_format,
    validate_github_url,
    validate_docker_image,
)
from .ssrf import validate_url_ssrf, validate_url_ssrf_async, is_ip_blocked, resolve_hostname, BLOCKED_IP_RANGES
from .secrets import (
    is_secret_env_var,
    validate_container_env,
    redact_secrets,
    scan_build_output,
    FORBIDDEN_ENV_PATTERNS,
)
from .build import BUILD_SECURITY_POLICY
from .runtime import RUNTIME_SECURITY_POLICY
from .exceptions import (
    SecurityException,
    SandboxViolationException,
    NetworkPolicyViolationException,
    SSRFBlockedException,
    SecretLeakException,
    RepositoryPolicyException,
    ContainerEscapeException,
    ResourceLimitException,
    AuditLogException,
)

__all__ = [
    # Sandbox
    "SandboxConfig",
    "ContainerType",
    "NetworkMode",
    # Network
    "NetworkPolicy",
    "NetworkRule",
    "Protocol",
    "Direction",
    "BUILD_NETWORK_POLICY",
    "RUNTIME_NETWORK_POLICY",
    "generate_iptables_rules",
    # Repository
    "RepositoryPolicy",
    "DEFAULT_REPO_POLICY",
    "validate_commit_sha",
    "validate_short_sha",
    "validate_url",
    # Docker Security
    "DockerSecurityConfig",
    "validate_docker_config",
    # Audit
    "SecurityEvent",
    "SecurityEventType",
    "SecurityAuditLogger",
    "audit_logger",
    "redact_sensitive",
    # Validation
    "validate_file_path",
    "validate_branch_name",
    "validate_commit_sha_format",
    "validate_github_url",
    "validate_docker_image",
    # SSRF
    "validate_url_ssrf",
    "validate_url_ssrf_async",
    "is_ip_blocked",
    "resolve_hostname",
    "BLOCKED_IP_RANGES",
    # Secrets
    "is_secret_env_var",
    "validate_container_env",
    "redact_secrets",
    "scan_build_output",
    "FORBIDDEN_ENV_PATTERNS",
    # Policies
    "BUILD_SECURITY_POLICY",
    "RUNTIME_SECURITY_POLICY",
    # Exceptions
    "SecurityException",
    "SandboxViolationException",
    "NetworkPolicyViolationException",
    "SSRFBlockedException",
    "SecretLeakException",
    "RepositoryPolicyException",
    "ContainerEscapeException",
    "ResourceLimitException",
    "AuditLogException",
]
