"""Manifest Parser module.

Parses package manifests to extract dependencies, scripts, and configuration.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ManifestData:
    """Parsed manifest data."""

    package_manager: str
    dependencies: dict[str, str] = field(default_factory=dict)
    dev_dependencies: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    engines: dict[str, str] = field(default_factory=dict)
    python_version: Optional[str] = None
    node_version: Optional[str] = None


def parse_package_json(content: str) -> Optional[ManifestData]:
    """Parse package.json content.

    Args:
        content: Raw content of package.json.

    Returns:
        ManifestData or None if parsing fails.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None

    dependencies = data.get("dependencies", {})
    dev_dependencies = data.get("devDependencies", {})
    scripts = data.get("scripts", {})
    engines = data.get("engines", {})

    node_version = engines.get("node")
    if not node_version:
        # Try to extract from .nvmrc or .node-version patterns in engines
        node_version = engines.get("node")

    return ManifestData(
        package_manager="npm",
        dependencies=dependencies,
        dev_dependencies=dev_dependencies,
        scripts=scripts,
        engines=engines,
        node_version=node_version,
    )


def parse_requirements_txt(content: str) -> Optional[ManifestData]:
    """Parse requirements.txt content.

    Args:
        content: Raw content of requirements.txt.

    Returns:
        ManifestData or None if parsing fails.
    """
    dependencies = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        # Parse package==version or package>=version
        match = re.match(r"^([a-zA-Z0-9_-]+)\s*[=<>!~]+\s*([^\s;#]+)", line)
        if match:
            dependencies[match.group(1)] = match.group(2)
        else:
            # Just package name without version
            match = re.match(r"^([a-zA-Z0-9_-]+)", line)
            if match:
                dependencies[match.group(1)] = "*"

    return ManifestData(
        package_manager="pip",
        dependencies=dependencies,
    )


def parse_pyproject_toml(content: str) -> Optional[ManifestData]:
    """Parse pyproject.toml content.

    Args:
        content: Raw content of pyproject.toml.

    Returns:
        ManifestData or None if parsing fails.
    """
    # Simple TOML-like parsing for dependencies
    dependencies = {}
    python_version = None
    in_dependencies = False

    for line in content.splitlines():
        line = line.strip()

        # Check for python version requirement
        if line.startswith("python"):
            match = re.search(r'python\s*=\s*"([^"]+)"', line)
            if match:
                python_version = match.group(1)

        # Check for dependencies section
        if line == "[project.dependencies]" or line == "dependencies = [":
            in_dependencies = True
            continue

        if in_dependencies:
            if line == "]":
                in_dependencies = False
                continue

            # Parse dependency string
            match = re.match(r'"([a-zA-Z0-9_-]+)\s*[=<>!~]*\s*([^"]*)"', line)
            if match:
                dependencies[match.group(1)] = match.group(2) or "*"

    return ManifestData(
        package_manager="pip",
        dependencies=dependencies,
        python_version=python_version,
    )


