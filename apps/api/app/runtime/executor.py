"""
Container execution executors for build and runtime.

Integrates with security layer for policy enforcement.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.security import (
    SandboxConfig,
    NetworkPolicy,
    BUILD_NETWORK_POLICY,
    RUNTIME_NETWORK_POLICY,
    BUILD_SECURITY_POLICY,
    RUNTIME_SECURITY_POLICY,
    audit_logger,
    SecurityEvent,
    SecurityEventType,
    validate_docker_config,
    validate_url,
    RepositoryPolicy,
    DEFAULT_REPO_POLICY,
)
from app.security.validation import SHELL_METACHARACTERS

# Maximum allowed command length to prevent buffer-based attacks
MAX_COMMAND_LENGTH = 2000

# Allowed command prefixes for build steps (defense-in-depth allowlist)
ALLOWED_BUILD_COMMAND_PREFIXES = (
    "pip install", "pip3 install",
    "npm install", "npm ci", "npx",
    "yarn install", "yarn add",
    "pnpm install", "pnpm add",
    "gem install", "bundle install",
    "go install", "go build",
    "cargo build", "cargo install",
    "mvn", "gradle",
    "make", "cmake",
    "gcc", "g++", "clang",
    "mkdir", "cp", "mv", "ln",
    "echo", "cat", "head", "tail",
    "sed", "awk", "grep",
    "node", "python", "python3", "ruby", "java", "go",
    "uvicorn", "gunicorn", "streamlit", "flask",
    "npm start", "npm run",
)

# Allowed runtime command prefixes
ALLOWED_RUNTIME_COMMAND_PREFIXES = (
    "python", "python3", "node", "java", "ruby", "go",
    "uvicorn", "gunicorn", "streamlit", "flask",
    "npm start", "npm run", "npx",
    "yarn start", "yarn run",
    "pnpm start", "pnpm run",
    "pm2", "forever",
)

from .base import ContainerRuntime, ContainerConfig, ContainerStatus
from .health import HealthChecker, HealthCheckResult
from .cleanup import ContainerCleanup
from .exceptions import (
    ContainerCreateError,
    ContainerStartError,
    ContainerExecError,
    ContainerTimeoutError,
    SecurityPolicyViolationError,
)

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of build execution."""
    success: bool
    container_id: Optional[str] = None
    image: Optional[str] = None
    output: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0
    steps_completed: list[str] = field(default_factory=list)
    security_violations: list[str] = field(default_factory=list)


@dataclass
class RuntimeInstance:
    """Instance of a running application."""
    container_id: str
    status: str
    port: int
    internal_url: str
    external_url: Optional[str] = None
    health_check_url: Optional[str] = None
    started_at: Optional[datetime] = None
    security_violations: list[str] = field(default_factory=list)


