"""Comprehensive tests for the Repository Analyzer.

Tests cover:
- URL validation
- Python detection (all frameworks)
- Node.js detection (all frameworks)
- Entrypoint detection
- Port detection
- Environment detection
- Compatibility evaluation
- ExecutionPlan validation
- Security: no code execution during analysis
- Evidence attachment
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.analyzer.analyzer import analyze_repository
from app.analyzer.types import (
    CompatibilityResult,
    DetectedSignal,
    EnvironmentVariable,
    ExecutionPlan,
    RepositoryInfo,
    ServiceDependency,
)
from app.analyzer.file_inventory import scan_repository
from app.analyzer.manifest_parser import (
    detect_package_manager,
    parse_manifests,
    parse_package_json,
    parse_requirements_txt,
)
from app.analyzer.framework_detector import detect_framework
from app.analyzer.entrypoint_detector import detect_entrypoint
from app.analyzer.port_detector import detect_port
from app.analyzer.env_detector import detect_environment_variables
from app.analyzer.dependency_detector import detect_service_dependencies
from app.analyzer.compatibility import evaluate_compatibility
from app.analyzer.plan_validator import validate_plan


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fastapi_repo():
    """Path to FastAPI test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "python-fastapi")


@pytest.fixture
def flask_repo():
    """Path to Flask test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "python-flask")


@pytest.fixture
def streamlit_repo():
    """Path to Streamlit test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "python-streamlit")


@pytest.fixture
def django_repo():
    """Path to Django test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "python-django")


@pytest.fixture
def nextjs_repo():
    """Path to Next.js test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "node-nextjs")


@pytest.fixture
def vite_repo():
    """Path to Vite test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "node-vite")


@pytest.fixture
def express_repo():
    """Path to Express test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "node-express")


@pytest.fixture
def pnpm_repo():
    """Path to pnpm test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "node-pnpm")


@pytest.fixture
def cli_repo():
    """Path to CLI-only test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "unsupported-cli")


@pytest.fixture
def conflicting_repo():
    """Path to conflicting config test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "conflicting-config")


@pytest.fixture
def env_repo():
    """Path to env-example test fixture."""
    return str(Path(__file__).parent / "fixtures" / "repos" / "env-example")


# ============================================================================
# File Inventory Tests
# ============================================================================


class TestFileInventory:
    """Tests for file inventory scanning."""

    def test_scan_fastapi_repo(self, fastapi_repo):
        """Test scanning a FastAPI repository."""
        inventory = scan_repository(fastapi_repo)

        assert inventory.root == fastapi_repo
        assert "main.py" in inventory.files
        assert "requirements.txt" in inventory.files
        assert "requirements.txt" in inventory.key_files
        assert inventory.key_files["requirements.txt"] is not None

    def test_scan_repo_with_ignored_dirs(self, fastapi_repo):
        """Test that ignored directories are excluded."""
        # Create a node_modules directory
        node_modules = Path(fastapi_repo) / "node_modules"
        node_modules.mkdir(exist_ok=True)
        (node_modules / "test.js").write_text("console.log('test')")

        inventory = scan_repository(fastapi_repo)

        assert "node_modules/test.js" not in inventory.files

        # Cleanup
        import shutil
        shutil.rmtree(node_modules)

    def test_scan_nonexistent_repo(self):
        """Test scanning a non-existent repository."""
        with pytest.raises(FileNotFoundError):
            scan_repository("/nonexistent/path")


# ============================================================================
# Manifest Parser Tests
# ============================================================================


class TestManifestParser:
    """Tests for manifest parsing."""

    def test_parse_package_json(self):
        """Test parsing package.json."""
        content = json.dumps({
            "name": "test-app",
            "version": "1.0.0",
            "dependencies": {"express": "^4.18.0"},
            "devDependencies": {"nodemon": "^3.0.0"},
            "scripts": {"start": "node server.js"},
            "engines": {"node": ">=18.0.0"},
        })

        manifest = parse_package_json(content)

        assert manifest is not None
        assert manifest.package_manager == "npm"
        assert "express" in manifest.dependencies
        assert "nodemon" in manifest.dev_dependencies
        assert manifest.scripts.get("start") == "node server.js"
        assert manifest.node_version == ">=18.0.0"

    def test_parse_requirements_txt(self):
        """Test parsing requirements.txt."""
        content = """flask>=3.0.0
