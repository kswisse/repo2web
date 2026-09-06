"""
Resource metrics abstraction for container observability.

Defines the interface for collecting container resource metrics.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ContainerMetrics:
    """Container resource metrics snapshot."""
    container_id: str
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_bytes: int
    memory_limit_bytes: int
    memory_percent: float
    network_rx_bytes: int
    network_tx_bytes: int
    block_io_read_bytes: int
    block_io_write_bytes: int
    pids: int
    uptime_seconds: Optional[int] = None
    status: str = "unknown"
    exit_code: Optional[int] = None


class ResourceCollector(ABC):
    """Abstract resource collector interface."""

    @abstractmethod
    async def collect_metrics(self, container_id: str) -> Optional[ContainerMetrics]:
        """Collect metrics for a container."""
        ...

    @abstractmethod
    async def get_container_stats(self, container_id: str) -> dict:
        """Get raw container stats."""
        ...
