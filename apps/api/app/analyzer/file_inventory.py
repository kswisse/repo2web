"""File Inventory module.

Scans repository structure and reads key files for analysis.
"""

from pathlib import Path
from typing import Optional

from app.analyzer.types import FileInventory


# Directories to ignore during scanning
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    "eggs",
    "parts",
    "sdist",
    "wheels",
    "share/python-wheels",
    ".installed.cfg",
    "MANIFEST",
    "pip-log.txt",
    "pip-delete-this-directory.txt",
    "htmlcov",
    ".hypothesis",
    ".pytest_cache",
    "cover",
    "*.cover",
    "*.py,cover",
    ".hypothesis",
    ".pytest_cache",
    "cover",
    "*.cover",
    "*.py,cover",
    ".hypothesis",
    ".pytest_cache",
    "cover",
    "*.cover",
    "*.py,cover",
}

# Key files to read during inventory
KEY_FILES = [
    # Python source files
    "app.py",
    "main.py",
    "server.py",
    "cli.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "src/app.py",
    "src/main.py",
    "src/server.py",
    # Python
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "conda.yaml",
    "environment.yml",
    # Node.js source files
    "index.js",
    "index.ts",
    "server.js",
    "src/index.js",
    "src/index.ts",
    "src/server.js",
    "pages/index.js",
    "pages/index.ts",
    # Node.js
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    ".npmrc",
    ".yarnrc",
    ".yarnrc.yml",
    # Docker
    "Dockerfile",
    "Dockerfile.dev",
    "Dockerfile.prod",
    "docker-compose.yml",
    "docker-compose.yaml",
    "docker-compose.dev.yml",
    "docker-compose.prod.yml",
    ".dockerignore",
    # Environment
    ".env",
    ".env.example",
    ".env.sample",
    ".env.local",
    ".env.development",
    ".env.production",
    # Documentation
    "README.md",
    "README.rst",
    "README.txt",
    "CONTRIBUTING.md",
    # Configuration
    "Makefile",
    "Procfile",
    "Vagrantfile",
    ".editorconfig",
    ".gitignore",
    # TypeScript
    "tsconfig.json",
    "tsconfig.build.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "vite.config.js",
    "vite.config.mjs",
    "vite.config.ts",
    "nuxt.config.js",
    "nuxt.config.ts",
    # Python config
    "mypy.ini",
    ".mypy.ini",
    "setup.cfg",
    "tox.ini",
    ".flake8",
    ".pylintrc",
    # Frontend
    "angular.json",
    "vue.config.js",
    "vue.config.ts",
    "svelte.config.js",
    "svelte.config.ts",
]


def scan_repository(root_path: str) -> FileInventory:
    """Scan a repository and build a file inventory.

    Args:
        root_path: Path to the repository root.

    Returns:
        FileInventory with all files and key file contents.
    """
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root_path}")

    files = []
    key_files: dict[str, Optional[str]] = {}

    # Scan all files
    for item in sorted(root.rglob("*")):
        if item.is_file():
            rel_path = str(item.relative_to(root))
            if _should_ignore(rel_path):
                continue
            files.append(rel_path)

    # Read key files
    for key_file in KEY_FILES:
        file_path = root / key_file
        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                key_files[key_file] = content
            except Exception:
                key_files[key_file] = None

    # Detect monorepo structure
    is_monorepo, monorepo_packages = _detect_monorepo(root, files, key_files)

    # For monorepos, also read subdirectory package.json files
    if is_monorepo:
        _read_monorepo_packages(root, files, key_files, monorepo_packages)

    return FileInventory(
        root=str(root),
        files=files,
        key_files=key_files,
        ignored_dirs=list(IGNORED_DIRS),
        is_monorepo=is_monorepo,
        monorepo_packages=monorepo_packages,
    )


