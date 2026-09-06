"""
Build sandbox security policy.

Build containers need:
- Dependency installation (pip install, npm install)
- Compilation (gcc, go build, etc.)
- Process execution (build scripts)
- Network access (download packages)

Build containers MUST NOT have:
- Application secrets
- Host filesystem access
- Docker socket access
- Access to other containers
- Persistent state between builds
"""

from app.security.sandbox import SandboxConfig, ContainerType


BUILD_SECURITY_POLICY = {
    "container_type": ContainerType.BUILD,
    "sandbox": SandboxConfig.for_build(),

    # --- Allowed Commands ---
    "allowed_commands": {
        "python": ["python", "pip", "python3", "pip3"],
        "node": ["node", "npm", "npx", "yarn", "pnpm"],
        "ruby": ["ruby", "gem", "bundle"],
        "go": ["go"],
        "rust": ["cargo"],
        "java": ["javac", "java", "mvn", "gradle"],
        "general": ["git", "make", "cmake", "gcc", "g++"],
    },

    # --- Blocked Commands ---
    "blocked_commands": [
        "sudo", "su", "passwd", "chown", "chmod",
        "mount", "umount",
        "iptables", "nftables",
        "docker", "containerd",
        "systemctl", "service",
        "crontab", "at",
        "nc", "ncat", "netcat",
    ],

    # --- Environment Variables ---
    "allowed_env_vars": {
        "PORT": "8080",
        "NODE_ENV": "production",
        "BUILD_ID": "",
        "REPO_URL": "",
        "PYTHONUNBUFFERED": "1",
        "PIP_NO_CACHE_DIR": "1",
        "NPM_CONFIG_CACHE": "/tmp/.npm",
    },

    # --- Blocked Environment Variables ---
    "blocked_env_patterns": [
        "PASSWORD", "SECRET", "TOKEN", "KEY",
        "DATABASE_URL", "REDIS_URL", "DB_URL",
        "AWS_", "AZURE_", "GCP_",
    ],

    # --- Filesystem ---
    "writable_paths": ["/tmp", "/var/tmp", "/home/app"],
    "read_only_paths": ["/proc", "/sys"],

    # --- Build Step Validation ---
    "validate_build_command": True,
    "max_command_length": 1000,
    "forbidden_patterns_in_command": [
        r";", r"\|", r"`", r"\$\(",
        r"&&", r"\|\|",
        r">", r">>", r"<",
        r"rm\s+-rf",
        r"curl\s+.*\|\s*sh",
        r"wget\s+.*\|\s*sh",
    ],
}