fastapi==0.109.0
uvicorn
"""

        manifest = parse_requirements_txt(content)

        assert manifest is not None
        assert manifest.package_manager == "pip"
        assert "flask" in manifest.dependencies
        assert "fastapi" in manifest.dependencies
        assert "uvicorn" in manifest.dependencies

    def test_parse_requirements_txt_with_comments(self):
        """Test parsing requirements.txt with comments."""
        content = """# Web framework
flask>=3.0.0

# ASGI server
uvicorn
"""

        manifest = parse_requirements_txt(content)

        assert manifest is not None
        assert "flask" in manifest.dependencies
        assert "uvicorn" in manifest.dependencies

    def test_detect_package_manager_npm(self):
        """Test detecting npm package manager."""
        key_files = {"package.json": "{}", "package-lock.json": "{}"}
        assert detect_package_manager(key_files) == "npm"

    def test_detect_package_manager_yarn(self):
        """Test detecting yarn package manager."""
        key_files = {"package.json": "{}", "yarn.lock": "{}"}
        assert detect_package_manager(key_files) == "yarn"

    def test_detect_package_manager_pnpm(self):
        """Test detecting pnpm package manager."""
        key_files = {"package.json": "{}", "pnpm-lock.yaml": "{}"}
        assert detect_package_manager(key_files) == "pnpm"

    def test_detect_package_manager_pip(self):
        """Test detecting pip package manager."""
        key_files = {"requirements.txt": "flask"}
        assert detect_package_manager(key_files) == "pip"


# ============================================================================
# Framework Detector Tests
# ============================================================================


class TestFrameworkDetector:
    """Tests for framework detection."""

    def test_detect_fastapi(self):
        """Test FastAPI detection."""
        dependencies = {"fastapi": "0.109.0", "uvicorn": "0.27.0"}
        file_names = ["main.py", "requirements.txt"]

        result = detect_framework(dependencies, file_names, "python")

        assert result is not None
        assert result.name == "fastapi"
        assert result.confidence in ("HIGH", "MEDIUM")

    def test_detect_flask(self):
        """Test Flask detection."""
        dependencies = {"flask": "3.0.0"}
        file_names = ["app.py", "requirements.txt"]

        result = detect_framework(dependencies, file_names, "python")

        assert result is not None
        assert result.name == "flask"

    def test_detect_django(self):
        """Test Django detection."""
        dependencies = {"django": "4.2"}
        file_names = ["manage.py", "requirements.txt"]

        result = detect_framework(dependencies, file_names, "python")

        assert result is not None
        assert result.name == "django"

    def test_detect_streamlit(self):
        """Test Streamlit detection."""
        dependencies = {"streamlit": "1.28.0"}
        file_names = ["app.py", "requirements.txt"]

        result = detect_framework(dependencies, file_names, "python")

        assert result is not None
        assert result.name == "streamlit"

    def test_detect_nextjs(self):
        """Test Next.js detection."""
        dependencies = {"next": "14.0.0", "react": "18.2.0"}
        file_names = ["package.json", "next.config.js"]

        result = detect_framework(dependencies, file_names, "node")

        assert result is not None
        assert result.name == "nextjs"

    def test_detect_react(self):
        """Test React detection."""
        dependencies = {"react": "18.2.0", "react-dom": "18.2.0"}
        file_names = ["package.json"]

        result = detect_framework(dependencies, file_names, "node")

        assert result is not None
        assert result.name == "react"

    def test_detect_express(self):
        """Test Express detection."""
        dependencies = {"express": "4.18.0"}
        file_names = ["package.json", "server.js"]

        result = detect_framework(dependencies, file_names, "node")

        assert result is not None
        assert result.name == "express"

    def test_detect_vue(self):
        """Test Vue detection."""
        dependencies = {"vue": "3.3.0"}
        file_names = ["package.json"]

        result = detect_framework(dependencies, file_names, "node")

        assert result is not None
        assert result.name == "vue"

    def test_detect_nothing(self):
        """Test when no framework is detected."""
        dependencies = {"lodash": "4.17.0"}
        file_names = ["package.json"]

        result = detect_framework(dependencies, file_names, "node")

        assert result is None


# ============================================================================
# Entrypoint Detector Tests
# ============================================================================


class TestEntrypointDetector:
    """Tests for entrypoint detection."""

    def test_detect_node_start_script(self):
        """Test detecting Node.js start script."""
        key_files = {
            "package.json": json.dumps({
                "scripts": {"start": "node server.js"}
            })
        }
        file_names = ["package.json", "server.js"]

        result = detect_entrypoint(key_files, file_names, "express", "node")

        assert result is not None
        assert "node server.js" in result.command
        assert result.confidence == "HIGH"

    def test_detect_python_readme_command(self):
        """Test detecting Python command from README."""
        key_files = {
            "README.md": "Run with: `uvicorn main:app --host 0.0.0.0 --port 8000`"
        }
        file_names = ["README.md", "main.py"]

        result = detect_entrypoint(key_files, file_names, "fastapi", "python")

        assert result is not None
        assert "uvicorn" in result.command
        assert result.confidence == "HIGH"

    def test_detect_django_manage_py(self):
        """Test detecting Django manage.py."""
        key_files = {}
        file_names = ["manage.py", "requirements.txt"]

        result = detect_entrypoint(key_files, file_names, "django", "python")

        assert result is not None
        assert "manage.py runserver" in result.command

    def test_detect_no_entrypoint(self):
        """Test when no entrypoint is detected."""
        key_files = {}
        file_names = ["requirements.txt"]

        result = detect_entrypoint(key_files, file_names, None, "python")

        assert result is None


# ============================================================================
# Port Detector Tests
# ============================================================================


class TestPortDetector:
    """Tests for port detection."""

    def test_detect_port_from_scripts(self):
        """Test detecting port from scripts."""
        key_files = {
            "package.json": json.dumps({
                "scripts": {"start": "node server.js --port 4000"}
            })
        }
        file_names = ["package.json"]

        result = detect_port(key_files, file_names, None)

        assert result is not None
        assert result.port == 4000
        assert result.confidence == "HIGH"

    def test_detect_port_from_dockerfile(self):
        """Test detecting port from Dockerfile."""
        key_files = {
            "Dockerfile": "FROM node:18\nEXPOSE 8080\nCMD [\"npm\", \"start\"]"
        }
        file_names = ["Dockerfile"]

        result = detect_port(key_files, file_names, None)

        assert result is not None
        assert result.port == 8080
        assert result.confidence == "HIGH"

    def test_detect_port_from_env(self):
        """Test detecting port from .env.example."""
        key_files = {
            ".env.example": "PORT=3000\nDATABASE_URL=postgresql://localhost/db"
        }
        file_names = [".env.example"]

        result = detect_port(key_files, file_names, None)

        assert result is not None
        assert result.port == 3000
        assert result.confidence == "HIGH"

    def test_detect_framework_default_port(self):
        """Test using framework default port."""
        key_files = {}
        file_names = []

        result = detect_port(key_files, file_names, "fastapi")

        assert result is not None
        assert result.port == 8000
        assert result.confidence == "LOW"

    def test_detect_default_port(self):
        """Test using default port when nothing detected."""
        key_files = {}
        file_names = []

        result = detect_port(key_files, file_names, None)

        assert result is not None
        assert result.port == 3000
        assert result.confidence == "LOW"


# ============================================================================
# Environment Detector Tests
# ============================================================================


class TestEnvironmentDetector:
    """Tests for environment variable detection."""

    def test_detect_from_env_file(self):
        """Test detecting environment variables from .env.example."""
        key_files = {
            ".env.example": "DATABASE_URL=postgresql://localhost/db\nAPI_KEY=\nSECRET_KEY="
        }
        file_names = [".env.example"]

        result = detect_environment_variables(key_files, file_names)

        assert len(result) >= 3
        names = [v.name for v in result]
        assert "DATABASE_URL" in names
        assert "API_KEY" in names
        assert "SECRET_KEY" in names

    def test_detect_secret_variables(self):
        """Test that secret variables are correctly identified."""
        key_files = {
            ".env.example": "API_KEY=abc123\nSECRET_TOKEN=xyz789\nDATABASE_URL=postgresql://localhost/db"
        }
        file_names = [".env.example"]

        result = detect_environment_variables(key_files, file_names)

        for var in result:
            if var.name in ("API_KEY", "SECRET_TOKEN"):
                assert var.secret is True
            elif var.name == "DATABASE_URL":
                assert var.secret is False

    def test_detect_from_source_code(self):
        """Test detecting environment variables from source code."""
        key_files = {
            "app.py": 'import os\nDB_URL = os.environ.get("DATABASE_URL")\nAPI_KEY = os.environ.get("API_KEY")'
        }
        file_names = ["app.py"]

        result = detect_environment_variables(key_files, file_names)

        assert len(result) >= 2
        names = [v.name for v in result]
        assert "DATABASE_URL" in names
        assert "API_KEY" in names

    def test_detect_from_readme(self):
        """Test detecting environment variables from README."""
        key_files = {
            "README.md": "Set `DATABASE_URL` and `API_KEY` environment variables."
        }
        file_names = ["README.md"]

        result = detect_environment_variables(key_files, file_names)

        assert len(result) >= 2
        names = [v.name for v in result]
        assert "DATABASE_URL" in names
        assert "API_KEY" in names


# ============================================================================
# Dependency Detector Tests
# ============================================================================


class TestDependencyDetector:
    """Tests for service dependency detection."""

    def test_detect_postgresql(self):
        """Test detecting PostgreSQL dependency."""
        key_files = {}
        dependencies = {"psycopg2": "2.9.0", "sqlalchemy": "2.0.0"}

        result = detect_service_dependencies(key_files, dependencies)

        names = [s.name for s in result]
        assert "postgresql" in names

    def test_detect_redis(self):
        """Test detecting Redis dependency."""
        key_files = {}
        dependencies = {"redis": "5.0.0"}

        result = detect_service_dependencies(key_files, dependencies)

        names = [s.name for s in result]
        assert "redis" in names

    def test_detect_from_docker_compose(self):
        """Test detecting services from docker-compose."""
        key_files = {
            "docker-compose.yml": "services:\n  postgres:\n    image: postgres:15\n  redis:\n    image: redis:7"
        }
        dependencies = {}

        result = detect_service_dependencies(key_files, dependencies)

        names = [s.name for s in result]
        assert "postgresql" in names
        assert "redis" in names

    def test_detect_from_env(self):
        """Test detecting services from environment variables."""
        key_files = {
            ".env.example": "DATABASE_URL=postgresql://localhost/db\nREDIS_URL=redis://localhost:6379"
        }
        dependencies = {}

        result = detect_service_dependencies(key_files, dependencies)

        names = [s.name for s in result]
        assert "postgresql" in names
        assert "redis" in names

    def test_no_dependencies(self):
        """Test when no dependencies are detected."""
        key_files = {}
        dependencies = {}

        result = detect_service_dependencies(key_files, dependencies)

        assert len(result) == 0


# ============================================================================
# Compatibility Evaluator Tests
# ============================================================================


class TestCompatibilityEvaluator:
    """Tests for compatibility evaluation."""

    def test_supported_fastapi(self):
        """Test FastAPI is supported."""
        result = evaluate_compatibility(
            language="python",
            framework="fastapi",
            entrypoint="uvicorn main:app",
            port=8000,
            key_files={},
            file_names=[],
            evidence=[],
        )

        assert result.status == "SUPPORTED"
        assert result.confidence in ("HIGH", "MEDIUM")

    def test_supported_express(self):
        """Test Express is supported."""
        result = evaluate_compatibility(
            language="node",
            framework="express",
            entrypoint="node server.js",
            port=3000,
            key_files={},
            file_names=[],
            evidence=[],
        )

        assert result.status == "SUPPORTED"

    def test_unsupported_language(self):
        """Test unsupported language."""
        result = evaluate_compatibility(
            language="go",
            framework=None,
            entrypoint=None,
            port=None,
            key_files={},
            file_names=[],
            evidence=[],
        )

        assert result.status == "UNSUPPORTED"
        assert len(result.blockers) > 0

    def test_cli_only(self):
        """Test CLI-only application."""
        key_files = {
            "main.py": "import argparse\nparser = argparse.ArgumentParser()"
        }
        file_names = ["main.py"]

        result = evaluate_compatibility(
            language="python",
            framework=None,
            entrypoint=None,
            port=None,
            key_files=key_files,
            file_names=file_names,
            evidence=[],
        )

        assert result.status == "UNSUPPORTED"

    def test_supported_with_warnings(self):
        """Test application with warnings."""
        result = evaluate_compatibility(
            language="python",
            framework="fastapi",
            entrypoint=None,  # Missing entrypoint
            port=None,  # Missing port
            key_files={},
            file_names=[],
            evidence=[],
        )

        assert result.status == "SUPPORTED_WITH_WARNINGS"
        assert len(result.warnings) > 0


# ============================================================================
# Plan Validator Tests
# ============================================================================


class TestPlanValidator:
    """Tests for ExecutionPlan validation."""

    def test_valid_plan(self):
        """Test validating a valid plan."""
        from app.analyzer.types import (
            ApplicationInfo,
            BuildInfo,
            CompatibilityResult,
            RuntimeInfo,
        )

        plan = ExecutionPlan(
            repository=RepositoryInfo(
                url="https://github.com/test/repo",
                commit_sha="abc123def456",
                owner="test",
                repo="repo",
            ),
            application=ApplicationInfo(
                language="python",
                framework="fastapi",
                framework_version=None,
                confidence="HIGH",
            ),
            build=BuildInfo(
                package_manager="pip",
                install_command="pip install -r requirements.txt",
                build_command=None,
                working_directory=".",
            ),
            runtime=RuntimeInfo(
                start_command="uvicorn main:app --host 0.0.0.0 --port 8000",
                port=8000,
                host="0.0.0.0",
                health_check_path="/health",
            ),
            compatibility=CompatibilityResult(
                status="SUPPORTED",
                confidence="HIGH",
            ),
            created_at="2024-01-01T00:00:00Z",
        )

        result = validate_plan(plan)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_port(self):
        """Test validating plan with invalid port."""
        from app.analyzer.types import (
            ApplicationInfo,
            BuildInfo,
            CompatibilityResult,
            RuntimeInfo,
        )

        plan = ExecutionPlan(
            repository=RepositoryInfo(
                url="https://github.com/test/repo",
                commit_sha="abc123def456",
                owner="test",
                repo="repo",
            ),
            application=ApplicationInfo(
                language="python",
                framework="fastapi",
                framework_version=None,
                confidence="HIGH",
            ),
            build=BuildInfo(
                package_manager="pip",
                install_command="pip install -r requirements.txt",
                build_command=None,
                working_directory=".",
            ),
            runtime=RuntimeInfo(
                start_command="uvicorn main:app --host 0.0.0.0 --port 8000",
                port=99999,  # Invalid port
                host="0.0.0.0",
                health_check_path="/health",
            ),
            compatibility=CompatibilityResult(
                status="SUPPORTED",
                confidence="HIGH",
            ),
            created_at="2024-01-01T00:00:00Z",
        )

        result = validate_plan(plan)

        assert result.valid is False
        assert any("Port" in e for e in result.errors)

    def test_invalid_commit_sha(self):
        """Test validating plan with invalid commit SHA."""
        from app.analyzer.types import (
            ApplicationInfo,
            BuildInfo,
            CompatibilityResult,
            RuntimeInfo,
        )

        plan = ExecutionPlan(
            repository=RepositoryInfo(
                url="https://github.com/test/repo",
                commit_sha="not-a-hex-string",
                owner="test",
                repo="repo",
            ),
            application=ApplicationInfo(
                language="python",
                framework="fastapi",
                framework_version=None,
                confidence="HIGH",
            ),
            build=BuildInfo(
                package_manager="pip",
                install_command="pip install -r requirements.txt",
                build_command=None,
                working_directory=".",
            ),
            runtime=RuntimeInfo(
                start_command="uvicorn main:app --host 0.0.0.0 --port 8000",
                port=8000,
                host="0.0.0.0",
                health_check_path="/health",
            ),
            compatibility=CompatibilityResult(
                status="SUPPORTED",
                confidence="HIGH",
            ),
            created_at="2024-01-01T00:00:00Z",
        )

        result = validate_plan(plan)

        assert result.valid is False
        assert any("SHA" in e for e in result.errors)

    def test_invalid_compatibility_status(self):
        """Test validating plan with invalid compatibility status."""
        from app.analyzer.types import (
            ApplicationInfo,
            BuildInfo,
            CompatibilityResult,
            RuntimeInfo,
        )

        plan = ExecutionPlan(
            repository=RepositoryInfo(
                url="https://github.com/test/repo",
                commit_sha="abc123def456",
                owner="test",
                repo="repo",
            ),
            application=ApplicationInfo(
                language="python",
                framework="fastapi",
                framework_version=None,
                confidence="HIGH",
            ),
            build=BuildInfo(
                package_manager="pip",
                install_command="pip install -r requirements.txt",
                build_command=None,
                working_directory=".",
            ),
            runtime=RuntimeInfo(
                start_command="uvicorn main:app --host 0.0.0.0 --port 8000",
                port=8000,
                host="0.0.0.0",
                health_check_path="/health",
            ),
            compatibility=CompatibilityResult(
                status="INVALID_STATUS",
                confidence="HIGH",
            ),
            created_at="2024-01-01T00:00:00Z",
        )

        result = validate_plan(plan)

        assert result.valid is False
        assert any("status" in e.lower() for e in result.errors)


# ============================================================================
# Full Analyzer Integration Tests
# ============================================================================


class TestAnalyzerIntegration:
    """Integration tests for the full analyzer pipeline."""

    def test_analyze_fastapi_repo(self, fastapi_repo):
        """Test analyzing a FastAPI repository."""
        plan = analyze_repository(
            repo_path=fastapi_repo,
            url="https://github.com/test/fastapi-app",
            commit_sha="abc123def456",
            owner="test",
            repo="fastapi-app",
        )

        assert isinstance(plan, ExecutionPlan)
        assert plan.repository.url == "https://github.com/test/fastapi-app"
        assert plan.application.language == "python"
        assert plan.application.framework == "fastapi"
        assert plan.build.package_manager == "pip"
        assert plan.runtime.port == 8000
        assert plan.compatibility.status in ("SUPPORTED", "SUPPORTED_WITH_WARNINGS")
        assert len(plan.evidence) > 0
        assert plan.created_at != ""

    def test_analyze_flask_repo(self, flask_repo):
        """Test analyzing a Flask repository."""
        plan = analyze_repository(
            repo_path=flask_repo,
            url="https://github.com/test/flask-app",
            commit_sha="abc123def456",
            owner="test",
            repo="flask-app",
        )

        assert plan.application.language == "python"
        assert plan.application.framework == "flask"
        assert plan.runtime.port == 5000

    def test_analyze_streamlit_repo(self, streamlit_repo):
        """Test analyzing a Streamlit repository."""
        plan = analyze_repository(
            repo_path=streamlit_repo,
            url="https://github.com/test/streamlit-app",
            commit_sha="abc123def456",
            owner="test",
            repo="streamlit-app",
        )

        assert plan.application.language == "python"
        assert plan.application.framework == "streamlit"
        assert plan.runtime.port == 8501

    def test_analyze_django_repo(self, django_repo):
        """Test analyzing a Django repository."""
        plan = analyze_repository(
            repo_path=django_repo,
            url="https://github.com/test/django-app",
            commit_sha="abc123def456",
            owner="test",
            repo="django-app",
        )

        assert plan.application.language == "python"
        assert plan.application.framework == "django"
        assert plan.runtime.port == 8000

    def test_analyze_nextjs_repo(self, nextjs_repo):
        """Test analyzing a Next.js repository."""
        plan = analyze_repository(
            repo_path=nextjs_repo,
            url="https://github.com/test/nextjs-app",
            commit_sha="abc123def456",
            owner="test",
            repo="nextjs-app",
        )

        assert plan.application.language == "node"
        assert plan.application.framework == "nextjs"
        assert plan.build.package_manager == "npm"
        assert plan.runtime.port == 3000

    def test_analyze_vite_repo(self, vite_repo):
        """Test analyzing a Vite repository."""
        plan = analyze_repository(
            repo_path=vite_repo,
            url="https://github.com/test/vite-app",
            commit_sha="abc123def456",
            owner="test",
            repo="vite-app",
        )

        assert plan.application.language == "node"
        assert plan.application.framework == "react"
        assert plan.build.package_manager == "npm"

    def test_analyze_express_repo(self, express_repo):
        """Test analyzing an Express repository."""
        plan = analyze_repository(
            repo_path=express_repo,
            url="https://github.com/test/express-app",
            commit_sha="abc123def456",
            owner="test",
            repo="express-app",
        )

        assert plan.application.language == "node"
        assert plan.application.framework == "express"
        assert plan.build.package_manager == "npm"
        assert plan.runtime.port == 3000

    def test_analyze_pnpm_repo(self, pnpm_repo):
        """Test analyzing a pnpm repository."""
        plan = analyze_repository(
            repo_path=pnpm_repo,
            url="https://github.com/test/pnpm-app",
            commit_sha="abc123def456",
            owner="test",
            repo="pnpm-app",
        )

        assert plan.application.language == "node"
        assert plan.build.package_manager == "pnpm"

    def test_analyze_cli_repo(self, cli_repo):
        """Test analyzing a CLI-only repository."""
        plan = analyze_repository(
            repo_path=cli_repo,
            url="https://github.com/test/cli-app",
            commit_sha="abc123def456",
            owner="test",
            repo="cli-app",
        )

        assert plan.compatibility.status == "UNSUPPORTED"
        assert len(plan.compatibility.blockers) > 0

    def test_analyze_env_repo(self, env_repo):
        """Test analyzing a repository with environment variables."""
        plan = analyze_repository(
            repo_path=env_repo,
            url="https://github.com/test/env-app",
            commit_sha="abc123def456",
            owner="test",
            repo="env-app",
        )

        assert len(plan.environment) > 0
        env_names = [v.name for v in plan.environment]
        assert "DATABASE_URL" in env_names
        assert "API_KEY" in env_names

    def test_analyze_nonexistent_repo(self):
        """Test analyzing a non-existent repository."""
        with pytest.raises(FileNotFoundError):
            analyze_repository(
                repo_path="/nonexistent/path",
                url="https://github.com/test/nonexistent",
                commit_sha="abc123def456",
                owner="test",
                repo="nonexistent",
            )

    def test_plan_is_frozen(self, fastapi_repo):
        """Test that ExecutionPlan is immutable."""
        plan = analyze_repository(
            repo_path=fastapi_repo,
            url="https://github.com/test/fastapi-app",
            commit_sha="abc123def456",
            owner="test",
            repo="fastapi-app",
        )

        # Try to modify the plan
        with pytest.raises(AttributeError):
            plan.application.language = "node"


# ============================================================================
# Security Tests
# ============================================================================


class TestSecurity:
    """Tests for security requirements."""

    def test_no_code_execution(self, fastapi_repo):
        """Test that analyzer never executes code."""
        # This test verifies that the analyzer only does static analysis
        # by checking that no subprocess calls are made
        import unittest.mock as mock

        with mock.patch("subprocess.run") as mock_run:
            with mock.patch("os.system") as mock_system:
                plan = analyze_repository(
                    repo_path=fastapi_repo,
                    url="https://github.com/test/fastapi-app",
                    commit_sha="abc123def456",
                    owner="test",
                    repo="fastapi-app",
                )

                # Verify no subprocess calls were made
                mock_run.assert_not_called()
                mock_system.assert_not_called()

    def test_no_npm_pip_execution(self, fastapi_repo):
        """Test that npm/pip are never invoked."""
        import unittest.mock as mock

        with mock.patch("subprocess.run") as mock_run:
            plan = analyze_repository(
                repo_path=fastapi_repo,
                url="https://github.com/test/fastapi-app",
                commit_sha="abc123def456",
                owner="test",
                repo="fastapi-app",
            )

            # Verify no package manager commands were executed
            mock_run.assert_not_called()

    def test_no_secret_values_in_response(self, env_repo):
        """Test that secret values are not included in response."""
        plan = analyze_repository(
            repo_path=env_repo,
            url="https://github.com/test/env-app",
            commit_sha="abc123def456",
            owner="test",
            repo="env-app",
        )

        # Check that no actual secret values are in the plan
        # The plan should only contain metadata about secrets, not the values
        for env_var in plan.environment:
            if env_var.secret:
                # Secret variables should not have their values exposed
                assert env_var.default is None or env_var.default == ""


# ============================================================================
# Evidence Tests
# ============================================================================


class TestEvidence:
    """Tests for evidence attachment."""

    def test_evidence_attached(self, fastapi_repo):
        """Test that evidence is attached to the plan."""
        plan = analyze_repository(
            repo_path=fastapi_repo,
            url="https://github.com/test/fastapi-app",
            commit_sha="abc123def456",
            owner="test",
            repo="fastapi-app",
        )

        assert len(plan.evidence) > 0
        for signal in plan.evidence:
            assert isinstance(signal, DetectedSignal)
            assert signal.field != ""
            assert signal.value != ""
            assert signal.confidence in ("HIGH", "MEDIUM", "LOW")
            assert len(signal.evidence) > 0

    def test_framework_evidence(self, fastapi_repo):
        """Test that framework detection has evidence."""
        plan = analyze_repository(
            repo_path=fastapi_repo,
            url="https://github.com/test/fastapi-app",
            commit_sha="abc123def456",
            owner="test",
            repo="fastapi-app",
        )

        framework_signals = [s for s in plan.evidence if s.field == "framework"]
        assert len(framework_signals) > 0
        assert framework_signals[0].value == "fastapi"
