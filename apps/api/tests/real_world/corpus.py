"""
Phase 2.8 — Real-World Repository Corpus.

Defines a representative set of real GitHub repositories for testing
Repo2Web's compatibility and deployment reliability.

Each entry contains:
- url: GitHub HTTPS URL
- commit_sha: Pinned commit for reproducibility (use HEAD initially)
- framework: Expected framework detection
- language: Expected language detection
- package_manager: Expected package manager
- expected_port: Expected port
- expected_entrypoint_pattern: Pattern the start command should match
- source: How expected behavior was established
- category: Classification for analysis
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RealRepo:
    """Definition of a real repository for compatibility testing."""

    url: str
    commit_sha: str = ""  # Empty = use HEAD after clone
    framework: str = ""
    language: str = ""
    package_manager: str = ""
    expected_port: int = 0  # 0 = any reasonable port
    expected_entrypoint_pattern: str = ""
    source: str = "manual_selection"
    category: str = "standard"
    notes: str = ""
    # Build/runtime expectations
    has_build_step: bool = False
    requires_db: bool = False
    requires_secrets: bool = False
    expected_health_path: str = "/"


# ============================================================================
# REAL-WORLD REPOSITORY CORPUS
# ============================================================================

REAL_WORLD_REPOSITORIES: list[RealRepo] = [
    # -----------------------------------------------------------------------
    # PYTHON FRAMEWORKS
    # -----------------------------------------------------------------------

    # FastAPI - Official full-stack template (has requirements.txt)
    RealRepo(
        url="https://github.com/tiangolo/full-stack-fastapi-template",
        framework="fastapi",
        language="python",
        package_manager="pip",
        expected_port=8000,
        expected_entrypoint_pattern="uvicorn",
        category="python-fastapi",
        notes="Official FastAPI full-stack template. Has requirements.txt, Dockerfile, frontend.",
        has_build_step=True,
        expected_health_path="/health",
    ),

    # FastAPI - tiangolo's advanced/learn example
    RealRepo(
        url="https://github.com/tiangolo/fastapi",
        framework="fastapi",
        language="python",
        package_manager="pip",
        expected_port=8000,
        expected_entrypoint_pattern="uvicorn",
        category="python-fastapi",
        notes="FastAPI framework itself. Has pyproject.toml and examples.",
    ),

    # Flask - Official Flask framework
    RealRepo(
        url="https://github.com/pallets/flask",
        framework="flask",
        language="python",
        package_manager="pip",
        expected_port=5000,
        expected_entrypoint_pattern="flask",
        category="python-flask",
        notes="Flask framework itself. Has pyproject.toml.",
    ),

    # Flask - Minimal example
    RealRepo(
        url="https://github.com/mfieldhouse/flask-minimal",
        framework="flask",
        language="python",
        package_manager="pip",
        expected_port=5000,
        expected_entrypoint_pattern="python app.py",
        category="python-flask",
        notes="Minimal Flask starter. Single file app.py.",
    ),

    # Django - Django itself (has manage.py, settings.py)
    RealRepo(
        url="https://github.com/django/django",
        framework="django",
        language="python",
        package_manager="pip",
        expected_port=8000,
        expected_entrypoint_pattern="manage.py runserver",
        category="python-django",
        notes="Django framework itself. Has manage.py at root.",
        has_build_step=False,
    ),

    # Streamlit - Official LLM examples
    RealRepo(
        url="https://github.com/streamlit/llm-examples",
        framework="streamlit",
        language="python",
        package_manager="pip",
        expected_port=8501,
        expected_entrypoint_pattern="streamlit run",
        category="python-streamlit",
        notes="Streamlit LLM examples app. Has requirements.txt.",
    ),

    # Gradio - Official examples
    RealRepo(
        url="https://github.com/gradio-app/gradio",
        framework="gradio",
        language="python",
        package_manager="pip",
        expected_port=7860,
        expected_entrypoint_pattern="python",
        category="python-gradio",
        notes="Gradio framework itself. Complex but has example apps.",
        has_build_step=True,
    ),

    # -----------------------------------------------------------------------
    # NODE.JS FRAMEWORKS
    # -----------------------------------------------------------------------

    # Express - Official examples
    RealRepo(
        url="https://github.com/expressjs/express",
        framework="express",
        language="node",
        package_manager="npm",
        expected_port=3000,
        expected_entrypoint_pattern="node",
        category="node-express",
        notes="Express framework itself. Has examples/ directory.",
    ),

    # Express - Simple hello world
    RealRepo(
        url="https://github.com/coderooz/Hello-World-Web-Server",
        framework="express",
        language="node",
        package_manager="npm",
        expected_port=3000,
        expected_entrypoint_pattern="node index.js",
        category="node-express",
        notes="Minimal Express hello world. Has package-lock.json.",
    ),

    # Next.js - Simple Next.js app
    RealRepo(
        url="https://github.com/vercel/next.js",
        framework="nextjs",
        language="node",
        package_manager="npm",
        expected_port=3000,
        expected_entrypoint_pattern="next",
        category="node-nextjs",
        notes="Next.js framework. Large repo. May fail on Windows due to long paths.",
        has_build_step=True,
    ),

    # React + Vite - Official template
    RealRepo(
        url="https://github.com/vitejs/vite",
        framework="react",
        language="node",
        package_manager="npm",
        expected_port=3000,
        expected_entrypoint_pattern="vite",
        category="node-vite",
        notes="Vite framework. Has create-vite templates.",
        has_build_step=True,
    ),

    # Vue - Official vue-next
    RealRepo(
        url="https://github.com/vuejs/core",
        framework="vue",
        language="node",
        package_manager="npm",
        expected_port=3000,
        expected_entrypoint_pattern="vite",
        category="node-vue",
        notes="Vue.js core framework.",
        has_build_step=True,
    ),

    # SvelteKit - Official starter
    RealRepo(
        url="https://github.com/sveltejs/kit",
        framework="svelte",
        language="node",
        package_manager="npm",
        expected_port=3000,
        expected_entrypoint_pattern="vite dev",
        category="node-svelte",
        notes="SvelteKit framework. Has clear entry points.",
        has_build_step=True,
    ),

    # -----------------------------------------------------------------------
    # REPOSITORY STRUCTURE VARIANTS
    # -----------------------------------------------------------------------

    # Monorepo - Example with workspaces
    RealRepo(
        url="https://github.com/LekoArts/gatsby-themes",
        language="node",
        package_manager="npm",
        category="monorepo",
        notes="Monorepo with multiple Gatsby theme packages.",
        has_build_step=True,
    ),

    # Python with pyproject.toml (no requirements.txt)
    RealRepo(
        url="https://github.com/pypa/sampleproject",
        framework="",
        language="python",
        package_manager="pip",
        category="python-pyproject",
        notes="Python sample project with pyproject.toml.",
    ),

    # Node with pnpm
    RealRepo(
        url="https://github.com/pnpm/pnpm",
        framework="",
        language="node",
        package_manager="pnpm",
        category="node-pnpm",
        notes="pnpm package manager itself.",
        has_build_step=True,
    ),

    # Generic Python HTTP app (no framework)
    RealRepo(
        url="https://github.com/python/cpython",
        framework="",
        language="python",
        package_manager="",
        category="generic-python",
        notes="CPython itself. Tests analyzer on non-framework Python code.",
    ),
]


def get_corpus() -> list[RealRepo]:
    """Get the full real-world repository corpus."""
    return REAL_WORLD_REPOSITORIES


def get_corpus_by_language(language: str) -> list[RealRepo]:
    """Get repositories filtered by language."""
    return [r for r in REAL_WORLD_REPOSITORIES if r.language == language]


def get_corpus_by_framework(framework: str) -> list[RealRepo]:
    """Get repositories filtered by framework."""
    return [r for r in REAL_WORLD_REPOSITORIES if r.framework == framework]


def get_corpus_by_category(category: str) -> list[RealRepo]:
    """Get repositories filtered by category."""
    return [r for r in REAL_WORLD_REPOSITORIES if r.category == category]
