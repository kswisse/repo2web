# Repo2Web Security Architecture

## Overview

Repo2Web executes untrusted GitHub repository code in isolated Docker containers. This document describes the security controls implemented in Phase 1B to prevent abuse, data exfiltration, and container escape.

## Threat Model

### Malicious Repository
- Fork bombs, infinite process creation → PID limits (100), cgroup isolation
- CPU/memory exhaustion → CPU quota (2 cores max), memory limits (1GB)
- Disk exhaustion → tmpfs size limits, storage_opt=1GB
- Filesystem traversal → Non-root user (1000:1000), read-only rootfs
- Reverse shells → Outbound port restrictions (80, 443 only)
- Crypto mining → CPU limits, network restrictions, timeout (300s build, 24h runtime)

### Secret Theft
- Build env: `PORT`, `BUILD_ID`, `REPO_URL`, `NODE_ENV`, `PYTHONUNBUFFERED`
- Runtime env: `PORT`, `RUNTIME_ID`
- BLOCKED: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `SECRET_KEY`, `GITHUB_TOKEN`, any `*_PASSWORD`, `*_SECRET`, `*_TOKEN`, `*_KEY`

### SSRF
- Localhost, private IPs, cloud metadata → Blocked in URL validation and outbound rules
- Docker daemon → No Docker socket mount
- Internal services → Separate Docker network, no route from build/runtime networks

## Security Controls

### 1. Sandbox Configuration (`app/security/sandbox.py`)

Immutable `SandboxConfig` dataclass with secure defaults:

| Setting | Build | Runtime |
|---------|-------|---------|
| CPU | 2.0 cores | 1.0 core |
| Memory | 1GB | 512MB |
| PIDs | 100 | 50 |
| Disk | 1GB | 512MB |
| Root FS | Writable | Read-only |
| Network | repo2web-isolated | repo2web-runtimes |
| User | 1000:1000 | 1000:1000 |

**Validation rules:**
- Must not run as root
- Must drop ALL capabilities
- Must not add capabilities
- Must enable no-new-privileges
- Must not mount host volumes
- DNS servers must be public (8.8.8.8, 1.1.1.1)

### 2. Network Policy (`app/security/network.py`)

Deny-by-default network policies:

- **Build**: HTTP/HTTPS outbound only (80, 443), DNS (53/UDP)
- **Runtime**: HTTP/HTTPS outbound only (80, 443), DNS (53/UDP)
- **Blocked CIDRs**: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, 127.0.0.0/8, fc00::/7, ::1/128
- **Blocked ports**: 22 (SSH), 23 (Telnet), 25 (SMTP), 4444 (Metasploit), 5555 (reverse shell)

### 3. SSRF Protection (`app/security/ssrf.py`)

URL validation with DNS resolution check:

1. Parse URL and validate scheme (HTTPS only)
2. Check hostname against blocked hosts (localhost, 127.0.0.1, 169.254.169.254)
3. Resolve hostname to IP addresses
4. Check resolved IPs against blocked ranges
5. Verify final URL still safe (max 3 redirects)

### 4. Repository Policy (`app/security/repository.py`)

Repository ingestion policy:

- **URL**: HTTPS GitHub URLs only
- **Size**: 50MB max repository, 10MB max file, 10,000 max files
- **Git**: Shallow clone (--depth 1), hooks disabled, .gitmodules deleted
- **Files**: Block .exe, .dll, .so, .dylib, .bin, .dat

### 5. Secret Isolation (`app/security/secrets.py`)

Environment variable validation:

- **Forbidden patterns**: PASSWORD, SECRET, TOKEN, KEY, CREDENTIAL, DATABASE_URL, REDIS_URL, GITHUB_TOKEN, JWT_SECRET, SECRET_KEY
- **Build allowed**: PORT, BUILD_ID, REPO_URL, NODE_ENV, PYTHONUNBUFFERED
- **Runtime allowed**: PORT, RUNTIME_ID, NODE_ENV
- **Log redaction**: Sensitive fields redacted from audit logs

### 6. Docker Security (`app/security/docker_security.py`)

Docker configuration validation:

**Forbidden:**
- `--privileged`, `--pid=host`, `--network=host`, `--ipc=host`, `--uts=host`, `--userns=host`
- `--cap-add`, `--device`, `--security-opt`
- Mounts: `/var/run/docker.sock`, `/proc`, `/sys`, `/dev`, `/`

**Required:**
- `no-new-privileges:true`
- `--cap-drop=ALL`
- User: `1000:1000` (non-root)

### 7. Security Audit Logging (`app/security/audit.py`)

Structured security event logging:

- **Event types**: repo.accepted, repo.rejected, sandbox.created, build.started, security.ssrf_attempt, security.secret_detected, etc.
- **Severity levels**: info, warning, error, critical
- **Data**: deployment_id, container_id, user_id, client_ip, user_agent, details
- **Redaction**: Sensitive fields automatically redacted

## Docker Compose Changes

### Before (Phase 0)
```yaml
api:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock  # CRITICAL SECURITY ISSUE
```

### After (Phase 1B)
```yaml
api:
  # Docker socket mount removed for security
  networks:
    - repo2web-internal

worker:
  # Docker socket mount removed for security
  networks:
    - repo2web-internal

networks:
  repo2web-internal:
    driver: bridge
  repo2web-isolated:
    driver: bridge
  repo2web-runtimes:
    driver: bridge
```

## Integration Points

### RuntimeService.start_container()
- Accepts `SandboxConfig` parameter
- Validates config before container creation
- Validates environment variables for secrets
- Logs security events (sandbox_created, sandbox_rejected, secret_detected)
- Never creates container without validation

### BuildService.clone_repository()
- Validates URL format against repository policy
- Validates SSRF protection (DNS resolution check)
- Logs security events (repo_clone_started, repo_clone_completed, ssrf_attempt)
- Deletes .gitmodules after clone

## Security Tests

137 tests covering:
- SandboxConfig validation (17 tests)
- NetworkPolicy configuration (13 tests)
- SSRF protection (15 tests)
- RepositoryPolicy (15 tests)
- Secret isolation (14 tests)
- Docker security (16 tests)
- Audit logging (11 tests)
- Input validation (14 tests)

## Remaining Risks

| Risk | Severity | Mitigation | Acceptance |
|------|----------|------------|------------|
| Container escape via kernel exploit | CRITICAL | Docker hardening, planned gVisor migration | Accepted for Phase 1A |
| Supply chain attack via popular package | HIGH | Lock files, future dependency scanning | Accepted for Phase 1A |
| DNS exfiltration | MEDIUM | Public DNS only, log monitoring | Accepted for Phase 1A |
| Sophisticated side-channel attacks | LOW | Not mitigated in Phase 1A | Accepted for Phase 1A |

## Next Steps (Phase 2)

1. Migrate to gVisor/Kata Containers for hardware-level sandboxing
2. Add dependency scanning (npm audit, pip-audit)
3. Add container image signing verification
4. Add network traffic monitoring
5. Add rate limiting middleware
6. Add build log secret scanning
