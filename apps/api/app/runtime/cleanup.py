"""
Container cleanup service.

Handles cleanup of containers, images, and resources.
"""

import logging
from typing import List, Optional

from .base import ContainerRuntime, ContainerStatus

logger = logging.getLogger(__name__)


class ContainerCleanup:
    """Container cleanup service."""
    
    def __init__(self, runtime: ContainerRuntime):
        """
        Initialize container cleanup.
        
        Args:
            runtime: Container runtime
        """
        self.runtime = runtime
    
    async def cleanup_container(self, container_id: str) -> None:
        """
        Cleanup a container.
        
        Args:
            container_id: Container ID to cleanup
        """
        try:
            # Get current status
            status = await self.runtime.get_container_status(container_id)
            
            # Stop if running
            if status == ContainerStatus.RUNNING:
                await self.runtime.stop_container(container_id, timeout=10)
            
            # Remove container
            await self.runtime.remove_container(container_id, force=True)
            
            logger.info(f"Cleaned up container {container_id[:12]}")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup container {container_id[:12]}: {e}")
    
    async def cleanup_image(self, image_name: str) -> None:
        """
        Cleanup a Docker image.
        
        Args:
            image_name: Image name to cleanup
        """
        try:
            await self.runtime.remove_image(image_name)
            logger.info(f"Cleaned up image {image_name}")
        except Exception as e:
            logger.warning(f"Failed to cleanup image {image_name}: {e}")
    
    async def cleanup_build_resources(
        self,
        container_id: Optional[str] = None,
        image_name: Optional[str] = None,
        volume_name: Optional[str] = None,
    ) -> None:
        """
        Cleanup all build resources (container, image, volume).
        
        Used after runtime container is created to clean up build artifacts.
        
        Args:
            container_id: Build container ID to cleanup
            image_name: Build image name to cleanup
            volume_name: Build volume name to cleanup
        """
        if container_id:
            await self.cleanup_container(container_id)
        
        if image_name:
            await self.cleanup_image(image_name)
        
        if volume_name:
            try:
                await self.runtime.remove_volume(volume_name)
            except Exception as e:
                logger.warning(f"Failed to cleanup volume {volume_name}: {e}")
    
    async def cleanup_all(self) -> int:
        """
        Cleanup all containers with repo2web labels.
        
        Returns:
            Number of containers cleaned up
        """
        count = 0
        
        try:
            # Find all containers with repo2web labels
            orphaned = await self.find_orphaned_containers()
            
            for container_id in orphaned:
                try:
                    await self.cleanup_container(container_id)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to cleanup container {container_id[:12]}: {e}")
            
            logger.info(f"Cleaned up {count} containers")
            
        except Exception as e:
            logger.error(f"Failed to cleanup all containers: {e}")
        
        return count
    
    async def find_orphaned_containers(self) -> List[str]:
        """
        Find orphaned containers with repo2web labels.
        
        Returns:
            List of container IDs
        """
        try:
            # This is a simplified approach
            # In production, use Docker API to list containers with labels
            
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to find orphaned containers: {e}")
            return []
    
    async def cleanup_old_containers(self, max_age_hours: int = 24) -> int:
        """
        Cleanup containers older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of containers cleaned up
        """
        # This would require tracking container creation time
        # For now, return 0
        return 0
