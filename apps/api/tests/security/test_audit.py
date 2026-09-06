"""Tests for Security Audit Logging."""

import pytest
from datetime import datetime, timezone
from app.security.audit import (
    SecurityEvent,
    SecurityEventType,
    SecurityAuditLogger,
    audit_logger,
    redact_sensitive,
    SENSITIVE_FIELDS,
)


class TestSecurityAuditLogging:
    """Test security audit logging functions."""

    def test_security_event_types_exist(self):
        """Security event types must be defined."""
        assert len(SecurityEventType) > 0

    def test_security_event_is_immutable(self):
        """Security events must be immutable."""
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            event.event_type = SecurityEventType.BUILD_COMPLETED

    def test_security_event_has_required_fields(self):
        """Security events must have required fields."""
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.event_type == SecurityEventType.BUILD_STARTED
        assert event.timestamp is not None
        assert event.severity == "info"

    def test_security_event_with_optional_fields(self):
        """Security events must support optional fields."""
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
            deployment_id="dep-123",
            container_id="container-456",
            user_id="user-789",
            client_ip="192.168.1.1",
            user_agent="Mozilla/5.0",
            details={"key": "value"},
            severity="warning",
        )
        assert event.deployment_id == "dep-123"
        assert event.container_id == "container-456"
        assert event.user_id == "user-789"
        assert event.client_ip == "192.168.1.1"
        assert event.user_agent == "Mozilla/5.0"
        assert event.details == {"key": "value"}
        assert event.severity == "warning"

    def test_sensitive_fields_exist(self):
        """Sensitive fields must be defined."""
        assert "password" in SENSITIVE_FIELDS
        assert "token" in SENSITIVE_FIELDS
        assert "secret_key" in SENSITIVE_FIELDS
        assert "database_url" in SENSITIVE_FIELDS

    def test_redact_sensitive_removes_secrets(self):
        """Sensitive fields must be redacted from events."""
        event = SecurityEvent(
            event_type=SecurityEventType.SECRET_DETECTED,
            timestamp=datetime.now(timezone.utc),
            details={"password": "hunter2", "token": "abc123"},
        )
        redacted = redact_sensitive(event)
        assert redacted.details["password"] == "[REDACTED]"
        assert redacted.details["token"] == "[REDACTED]"

    def test_redact_sensitive_preserves_non_sensitive(self):
        """Non-sensitive fields must be preserved."""
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
            details={"build_id": "abc123", "repo_url": "https://github.com/user/repo"},
        )
        redacted = redact_sensitive(event)
        assert redacted.details["build_id"] == "abc123"
        assert redacted.details["repo_url"] == "https://github.com/user/repo"

    def test_redact_sensitive_handles_none_details(self):
        """None details must be handled gracefully."""
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
            details=None,
        )
        redacted = redact_sensitive(event)
        assert redacted.details is None

    def test_audit_logger_exists(self):
        """Audit logger singleton must exist."""
        assert audit_logger is not None
        assert isinstance(audit_logger, SecurityAuditLogger)

    def test_audit_logger_has_log_method(self):
        """Audit logger must have log method."""
        assert hasattr(audit_logger, "log")
        assert callable(audit_logger.log)

    def test_audit_logger_logs_event(self):
        """Audit logger must log events without error."""
        event = SecurityEvent(
            event_type=SecurityEventType.BUILD_STARTED,
            timestamp=datetime.now(timezone.utc),
            details={"test": "value"},
        )
        # Should not raise
        audit_logger.log(event)
