"""
Health checker for containers.

Provides HTTP-based health checking with retry logic.
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
        """
        Check container health with retries.
        
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
        
        for attempt in range(1, max_retries + 1):
            try:
                # Get container IP
                container_ip = await self._get_container_ip(container_id)
                
                if not container_ip:
                    last_error = "Could not determine container IP"
                    logger.warning(f"Attempt {attempt}/{max_retries}: {last_error}")
                    await asyncio.sleep(retry_delay)
                    continue
                
                # Perform HTTP health check
                url = f"http://{container_ip}:{port}{path}"
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url)
                    
                    if 200 <= response.status_code < 300:
                        return HealthCheckResult(
                            status="healthy",
                            status_code=response.status_code,
                            response_time_ms=int(response.elapsed.total_seconds() * 1000),
                            attempts=attempt,
                        )
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
        """Get container IP address."""
        try:
            # Use runtime to get container info
            status = await self.runtime.get_container_status(container_id)
            
            # For Docker, we need to inspect the container
            # This is a simplified approach - in production, use Docker API
            # to get the actual IP address
            
            # For now, return localhost (works for local development)
            return "localhost"
            
        except Exception as e:
            logger.error(f"Failed to get container IP: {e}")
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