def parse_setup_py(content: str) -> Optional[ManifestData]:
    """Parse setup.py content.

    Args:
        content: Raw content of setup.py.

    Returns:
        ManifestData or None if parsing fails.
    """
    dependencies = {}

    # Look for install_requires
    match = re.search(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if match:
        deps_str = match.group(1)
        for dep in re.findall(r'"([^"]+)"', deps_str):
            dep_match = re.match(r"([a-zA-Z0-9_-]+)\s*[=<>!~]*\s*(.*)", dep)
            if dep_match:
                dependencies[dep_match.group(1)] = dep_match.group(2) or "*"

    return ManifestData(
        package_manager="pip",
        dependencies=dependencies,
    )


def parse_pipfile(content: str) -> Optional[ManifestData]:
    """Parse Pipfile content.

    Args:
        content: Raw content of Pipfile.

    Returns:
        ManifestData or None if parsing fails.
    """
    dependencies = {}
    dev_dependencies = {}
    python_version = None

    in_packages = False
    in_dev_packages = False

    for line in content.splitlines():
        line = line.strip()

        if line == "[packages]":
            in_packages = True
            in_dev_packages = False
            continue
        elif line == "[dev-packages]":
            in_packages = False
            in_dev_packages = True
            continue
        elif line.startswith("["):
            in_packages = False
            in_dev_packages = False
            continue

        # Check for python version
        if line.startswith("python_version"):
            match = re.search(r'python_version\s*=\s*"([^"]+)"', line)
            if match:
                python_version = match.group(1)

        # Parse dependency
        match = re.match(r'([a-zA-Z0-9_-]+)\s*=\s*"{0,1}([^"]*?)"{0,1}\s*$', line)
        if match:
            dep_name = match.group(1)
            dep_version = match.group(2) or "*"
            if in_packages:
                dependencies[dep_name] = dep_version
            elif in_dev_packages:
                dev_dependencies[dep_name] = dep_version

    return ManifestData(
        package_manager="pipenv",
        dependencies=dependencies,
        dev_dependencies=dev_dependencies,
        python_version=python_version,
    )


def detect_package_manager(key_files: dict[str, Optional[str]]) -> str:
    """Detect the package manager from key files.

    Checks for lockfiles first (most reliable), then falls back to manifest files.
    Also checks for monorepo-specific lockfiles.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        Package manager name.
    """
    # Check lockfiles first (most reliable indicator)
    if "pnpm-lock.yaml" in key_files:
        return "pnpm"
    if "yarn.lock" in key_files:
        return "yarn"
    if "package-lock.json" in key_files:
        return "npm"
    if "Pipfile.lock" in key_files:
        return "pipenv"
    if "poetry.lock" in key_files:
        return "poetry"

    # Check for monorepo lockfiles (keys with monorepo: prefix)
    for key in key_files:
        if key.startswith("monorepo:") and key.endswith("pnpm-lock.yaml"):
            return "pnpm"
        if key.startswith("monorepo:") and key.endswith("yarn.lock"):
            return "yarn"
        if key.startswith("monorepo:") and key.endswith("package-lock.json"):
            return "npm"

    # Check manifest files
    if "package.json" in key_files:
        # Check if it's a monorepo with workspaces
        import json
        try:
            pkg_content = key_files["package.json"]
            if pkg_content:
                pkg_data = json.loads(pkg_content)
                if pkg_data.get("workspaces"):
                    # Monorepo - check for lockfiles in subdirectories
                    for key in key_files:
                        if "pnpm-lock.yaml" in key:
                            return "pnpm"
                        if "yarn.lock" in key:
                            return "yarn"
                        if "package-lock.json" in key:
                            return "npm"
                    # Default to npm for monorepos without clear lockfile
                    return "npm"
        except (json.JSONDecodeError, KeyError):
            pass
        return "npm"

    if "requirements.txt" in key_files:
        return "pip"
    if "pyproject.toml" in key_files:
        return "pip"
    if "setup.py" in key_files:
        return "pip"
    return "unknown"


def parse_manifests(key_files: dict[str, Optional[str]]) -> list[ManifestData]:
    """Parse all manifests from key files.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        List of parsed manifest data.
    """
    manifests = []

    # Node.js manifests
    if "package.json" in key_files and key_files["package.json"]:
        manifest = parse_package_json(key_files["package.json"])
        if manifest:
            manifests.append(manifest)

    # Python manifests
    if "requirements.txt" in key_files and key_files["requirements.txt"]:
        manifest = parse_requirements_txt(key_files["requirements.txt"])
        if manifest:
            manifests.append(manifest)

    if "pyproject.toml" in key_files and key_files["pyproject.toml"]:
        manifest = parse_pyproject_toml(key_files["pyproject.toml"])
        if manifest:
            manifests.append(manifest)

    if "setup.py" in key_files and key_files["setup.py"]:
        manifest = parse_setup_py(key_files["setup.py"])
        if manifest:
            manifests.append(manifest)

    if "Pipfile" in key_files and key_files["Pipfile"]:
        manifest = parse_pipfile(key_files["Pipfile"])
        if manifest:
            manifests.append(manifest)

    return manifests