def _detect_monorepo(
    root: Path, files: list[str], key_files: dict[str, Optional[str]]
) -> tuple[bool, list[str]]:
    """Detect if the repository is a monorepo.

    Returns (is_monorepo, list_of_package_paths).
    """
    import re

    packages = []

    def _expand_glob_pattern(pattern: str, files_list: list[str]) -> list[str]:
        """Expand a glob pattern like 'packages/*' against the file list."""
        result = []
        # Normalize pattern to use forward slashes
        pattern_norm = pattern.replace("\\", "/")
        base = pattern_norm.split("*")[0]

        for f in files_list:
            # Normalize file path to forward slashes for comparison
            f_norm = f.replace("\\", "/")
            if f_norm.startswith(base) and f_norm.endswith("package.json"):
                # Get the full relative path from base
                relative_to_base = f_norm[len(base):]  # e.g., "my-app/package.json"
                pkg_dir = str(Path(relative_to_base).parent)  # e.g., "my-app"
                # If base is "packages/", the full path is "packages/my-app"
                full_pkg_dir = str(Path(base) / pkg_dir) if pkg_dir != "." else base.rstrip("/")
                if full_pkg_dir not in result:
                    result.append(full_pkg_dir)
        return result

    # Check for pnpm workspace
    if "pnpm-workspace.yaml" in key_files:
        content = key_files["pnpm-workspace.yaml"] or ""
        for match in re.finditer(r"-\s+[\"']?([^\"'\s]+)[\"']?", content):
            pkg_pattern = match.group(1)
            if "*" in pkg_pattern:
                found = _expand_glob_pattern(pkg_pattern, files)
                for pkg_dir in found:
                    if pkg_dir not in packages:
                        packages.append(pkg_dir)
            elif pkg_pattern.endswith("package.json"):
                if pkg_pattern not in packages:
                    packages.append(pkg_pattern)

    # Check for npm/yarn workspaces in root package.json
    root_pkg = key_files.get("package.json")
    if root_pkg:
        try:
            import json
            pkg_data = json.loads(root_pkg)
            workspaces = pkg_data.get("workspaces")
            if workspaces:
                if isinstance(workspaces, list):
                    for ws in workspaces:
                        if "*" in ws:
                            found = _expand_glob_pattern(ws, files)
                            for pkg_dir in found:
                                if pkg_dir not in packages:
                                    packages.append(pkg_dir)
                        elif ws.endswith("package.json"):
                            if ws not in packages:
                                packages.append(ws)
                        else:
                            # It's a directory pattern
                            ws_path = root / ws
                            if ws_path.is_dir():
                                for child in sorted(ws_path.iterdir()):
                                    if child.is_dir() and (child / "package.json").exists():
                                        pkg_dir = str(child.relative_to(root))
                                        if pkg_dir not in packages:
                                            packages.append(pkg_dir)
        except (json.JSONDecodeError, KeyError):
            pass

    # Check for lerna.json
    if "lerna.json" in files:
        try:
            import json
            lerna_path = root / "lerna.json"
            with open(lerna_path) as f:
                lerna_data = json.load(f)
            lerna_packages = lerna_data.get("packages", [])
            for lp in lerna_packages:
                if "*" in lp:
                    found = _expand_glob_pattern(lp, files)
                    for pkg_dir in found:
                        if pkg_dir not in packages:
                            packages.append(pkg_dir)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Check for nx.json
    if "nx.json" in files:
        for f in files:
            if f.endswith("project.json") and f != "project.json":
                pkg_dir = str(Path(f).parent)
                if pkg_dir not in packages:
                    packages.append(pkg_dir)

    return len(packages) > 0, packages


def _read_monorepo_packages(
    root: Path,
    files: list[str],
    key_files: dict[str, Optional[str]],
    packages: list[str],
) -> None:
    """Read package.json files from monorepo subdirectories.

    Adds them to key_files with a prefix to avoid overwriting root package.json.
    Also creates merged dependency view.
    """
    import json

    all_deps = {}
    all_scripts = {}

    for pkg_path in packages:
        pkg_file = root / pkg_path / "package.json"
        if pkg_file.exists():
            try:
                content = pkg_file.read_text(encoding="utf-8", errors="ignore")
                pkg_data = json.loads(content)
                deps = pkg_data.get("dependencies", {})
                scripts = pkg_data.get("scripts", {})
                all_deps.update(deps)
                all_scripts.update(scripts)

                # Store with prefix for individual access
                key_file_name = f"monorepo:{pkg_path}/package.json"
                key_files[key_file_name] = content
            except (json.JSONDecodeError, Exception):
                pass

    # If root package.json has workspaces, merge sub-package deps into root deps
    # This helps the framework detector find dependencies across the monorepo
    root_pkg_content = key_files.get("package.json")
    if root_pkg_content:
        try:
            root_pkg = json.loads(root_pkg_content)
            root_deps = root_pkg.get("dependencies", {})
            root_deps.update(all_deps)  # Merge sub-package deps
            root_pkg["dependencies"] = root_deps

            root_scripts = root_pkg.get("scripts", {})
            root_scripts.update(all_scripts)
            root_pkg["scripts"] = root_scripts

            # Update the key_files with merged content
            key_files["package.json"] = json.dumps(root_pkg, indent=2)
        except (json.JSONDecodeError, KeyError):
            pass


def _should_ignore(rel_path: str) -> bool:
    """Check if a relative path should be ignored.

    Args:
        rel_path: Relative path from repository root.

    Returns:
        True if the path should be ignored.
    """
    parts = Path(rel_path).parts
    for part in parts:
        if part in IGNORED_DIRS:
            return True
        # Handle glob-like patterns
        if part.endswith(".egg-info"):
            return True
    return False
