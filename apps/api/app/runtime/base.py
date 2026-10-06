"""
Abstract container runtime interface.

All container runtimes must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ContainerStatus(Enum):
    """Container status states."""
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    REMOVED = "removed"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExecResult:
    """Result of command execution in container."""
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass
class ContainerConfig:
    """Configuration for container creation."""
    image: str
    command: list[str] = field(default_factory=list)
    name: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    working_dir: Optional[str] = None
    ports: dict[str, int] = field(default_factory=dict)  # container_port -> host_port
    labels: dict[str, str] = field(default_factory=dict)
    volumes: dict[str, dict] = field(default_factory=dict)
    
    # Security settings from SandboxConfig
    cpu_limit: float = 1.0
    memory_limit: str = "512m"
    memory_swap_limit: str = "512m"
    pids_limit: int = 50
    user: str = "1000:1000"
    no_new_privileges: bool = True
    read_only_rootfs: bool = False
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    cap_add: list[str] = field(default_factory=list)
    security_opt: list[str] = field(default_factory=lambda: ["no-new-privileges:true"])
    network_mode: str = "repo2web-isolated"
    dns_servers: list[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    tmpfs: dict[str, str] = field(default_factory=lambda: {
        "/tmp": "size=256m,noexec,nosuid",
        "/var/tmp": "size=128m,noexec,nosuid",
    })
    storage_opt: Optional[dict[str, str]] = None
    detach: bool = True
    timeout: int = 300  # seconds
    
    def to_dict(self) -> dict:
        """Convert to dictionary for Docker API."""
        result = {
            "image": self.image,
            "command": self.command,
            "name": self.name,
            "environment": self.env_vars,
            "detach": self.detach,
            "user": self.user,
            "nano_cpus": int(self.cpu_limit * 1_000_000_000),
            "mem_limit": self.memory_limit,
            "memswap_limit": self.memory_swap_limit,
            "pids_limit": self.pids_limit,
            "cap_drop": self.cap_drop,
            "cap_add": self.cap_add,
            "security_opt": self.security_opt,
            "network_mode": self.network_mode,
            "dns": self.dns_servers,
            "read_only": self.read_only_rootfs,
            "tmpfs": self.tmpfs,
            "labels": self.labels,
        }

        if self.working_dir is not None:
            result["working_dir"] = self.working_dir
        
        if self.storage_opt:
            result["storage_opt"] = self.storage_opt
        
        if self.ports:
            result["ports"] = {
                f"{container_port}/tcp": host_port
                for container_port, host_port in self.ports.items()
            }
        
        if self.volumes:
            result["volumes"] = self.volumes
        
        return result


class ContainerRuntime(ABC):
    """Abstract container runtime interface."""
    
    @abstractmethod
    async def create_container(self, config: ContainerConfig) -> str:
        """
        Create a container with the given configuration.
        
        Args:
            config: Container configuration
            
        Returns:
            Container ID
            
        Raises:
            ContainerCreateError: If container creation fails
        """
        ...
    
    @abstractmethod
    async def start_container(self, container_id: str) -> None:
        """
        Start a container.
        
        Args:
            container_id: Container ID to start
            
        Raises:
            ContainerStartError: If container start fails
        """
        ...
    
    @abstractmethod
    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Stop a container.
        
        Args:
            container_id: Container ID to stop
            timeout: Timeout in seconds
            
        Raises:
            ContainerStopError: If container stop fails
        """
        ...
    
    @abstractmethod
    async def remove_container(self, container_id: str, force: bool = False) -> None:
        """
        Remove a container.
        
        Args:
            container_id: Container ID to remove
            force: Force removal even if running
            
        Raises:
            ContainerRuntimeError: If container removal fails
        """
        ...
    
    @abstractmethod
    async def get_container_status(self, container_id: str) -> ContainerStatus:
        """
        Get container status.
        
        Args:
            container_id: Container ID
            
        Returns:
            Container status
        """
        ...
    
    @abstractmethod
    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Get container logs.
        
        Args:
            container_id: Container ID
            tail: Number of lines to return from the end
            
        Returns:
            Container logs
        """
        ...
    
    @abstractmethod
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        timeout: int = 300,
    ) -> ExecResult:
        """
        Execute a command in a container.
        
        Args:
            container_id: Container ID
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            Execution result
            
        Raises:
            ContainerExecError: If execution fails
        """
        ...
    
    @abstractmethod
    async def wait_for_container(
        self,
        container_id: str,
        timeout: int = 300,
    ) -> int:
        """
        Wait for container to finish.
        
        Args:
            container_id: Container ID
            timeout: Timeout in seconds
            
        Returns:
            Exit code
        """
        ...
    
    @abstractmethod
    async def health_check(
        self,
        container_id: str,
        port: int,
        path: str = "/",
        timeout: int = 5,
    ) -> dict:
        """
        Perform health check on container.
        
        Args:
            container_id: Container ID
            port: Port to check
            path: Health check path
            timeout: Timeout in seconds
            
        Returns:
            Health check result
        """
        ...
    
    @abstractmethod
    async def commit_container(
        self,
        container_id: str,
        repository: str,
        tag: str = "latest",
        changes: Optional[list[str]] = None,
    ) -> str:
        """
        Commit a container as a Docker image.
        
        Args:
            container_id: Container to commit
            repository: Image repository name
            tag: Image tag
            changes: Dockerfile instructions to apply
            
        Returns:
            Committed image name (repository:tag)
        """
        ...
    
    @abstractmethod
    async def remove_image(self, image_name: str) -> None:
        """
        Remove a Docker image.
        
        Args:
            image_name: Image name to remove
        """
        ...