class BuildExecutor:
    """Executor for build operations in containers."""
    
    def __init__(
        self,
        runtime: ContainerRuntime,
        cleanup: Optional[ContainerCleanup] = None,
    ):
        """
        Initialize build executor.
        
        Args:
            runtime: Container runtime
            cleanup: Container cleanup service
        """
        self.runtime = runtime
        self.cleanup = cleanup or ContainerCleanup(runtime)
        self.health_checker = HealthChecker(runtime)
    
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
        start_time = datetime.now(timezone.utc)
        container_id = None
        
        try:
            # 1. Validate repository URL
            is_valid, reason = validate_url(repo_url)
            if not is_valid:
                audit_logger.log(SecurityEvent(
                    event_type=SecurityEventType.REPO_REJECTED,
                    timestamp=datetime.now(timezone.utc),
                    deployment_id=deployment_id,
                    details={"url": repo_url, "reason": reason},
                ))
                return BuildResult(
                    success=False,
                    error=f"Repository URL rejected: {reason}",
                    security_violations=[reason],
                )
            
            # 2. Create build sandbox config
            sandbox_config = SandboxConfig.for_build()
            
            # 3. Validate sandbox configuration
            violations = sandbox_config.validate()
            if violations:
                audit_logger.log(SecurityEvent(
                    event_type=SecurityEventType.SANDBOX_REJECTED,
                    timestamp=datetime.now(timezone.utc),
                    deployment_id=deployment_id,
                    details={"violations": violations},
                    severity="error",
                ))
                return BuildResult(
                    success=False,
                    error=f"Sandbox configuration violates security policy: {violations}",
                    security_violations=violations,
                )
            
            # 4. Validate network policy
            network_violations = self._validate_network_policy(BUILD_NETWORK_POLICY)
            if network_violations:
                return BuildResult(
                    success=False,
                    error=f"Network policy violations: {network_violations}",
                    security_violations=network_violations,
                )
            
            # 5. Generate build commands from execution plan
            build_commands = self._generate_build_commands(execution_plan, build_dir)
            
            # 6. Create container configuration
            container_config = ContainerConfig(
                image=self._select_base_image(execution_plan),
                command=["/bin/sh", "-c", " && ".join(build_commands)],
                name=f"build-{deployment_id[:8]}",
                env_vars={
                    "BUILD_ID": deployment_id,
                    "REPO_URL": repo_url,
                    "COMMIT_SHA": commit_sha,
                    "PYTHONUNBUFFERED": "1",
                    "PIP_NO_CACHE_DIR": "1",
                    "NPM_CONFIG_CACHE": "/tmp/.npm",
                },
                working_dir="/workspace",
                cpu_limit=sandbox_config.cpu_limit,
                memory_limit=sandbox_config.memory_limit,
                memory_swap_limit=sandbox_config.memory_swap_limit,
                pids_limit=sandbox_config.pids_limit,
                user=sandbox_config.user,
                no_new_privileges=sandbox_config.no_new_privileges,
                read_only_rootfs=sandbox_config.read_only_rootfs,
                cap_drop=sandbox_config.cap_drop,
                cap_add=sandbox_config.cap_add,
                security_opt=sandbox_config.security_opt,
                network_mode=sandbox_config.network_mode.value,
                dns_servers=sandbox_config.dns_servers,
                tmpfs=sandbox_config.tmpfs,
                storage_opt={"size": sandbox_config.disk_limit} if sandbox_config.disk_limit else None,
                labels={
                    "deployment_id": deployment_id,
                    "type": "build",
                },
            )
            
            # 7. Validate Docker configuration
            docker_violations = validate_docker_config(container_config.to_dict())
            if docker_violations:
                audit_logger.log(SecurityEvent(
                    event_type=SecurityEventType.SECURITY_POLICY_VIOLATION,
                    timestamp=datetime.now(timezone.utc),
                    deployment_id=deployment_id,
                    details={"docker_violations": docker_violations},
                    severity="error",
                ))
                return BuildResult(
                    success=False,
                    error=f"Docker configuration violates security policy: {docker_violations}",
                    security_violations=docker_violations,
                )
            
            # 8. Log build start
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.BUILD_STARTED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={
                    "repo_url": repo_url,
                    "commit_sha": commit_sha,
                    "image": container_config.image,
                },
            ))
            
            # 9. Create and start container
            container_id = await self.runtime.create_container(container_config)
            await self.runtime.start_container(container_id)
            
            # 10. Wait for build to complete
            try:
                exit_code = await self.runtime.wait_for_container(
                    container_id,
                    timeout=sandbox_config.execution_timeout,
                )
            except Exception as e:
                if "timed out" in str(e).lower():
                    audit_logger.log(SecurityEvent(
                        event_type=SecurityEventType.BUILD_TIMEOUT,
                        timestamp=datetime.now(timezone.utc),
                        deployment_id=deployment_id,
                        container_id=container_id,
                        details={"timeout": sandbox_config.execution_timeout},
                        severity="warning",
                    ))
                    return BuildResult(
                        success=False,
                        container_id=container_id,
                        error=f"Build timed out after {sandbox_config.execution_timeout}s",
                    )
                raise
            
            # 11. Get build output
            output = await self.runtime.get_container_logs(container_id)
            
            # 12. Check for security violations in output
            security_violations = self._scan_build_output(output)
            
            # 13. Determine success
            success = exit_code == 0 and not security_violations
            
            # 14. Log build completion
            event_type = SecurityEventType.BUILD_COMPLETED if success else SecurityEventType.BUILD_FAILED
            audit_logger.log(SecurityEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                container_id=container_id,
                details={
                    "exit_code": exit_code,
                    "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
                    "security_violations": security_violations,
                },
            ))
            
            # 15. Calculate duration
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return BuildResult(
                success=success,
                container_id=container_id,
                output=output,
                error=None if success else f"Build failed with exit code {exit_code}",
                duration_seconds=duration,
                security_violations=security_violations,
            )
            
        except Exception as e:
            logger.error(f"Build execution failed: {e}")
            
            # Log failure
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.BUILD_FAILED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                container_id=container_id,
                details={"error": str(e)},
                severity="error",
            ))
            
            return BuildResult(
                success=False,
                container_id=container_id,
                error=str(e),
                duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
            )
            
        finally:
            # 16. Always cleanup build container
            if container_id:
                try:
                    await self.cleanup.cleanup_container(container_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup build container: {e}")
    
    def _validate_network_policy(self, policy: NetworkPolicy) -> list[str]:
        """Validate network policy for compliance."""
        violations = []
        
        # Check for blocked CIDRs
        for cidr in policy.BLOCKED_CIDRS:
            for rule in policy.rules:
                if rule.direction.value == "egress" and rule.dest_cidr == cidr:
                    violations.append(f"Blocked CIDR {cidr} in egress rules")
        
        # Check for blocked ports
        for port in policy.BLOCKED_PORTS:
            for rule in policy.rules:
                if (rule.direction.value == "egress" and 
                    rule.port == port and 
                    rule.action == "allow"):
                    violations.append(f"Blocked port {port} allowed in egress rules")
        
        return violations
    
    def _generate_build_commands(self, execution_plan: dict, build_dir: str) -> list[str]:
        """Generate build commands from execution plan.
        
        Validates each command against security policy:
        - Rejects commands with shell metacharacters
        - Enforces command length limits
        - Validates command prefixes against allowlist
        """
        commands = []
        
        # Add setup commands (these are safe, hardcoded)
        commands.append("mkdir -p /workspace")
        commands.append(f"cp -r {build_dir}/* /workspace/")
        
        # Validate and add install steps
        for step in execution_plan.get("install_steps", []):
            cmd = step.get("command", "")
            if cmd:
                validated_cmd = self._validate_build_command(cmd)
                commands.append(validated_cmd)
        
        # Validate and add build steps
        for step in execution_plan.get("build_steps", []):
            cmd = step.get("command", "")
            if cmd:
                validated_cmd = self._validate_build_command(cmd)
                commands.append(validated_cmd)
        
        return commands
    
    def _validate_build_command(self, cmd: str) -> str:
        """Validate a build command for security.
        
        Args:
            cmd: The build command to validate
            
        Returns:
            The validated command
            
        Raises:
            SecurityPolicyViolationError: If command is dangerous
        """
        if not cmd or not cmd.strip():
            raise SecurityPolicyViolationError("Empty build command")
        
        cmd = cmd.strip()
        
        # Enforce command length limit
        if len(cmd) > MAX_COMMAND_LENGTH:
            raise SecurityPolicyViolationError(
                f"Build command exceeds maximum length of {MAX_COMMAND_LENGTH}"
            )
        
        # Block shell metacharacters (injection prevention)
        if SHELL_METACHARACTERS.search(cmd):
            raise SecurityPolicyViolationError(
                f"Build command contains shell metacharacters: {cmd!r}"
            )
        
        # Validate command starts with an allowed prefix
        cmd_lower = cmd.lower()
        if not any(cmd_lower.startswith(prefix) for prefix in ALLOWED_BUILD_COMMAND_PREFIXES):
            raise SecurityPolicyViolationError(
                f"Build command not in allowlist: {cmd!r}"
            )
        
        return cmd
    
    def _select_base_image(self, execution_plan: dict) -> str:
        """Select appropriate base image based on execution plan."""
        framework = execution_plan.get("framework", "unknown")
        
        image_map = {
            "fastapi": "python:3.11-slim",
            "flask": "python:3.11-slim",
            "django": "python:3.11-slim",
            "streamlit": "python:3.11-slim",
            "nextjs": "node:20-alpine",
            "react": "node:20-alpine",
            "vue": "node:20-alpine",
            "express": "node:20-alpine",
        }
        
        return image_map.get(framework, "python:3.11-slim")
    
    def _scan_build_output(self, output: str) -> list[str]:
        """Scan build output for security violations."""
        violations = []
        
        # Check for common security issues
        suspicious_patterns = [
            "docker",
            "kubectl",
            "sudo",
            "chmod 777",
            "rm -rf /",
            "curl | sh",
            "wget | sh",
            "eval(",
            "exec(",
        ]
        
        for pattern in suspicious_patterns:
            if pattern.lower() in output.lower():
                violations.append(f"Suspicious pattern detected: {pattern}")
        
        return violations


class RuntimeExecutor:
    """Executor for runtime operations."""
    
    def __init__(
        self,
        runtime: ContainerRuntime,
        cleanup: Optional[ContainerCleanup] = None,
    ):
        """
        Initialize runtime executor.
        
        Args:
            runtime: Container runtime
            cleanup: Container cleanup service
        """
        self.runtime = runtime
        self.cleanup = cleanup or ContainerCleanup(runtime)
        self.health_checker = HealthChecker(runtime)
    
    async def start_runtime(
        self,
        deployment_id: str,
        build_image: str,
        execution_plan: dict,
        port: int = 8000,
    ) -> RuntimeInstance:
        """
        Start a runtime container.
        
        Args:
            deployment_id: Deployment ID for audit logging
            build_image: Docker image from build
            execution_plan: Execution plan
            port: Port to expose
            
        Returns:
            Runtime instance
        """
        container_id = None
        
        try:
            # 1. Create runtime sandbox config
            sandbox_config = SandboxConfig.for_runtime()
            
            # 2. Validate sandbox configuration
            violations = sandbox_config.validate()
            if violations:
                audit_logger.log(SecurityEvent(
                    event_type=SecurityEventType.SANDBOX_REJECTED,
                    timestamp=datetime.now(timezone.utc),
                    deployment_id=deployment_id,
                    details={"violations": violations},
                    severity="error",
                ))
                raise SecurityPolicyViolationError(
                    f"Sandbox configuration violates security policy: {violations}"
                )
            
            # 3. Validate network policy
            network_violations = self._validate_network_policy(RUNTIME_NETWORK_POLICY)
            if network_violations:
                raise SecurityPolicyViolationError(
                    f"Network policy violations: {network_violations}"
                )
            
            # 4. Validate run command from execution plan
            run_command = execution_plan.get("run_command", "python app.py")
            self._validate_runtime_command(run_command)
            
            # 5. Create container configuration
            container_config = ContainerConfig(
                image=build_image,
                command=["/bin/sh", "-c", run_command],
                name=f"runtime-{deployment_id[:8]}",
                env_vars={
                    "RUNTIME_ID": deployment_id,
                    "PORT": str(port),
                    "NODE_ENV": "production",
                },
                working_dir="/app",
                ports={port: None},  # Dynamic port mapping
                cpu_limit=sandbox_config.cpu_limit,
                memory_limit=sandbox_config.memory_limit,
                memory_swap_limit=sandbox_config.memory_swap_limit,
                pids_limit=sandbox_config.pids_limit,
                user=sandbox_config.user,
                no_new_privileges=sandbox_config.no_new_privileges,
                read_only_rootfs=sandbox_config.read_only_rootfs,
                cap_drop=sandbox_config.cap_drop,
                cap_add=sandbox_config.cap_add,
                security_opt=sandbox_config.security_opt,
                network_mode=sandbox_config.network_mode.value,
                dns_servers=sandbox_config.dns_servers,
                tmpfs=sandbox_config.tmpfs,
                storage_opt={"size": sandbox_config.disk_limit} if sandbox_config.disk_limit else None,
                labels={
                    "deployment_id": deployment_id,
                    "type": "runtime",
                },
                timeout=sandbox_config.runtime_timeout,
            )
            
            # 6. Validate Docker configuration
            docker_violations = validate_docker_config(container_config.to_dict())
            if docker_violations:
                audit_logger.log(SecurityEvent(
                    event_type=SecurityEventType.SECURITY_POLICY_VIOLATION,
                    timestamp=datetime.now(timezone.utc),
                    deployment_id=deployment_id,
                    details={"docker_violations": docker_violations},
                    severity="error",
                ))
                raise SecurityPolicyViolationError(
                    f"Docker configuration violates security policy: {docker_violations}"
                )
            
            # 7. Log runtime start
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.RUNTIME_STARTED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={
                    "image": build_image,
                    "port": port,
                    "run_command": run_command,
                },
            ))
            
            # 8. Create and start container
            container_id = await self.runtime.create_container(container_config)
            await self.runtime.start_container(container_id)
            
            # 9. Wait for startup
            import asyncio
            await asyncio.sleep(2)  # Give container time to start
            
            # 10. Perform health check
            health_result = await self.health_checker.check_health(
                container_id=container_id,
                port=port,
                path="/",
                timeout=10,
            )
            
            # 11. Get container status
            status = await self.runtime.get_container_status(container_id)
            
            # 12. Build internal URL
            internal_url = f"http://localhost:{port}"
            
            # 13. Return runtime instance
            return RuntimeInstance(
                container_id=container_id,
                status="running" if status == ContainerStatus.RUNNING else "starting",
                port=port,
                internal_url=internal_url,
                health_check_url=f"{internal_url}/health",
                started_at=datetime.now(timezone.utc),
                security_violations=[],
            )
            
        except SecurityPolicyViolationError:
            raise
        except Exception as e:
            logger.error(f"Runtime start failed: {e}")
            
            # Log failure
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SANDBOX_TERMINATED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                container_id=container_id,
                details={"error": str(e)},
                severity="error",
            ))
            
            # Cleanup on failure
            if container_id:
                try:
                    await self.cleanup.cleanup_container(container_id)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup runtime container: {cleanup_error}")
            
            raise
    
    def _validate_network_policy(self, policy: NetworkPolicy) -> list[str]:
        """Validate network policy for compliance."""
        violations = []
        
        # Check for blocked CIDRs
        for cidr in policy.BLOCKED_CIDRS:
            for rule in policy.rules:
                if rule.direction.value == "egress" and rule.dest_cidr == cidr:
                    violations.append(f"Blocked CIDR {cidr} in egress rules")
        
        # Check for blocked ports
        for port in policy.BLOCKED_PORTS:
            for rule in policy.rules:
                if (rule.direction.value == "egress" and 
                    rule.port == port and 
                    rule.action == "allow"):
                    violations.append(f"Blocked port {port} allowed in egress rules")
        
        return violations
    
    def _validate_runtime_command(self, cmd: str) -> str:
        """Validate a runtime command for security.
        
        Args:
            cmd: The runtime command to validate
            
        Returns:
            The validated command
            
        Raises:
            SecurityPolicyViolationError: If command is dangerous
        """
        if not cmd or not cmd.strip():
            raise SecurityPolicyViolationError("Empty runtime command")
        
        cmd = cmd.strip()
        
        # Enforce command length limit
        if len(cmd) > MAX_COMMAND_LENGTH:
            raise SecurityPolicyViolationError(
                f"Runtime command exceeds maximum length of {MAX_COMMAND_LENGTH}"
            )
        
        # Block shell metacharacters (injection prevention)
        if SHELL_METACHARACTERS.search(cmd):
            raise SecurityPolicyViolationError(
                f"Runtime command contains shell metacharacters: {cmd!r}"
            )
        
        # Validate command starts with an allowed prefix
        cmd_lower = cmd.lower()
        if not any(cmd_lower.startswith(prefix) for prefix in ALLOWED_RUNTIME_COMMAND_PREFIXES):
            raise SecurityPolicyViolationError(
                f"Runtime command not in allowlist: {cmd!r}"
            )
        
        return cmd
