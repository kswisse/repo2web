# ADR-002: Docker-First Runtime with Abstraction Layer

## Status

Accepted

## Context

Repo2Web executes untrusted GitHub repository code. We need an execution environment that provides isolation while being replaceable as the product matures.

## Decision

Use Docker containers for Phase 0 execution, abstracted behind a `RuntimeManager` interface that can be swapped for Firecracker, gVisor, or Kata Containers in future phases.

## Consequences

**Positive:**
- Docker is widely available and easy to develop with
- Container isolation provides basic security boundaries
- Docker Compose simplifies local development
- Abstraction layer allows future replacement without changing service boundaries

**Negative:**
- Docker does not provide production-grade sandboxing
- Kernel-level exploits can escape Docker containers
- Resource limits are not as strict as Firecracker/gVisor
- Requires honest documentation of security limitations

## Security Limitations

Docker Phase 0 does NOT protect against:
- Kernel exploits (CVE-class vulnerabilities)
- Side-channel attacks (Spectre, Meltdown)
- Container escape via misconfigured capabilities
- Resource exhaustion at kernel level

These limitations are accepted for Phase 0 with the understanding that production requires gVisor or Kata Containers.

## Future Migration

When ready for production:
1. Implement `RuntimeManager` interface for Firecracker/gVisor
2. Update container configuration
3. No changes needed to service layer or API
