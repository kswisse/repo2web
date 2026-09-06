import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.analyzer import detect_framework, detect_languages, generate_execution_plan
from app.security import (
    SandboxConfig,
    RepositoryPolicy,
    DEFAULT_REPO_POLICY,
    validate_url_ssrf,
    validate_url,
    validate_container_env,
    audit_logger,
    SecurityEvent,
    SecurityEventType,
    scan_build_output,
    SSRFBlockedException,
    RepositoryPolicyException,
    SecretLeakException,
)
from app.runtime.docker import DockerContainerRuntime
from app.runtime.executor import BuildExecutor, BuildResult
from app.runtime.cleanup import ContainerCleanup

settings = get_settings()


class BuildService:
    def __init__(self):
        self.builds_dir = Path(tempfile.gettempdir()) / "repo2web_builds"
        self.builds_dir.mkdir(exist_ok=True)
        
        # Initialize runtime components
        self.runtime = None
        self.executor = None
        self.cleanup = None
        
        try:
            self.runtime = DockerContainerRuntime(base_url=settings.DOCKER_SOCKET)
            self.executor = BuildExecutor(self.runtime)
            self.cleanup = ContainerCleanup(self.runtime)
        except Exception:
            pass

    def clone_repository(
        self,
        url: str,
        commit_sha: str,
        deployment_id: str | None = None,
        policy: RepositoryPolicy | None = None,
    ) -> Path:
        """
        Clone a repository with security validation.

        Args:
            url: GitHub repository URL
            commit_sha: Commit SHA to checkout
            deployment_id: Deployment ID for audit logging
            policy: Repository policy (defaults to DEFAULT_REPO_POLICY)

        Returns:
            Path to cloned repository

        Raises:
            RepositoryPolicyException: If URL violates policy
            SSRFBlockedException: If URL resolves to blocked IP
        """
        policy = policy or DEFAULT_REPO_POLICY

        # Validate URL format
        is_valid, reason = validate_url(url, policy)
        if not is_valid:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.REPO_REJECTED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"url": url, "reason": reason},
            ))
            raise RepositoryPolicyException(f"Repository URL rejected: {reason}")

        # Validate SSRF protection
        is_safe, ssrf_reason = validate_url_ssrf(url)
        if not is_safe:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SSRF_ATTEMPT,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"url": url, "reason": ssrf_reason},
                severity="warning",
            ))
            raise SSRFBlockedException(f"SSRF protection blocked URL: {ssrf_reason}")

        # Log clone start
        audit_logger.log(SecurityEvent(
            event_type=SecurityEventType.REPO_CLONE_STARTED,
            timestamp=datetime.now(timezone.utc),
            deployment_id=deployment_id,
            details={"url": url, "commit_sha": commit_sha},
        ))

        dest = self.builds_dir / commit_sha[:12]
        if dest.exists():
            import shutil
            shutil.rmtree(dest)

        try:
            # Build safe clone command
            clone_cmd = [
                "git", "clone",
                "--no-local", "--no-hardlinks",
                "--config", "core.hooksPath=/dev/null",
                "--config", "core.fsmonitor=",
            ]

            if policy.shallow_clone:
                clone_cmd.extend(["--depth", "1"])

            if policy.disable_untracked_cache:
                clone_cmd.extend(["--config", "core.untrackedCache=false"])

            clone_cmd.extend([url, str(dest)])

            subprocess.run(
                clone_cmd,
                check=True,
                capture_output=True,
                timeout=policy.clone_timeout_seconds,
            )

            # Checkout specific commit
            subprocess.run(
                ["git", "checkout", commit_sha],
                cwd=str(dest),
                check=True,
                capture_output=True,
            )

            # Delete .gitmodules if policy requires
            if policy.delete_gitmodules:
                gitmodules = dest / ".gitmodules"
                if gitmodules.exists():
                    gitmodules.unlink()

            # Log clone success
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.REPO_CLONE_COMPLETED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"url": url, "commit_sha": commit_sha},
            ))

            return dest

        except subprocess.TimeoutExpired:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.REPO_CLONE_FAILED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"url": url, "reason": "clone_timeout"},
            ))
            raise RepositoryPolicyException(f"Clone timed out after {policy.clone_timeout_seconds}s")
        except subprocess.CalledProcessError as e:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.REPO_CLONE_FAILED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"url": url, "reason": str(e)},
            ))
            raise RepositoryPolicyException(f"Clone failed: {e}")

    def analyze_repository(self, repo_path: str) -> dict:
        """Analyze repository for framework detection."""
        framework, confidence = detect_framework(repo_path)
        languages = detect_languages(repo_path)
        return {
            "framework": framework,
            "detected_languages": languages,
            "confidence_score": confidence,
        }

    def generate_plan(self, analysis: dict) -> dict:
        """Generate execution plan from analysis."""
        return generate_execution_plan(analysis)

    async def execute_build(
        self,
        deployment_id: str,
        repo_url: str,
        commit_sha: str,
        execution_plan: dict,
        build_dir: str,
    ) -> BuildResult:
        """
        Execute a build in a container.
        
        Args:
            deployment_id: Deployment ID for audit logging
            repo_url: Repository URL
            commit_sha: Commit SHA
            execution_plan: Execution plan from analyzer
            build_dir: Path to cloned repository
            
        Returns:
            Build result
        """
        if not self.executor:
            return BuildResult(
                success=False,
                error="Build executor not available",
            )
        
        return await self.executor.execute_build(
            deployment_id=deployment_id,
            repo_url=repo_url,
            commit_sha=commit_sha,
            execution_plan=execution_plan,
            build_dir=build_dir,
        )

    def validate_build_env(
        self,
        env: dict[str, str],
        deployment_id: str | None = None,
    ) -> None:
        """
        Validate build environment variables against security policy.

        Raises:
            SecretLeakException: If secrets detected in environment
        """
        from app.security import BUILD_SECURITY_POLICY

        allowed_vars = BUILD_SECURITY_POLICY.get("allowed_env_vars", {})
        forbidden = validate_container_env(env, allowed_vars=allowed_vars)

        if forbidden:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SECRET_DETECTED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"forbidden_env_vars": forbidden},
                severity="critical",
            ))
            raise SecretLeakException(
                f"Secrets detected in build environment: {forbidden}",
                details={"forbidden_env_vars": forbidden},
            )

    def scan_build_logs(
        self,
        output: str,
        deployment_id: str | None = None,
    ) -> list[str]:
        """
        Scan build output for leaked secrets.

        Returns:
            List of detected secret patterns
        """
        detected = scan_build_output(output)

        if detected:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SECRET_DETECTED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"detected_patterns": detected},
                severity="warning",
            ))

        return detected
