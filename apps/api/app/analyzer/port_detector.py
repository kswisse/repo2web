"""Port Detector module.

Detects the application port using deterministic rules.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import DetectedSignal


@dataclass(frozen=True)
class PortDetection:
    """Result of port detection."""

    port: int
    confidence: str  # HIGH, MEDIUM, LOW
    evidence: list[str]


# Framework default ports
FRAMEWORK_DEFAULT_PORTS = {
    "fastapi": 8000,
    "flask": 5000,
    "django": 8000,
    "streamlit": 8501,
    "gradio": 7860,
    "sanic": 8000,
    "tornado": 8888,
    "nextjs": 3000,
    "nuxt": 3000,
    "svelte": 5173,
    "angular": 4200,
    "vue": 3000,
    "react": 3000,
    "express": 3000,
    "koa": 3000,
    "fastify": 3000,
}


def detect_port(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
    framework: Optional[str],
) -> Optional[PortDetection]:
    """Detect the application port.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.
        framework: Detected framework name.

    Returns:
        PortDetection or None if no port detected.
    """
    # 1. Check for explicit port in scripts/commands
    port_from_scripts = _detect_port_from_scripts(key_files)
    if port_from_scripts:
        return port_from_scripts

    # 2. Check Dockerfile EXPOSE
    port_from_dockerfile = _detect_port_from_dockerfile(key_files)
    if port_from_dockerfile:
        return port_from_dockerfile

    # 3. Check source code for port patterns
    port_from_source = _detect_port_from_source(key_files, file_names)
    if port_from_source:
        return port_from_source

    # 4. Check .env.example for PORT variable
    port_from_env = _detect_port_from_env(key_files)
    if port_from_env:
        return port_from_env

    # 5. Framework defaults
    if framework and framework in FRAMEWORK_DEFAULT_PORTS:
        return PortDetection(
            port=FRAMEWORK_DEFAULT_PORTS[framework],
            confidence="LOW",
            evidence=[f"Using default port for {framework} framework"],
        )

    # Default fallback
    return PortDetection(
        port=3000,
        confidence="LOW",
        evidence=["No port detected, using default port 3000"],
    )


def _detect_port_from_scripts(key_files: dict[str, Optional[str]]) -> Optional[PortDetection]:
    """Detect port from scripts/commands.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        PortDetection or None if no port found.
    """
    # Check package.json scripts
    package_json = key_files.get("package.json")
    if package_json:
        # Look for port in scripts
        match = re.search(r'--port\s+(\d+)', package_json)
        if match:
            port = int(match.group(1))
            if 1 <= port <= 65535:
                return PortDetection(
                    port=port,
                    confidence="HIGH",
                    evidence=["Found explicit port in package.json scripts"],
                )

    # Check README for port
    readme = key_files.get("README.md") or key_files.get("README.rst") or key_files.get("README.txt")
    if readme:
        match = re.search(r'--port\s+(\d+)', readme)
        if match:
            port = int(match.group(1))
            if 1 <= port <= 65535:
                return PortDetection(
                    port=port,
                    confidence="MEDIUM",
                    evidence=["Found explicit port in README"],
                )

    return None


def _detect_port_from_dockerfile(key_files: dict[str, Optional[str]]) -> Optional[PortDetection]:
    """Detect port from Dockerfile EXPOSE.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        PortDetection or None if no port found.
    """
    dockerfile = key_files.get("Dockerfile")
    if not dockerfile:
        return None

    # Look for EXPOSE directive
    match = re.search(r'EXPOSE\s+(\d+)', dockerfile)
    if match:
        port = int(match.group(1))
        if 1 <= port <= 65535:
            return PortDetection(
                port=port,
                confidence="HIGH",
                evidence=["Found EXPOSE directive in Dockerfile"],
            )

    return None


def _detect_port_from_source(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
) -> Optional[PortDetection]:
    """Detect port from source code patterns.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.

    Returns:
        PortDetection or None if no port found.
    """
    # Common source files to check
    source_files = [
        "app.py",
        "main.py",
        "server.py",
        "index.js",
        "index.ts",
        "server.js",
        "src/index.js",
        "src/index.ts",
        "src/server.js",
    ]

    for source_file in source_files:
        content = key_files.get(source_file)
        if not content:
            continue

        # Look for port patterns
        port_patterns = [
            r'port\s*=\s*(\d+)',
            r'PORT\s*=\s*(\d+)',
            r'listen\(\s*(\d+)',
            r'\.listen\(\s*(\d+)',
            r'port:\s*(\d+)',
            r'--port\s+(\d+)',
        ]

        for pattern in port_patterns:
            match = re.search(pattern, content)
            if match:
                port = int(match.group(1))
                if 1 <= port <= 65535:
                    return PortDetection(
                        port=port,
                        confidence="MEDIUM",
                        evidence=[f"Found port pattern in {source_file}"],
                    )

    return None


def _detect_port_from_env(key_files: dict[str, Optional[str]]) -> Optional[PortDetection]:
    """Detect port from .env.example.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        PortDetection or None if no port found.
    """
    env_files = [".env.example", ".env.sample", ".env"]

    for env_file in env_files:
        content = key_files.get(env_file)
        if not content:
            continue

        # Look for PORT variable
        match = re.search(r'^PORT\s*=\s*(\d+)', content, re.MULTILINE)
        if match:
            port = int(match.group(1))
            if 1 <= port <= 65535:
                return PortDetection(
                    port=port,
                    confidence="HIGH",
                    evidence=[f"Found PORT variable in {env_file}"],
                )

    return None
