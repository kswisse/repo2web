"""
Secret isolation — validates container environments and redacts secrets from logs.
"""

import re


FORBIDDEN_ENV_PATTERNS = [
    re.compile(r".*PASSWORD.*", re.IGNORECASE),
    re.compile(r".*SECRET.*", re.IGNORECASE),
    re.compile(r".*TOKEN.*", re.IGNORECASE),
    re.compile(r".*KEY.*", re.IGNORECASE),
    re.compile(r".*CREDENTIAL.*", re.IGNORECASE),
    re.compile(r"DATABASE_URL"),
    re.compile(r"REDIS_URL"),
    re.compile(r"GITHUB_TOKEN"),
    re.compile(r"JWT_SECRET"),
    re.compile(r"SECRET_KEY"),
]

SENSITIVE_FIELD_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api_key", re.IGNORECASE),
    re.compile(r"private_key", re.IGNORECASE),
    re.compile(r"database_url", re.IGNORECASE),
    re.compile(r"redis_url", re.IGNORECASE),
    re.compile(r"aws_access_key", re.IGNORECASE),
    re.compile(r"aws_secret_key", re.IGNORECASE),
    re.compile(r"credit_card", re.IGNORECASE),
    re.compile(r"ssn", re.IGNORECASE),
]


def is_secret_env_var(key: str) -> bool:
    """Check if an environment variable name matches secret patterns."""
    return any(pattern.search(key) for pattern in FORBIDDEN_ENV_PATTERNS)


def validate_container_env(env: dict[str, str], allowed_vars: dict[str, str] | None = None) -> list[str]:
    """
    Validate container environment variables against policy.
    Returns list of forbidden env vars found.
    """
    forbidden = []
    for key in env:
        if is_secret_env_var(key):
            forbidden.append(key)
        elif allowed_vars is not None and key not in allowed_vars:
            forbidden.append(key)
    return forbidden


def redact_secrets(text: str) -> str:
    """Redact secret patterns from text."""
    redacted = text
    for pattern in SENSITIVE_FIELD_PATTERNS:
        # Redact values that look like secrets (long strings after =)
        redacted = re.sub(
            rf"({pattern.pattern})\s*=\s*\S+",
            r"\1=[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted


def scan_build_output(output: str) -> list[str]:
    """
    Scan build output for leaked secrets.
    Returns list of detected secret patterns.
    """
    detected = []
    for pattern in SENSITIVE_FIELD_PATTERNS:
        if pattern.search(output):
            detected.append(pattern.pattern)
    return detected
