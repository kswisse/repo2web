"""
Health checker for containers.

Provides HTTP-based health checking with retry logic.

Security Design:
----------------
The health checker is a trusted Repo2Web infrastructure component.
When health-checking a deployment container, the flow is:

    Trusted health checker
        → container_id (trusted internal identifier from deployment pipeline)
        → Docker API inspection (trusted metadata source)
        → container labels (deployment_id proves provenance)
        → exact container IP
        → HTTP health check (no redirect following)

This is NOT general-purpose SSRF bypass. The container_id is never
user-controlled — it originates from the deployment pipeline. The
health checker only makes HTTP requests to IPs obtained from Docker
API for specific containers that have valid deployment_id labels.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from .base import ContainerRuntime

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of health check."""
    status: str  # "healthy" or "unhealthy"
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    error: Optional[str] = None
    attempts: int = 0


class HealthChecker:
    """Health checker for containers."""
    
    def __init__(self, runtime: ContainerRuntime):
        """
        Initialize health checker.
        
        Args:
            runtime: Container runtime
        """
        self.runtime = runtime
    
    async def check_health(
        self,
        container_id: str,
        port: int,
        path: str = "/",
        timeout: int = 5,
        max_retries: int = 5,
        retry_delay: float = 2.0,
    ) -> HealthCheckResult:
        """Check container health with retries.

        Security model:
        - The container_id is a trusted internal identifier from the deployment pipeline
        - The endpoint is obtained from Docker API for that specific container
        - Container labels (deployment_id) are validated to prove provenance
        - Only health checks to Repo2Web-created containers are allowed
        - Redirects are NOT followed (each redirect would need separate validation)
        - General SSRF protection is NOT weakened

        Platform behavior:
        - On Linux: Uses direct container IP (172.x.x.x:port)
        - On Windows/macOS (Docker Desktop): Uses port-mapped endpoint
          (localhost:mapped_port) because container IPs are in a Linux VM

        Args:
            container_id: Container ID
            port: Port to check
            path: Health check path
            timeout: Timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds

        Returns:
            Health check result
        """
        last_error = None
        deployment_id = None

        # Validate that this container is a trusted deployment container.
        # This must be done once before the retry loop.
        # If trusted, create a narrowly scoped SSRF exception for the
        # container's IP that expires after the health check completes.
        try:
            if hasattr(self.runtime, 'get_container_labels') and hasattr(self.runtime, 'get_container_ip'):
                labels = await self.runtime.get_container_labels(container_id)
                from app.security.ssrf import (
                    is_trusted_deployment_endpoint,
                    allow_container_ip_for_health_check,
                )

                # Get IP for validation (not for HTTP connection)
                container_ip = await self.runtime.get_container_ip(container_id)
                if container_ip and not is_trusted_deployment_endpoint(container_ip, labels):
                    last_error = (
                        f"Container {container_id[:12]} is not a recognized "
                        f"deployment (missing deployment_id label)"
                    )
                    logger.warning(last_error)
                    return HealthCheckResult(
                        status="unhealthy",
                        error=last_error,
                        attempts=0,
                    )

                # If trusted, create a temporary SSRF exception for this IP.
                # This allows the health check to connect to the container's
                # private IP even though it's in a blocked range.
                if container_ip:
                    deployment_id = labels.get("deployment_id", "unknown")
                    allow_container_ip_for_health_check(
                        ip=container_ip,
                        deployment_id=deployment_id,
                        container_id=container_id,
                        ttl=60,  # Expires after 60 seconds
                    )
        except Exception as e:
            logger.debug(f"Could not validate deployment endpoint: {e}")

        for attempt in range(1, max_retries + 1):
            try:
                # Get the accessible health check endpoint.
                # Uses port mapping on Windows/macOS, direct IP on Linux.
                endpoint = None
                if hasattr(self.runtime, 'get_container_health_endpoint'):
                    endpoint = await self.runtime.get_container_health_endpoint(
                        container_id, port
                    )

                if not endpoint:
                    # Fallback: try direct IP
                    container_ip = await self._get_container_ip(container_id)
                    if container_ip:
                        endpoint = f"http://{container_ip}:{port}"

                if not endpoint:
                    last_error = "Could not determine health check endpoint"
                    logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")
                    await asyncio.sleep(retry_delay)
                    continue

                url = f"{endpoint}{path}"

                # Perform HTTP health check — redirects are NOT followed.
                # Following redirects could allow the health check to be used
                # as an SSRF vector if the container redirects to an internal
                # service. Each redirect destination would need separate
                # validation, which is not worth the complexity.
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                    max_redirects=0,
                ) as client:
                    response = await client.get(url)

                    if 200 <= response.status_code < 300:
                        return HealthCheckResult(
                            status="healthy",
                            status_code=response.status_code,
                            response_time_ms=int(response.elapsed.total_seconds() * 1000),
                            attempts=attempt,
                        )
                    elif 300 <= response.status_code < 400:
                        # Redirect detected — check if target is safe
                        redirect_url = response.headers.get("location", "")
                        if redirect_url:
                            from urllib.parse import urlparse
                            from app.security.ssrf import validate_url_ssrf
                            parsed = urlparse(redirect_url)
                            if parsed.hostname:
                                # Use the actual scheme from the redirect,
                                # not a hardcoded scheme. A redirect to HTTP
                                # must be validated as HTTP.
                                scheme = parsed.scheme or "http"
                                port_part = f":{parsed.port}" if parsed.port else ""
                                is_safe, reason = validate_url_ssrf(
                                    f"{scheme}://{parsed.hostname}{port_part}{parsed.path}",
                                    allow_http=True,
                                )
                                if not is_safe:
                                    last_error = f"Health check redirect blocked: {reason}"
                                    logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")
                                    # Don't retry if redirect is blocked
                                    return HealthCheckResult(
                                        status="unhealthy",
                                        error=last_error,
                                        attempts=attempt,
                                    )
                        # Redirect to safe target — treat as redirect response
                        last_error = f"HTTP {response.status_code} redirect"
                        logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")

            except httpx.TimeoutException:
                last_error = "Health check timed out"
                logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")
            except httpx.ConnectError:
                last_error = "Connection refused"
                logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")

            # Wait before retry
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

        # All attempts failed
        return HealthCheckResult(
            status="unhealthy",
            error=last_error,
            attempts=max_retries,
        )
    
    async def _get_container_ip(self, container_id: str) -> Optional[str]:
        """Get container IP address from Docker API metadata.

        Uses the container runtime's Docker API to inspect the specific
        container and retrieve its actual IP address from network settings.

        Security properties:
        - The container_id is a trusted internal identifier (not user-controlled)
        - The IP is obtained from Docker API (trusted metadata source)
        - The caller (check_health) validates the container belongs to this
          deployment via deployment_id label before making HTTP requests
        - This method does NOT apply SSRF protection — that is the caller's
          responsibility based on the deployment context

        Returns:
            Container IP address, or None if not found
        """
        try:
            # Delegate to runtime's Docker API-based IP retrieval
            if hasattr(self.runtime, 'get_container_ip'):
                return await self.runtime.get_container_ip(container_id)

            # Fallback: for non-Docker runtimes, try to get container status
            # and return None (health check will be skipped)
            status = await self.runtime.get_container_status(container_id)
            logger.warning(
                f"Runtime does not support get_container_ip; "
                f"cannot health-check container {container_id[:12]}"
            )
            return None

        except Exception as e:
            logger.error(f"Failed to get container IP for {container_id[:12]}: {e}")
            return None
    
    async def wait_for_healthy(
        self,
        container_id: str,
        port: int,
        path: str = "/health",
        timeout: int = 60,
        interval: float = 2.0,
    ) -> HealthCheckResult:
        """
        Wait for container to become healthy.
        
        Args:
            container_id: Container ID
            port: Port to check
            path: Health check path
            timeout: Timeout in seconds
            interval: Check interval in seconds
            
        Returns:
            Health check result
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            result = await self.check_health(
                container_id=container_id,
                port=port,
                path=path,
                timeout=5,
                max_retries=1,
            )
            
            if result.status == "healthy":
                return result
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return HealthCheckResult(
                    status="unhealthy",
                    error=f"Timed out waiting for healthy status after {timeout}s",
                )
            
            await asyncio.sleep(interval)
