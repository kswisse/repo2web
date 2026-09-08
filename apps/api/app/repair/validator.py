"""
Repair Validator — deterministic validation of repair proposals.

Every proposal must pass this validator before being applied.
The validator enforces all existing security boundaries.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.repair.types import RepairProposal, RepairType
from app.security.validation import SHELL_METACHARACTERS, MAX_URL_LENGTH


# Maximum command length for repair values
MAX_REPAIR_COMMAND_LENGTH = 2000

# Valid health check paths
VALID_HEALTH_PATH_PATTERN = re.compile(r"^/[a-zA-Z0-9_/.-]*$")

# Valid port range
MIN_PORT = 1
MAX_PORT = 65535

# Allowed repair targets per repair type
ALLOWED_TARGETS = {
    RepairType.FRAMEWORK_DETECTION: {"framework"},
    RepairType.START_COMMAND: {"start_command"},
    RepairType.HEALTH_CHECK_PATH: {"health_check_path"},
    RepairType.PACKAGE_MANAGER: {"package_manager"},
    RepairType.INSTALL_COMMAND: {"install_command"},
    RepairType.BUILD_COMMAND: {"build_command"},
    RepairType.PORT: {"port"},
}

# Allowed framework values (must match known frameworks)
ALLOWED_FRAMEWORKS = {
    "fastapi", "flask", "django", "streamlit", "gradio", "sanic", "tornado",
    "nextjs", "nuxt", "svelte", "angular", "vue", "react", "express", "koa", "fastify",
}

# Allowed package manager values
ALLOWED_PACKAGE_MANAGERS = {"npm", "yarn", "pnpm", "pip", "pipenv", "poetry"}

# Allowed build command prefixes (subset of executor allowlist)
ALLOWED_REPAIR_COMMAND_PREFIXES = (
    "pip install", "pip3 install",
    "npm install", "npm ci", "npm start", "npm run",
    "npx",
    "yarn install", "yarn add", "yarn start",
    "pnpm install", "pnpm add",
    "python", "python3", "uvicorn", "gunicorn", "streamlit", "flask",
    "node",
)


@dataclass(frozen=True)
class ValidationResult:
    """Result of repair proposal validation."""

    valid: bool
    errors: list[str]


def validate_repair_proposal(proposal: RepairProposal) -> ValidationResult:
    """Validate a repair proposal against all security and integrity constraints.

    Args:
        proposal: The repair proposal to validate.

    Returns:
        ValidationResult with valid flag and any errors.
    """
    errors = []

    # 1. Validate repair type
    if not isinstance(proposal.repair_type, RepairType):
        errors.append(f"Unsupported repair type: {proposal.repair_type}")
        return ValidationResult(valid=False, errors=errors)

    # 2. Validate target matches repair type
    allowed_targets = ALLOWED_TARGETS.get(proposal.repair_type, set())
    if proposal.target not in allowed_targets:
        errors.append(
            f"Target '{proposal.target}' not allowed for repair type '{proposal.repair_type.value}'"
        )

    # 3. Validate confidence
    if proposal.confidence not in ("HIGH", "MEDIUM", "LOW"):
        errors.append(f"Invalid confidence level: {proposal.confidence}")

    # 4. Type-specific validation
    if proposal.repair_type == RepairType.FRAMEWORK_DETECTION:
        errors.extend(_validate_framework(proposal))

    elif proposal.repair_type == RepairType.START_COMMAND:
        errors.extend(_validate_command(proposal))

    elif proposal.repair_type == RepairType.HEALTH_CHECK_PATH:
        errors.extend(_validate_health_path(proposal))

    elif proposal.repair_type == RepairType.PACKAGE_MANAGER:
        errors.extend(_validate_package_manager(proposal))

    elif proposal.repair_type == RepairType.INSTALL_COMMAND:
        errors.extend(_validate_command(proposal))

    elif proposal.repair_type == RepairType.BUILD_COMMAND:
        errors.extend(_validate_command(proposal))

    elif proposal.repair_type == RepairType.PORT:
        errors.extend(_validate_port(proposal))

    # 5. Validate no security weakening
    errors.extend(_validate_no_security_weakening(proposal))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def _validate_framework(proposal: RepairProposal) -> list[str]:
    """Validate framework detection repair."""
    errors = []
    if proposal.proposed_value not in ALLOWED_FRAMEWORKS:
        errors.append(f"Proposed framework '{proposal.proposed_value}' is not a recognized framework")
    if proposal.original_value and proposal.original_value not in ALLOWED_FRAMEWORKS and proposal.original_value != "unknown":
        # Original was invalid — that's the point of the repair
        pass
    return errors


def _validate_command(proposal: RepairProposal) -> list[str]:
    """Validate a command repair (start, install, build)."""
    errors = []
    value = proposal.proposed_value

    # Reject empty commands
    if not value or not value.strip():
        errors.append("Proposed command cannot be empty")
        return errors

    # Reject excessively long commands
    if len(value) > MAX_REPAIR_COMMAND_LENGTH:
        errors.append(f"Proposed command exceeds maximum length of {MAX_REPAIR_COMMAND_LENGTH}")
        return errors

    # Reject shell metacharacters (injection prevention)
    if SHELL_METACHARACTERS.search(value):
        errors.append(f"Proposed command contains shell metacharacters: {value!r}")
        return errors

    # Reject null bytes
    if "\x00" in value:
        errors.append("Proposed command contains null bytes")
        return errors

    # Reject newlines (CRLF injection)
    if "\n" in value or "\r" in value:
        errors.append("Proposed command contains newlines")
        return errors

    return errors


def _validate_health_path(proposal: RepairProposal) -> list[str]:
    """Validate health check path repair."""
    errors = []
    value = proposal.proposed_value

    if not value.startswith("/"):
        errors.append("Health check path must start with /")

    if not VALID_HEALTH_PATH_PATTERN.match(value):
        errors.append(f"Invalid health check path: {value!r}")

    if len(value) > 200:
        errors.append("Health check path too long")

    return errors


def _validate_package_manager(proposal: RepairProposal) -> list[str]:
    """Validate package manager repair."""
    errors = []
    if proposal.proposed_value not in ALLOWED_PACKAGE_MANAGERS:
        errors.append(f"Unsupported package manager: {proposal.proposed_value}")
    return errors


def _validate_port(proposal: RepairProposal) -> list[str]:
    """Validate port repair."""
    errors = []
    try:
        port = int(proposal.proposed_value)
        if not (MIN_PORT <= port <= MAX_PORT):
            errors.append(f"Port must be between {MIN_PORT} and {MAX_PORT}")
    except ValueError:
        errors.append(f"Invalid port value: {proposal.proposed_value!r}")
    return errors


def _validate_no_security_weakening(proposal: RepairProposal) -> list[str]:
    """Ensure the proposal does not weaken security controls."""
    errors = []

    # Block any attempt to modify security-related settings
    blocked_targets = {
        "privileged", "cap_add", "cap_drop", "network_mode", "pid_mode",
        "user", "security_opt", "volumes", "docker_socket", "host_network",
        "host_pid", "secrets", "ssrf", "sandbox",
    }
    if proposal.target in blocked_targets:
        errors.append(f"Cannot modify security-related target: {proposal.target}")

    # Block proposals that try to weaken command validation
    dangerous_patterns = [
        "disable", "bypass", "skip", "ignore", "unsafe", "nosec",
    ]
    combined = (proposal.proposed_value + " " + proposal.rationale).lower()
    for pattern in dangerous_patterns:
        if pattern in combined:
            errors.append(f"Proposal contains security-weakening language: '{pattern}'")
            break

    return errors
