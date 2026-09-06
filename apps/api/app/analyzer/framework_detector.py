"""Framework Detector module.

Detects the application framework using deterministic rules.
"""

from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import DetectedSignal


@dataclass(frozen=True)
class FrameworkDetection:
    """Result of framework detection."""

    name: str
    confidence: str  # HIGH, MEDIUM, LOW
    evidence: list[str]


# Python framework detection rules (ordered by priority)
PYTHON_FRAMEWORKS = [
    {
        "name": "fastapi",
        "dependencies": ["fastapi"],
        "optional_dependencies": ["uvicorn", "hypercorn"],
        "file_patterns": [],
        "default_port": 8000,
    },
    {
        "name": "flask",
        "dependencies": ["flask"],
        "optional_dependencies": ["werkzeug"],
        "file_patterns": [],
        "default_port": 5000,
    },
    {
        "name": "django",
        "dependencies": ["django"],
        "optional_dependencies": [],
        "file_patterns": ["manage.py"],
        "default_port": 8000,
    },
    {
        "name": "streamlit",
        "dependencies": ["streamlit"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 8501,
    },
    {
        "name": "gradio",
        "dependencies": ["gradio"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 7860,
    },
    {
        "name": "sanic",
        "dependencies": ["sanic"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 8000,
    },
    {
        "name": "tornado",
        "dependencies": ["tornado"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 8888,
    },
]

# Node.js framework detection rules (ordered by priority)
NODE_FRAMEWORKS = [
    {
        "name": "nextjs",
        "dependencies": ["next"],
        "optional_dependencies": [],
        "file_patterns": ["next.config.js", "next.config.mjs", "next.config.ts"],
        "default_port": 3000,
    },
    {
        "name": "nuxt",
        "dependencies": ["nuxt"],
        "optional_dependencies": ["@nuxt/core"],
        "file_patterns": ["nuxt.config.js", "nuxt.config.ts"],
        "default_port": 3000,
    },
    {
        "name": "svelte",
        "dependencies": ["svelte"],
        "optional_dependencies": ["@sveltejs/kit"],
        "file_patterns": ["svelte.config.js", "svelte.config.ts"],
        "default_port": 5173,
    },
    {
        "name": "angular",
        "dependencies": ["@angular/core"],
        "optional_dependencies": [],
        "file_patterns": ["angular.json"],
        "default_port": 4200,
    },
    {
        "name": "vue",
        "dependencies": ["vue"],
        "optional_dependencies": ["@vue/cli-service", "vite"],
        "file_patterns": ["vue.config.js", "vue.config.ts"],
        "default_port": 3000,
    },
    {
        "name": "react",
        "dependencies": ["react", "react-dom"],
        "optional_dependencies": ["react-scripts", "vite", "webpack"],
        "file_patterns": [],
        "default_port": 3000,
    },
    {
        "name": "express",
        "dependencies": ["express"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 3000,
    },
    {
        "name": "koa",
        "dependencies": ["koa"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 3000,
    },
    {
        "name": "fastify",
        "dependencies": ["fastify"],
        "optional_dependencies": [],
        "file_patterns": [],
        "default_port": 3000,
    },
]


def detect_framework(
    dependencies: dict[str, str],
    file_names: list[str],
    language: str,
) -> Optional[FrameworkDetection]:
    """Detect the framework from dependencies and file names.

    Args:
        dependencies: Dictionary of dependency names to versions.
        file_names: List of file names in the repository.
        language: Detected language (python or node).

    Returns:
        FrameworkDetection or None if no framework detected.
    """
    if language == "python":
        return _detect_python_framework(dependencies, file_names)
    elif language == "node":
        return _detect_node_framework(dependencies, file_names)
    return None


def _detect_python_framework(
    dependencies: dict[str, str],
    file_names: list[str],
) -> Optional[FrameworkDetection]:
    """Detect Python framework.

    Args:
        dependencies: Dictionary of dependency names to versions.
        file_names: List of file names in the repository.

    Returns:
        FrameworkDetection or None if no framework detected.
    """
    dep_names = set(dependencies.keys())

    for framework in PYTHON_FRAMEWORKS:
        # Check if required dependencies are present
        required_present = all(d in dep_names for d in framework["dependencies"])
        if not required_present:
            continue

        # Check file patterns
        file_pattern_match = any(
            fp in file_names for fp in framework["file_patterns"]
        )

        # Calculate confidence
        evidence = []
        confidence = "HIGH"

        for dep in framework["dependencies"]:
            if dep in dep_names:
                evidence.append(f"Dependency '{dep}' found in manifest")

        for dep in framework.get("optional_dependencies", []):
            if dep in dep_names:
                evidence.append(f"Optional dependency '{dep}' found")

        for fp in framework["file_patterns"]:
            if fp in file_names:
                evidence.append(f"File '{fp}' found")

        # Lower confidence if only dependencies match (no file patterns)
        if framework["file_patterns"] and not file_pattern_match:
            confidence = "MEDIUM"

        return FrameworkDetection(
            name=framework["name"],
            confidence=confidence,
            evidence=evidence,
        )

    return None


def _detect_node_framework(
    dependencies: dict[str, str],
    file_names: list[str],
) -> Optional[FrameworkDetection]:
    """Detect Node.js framework.

    Args:
        dependencies: Dictionary of dependency names to versions.
        file_names: List of file names in the repository.

    Returns:
        FrameworkDetection or None if no framework detected.
    """
    dep_names = set(dependencies.keys())

    for framework in NODE_FRAMEWORKS:
        # Check if required dependencies are present
        required_present = all(d in dep_names for d in framework["dependencies"])
        if not required_present:
            continue

        # Check file patterns
        file_pattern_match = any(
            fp in file_names for fp in framework["file_patterns"]
        )

        # Calculate confidence
        evidence = []
        confidence = "HIGH"

        for dep in framework["dependencies"]:
            if dep in dep_names:
                evidence.append(f"Dependency '{dep}' found in manifest")

        for dep in framework.get("optional_dependencies", []):
            if dep in dep_names:
                evidence.append(f"Optional dependency '{dep}' found")

        for fp in framework["file_patterns"]:
            if fp in file_names:
                evidence.append(f"File '{fp}' found")

        # Lower confidence if only dependencies match (no file patterns)
        if framework["file_patterns"] and not file_pattern_match:
            confidence = "MEDIUM"

        return FrameworkDetection(
            name=framework["name"],
            confidence=confidence,
            evidence=evidence,
        )

    return None


def get_framework_default_port(framework_name: str) -> int:
    """Get the default port for a framework.

    Args:
        framework_name: Name of the framework.

    Returns:
        Default port number.
    """
    for framework in PYTHON_FRAMEWORKS + NODE_FRAMEWORKS:
        if framework["name"] == framework_name:
            return framework["default_port"]
    return 3000  # Default fallback
