"""Compatibility Evaluator module.

Evaluates if a repository is compatible with the deployment system.
"""

from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import CompatibilityResult, DetectedSignal


# Supported languages
SUPPORTED_LANGUAGES = {"python", "node"}

# Supported frameworks per language
SUPPORTED_FRAMEWORKS = {
    "python": {"fastapi", "flask", "django", "streamlit", "gradio", "sanic", "tornado"},
    "node": {"nextjs", "nuxt", "svelte", "angular", "vue", "react", "express", "koa", "fastify"},
}

# Frameworks that are blocked for security/policy reasons
BLOCKED_FRAMEWORKS = set()

# Patterns that indicate CLI-only or library code
CLI_PATTERNS = [
    r"argparse",
    r"click\.command",
    r"typer\.Typer",
    r"if __name__\s*==\s*['\"]__main__['\"]",
    r"commander\.Command",
    r"yargs",
]

# Patterns that indicate library code (no HTTP entrypoint)
LIBRARY_PATTERNS = [
    r"def\s+calculate",
    r"def\s+process",
    r"def\s+transform",
    r"module\.exports\s*=",
    r"export\s+default\s+function",
]


def evaluate_compatibility(
    language: Optional[str],
    framework: Optional[str],
    entrypoint: Optional[str],
    port: Optional[int],
    key_files: dict[str, Optional[str]],
    file_names: list[str],
    evidence: list[DetectedSignal],
) -> CompatibilityResult:
    """Evaluate if a repository is compatible with the deployment system.

    Args:
        language: Detected language.
        framework: Detected framework.
        entrypoint: Detected entrypoint command.
        port: Detected port.
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.
        evidence: List of detected signals.

    Returns:
        CompatibilityResult with status, confidence, blockers, and warnings.
    """
    blockers = []
    warnings = []
    confidence_factors = []

    # 1. Check language support
    if not language:
        blockers.append("No supported language detected")
        return CompatibilityResult(
            status="UNSUPPORTED",
            confidence="HIGH",
            blockers=blockers,
            warnings=warnings,
        )

    if language not in SUPPORTED_LANGUAGES:
        blockers.append(f"Language '{language}' is not supported")
        return CompatibilityResult(
            status="UNSUPPORTED",
            confidence="HIGH",
            blockers=blockers,
            warnings=warnings,
        )

    confidence_factors.append("Language is supported")

    # 2. Check framework support
    if framework:
        if framework in BLOCKED_FRAMEWORKS:
            blockers.append(f"Framework '{framework}' is blocked for security/policy reasons")
            return CompatibilityResult(
                status="BLOCKED",
                confidence="HIGH",
                blockers=blockers,
                warnings=warnings,
            )

        if framework in SUPPORTED_FRAMEWORKS.get(language, set()):
            confidence_factors.append("Framework is supported")
        else:
            warnings.append(f"Framework '{framework}' is not officially supported")
            confidence_factors.append("Framework is not officially supported")

    # 3. Check for CLI-only code
    is_cli = _detect_cli_only(key_files, file_names)
    if is_cli:
        blockers.append("Repository appears to be CLI-only (no HTTP entrypoint)")
        return CompatibilityResult(
            status="UNSUPPORTED",
            confidence="MEDIUM",
            blockers=blockers,
            warnings=warnings,
        )

    # 4. Check for library code
    is_library = _detect_library_code(key_files, file_names)
    if is_library:
        warnings.append("Repository appears to be a library (no HTTP entrypoint)")
        confidence_factors.append("Library detected")

    # 5. Check entrypoint
    if not entrypoint:
        warnings.append("No entrypoint detected, will use framework default")
        confidence_factors.append("No entrypoint detected")
    else:
        confidence_factors.append("Entrypoint detected")

    # 6. Check port
    if not port:
        warnings.append("No port detected, will use framework default")
        confidence_factors.append("No port detected")
    else:
        confidence_factors.append("Port detected")

    # 7. Check for security concerns
    security_warnings = _check_security_concerns(key_files, file_names)
    warnings.extend(security_warnings)

    # Determine final status
    if blockers:
        status = "UNSUPPORTED"
    elif warnings:
        status = "SUPPORTED_WITH_WARNINGS"
    else:
        status = "SUPPORTED"

    # Determine confidence
    if len(confidence_factors) >= 3:
        confidence = "HIGH"
    elif len(confidence_factors) >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return CompatibilityResult(
        status=status,
        confidence=confidence,
        blockers=blockers,
        warnings=warnings,
    )


def _detect_cli_only(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
) -> bool:
    """Detect if repository is CLI-only.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.

    Returns:
        True if repository appears to be CLI-only.
    """
    # Check for CLI patterns in source files
    source_files = [
        "app.py",
        "main.py",
        "server.py",
        "cli.py",
        "index.js",
        "index.ts",
        "cli.js",
        "cli.ts",
    ]

    cli_count = 0
    http_count = 0

    for source_file in source_files:
        content = key_files.get(source_file)
        if not content:
            continue

        # Check for CLI patterns
        for pattern in CLI_PATTERNS:
            if __import__("re").search(pattern, content):
                cli_count += 1
                break

        # Check for HTTP patterns
        http_patterns = [
            r"@app\.(get|post|put|delete|patch)",
            r"app\.route\(",
            r"FastAPI\(",
            r"Flask\(",
            r"express\(\)",
            r"app\.listen\(",
        ]
        for pattern in http_patterns:
            if __import__("re").search(pattern, content):
                http_count += 1
                break

    # If CLI patterns found but no HTTP patterns, likely CLI-only
    return cli_count > 0 and http_count == 0


def _detect_library_code(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
) -> bool:
    """Detect if repository is library code.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.

    Returns:
        True if repository appears to be library code.
    """
    # Check for library patterns
    source_files = [
        "app.py",
        "main.py",
        "index.js",
        "index.ts",
        "src/index.js",
        "src/index.ts",
    ]

    library_count = 0
    http_count = 0

    for source_file in source_files:
        content = key_files.get(source_file)
        if not content:
            continue

        # Check for library patterns
        for pattern in LIBRARY_PATTERNS:
            if __import__("re").search(pattern, content):
                library_count += 1
                break

        # Check for HTTP patterns
        http_patterns = [
            r"@app\.(get|post|put|delete|patch)",
            r"app\.route\(",
            r"FastAPI\(",
            r"Flask\(",
            r"express\(\)",
            r"app\.listen\(",
        ]
        for pattern in http_patterns:
            if __import__("re").search(pattern, content):
                http_count += 1
                break

    # If library patterns found but no HTTP patterns, likely library
    return library_count > 0 and http_count == 0


def _check_security_concerns(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
) -> list[str]:
    """Check for security concerns.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.

    Returns:
        List of security warnings.
    """
    warnings = []

    # Check for Dockerfile with privileged mode
    dockerfile = key_files.get("Dockerfile")
    if dockerfile:
        if "privileged" in dockerfile.lower():
            warnings.append("Dockerfile contains privileged mode (security risk)")
        if "docker.sock" in dockerfile.lower():
            warnings.append("Dockerfile mounts Docker socket (security risk)")

    # Check for docker-compose with privileged mode
    compose_files = ["docker-compose.yml", "docker-compose.yaml"]
    for compose_file in compose_files:
        content = key_files.get(compose_file)
        if content and "privileged: true" in content.lower():
            warnings.append(f"{compose_file} contains privileged mode (security risk)")

    # Check for .env files committed
    if ".env" in file_names:
        warnings.append(".env file found in repository (potential secret exposure)")

    return warnings
