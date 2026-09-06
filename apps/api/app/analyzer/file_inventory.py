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

    return FileInventory(
        root=str(root),
        files=files,
        key_files=key_files,
        ignored_dirs=list(IGNORED_DIRS),
    )


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
