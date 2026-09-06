"""Entrypoint Detector module.

Detects the application start command using deterministic rules.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import DetectedSignal


@dataclass(frozen=True)
class EntrypointDetection:
    """Result of entrypoint detection."""

    command: str
    confidence: str  # HIGH, MEDIUM, LOW
    evidence: list[str]


# Node.js entrypoint patterns
NODE_ENTRYPOINTS = [
    # From package.json scripts
    {"pattern": r'"start"\s*:\s*"([^"]+)"', "source": "package.json", "priority": 1},
    {"pattern": r'"dev"\s*:\s*"([^"]+)"', "source": "package.json", "priority": 2},
    {"pattern": r'"serve"\s*:\s*"([^"]+)"', "source": "package.json", "priority": 3},
    # Common entry files
    {"file": "index.js", "priority": 4},
    {"file": "index.ts", "priority": 4},
    {"file": "main.js", "priority": 5},
    {"file": "main.ts", "priority": 5},
    {"file": "server.js", "priority": 6},
    {"file": "app.js", "priority": 7},
    {"file": "src/index.js", "priority": 8},
    {"file": "src/index.ts", "priority": 8},
    {"file": "src/main.js", "priority": 9},
    {"file": "src/main.ts", "priority": 9},
    {"file": "src/server.js", "priority": 10},
    {"file": "src/app.js", "priority": 11},
]

# Python entrypoint patterns
PYTHON_ENTRYPOINTS = [
    # From README or scripts
    {"pattern": r"uvicorn\s+([^\s:]+(?:\.[^\s:]+)*):app", "source": "readme", "priority": 1},
    {"pattern": r"flask\s+run", "source": "readme", "priority": 2},
    {"pattern": r"streamlit\s+run\s+([^\s]+)", "source": "readme", "priority": 3},
    {"pattern": r"python\s+manage\.py\s+runserver", "source": "readme", "priority": 4},
    # Common entry files
    {"file": "app.py", "priority": 5},
    {"file": "main.py", "priority": 6},
    {"file": "server.py", "priority": 7},
    {"file": "wsgi.py", "priority": 8},
    {"file": "asgi.py", "priority": 9},
    {"file": "manage.py", "priority": 10},
    {"file": "src/app.py", "priority": 11},
    {"file": "src/main.py", "priority": 12},
]


def detect_entrypoint(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
    framework: Optional[str],
    language: str,
) -> Optional[EntrypointDetection]:
    """Detect the application entrypoint.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.
        framework: Detected framework name.
        language: Detected language (python or node).

    Returns:
        EntrypointDetection or None if no entrypoint detected.
    """
    if language == "node":
        return _detect_node_entrypoint(key_files, file_names, framework)
    elif language == "python":
        return _detect_python_entrypoint(key_files, file_names, framework)
    return None


def _detect_node_entrypoint(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
    framework: Optional[str],
) -> Optional[EntrypointDetection]:
    """Detect Node.js entrypoint.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.
        framework: Detected framework name.

    Returns:
        EntrypointDetection or None if no entrypoint detected.
    """
    # First check package.json scripts
    package_json = key_files.get("package.json")
    if package_json:
        # Look for start script
        match = re.search(r'"start"\s*:\s*"([^"]+)"', package_json)
        if match:
            return EntrypointDetection(
                command=match.group(1),
                confidence="HIGH",
                evidence=["Found 'start' script in package.json"],
            )

        # Look for dev script
        match = re.search(r'"dev"\s*:\s*"([^"]+)"', package_json)
        if match:
            return EntrypointDetection(
                command=match.group(1),
                confidence="MEDIUM",
                evidence=["Found 'dev' script in package.json (no 'start' script)"],
            )

        # Look for serve script
        match = re.search(r'"serve"\s*:\s*"([^"]+)"', package_json)
        if match:
            return EntrypointDetection(
                command=match.group(1),
                confidence="MEDIUM",
                evidence=["Found 'serve' script in package.json"],
            )

    # Check for common entry files
    for entrypoint in NODE_ENTRYPOINTS:
        if "file" in entrypoint:
            if entrypoint["file"] in file_names:
                return EntrypointDetection(
                    command=f"node {entrypoint['file']}",
                    confidence="LOW",
                    evidence=[f"Found entry file '{entrypoint['file']}'"],
                )

    # Framework-specific defaults
    if framework == "nextjs":
        return EntrypointDetection(
            command="npm start",
            confidence="HIGH",
            evidence=["Next.js framework detected, using default start command"],
        )
    elif framework == "react":
        return EntrypointDetection(
            command="npm start",
            confidence="MEDIUM",
            evidence=["React framework detected, using default start command"],
        )

    return None


def _detect_python_entrypoint(
    key_files: dict[str, Optional[str]],
    file_names: list[str],
    framework: Optional[str],
) -> Optional[EntrypointDetection]:
    """Detect Python entrypoint.

    Args:
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.
        framework: Detected framework name.

    Returns:
        EntrypointDetection or None if no entrypoint detected.
    """
    # First check README for commands
    readme = key_files.get("README.md") or key_files.get("README.rst") or key_files.get("README.txt")
    if readme:
        # Look for uvicorn command
        match = re.search(r"uvicorn\s+([^\s:]+(?:\.[^\s:]+)*):app", readme)
        if match:
            module = match.group(1)
            return EntrypointDetection(
                command=f"uvicorn {module}:app --host 0.0.0.0 --port 8000",
                confidence="HIGH",
                evidence=["Found uvicorn command in README"],
            )

        # Look for flask run
        if "flask run" in readme:
            return EntrypointDetection(
                command="flask run --host 0.0.0.0 --port 5000",
                confidence="HIGH",
                evidence=["Found 'flask run' command in README"],
            )

        # Look for streamlit run
        match = re.search(r"streamlit\s+run\s+([^\s]+)", readme)
        if match:
            entry_file = match.group(1)
            return EntrypointDetection(
                command=f"streamlit run {entry_file}",
                confidence="HIGH",
                evidence=["Found streamlit run command in README"],
            )

        # Look for django runserver
        if "python manage.py runserver" in readme:
            return EntrypointDetection(
                command="python manage.py runserver 0.0.0.0:8000",
                confidence="HIGH",
                evidence=["Found django runserver command in README"],
            )

    # Check for common entry files
    for entrypoint in PYTHON_ENTRYPOINTS:
        if "file" in entrypoint:
            if entrypoint["file"] in file_names:
                # For Django, use manage.py
                if entrypoint["file"] == "manage.py":
                    return EntrypointDetection(
                        command="python manage.py runserver 0.0.0.0:8000",
                        confidence="MEDIUM",
                        evidence=["Found manage.py, inferring Django runserver"],
                    )

                # For other Python files, check if they have HTTP patterns
                file_content = key_files.get(entrypoint["file"])
                if file_content and _has_http_patterns(file_content):
                    module = entrypoint["file"].replace(".py", "")
                    return EntrypointDetection(
                        command=f"python {entrypoint['file']}",
                        confidence="LOW",
                        evidence=[f"Found entry file '{entrypoint['file']}' with HTTP patterns"],
                    )

    # Framework-specific defaults
    if framework == "fastapi":
        return EntrypointDetection(
            command="uvicorn main:app --host 0.0.0.0 --port 8000",
            confidence="HIGH",
            evidence=["FastAPI framework detected, using default uvicorn command"],
        )
    elif framework == "flask":
        return EntrypointDetection(
            command="python app.py",
            confidence="MEDIUM",
            evidence=["Flask framework detected, using default command"],
        )
    elif framework == "django":
        return EntrypointDetection(
            command="python manage.py runserver 0.0.0.0:8000",
            confidence="HIGH",
            evidence=["Django framework detected, using default runserver command"],
        )
    elif framework == "streamlit":
        return EntrypointDetection(
            command="streamlit run app.py",
            confidence="MEDIUM",
            evidence=["Streamlit framework detected, using default command"],
        )

    return None


def _has_http_patterns(content: str) -> bool:
    """Check if file content has HTTP-related patterns.

    Args:
        content: File content.

    Returns:
        True if HTTP patterns found.
    """
    http_patterns = [
        r"@app\.(get|post|put|delete|patch)",
        r"app\.route\(",
        r"FastAPI\(",
        r"Flask\(",
        r"Django",
        r"HTTPServer",
        r"BaseHTTPRequestHandler",
        r"uvicorn\.run",
        r"app\.run\(",
    ]
    for pattern in http_patterns:
        if re.search(pattern, content):
            return True
    return False
