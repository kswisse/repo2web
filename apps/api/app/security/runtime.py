"""
Runtime sandbox security policy.

Runtime containers need:
- Application process execution
- Listening port for serving
- Outbound HTTP (for APIs, external services)
- Minimal filesystem (read-only root)

Runtime containers MUST NOT have:
- Package installation capability
- Compilers or build tools
- Shell access (if possible)
- Persistent state (read-only rootfs)
- Access to build artifacts beyond /app
"""

from app.security.sandbox import SandboxConfig, ContainerType


RUNTIME_SECURITY_POLICY = {
    "container_type": ContainerType.RUNTIME,
    "sandbox": SandboxConfig.for_runtime(),

    # --- Allowed Process ---
    "allowed_process_names": [
        "python", "python3", "node", "java", "ruby", "go",
        "uvicorn", "gunicorn", "streamlit", "flask",
        "npm", "yarn", "pm2",
    ],

    # --- Blocked Capabilities ---
    "blocked_capabilities": [
        "SYS_ADMIN", "SYS_PTRACE", "SYS_MODULE",
        "NET_ADMIN", "NET_RAW", "SYS_RAWIO",
    ],

    # --- Environment Variables ---
    "allowed_env_vars": {
        "PORT": "8080",
        "RUNTIME_ID": "",
        "NODE_ENV": "production",
    },

    # --- Filesystem ---
    "writable_paths": ["/tmp", "/var/cache"],
    "read_only_paths": ["/app", "/usr", "/etc", "/var"],
    "tmpfs_mounts": {
        "/tmp": "size=128m,noexec,nosuid",
        "/var/cache": "size=128m",
    },

    # --- Network ---
    "listen_port": None,
    "allowed_outbound_ports": [80, 443],
    "max_connections": 100,
    "connection_timeout": 30,

    # --- Health Check ---
    "health_check_path": "/health",
    "health_check_interval": 30,
    "health_check_timeout": 5,
    "health_check_retries": 3,

    # --- Process Limits ---
    "max_threads": 50,
    "max_open_files": 1024,
}
