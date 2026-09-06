"""
Sandbox configuration for build and runtime containers.

Every field has a secure default. Override only with explicit, validated values.
Immutable dataclass — once created, cannot be modified.
"""

from dataclasses import dataclass, field
from enum import Enum


class ContainerType(Enum):
    BUILD = "build"
    RUNTIME = "runtime"


class NetworkMode(Enum):
    ISOLATED = "repo2web-isolated"
    RUNTIMES = "repo2web-runtimes"
    INTERNAL = "repo2web-internal"


@dataclass(frozen=True)
class SandboxConfig:
    """
    Immutable sandbox configuration. Once created, cannot be modified.
    Use factory methods for common configurations.
    """

    # --- Resource Limits (cgroups v2) ---
    cpu_limit: float = 1.0
    memory_limit: str = "512m"
    memory_swap_limit: str = "512m"
    disk_limit: str = "512m"
    pids_limit: int = 50

    # --- Timeouts ---
    execution_timeout: int = 300
    runtime_timeout: int = 86400

    # --- User Isolation ---
    user: str = "1000:1000"
    no_new_privileges: bool = True

    # --- Filesystem ---
    read_only_rootfs: bool = False
    tmpfs: dict = field(default_factory=lambda: {
        "/tmp": "size=256m,noexec,nosuid",
        "/var/tmp": "size=128m,noexec,nosuid",
    })

    # --- Capabilities ---
    cap_drop: list = field(default_factory=lambda: ["ALL"])
    cap_add: list = field(default_factory=list)

    # --- Seccomp ---
    seccomp_profile: str = "default"

    # --- Network ---
    network_mode: NetworkMode = NetworkMode.ISOLATED
    dns_servers: list = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    dns_search: list = field(default_factory=list)
    allowed_outbound_ports: list = field(default_factory=lambda: [80, 443])

    # --- Security Options ---
    security_opt: list = field(default_factory=lambda: ["no-new-privileges:true"])

    # --- Volumes (MUST be empty — no host mounts) ---
    volumes: list = field(default_factory=list)

    @classmethod
    def for_build(cls) -> "SandboxConfig":
        """Build sandbox: needs dependency installation, compilation."""
        return cls(
            cpu_limit=2.0,
            memory_limit="1g",
            memory_swap_limit="1g",
            disk_limit="1g",
            pids_limit=100,
            execution_timeout=300,
            read_only_rootfs=False,
            tmpfs={
                "/tmp": "size=512m,noexec,nosuid",
                "/var/tmp": "size=256m,noexec,nosuid",
                "/home/app": "size=256m",
            },
            network_mode=NetworkMode.ISOLATED,
        )

    @classmethod
    def for_runtime(cls) -> "SandboxConfig":
        """Runtime sandbox: serves built application, more restrictive."""
        return cls(
            cpu_limit=1.0,
            memory_limit="512m",
            memory_swap_limit="512m",
            disk_limit="512m",
            pids_limit=50,
            execution_timeout=86400,
            read_only_rootfs=True,
            tmpfs={
                "/tmp": "size=128m,noexec,nosuid",
                "/var/cache": "size=128m",
            },
            network_mode=NetworkMode.RUNTIMES,
        )

    def to_docker_run_args(
        self,
        image: str,
        command: list[str],
        env_vars: dict[str, str],
        name: str,
    ) -> dict:
        """Generate Docker API arguments for container creation."""
        return {
            "image": image,
            "command": command,
            "name": name,
            "detach": True,
            "user": self.user,
            "nano_cpus": int(self.cpu_limit * 1_000_000_000),
            "mem_limit": self.memory_limit,
            "memswap_limit": self.memory_swap_limit,
            "pids_limit": self.pids_limit,
            "cap_drop": self.cap_drop,
            "security_opt": self.security_opt,
            "network_mode": self.network_mode.value,
            "dns": self.dns_servers,
            "dns_search": self.dns_search,
            "read_only": self.read_only_rootfs,
            "tmpfs": self.tmpfs,
            "storage_opt": {"size": self.disk_limit} if self.disk_limit else None,
            "environment": env_vars,
            "volumes": self.volumes,
        }

    def validate(self) -> list[str]:
        """Validate configuration for security compliance. Returns list of violations."""
        violations = []

        if self.user == "root" or self.user.startswith("0:"):
            violations.append("Container must not run as root")

        if "ALL" not in self.cap_drop:
            violations.append("Must drop ALL capabilities")

        if self.cap_add:
            violations.append("Must not add capabilities")

        if not self.no_new_privileges:
            violations.append("Must enable no-new-privileges")

        if self.volumes:
            violations.append("Must not mount host volumes")

        if self.network_mode == NetworkMode.INTERNAL:
            violations.append("Untrusted code must not use internal network")

        if len(self.dns_servers) == 0:
            violations.append("Must configure DNS servers")

        for dns in self.dns_servers:
            if dns not in ("8.8.8.8", "1.1.1.1", "8.8.4.4"):
                violations.append(f"DNS server {dns} not in allowlist")

        return violations
