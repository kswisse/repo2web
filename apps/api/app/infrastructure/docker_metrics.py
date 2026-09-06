"""
Docker resource collector implementation.

Collects container resource metrics from Docker daemon.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

try:
    import docker
    from docker.errors import NotFound as DockerNotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from app.runtime.metrics import ResourceCollector, ContainerMetrics

logger = logging.getLogger(__name__)


class DockerResourceCollector(ResourceCollector):
    """Docker implementation of resource collector."""

    def __init__(self):
        try:
            if DOCKER_AVAILABLE:
                self.client = docker.from_env()
                self.available = True
            else:
                self.client = None
                self.available = False
        except Exception:
            self.client = None
            self.available = False

    async def collect_metrics(self, container_id: str) -> Optional[ContainerMetrics]:
        """Collect metrics from Docker container stats."""
        if not self.available:
            return None

        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)

            # Parse CPU usage
            cpu_delta = (
                stats['cpu_stats']['cpu_usage']['total_usage']
                - stats['precpu_stats']['cpu_usage']['total_usage']
            )
            system_delta = (
                stats['cpu_stats']['system_cpu_usage']
                - stats['precpu_stats']['system_cpu_usage']
            )
            cpu_count = stats['cpu_stats']['online_cpus']
            cpu_percent = (
                (cpu_delta / system_delta) * cpu_count * 100.0
                if system_delta > 0
                else 0.0
            )

            # Parse memory
            memory_usage = stats['memory_stats'].get('usage', 0)
            memory_limit = stats['memory_stats'].get('limit', 0)
            memory_percent = (
                (memory_usage / memory_limit) * 100.0
                if memory_limit > 0
                else 0.0
            )

            # Parse network
            networks = stats.get('networks', {})
            network_rx = sum(v.get('rx_bytes', 0) for v in networks.values())
            network_tx = sum(v.get('tx_bytes', 0) for v in networks.values())

            # Parse block IO
            io_service = stats.get('io_service_bytes_recursive', [])
            io_read = sum(
                v.get('value', 0)
                for v in io_service
                if v.get('op') == 'read'
            )
            io_write = sum(
                v.get('value', 0)
                for v in io_service
                if v.get('op') == 'write'
            )

            # Calculate uptime from started_at
            uptime_seconds = None
            started_at = container.attrs.get('State', {}).get('StartedAt', '')
            if started_at:
                try:
                    start_dt = datetime.fromisoformat(
                        started_at.replace('Z', '+00:00')
                    )
                    uptime_seconds = int(
                        (datetime.now(timezone.utc) - start_dt).total_seconds()
                    )
                except (ValueError, TypeError):
                    pass

            return ContainerMetrics(
                container_id=container_id,
                timestamp=datetime.now(timezone.utc),
                cpu_usage_percent=round(cpu_percent, 2),
                memory_usage_bytes=memory_usage,
                memory_limit_bytes=memory_limit,
                memory_percent=round(memory_percent, 2),
                network_rx_bytes=network_rx,
                network_tx_bytes=network_tx,
                block_io_read_bytes=io_read,
                block_io_write_bytes=io_write,
                pids=stats.get('pids_stats', {}).get('current', 0),
                uptime_seconds=uptime_seconds,
                status=container.status,
            )

        except DockerNotFound:
            logger.warning(f"Container {container_id[:12]} not found for metrics")
            return None
        except Exception as e:
            logger.warning(f"Failed to collect metrics for {container_id[:12]}: {e}")
            return None

    async def get_container_stats(self, container_id: str) -> dict:
        """Get raw container stats."""
        if not self.available:
            return {}

        try:
            container = self.client.containers.get(container_id)
            return container.stats(stream=False)
        except DockerNotFound:
            logger.warning(f"Container {container_id[:12]} not found")
            return {}
        except Exception as e:
            logger.warning(f"Failed to get stats for {container_id[:12]}: {e}")
            return {}
