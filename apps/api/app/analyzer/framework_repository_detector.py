"""Framework Repository Detector module.

Detects whether a repository IS the framework itself (e.g., tiangolo/fastapi)
vs. an application USING the framework (e.g., my-fastapi-app).

This runs AFTER framework detection and BEFORE compatibility evaluation.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import DetectedSignal


@dataclass(frozen=True)
class FrameworkRepositoryDetection:
    """Result of framework repository detection."""

    is_framework_repository: bool
    confidence: str  # HIGH, MEDIUM, LOW
    evidence: list[str]


# Known framework repositories - exact owner/name matches required
KNOWN_FRAMEWORK_REPOSITORIES = {
    # Python frameworks
    ("tiangolo", "fastapi"),
    ("pallets", "flask"),
    ("django", "django"),
    ("streamlit", "streamlit"),
    ("gradio-app", "gradio"),
    ("nicegui", "nicegui"),
    # Node.js frameworks
    ("vercel", "next.js"),
    ("nuxt", "nuxt"),
    ("sveltejs", "kit"),
    ("angular", "angular"),
    ("vuejs", "core"),
    ("facebook", "react"),
    ("expressjs", "express"),
    ("koajs", "koa"),
    ("fastify", "fastify"),
}

# Framework package names that match their repository
FRAMEWORK_PACKAGE_NAMES = {
    "fastapi",
    "flask",
    "django",
    "streamlit",
    "gradio",
    "sanic",
    "tornado",
    "next",
    "nuxt",
    "svelte",
    "angular",
    "vue",
    "react",
    "express",
    "koa",
    "fastify",
}

# Application indicator files at root level
APPLICATION_INDICATORS = {
    "app.py",
    "main.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "index.js",
    "index.ts",
    "server.js",
    "app.js",
}


def detect_framework_repository(
    owner: str,
    repo: str,
    key_files: dict[str, Optional[str]],
    file_names: list[str],
    all_dependencies: dict[str, str],
    framework_name: Optional[str],
) -> FrameworkRepositoryDetection:
    """Detect if a repository IS the framework itself.

    Uses multiple deterministic signals:
    1. owner/name identity (exact match to known framework repos)
    2. project metadata (pyproject.toml name matches framework)
    3. source package structure (package dir matches framework name)
    4. dependency declarations (framework NOT listed as external dependency)
    5. absence of application indicators (no app.py, main.py at root)

    Args:
        owner: Repository owner.
        repo: Repository name.
        key_files: Dictionary of key file contents.
        file_names: List of file names in the repository.
        all_dependencies: Dictionary of all dependencies.
        framework_name: Detected framework name (from framework_detector).

    Returns:
        FrameworkRepositoryDetection with result and evidence.
    """
    evidence = []
    confidence_factors = []

    # Signal 1: owner/name identity check
    identity_match = _check_owner_name_identity(owner, repo)
    if identity_match:
        evidence.append(f"Repository owner/name matches known framework: {owner}/{repo}")
        confidence_factors.append("IDENTITY_MATCH")

    # Signal 2: project metadata check
    metadata_match = _check_project_metadata(key_files, framework_name)
    if metadata_match:
        evidence.append(f"Project metadata indicates framework: {metadata_match}")
        confidence_factors.append("METADATA_MATCH")

    # Signal 3: source package structure check
    structure_match = _check_source_package_structure(file_names, framework_name)
    if structure_match:
        evidence.append(f"Source package structure matches framework: {structure_match}")
        confidence_factors.append("STRUCTURE_MATCH")

    # Signal 4: dependency declarations check
    dependency_match = _check_dependency_declarations(all_dependencies, framework_name)
    if dependency_match:
        evidence.append(f"Dependency declarations indicate framework: {dependency_match}")
        confidence_factors.append("DEPENDENCY_MATCH")

    # Signal 5: absence of application indicators
    no_app_indicators = _check_no_application_indicators(file_names)
    if no_app_indicators:
        evidence.append("No application indicator files at root (app.py, main.py, etc.)")
        confidence_factors.append("NO_APP_INDICATORS")

    # Determine result based on evidence
    is_framework_repository = False
    confidence = "LOW"

    # Strong signal: exact identity match
    if "IDENTITY_MATCH" in confidence_factors:
        is_framework_repository = True
        confidence = "HIGH"
    # Multiple supporting signals
    elif len(confidence_factors) >= 3:
        is_framework_repository = True
        confidence = "HIGH"
    elif len(confidence_factors) >= 2:
        is_framework_repository = True
        confidence = "MEDIUM"
    # Single weak signal - need to be careful about false positives
    elif len(confidence_factors) == 1:
        # Only mark as framework repo if the single signal is strong
        if "METADATA_MATCH" in confidence_factors or "DEPENDENCY_MATCH" in confidence_factors:
            is_framework_repository = True
            confidence = "LOW"

    # If no signals matched, it's NOT a framework repository
    if not confidence_factors:
        evidence.append("No framework repository signals detected")

    return FrameworkRepositoryDetection(
        is_framework_repository=is_framework_repository,
        confidence=confidence,
        evidence=evidence,
    )


def _check_owner_name_identity(owner: str, repo: str) -> bool:
    """Check if owner/repo matches a known framework repository.

    Args:
        owner: Repository owner.
        repo: Repository name.

    Returns:
        True if exact match found.
    """
    return (owner.lower(), repo.lower()) in KNOWN_FRAMEWORK_REPOSITORIES


def _check_project_metadata(
    key_files: dict[str, Optional[str]],
    framework_name: Optional[str],
) -> Optional[str]:
    """Check project metadata for framework indicators.

    Looks at pyproject.toml [project] name and setup.py name=.

    Args:
        key_files: Dictionary of key file contents.
        framework_name: Detected framework name.

    Returns:
        Match description or None.
    """
    if not framework_name:
        return None

    # Check pyproject.toml
    pyproject_content = key_files.get("pyproject.toml")
    if pyproject_content:
        # Look for [project] name = "framework_name"
        match = re.search(
            r'\[project\]\s*\n.*?name\s*=\s*"([^"]+)"',
            pyproject_content,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            project_name = match.group(1).lower().replace("-", "").replace("_", "")
            framework_normalized = framework_name.lower().replace("-", "").replace("_", "")
            if project_name == framework_normalized:
                return f"pyproject.toml [project] name matches framework ({match.group(1)})"

    # Check setup.py
    setup_py_content = key_files.get("setup.py")
    if setup_py_content:
        # Look for name="framework_name" or name='framework_name'
        match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', setup_py_content)
        if match:
            setup_name = match.group(1).lower().replace("-", "").replace("_", "")
            framework_normalized = framework_name.lower().replace("-", "").replace("_", "")
            if setup_name == framework_normalized:
                return f"setup.py name matches framework ({match.group(1)})"

    return None


def _check_source_package_structure(
    file_names: list[str],
    framework_name: Optional[str],
) -> Optional[str]:
    """Check if source package structure matches framework name.

    Looks for a package directory named after the framework with __init__.py.

    Args:
        file_names: List of file names in the repository.
        framework_name: Detected framework name.

    Returns:
        Match description or None.
    """
    if not framework_name:
        return None

    # Normalize framework name for comparison
    framework_normalized = framework_name.lower().replace("-", "").replace("_", "")

    # Check for package directory with __init__.py
    for file_name in file_names:
        # Look for pattern: framework_name/__init__.py
        if file_name.endswith("/__init__.py") or file_name == "__init__.py":
            # Extract the directory name
            parts = file_name.split("/")
            if len(parts) >= 2:
                dir_name = parts[-2].lower().replace("-", "").replace("_", "")
                if dir_name == framework_normalized:
                    return f"Package directory '{parts[-2]}' matches framework"

    return None


def _check_dependency_declarations(
    all_dependencies: dict[str, str],
    framework_name: Optional[str],
) -> Optional[str]:
    """Check if framework is NOT listed as an external dependency.

    If the repo IS the framework, the framework package won't be in dependencies.
    If the repo USES the framework, it WILL be in dependencies.

    Args:
        all_dependencies: Dictionary of all dependencies.
        framework_name: Detected framework name.

    Returns:
        Match description or None.
    """
    if not framework_name:
        return None

    # Normalize framework name
    framework_normalized = framework_name.lower().replace("-", "_")

    # Check if framework appears in dependencies
    dep_names_normalized = {k.lower().replace("-", "_") for k in all_dependencies.keys()}

    if framework_normalized not in dep_names_normalized:
        # Framework NOT in dependencies - could be the framework itself
        # But only if we have other evidence (this alone is weak)
        return f"Framework '{framework_name}' NOT listed as external dependency"

    return None


def _check_no_application_indicators(file_names: list[str]) -> bool:
    """Check for absence of application indicator files at root.

    Args:
        file_names: List of file names in the repository.

    Returns:
        True if no application indicators found.
    """
    # Check root-level files only (not in subdirectories)
    root_files = {f for f in file_names if "/" not in f}

    # If there are application indicators, this is likely an app, not a framework
    has_app_indicators = bool(root_files.intersection(APPLICATION_INDICATORS))

    return not has_app_indicators


def get_framework_repository_signal(
    detection: FrameworkRepositoryDetection,
) -> Optional[DetectedSignal]:
    """Convert detection to a DetectedSignal for evidence collection.

    Args:
        detection: FrameworkRepositoryDetection result.

    Returns:
        DetectedSignal if framework repository detected, None otherwise.
    """
    if not detection.is_framework_repository:
        return None

    return DetectedSignal(
        field="framework_repository",
        value="true",
        confidence=detection.confidence,
        evidence=detection.evidence,
    )
