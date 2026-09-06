from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceException
from app.security import (
    SandboxConfig,
    NetworkMode,
    validate_docker_config,
    audit_logger,
    SecurityEvent,
    SecurityEventType,
    validate_container_env,
    SecretLeakException,
    SandboxViolationException,
)
from app.runtime.docker import DockerContainerRuntime
from app.runtime.executor import RuntimeExecutor
from app.runtime.health import HealthChecker
from app.runtime.cleanup import ContainerCleanup

settings = get_settings()


class RuntimeService:
    def __init__(self):
        self.client = None
        self.runtime = None
        self.executor = None
        self.health_checker = None
        self.cleanup = None
        
        try:
            import docker
            self.client = docker.DockerClient(base_url=settings.DOCKER_SOCKET)
            # Initialize runtime components
            self.runtime = DockerContainerRuntime(base_url=settings.DOCKER_SOCKET)
            self.executor = RuntimeExecutor(self.runtime)
            self.health_checker = HealthChecker(self.runtime)
            self.cleanup = ContainerCleanup(self.runtime)
        except Exception:
            pass

    async def start_container(
        self,
        image: str,
        name: str,
        port: int,
        env: dict[str, str] | None = None,
        sandbox_config: SandboxConfig | None = None,
        deployment_id: str | None = None,
    ) -> dict:
        """
        Start a container with security validation.

        Args:
            image: Docker image name
            name: Container name
            port: Port to expose
            env: Environment variables
            sandbox_config: Sandbox configuration (defaults to for_runtime())
            deployment_id: Deployment ID for audit logging

        Returns:
            Dict with container_id and status

        Raises:
            SandboxViolationException: If sandbox config is invalid
            SecretLeakException: If secrets detected in env
            ExternalServiceException: If Docker operation fails
        """
        if not self.runtime or not self.runtime.is_available:
            raise ExternalServiceException("Docker", "Docker daemon not available")

        # Use default runtime sandbox config if not provided
        if sandbox_config is None:
            sandbox_config = SandboxConfig.for_runtime()

        # Validate sandbox configuration
        violations = sandbox_config.validate()
        if violations:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SANDBOX_REJECTED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"violations": violations},
                severity="error",
            ))
            raise SandboxViolationException(
                f"Sandbox configuration violates security policy: {violations}",
                details={"violations": violations},
            )

        # Validate environment variables
        if env:
            forbidden = validate_container_env(
                env,
                allowed_vars={"PORT", "RUNTIME_ID", "NODE_ENV"},
            )
            if forbidden:
                audit_logger.log(SecurityEvent(
                    event_type=SecurityEventType.SECRET_DETECTED,
                    timestamp=datetime.now(timezone.utc),
                    deployment_id=deployment_id,
                    details={"forbidden_env_vars": forbidden},
                    severity="critical",
                ))
                raise SecretLeakException(
                    f"Secrets detected in container environment: {forbidden}",
                    details={"forbidden_env_vars": forbidden},
                )

        # Generate Docker run arguments from sandbox config
        docker_args = sandbox_config.to_docker_run_args(
            image=image,
            command=[],  # Use image default command
            env_vars=env or {},
            name=name,
        )

        # Add port mapping
        docker_args["ports"] = {f"{port}/tcp": None}

        # Validate Docker configuration
        docker_violations = validate_docker_config(docker_args)
        if docker_violations:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SECURITY_POLICY_VIOLATION,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"docker_violations": docker_violations},
                severity="error",
            ))
            raise SandboxViolationException(
                f"Docker configuration violates security policy: {docker_violations}",
                details={"docker_violations": docker_violations},
            )

        # Log sandbox creation
        audit_logger.log(SecurityEvent(
            event_type=SecurityEventType.SANDBOX_CREATED,
            timestamp=datetime.now(timezone.utc),
            deployment_id=deployment_id,
            details={
                "image": image,
                "name": name,
                "port": port,
                "sandbox_config": {
                    "cpu_limit": sandbox_config.cpu_limit,
                    "memory_limit": sandbox_config.memory_limit,
                    "pids_limit": sandbox_config.pids_limit,
                    "network_mode": sandbox_config.network_mode.value,
                },
            },
        ))

        try:
            # Use new runtime executor
            from app.runtime.base import ContainerConfig
            
            container_config = ContainerConfig(
                image=image,
                name=name,
                env_vars=env or {},
                ports={port: None},
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
                labels={"deployment_id": deployment_id or ""},
            )
            
            container_id = await self.runtime.create_container(container_config)
            await self.runtime.start_container(container_id)
            
            return {
                "container_id": container_id,
                "status": "running",
            }
        except Exception as e:
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SANDBOX_TERMINATED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                details={"error": str(e)},
                severity="error",
            ))
            raise ExternalServiceException("Docker", str(e))

    async def stop_container(self, container_id: str, deployment_id: str | None = None) -> bool:
        """Stop and remove a container."""
        if not self.runtime or not self.runtime.is_available:
            return False
        try:
            await self.cleanup.cleanup_container(container_id)

            # Log container termination
            audit_logger.log(SecurityEvent(
                event_type=SecurityEventType.SANDBOX_TERMINATED,
                timestamp=datetime.now(timezone.utc),
                deployment_id=deployment_id,
                container_id=container_id,
            ))

            return True
        except Exception:
            return False

    async def health_check(self, container_id: str, port: int, path: str = "/") -> dict:
        """Check container health via HTTP."""
        if not self.health_checker:
            return {
                "status": "unhealthy",
                "response_code": None,
                "response_time_ms": None,
                "error_message": "Health checker not available",
            }
        
        result = await self.health_checker.check_health(
            container_id=container_id,
            port=port,
            path=path,
        )
        
        return {
            "status": result.status,
            "response_code": result.status_code,
            "response_time_ms": result.response_time_ms,
            "error_message": result.error,
        }
