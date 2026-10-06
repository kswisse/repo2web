"""
Docker security configuration — forbidden and required settings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DockerSecurityConfig:
    """Immutable Docker security configuration."""

    # --- Forbidden Configurations (violation = BLOCK) ---
    FORBIDDEN_FLAGS: tuple = (
        "--privileged",
        "--pid=host",
        "--network=host",
        "--ipc=host",
        "--uts=host",
        "--userns=host",
        "--cap-add",
        "--device",
        "--security-opt",
    )

    FORBIDDEN_MOUNTS: tuple = (
        "/var/run/docker.sock",
        "/var/run/docker",
        "/proc",
        "/sys",
        "/dev",
        "/",
    )

    # --- Required Configurations ---
    REQUIRED_SECURITY_OPTS: tuple = (
        "no-new-privileges:true",
    )

    REQUIRED_FLAGS: tuple = (
        "--cap-drop=ALL",
        "--read-only",
    )

    # --- Linux Namespaces ---
    REQUIRED_NAMESPACES: tuple = (
        "pid",
        "net",
        "mnt",
        "uts",
        "user",
        "ipc",
    )

    # --- cgroups Requirements ---
    CGROUPS_VERSION: str = "v2"
    REQUIRED_CGROUP_CONTROLLERS: tuple = (
        "cpu",
        "memory",
        "pids",
        "io",
    )

    # --- Image Requirements ---
    ALLOWED_BASE_IMAGES: tuple = (
        "python:3.11-slim",
        "python:3.12-slim",
        "node:20-alpine",
        "node:22-alpine",
        "ruby:3.2-slim",
        "golang:1.22-alpine",
        "eclipse-temurin:21-jre-alpine",
    )

    # --- User Requirements ---
    REQUIRED_USER: str = "1000:1000"
    FORBIDDEN_USERS: tuple = ("root", "0", "0:0")


def validate_docker_config(container_config: dict) -> list[str]:
    """
    Validate Docker container configuration against security requirements.
    Returns list of violations (empty = valid).
    """
    violations = []
    config = DockerSecurityConfig()

    # Check forbidden flags
    command = container_config.get("command", [])
    if isinstance(command, str):
        command = command.split()

    for flag in config.FORBIDDEN_FLAGS:
        if any(flag in str(arg) for arg in command):
            violations.append(f"Forbidden flag detected: {flag}")

    # Check forbidden mounts
    volumes = container_config.get("volumes", [])
    if isinstance(volumes, dict):
        # Docker SDK format: {"volume_name_or_host_path": {"bind": "/path", "mode": "rw"}}
        # The KEY is the source (host path or volume name).
        # We check the source for forbidden host paths.
        for vol_source, vol_spec in volumes.items():
            source = str(vol_source)
            for forbidden in config.FORBIDDEN_MOUNTS:
                if source == forbidden or source.startswith(forbidden + "/"):
                    violations.append(f"Forbidden mount: {source}")
    elif isinstance(volumes, list):
        # Legacy string format: ["source:target:mode"]
        for volume in volumes:
            if isinstance(volume, str):
                source = volume.split(":")[0]
                for forbidden in config.FORBIDDEN_MOUNTS:
                    if source == forbidden or source.startswith(forbidden + "/"):
                        violations.append(f"Forbidden mount: {source}")

    # Check security options
    security_opt = container_config.get("security_opt", [])
    for required in config.REQUIRED_SECURITY_OPTS:
        if required not in security_opt:
            violations.append(f"Missing required security option: {required}")

    # Check user
    user = container_config.get("user", "root")
    if user in config.FORBIDDEN_USERS:
        violations.append(f"Forbidden user: {user}")

    # Check network mode
    network_mode = container_config.get("network_mode", "bridge")
    if network_mode == "host":
        violations.append("Network mode 'host' is forbidden")

    # Check PID mode
    pid_mode = container_config.get("pid_mode", None)
    if pid_mode == "host":
        violations.append("PID mode 'host' is forbidden")

    # Check IPC mode
    ipc_mode = container_config.get("ipc_mode", None)
    if ipc_mode == "host":
        violations.append("IPC mode 'host' is forbidden")

    # Check privileged mode (critical: Docker API uses "privileged" key)
    privileged = container_config.get("privileged", False)
    if privileged:
        violations.append("Privileged mode is forbidden")

    # Check cap_add is empty
    cap_add = container_config.get("cap_add", [])
    if cap_add:
        violations.append(f"Capability addition is forbidden: {cap_add}")

    # Check that cap_drop includes ALL
    cap_drop = container_config.get("cap_drop", [])
    if "ALL" not in cap_drop:
        violations.append("Must drop ALL capabilities")

    return violations
