"""
Docker container runtime implementation.

Uses docker-py to manage containers with security policy enforcement.
"""

import asyncio
import logging
import platform
from typing import Optional

from app.security.ssrf import is_ip_blocked

try:
    import docker
    from docker.errors import ImageNotFound, APIError, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .base import ContainerRuntime, ContainerConfig, ContainerStatus, ExecResult
from .exceptions import (
    ContainerCreateError,
    ContainerStartError,
    ContainerStopError,
    ContainerExecError,
    ContainerRuntimeError,
)

logger = logging.getLogger(__name__)


def _detect_docker_url() -> str:
    """Detect the correct Docker daemon URL for the current platform."""
    if platform.system() == "Windows":
        return "npipe:////./pipe/docker_engine"
    return "unix:///var/run/docker.sock"


class DockerContainerRuntime(ContainerRuntime):
    """Docker container runtime implementation."""
    
    def __init__(self, base_url: str = None):
        """
        Initialize Docker container runtime.
        
        Args:
            base_url: Docker daemon URL (auto-detected if None)
        """
        if base_url is None:
            base_url = _detect_docker_url()
        
        if not DOCKER_AVAILABLE:
            logger.warning("docker package not installed")
            self.client = None
            return
            
        try:
            self.client = docker.DockerClient(base_url=base_url)
            self.client.ping()
            logger.info(f"Connected to Docker daemon at {base_url}")
        except Exception as e:
            logger.warning(f"Failed to connect to Docker daemon: {e}")
            self.client = None
    
    @property
    def is_available(self) -> bool:
        """Check if Docker daemon is available."""
        return self.client is not None
    
    async def create_container(self, config: ContainerConfig) -> str:
        """
        Create a Docker container with the given configuration.
        
        Args:
            config: Container configuration
            
        Returns:
            Container ID
            
        Raises:
            ContainerCreateError: If container creation fails
        """
        if not self.is_available:
            raise ContainerCreateError("Docker daemon not available")
        
        try:
            # Convert config to Docker API format
            docker_args = config.to_dict()
            
            # Remove None values
            docker_args = {k: v for k, v in docker_args.items() if v is not None}
            
            # Create container
            container = self.client.containers.create(**docker_args)
            
            logger.info(f"Created container {container.id[:12]} with image {config.image}")
            return container.id
            
        except ImageNotFound as e:
            raise ContainerCreateError(f"Image not found: {config.image}") from e
        except APIError as e:
            raise ContainerCreateError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerCreateError(f"Failed to create container: {e}") from e
    
    async def start_container(self, container_id: str) -> None:
        """
        Start a Docker container.
        
        Args:
            container_id: Container ID
            
        Raises:
            ContainerStartError: If container start fails
        """
        if not self.is_available:
            raise ContainerStartError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"Started container {container_id[:12]}")
        except NotFound as e:
            raise ContainerStartError(f"Container not found: {container_id}") from e
        except APIError as e:
            raise ContainerStartError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerStartError(f"Failed to start container: {e}") from e
    
    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Stop a Docker container.
        
        Args:
            container_id: Container ID
            timeout: Timeout in seconds
            
        Raises:
            ContainerStopError: If container stop fails
        """
        if not self.is_available:
            raise ContainerStopError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container {container_id[:12]}")
        except NotFound:
            logger.warning(f"Container {container_id[:12]} not found (already removed?)")
        except APIError as e:
            raise ContainerStopError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerStopError(f"Failed to stop container: {e}") from e
    
    async def remove_container(self, container_id: str, force: bool = False) -> None:
        """
        Remove a Docker container.
        
        Args:
            container_id: Container ID
            force: Force removal even if running
            
        Raises:
            ContainerRuntimeError: If container removal fails
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container {container_id[:12]}")
        except NotFound:
            logger.warning(f"Container {container_id[:12]} not found (already removed?)")
        except APIError as e:
            raise ContainerRuntimeError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerRuntimeError(f"Failed to remove container: {e}") from e
    
    async def get_container_status(self, container_id: str) -> ContainerStatus:
        """
        Get Docker container status.
        
        Args:
            container_id: Container ID
            
        Returns:
            Container status
        """
        if not self.is_available:
            return ContainerStatus.UNKNOWN
        
        try:
            container = self.client.containers.get(container_id)
            status = container.status
            
            status_map = {
                "created": ContainerStatus.CREATED,
                "running": ContainerStatus.RUNNING,
                "restarting": ContainerStatus.RUNNING,
                "removing": ContainerStatus.STOPPED,
                "paused": ContainerStatus.STOPPED,
                "exited": ContainerStatus.STOPPED,
                "dead": ContainerStatus.FAILED,
            }
            
            return status_map.get(status, ContainerStatus.UNKNOWN)
            
        except NotFound:
            return ContainerStatus.REMOVED
        except Exception:
            return ContainerStatus.UNKNOWN
    
    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Get Docker container logs.
        
        Args:
            container_id: Container ID
            tail: Number of lines to return from the end
            
        Returns:
            Container logs
        """
        if not self.is_available:
            return ""
        
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=False)
            return logs.decode("utf-8", errors="replace")
        except NotFound:
            return ""
        except Exception as e:
            logger.error(f"Failed to get logs for container {container_id[:12]}: {e}")
            return ""
    
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        timeout: int = 300,
    ) -> ExecResult:
        """
        Execute a command in a Docker container.
        
        Args:
            container_id: Container ID
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            Execution result
            
        Raises:
            ContainerExecError: If execution fails
        """
        if not self.is_available:
            raise ContainerExecError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            
            # Execute command with timeout
            exit_code, output = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                timeout=timeout,
            )
            
            stdout = output.decode("utf-8", errors="replace") if output else ""
            
            return ExecResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr="",
                timed_out=False,
            )
            
        except NotFound as e:
            raise ContainerExecError(f"Container not found: {container_id}") from e
        except Exception as e:
            raise ContainerExecError(f"Failed to execute command: {e}") from e
    
    async def wait_for_container(
        self,
        container_id: str,
        timeout: int = 300,
    ) -> int:
        """
        Wait for Docker container to finish.
        
        Args:
            container_id: Container ID
            timeout: Timeout in seconds
            
        Returns:
            Exit code
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            
            # Wait for container with timeout
            result = container.wait(timeout=timeout)
            return result.get("StatusCode", -1)
            
        except NotFound as e:
            raise ContainerRuntimeError(f"Container not found: {container_id}") from e
        except Exception as e:
            raise ContainerRuntimeError(f"Failed to wait for container: {e}") from e
    
    async def health_check(
        self,
        container_id: str,
        port: int,
        path: str = "/",
        timeout: int = 5,
    ) -> dict:
        """
        Perform health check on container with SSRF protection.
        
        Prevents:
        - Redirect to internal/private IPs
        - DNS rebinding
        - SSRF via HTTP redirects
        
        Args:
            container_id: Container ID
            port: Port to check
            path: Health check path
            timeout: Timeout in seconds
            
        Returns:
            Health check result
        """
        if not self.is_available:
            return {
                "status": "unhealthy",
                "error": "Docker daemon not available",
            }
        
        if not HTTPX_AVAILABLE:
            return {
                "status": "unhealthy",
                "error": "httpx package not installed",
            }
        
        try:
            container = self.client.containers.get(container_id)
            
            # Get container IP
            container.reload()
            network_settings = container.attrs.get("NetworkSettings", {})
            networks = network_settings.get("Networks", {})
            
            ip_address = None
            for network_name, network_info in networks.items():
                ip_address = network_info.get("IPAddress")
                if ip_address:
                    break
            
            if not ip_address:
                return {
                    "status": "unhealthy",
                    "error": "Could not determine container IP",
                }
            
            # Validate container IP is not in a blocked range
            if is_ip_blocked(ip_address):
                return {
                    "status": "unhealthy",
                    "error": "Container IP is in blocked range",
                }
            
            # Perform HTTP health check with redirect protection
            url = f"http://{ip_address}:{port}{path}"
            
            # Disable automatic redirects and limit to 0 redirects
            # Health check should never redirect to a different host
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                max_redirects=0,
            ) as client:
                response = await client.get(url)
                
                # If response is a redirect, check the target
                if 300 <= response.status_code < 400:
                    redirect_url = response.headers.get("location", "")
                    if redirect_url:
                        # Parse redirect URL and check for SSRF
                        from urllib.parse import urlparse
                        parsed = urlparse(redirect_url)
                        if parsed.hostname:
                            # Check if redirect target is safe
                            from app.security.ssrf import validate_url_ssrf
                            is_safe, reason = validate_url_ssrf(
                                f"https://{parsed.hostname}:{parsed.port or 80}{parsed.path}"
                            )
                            if not is_safe:
                                return {
                                    "status": "unhealthy",
                                    "error": f"Health check redirect blocked: {reason}",
                                }
                
                if 200 <= response.status_code < 300:
                    return {
                        "status": "healthy",
                        "status_code": response.status_code,
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}",
                    }
                    
        except httpx.TimeoutException:
            return {
                "status": "unhealthy",
                "error": "Health check timed out",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
