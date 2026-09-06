"""Environment Detector module.

Detects environment variables required by the application.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import EnvironmentVariable


# Patterns that indicate secret variables
SECRET_PATTERNS = [
    r"key",
    r"token",
    r"secret",
    r"password",
    r"passwd",
    r"credential",
    r"auth",
    r"api_key",
    r"apikey",
    r"access_key",
    r"secret_key",
    r"private_key",
]


def detect_environment_variables(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
) -> list[EnvironmentVariable]:
    """Detect environment variables from various sources.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.

    Returns:
        List of detected environment variables.
    """
    variables = {}

    # 1. Check .env.example / .env.sample
    env_vars_from_files = _detect_from_env_files(key_files)
    for var in env_vars_from_files:
        variables[var.name] = var

    # 2. Check source code references
    env_vars_from_source = _detect_from_source_code(key_files, file_names)
    for var in env_vars_from_source:
        if var.name not in variables:
            variables[var.name] = var

    # 3. Check README mentions
    env_vars_from_readme = _detect_from_readme(key_files)
    for var in env_vars_from_readme:
        if var.name not in variables:
            variables[var.name] = var

    return list(variables.values())


def _detect_from_env_files(key_files: dict[str, Optional[str]]) -> list[EnvironmentVariable]:
    """Detect environment variables from .env files.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        List of detected environment variables.
    """
    variables = []
    env_files = [".env.example", ".env.sample", ".env"]

    for env_file in env_files:
        content = key_files.get(env_file)
        if not content:
            continue

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse KEY=value or KEY= (empty value)
            match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)', line)
            if match:
                name = match.group(1)
                value = match.group(2).strip()

                # Determine if required (empty value often means required)
                required = value == "" or value == '""' or value == "''"

                # Determine if secret
                secret = _is_secret_variable(name)

                # Determine source
                source = f"env_file:{env_file}"

                variables.append(EnvironmentVariable(
                    name=name,
                    required=required,
                    secret=secret,
                    source=source,
                    default=value if value else None,
                ))

    return variables


def _detect_from_source_code(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
) -> list[EnvironmentVariable]:
    """Detect environment variables from source code.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.

    Returns:
        List of detected environment variables.
    """
    variables = []

    # Source files to check
    source_files = [
        "app.py",
        "main.py",
        "server.py",
        "config.py",
        "settings.py",
        "index.js",
        "index.ts",
        "server.js",
        "config.js",
        "config.ts",
        "src/index.js",
        "src/index.ts",
        "src/server.js",
        "src/config.js",
        "src/config.ts",
    ]

    for source_file in source_files:
        content = key_files.get(source_file)
        if not content:
            continue

        # Python patterns: os.environ.get("KEY"), os.environ["KEY"], os.getenv("KEY")
        python_patterns = [
            r'os\.environ\.get\(["\']([A-Z_][A-Z0-9_]*)["\']',
            r'os\.environ\["([A-Z_][A-Z0-9_]*)"\]',
            r'os\.environ\["([A-Z_][A-Z0-9_]*)"\]',
            r'os\.getenv\(["\']([A-Z_][A-Z0-9_]*)["\']',
            r'os\.environ\.get\(["\']([A-Z_][A-Z0-9_]*)["\'],\s*["\']([^"\']*)["\']',
            r'os\.getenv\(["\']([A-Z_][A-Z0-9_]*)["\'],\s*["\']([^"\']*)["\']',
        ]

        for pattern in python_patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                default = match.group(2) if match.lastindex >= 2 else None
                variables.append(EnvironmentVariable(
                    name=name,
                    required=default is None,
                    secret=_is_secret_variable(name),
                    source=f"source:{source_file}",
                    default=default,
                ))

        # Node.js patterns: process.env.KEY, process.env["KEY"]
        node_patterns = [
            r'process\.env\.([A-Z_][A-Z0-9_]*)',
            r'process\.env\["([A-Z_][A-Z0-9_]*)"\]',
            r'process\.env\["([A-Z_][A-Z0-9_]*)"\]',
        ]

        for pattern in node_patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                variables.append(EnvironmentVariable(
                    name=name,
                    required=True,  # Can't determine default from source
                    secret=_is_secret_variable(name),
                    source=f"source:{source_file}",
                    default=None,
                ))

    return variables


def _detect_from_readme(key_files: dict[str, Optional[str]]) -> list[EnvironmentVariable]:
    """Detect environment variables from README.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        List of detected environment variables.
    """
    variables = []

    readme = key_files.get("README.md") or key_files.get("README.rst") or key_files.get("README.txt")
    if not readme:
        return variables

    # Look for environment variable mentions
    patterns = [
        r'`([A-Z_][A-Z0-9_]*)`',  # `DATABASE_URL`
        r'\*\*([A-Z_][A-Z0-9_]*)\*\*',  # **DATABASE_URL**
        r'([A-Z_][A-Z0-9_]*)\s*=',  # DATABASE_URL=
        r'export\s+([A-Z_][A-Z0-9_]*)',  # export DATABASE_URL
    ]

    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, readme):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                variables.append(EnvironmentVariable(
                    name=name,
                    required=False,  # README mentions don't guarantee required
                    secret=_is_secret_variable(name),
                    source="readme",
                    default=None,
                ))

    return variables


def _is_secret_variable(name: str) -> bool:
    """Check if a variable name indicates a secret.

    Args:
        name: Variable name.

    Returns:
        True if the variable appears to be a secret.
    """
    name_lower = name.lower()
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False
