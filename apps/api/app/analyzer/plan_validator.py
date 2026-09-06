"""Plan Validator module.

Validates ExecutionPlan objects for correctness and completeness.
"""

from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import ExecutionPlan


@dataclass(frozen=True)
class ValidationResult:
    """Result of plan validation."""

    valid: bool
    errors: list[str]


def validate_plan(plan: ExecutionPlan) -> ValidationResult:
    """Validate an ExecutionPlan.

    Args:
        plan: ExecutionPlan to validate.

    Returns:
        ValidationResult with valid flag and any errors.
    """
    errors = []

    # Validate repository
    errors.extend(_validate_repository(plan))

    # Validate application
    errors.extend(_validate_application(plan))

    # Validate build
    errors.extend(_validate_build(plan))

    # Validate runtime
    errors.extend(_validate_runtime(plan))

    # Validate compatibility
    errors.extend(_validate_compatibility(plan))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
    )


def _validate_repository(plan: ExecutionPlan) -> list[str]:
    """Validate repository info.

    Args:
        plan: ExecutionPlan.

    Returns:
        List of validation errors.
    """
    errors = []

    if not plan.repository.url:
        errors.append("Repository URL is required")

    if not plan.repository.commit_sha:
        errors.append("Repository commit SHA is required")
    elif not _is_valid_hex(plan.repository.commit_sha):
        errors.append(f"Repository commit SHA is not valid hex: {plan.repository.commit_sha}")

    if not plan.repository.owner:
        errors.append("Repository owner is required")

    if not plan.repository.repo:
        errors.append("Repository name is required")

    return errors


def _validate_application(plan: ExecutionPlan) -> list[str]:
    """Validate application info.

    Args:
        plan: ExecutionPlan.

    Returns:
        List of validation errors.
    """
    errors = []

    if not plan.application.language:
        errors.append("Application language is required")

    if plan.application.confidence not in ("HIGH", "MEDIUM", "LOW"):
        errors.append(f"Invalid confidence level: {plan.application.confidence}")

    return errors


def _validate_build(plan: ExecutionPlan) -> list[str]:
    """Validate build info.

    Args:
        plan: ExecutionPlan.

    Returns:
        List of validation errors.
    """
    errors = []

    if not plan.build.package_manager:
        errors.append("Package manager is required")

    if not plan.build.working_directory:
        errors.append("Working directory is required")

    return errors


def _validate_runtime(plan: ExecutionPlan) -> list[str]:
    """Validate runtime info.

    Args:
        plan: ExecutionPlan.

    Returns:
        List of validation errors.
    """
    errors = []

    if not plan.runtime.start_command:
        errors.append("Start command is required")

    if not isinstance(plan.runtime.port, int):
        errors.append("Port must be an integer")
    elif not (1 <= plan.runtime.port <= 65535):
        errors.append(f"Port must be between 1 and 65535, got {plan.runtime.port}")

    if not plan.runtime.host:
        errors.append("Host is required")

    if not plan.runtime.health_check_path:
        errors.append("Health check path is required")

    return errors


def _validate_compatibility(plan: ExecutionPlan) -> list[str]:
    """Validate compatibility info.

    Args:
        plan: ExecutionPlan.

    Returns:
        List of validation errors.
    """
    errors = []

    valid_statuses = {"SUPPORTED", "SUPPORTED_WITH_WARNINGS", "UNSUPPORTED", "BLOCKED"}
    if plan.compatibility.status not in valid_statuses:
        errors.append(f"Invalid compatibility status: {plan.compatibility.status}")

    valid_confidences = {"HIGH", "MEDIUM", "LOW"}
    if plan.compatibility.confidence not in valid_confidences:
        errors.append(f"Invalid compatibility confidence: {plan.compatibility.confidence}")

    return errors


def _is_valid_hex(s: str) -> bool:
    """Check if a string is valid hexadecimal.

    Args:
        s: String to check.

    Returns:
        True if valid hexadecimal.
    """
    try:
        int(s, 16)
        return True
    except ValueError:
        return False
