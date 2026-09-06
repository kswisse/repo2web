"""
Security audit logging — structured, searchable, tamper-evident.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import json
import structlog


class SecurityEventType(Enum):
    # Repository events
    REPO_ACCEPTED = "repo.accepted"
    REPO_REJECTED = "repo.rejected"
    REPO_SIZE_EXCEEDED = "repo.size_exceeded"
    REPO_CLONE_STARTED = "repo.clone_started"
    REPO_CLONE_COMPLETED = "repo.clone_completed"
    REPO_CLONE_FAILED = "repo.clone_failed"

    # Build events
    BUILD_STARTED = "build.started"
    BUILD_COMPLETED = "build.completed"
    BUILD_FAILED = "build.failed"
    BUILD_TIMEOUT = "build.timeout"
    BUILD_SECURITY_BLOCKED = "build.security_blocked"

    # Runtime events
    SANDBOX_CREATED = "sandbox.created"
    SANDBOX_TERMINATED = "sandbox.terminated"
    SANDBOX_ESCAPED = "sandbox.escaped"
    RUNTIME_STARTED = "runtime.started"
    RUNTIME_STOPPED = "runtime.stopped"
    RUNTIME_EXPIRED = "runtime.expired"

    # Security events
    RESOURCE_LIMIT_EXCEEDED = "security.resource_limit_exceeded"
    NETWORK_POLICY_VIOLATION = "security.network_policy_violation"
    SECURITY_POLICY_VIOLATION = "security.policy_violation"
    SSRF_ATTEMPT = "security.ssrf_attempt"
    PRIVILEGE_ESCALATION_ATTEMPT = "security.privilege_escalation"
    CONTAINER_ESCAPE_ATTEMPT = "security.container_escape"
    SECRET_DETECTED = "security.secret_detected"

    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_TOKEN_EXPIRED = "auth.token_expired"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"

    # Abuse
    SUSPICIOUS_BEHAVIOR = "abuse.suspicious"
    DEPLOYMENT_SPAM = "abuse.deployment_spam"
    CRYPTO_MINING_DETECTED = "abuse.crypto_mining"


@dataclass(frozen=True)
class SecurityEvent:
    """Immutable security event record."""
    event_type: SecurityEventType
    timestamp: datetime
    deployment_id: Optional[str] = None
    container_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    severity: str = "info"


# What MUST NOT be logged:
SENSITIVE_FIELDS = frozenset([
    "password", "passwd", "pwd",
    "token", "api_key", "secret_key",
    "database_url", "redis_url",
    "aws_access_key", "aws_secret_key",
    "github_token", "jwt_secret",
    "private_key", "ssh_key",
    "credit_card", "ssn",
])


def redact_sensitive(event: SecurityEvent) -> SecurityEvent:
    """Remove sensitive fields from event details."""
    if not event.details:
        return event

    redacted_details = {}
    for key, value in event.details.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            redacted_details[key] = "[REDACTED]"
        else:
            redacted_details[key] = value

    return SecurityEvent(
        event_type=event.event_type,
        timestamp=event.timestamp,
        deployment_id=event.deployment_id,
        container_id=event.container_id,
        user_id=event.user_id,
        client_ip=event.client_ip,
        user_agent=event.user_agent,
        details=redacted_details,
        severity=event.severity,
    )


class SecurityAuditLogger:
    """Structured security audit logger."""

    def __init__(self):
        self.logger = structlog.get_logger("security.audit")

    def log(self, event: SecurityEvent) -> None:
        """Log a security event with structured data."""
        redacted_event = redact_sensitive(event)

        log_data = {
            "event_type": redacted_event.event_type.value,
            "timestamp": redacted_event.timestamp.isoformat(),
            "severity": redacted_event.severity,
        }

        if redacted_event.deployment_id:
            log_data["deployment_id"] = redacted_event.deployment_id
        if redacted_event.container_id:
            log_data["container_id"] = redacted_event.container_id
        if redacted_event.user_id:
            log_data["user_id"] = redacted_event.user_id
        if redacted_event.client_ip:
            log_data["client_ip"] = redacted_event.client_ip
        if redacted_event.user_agent:
            log_data["user_agent"] = redacted_event.user_agent
        if redacted_event.details:
            log_data["details"] = redacted_event.details

        # Use appropriate log level based on severity
        if redacted_event.severity == "critical":
            self.logger.critical("security_event", **log_data)
        elif redacted_event.severity == "error":
            self.logger.error("security_event", **log_data)
        elif redacted_event.severity == "warning":
            self.logger.warning("security_event", **log_data)
        else:
            self.logger.info("security_event", **log_data)


# Singleton instance
audit_logger = SecurityAuditLogger()
