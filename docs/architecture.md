# Repo2Web Architecture

## Overview

Repo2Web converts public GitHub repositories into runnable web applications. The system clones repositories, analyzes their structure, generates execution plans, builds them in isolated containers, and exposes temporary public URLs.

## Repository Structure

```
repo2web/
├── apps/
│   ├── web/                    # Next.js 14 frontend
│   └── api/                    # FastAPI backend
├── infrastructure/
│   └── docker/                 # Dockerfiles
├── docs/
│   ├── architecture.md         # This document
│   ├── security.md             # Security design
│   ├── api.md                  # API reference
│   └── adr/                    # Architecture Decision Records
├── packages/
│   └── shared/                 # Shared types (future)
└── docker-compose.yml          # Local development
```

## Service Boundaries

| Service | Responsibility | Communication |
|---------|---------------|---------------|
| API Layer | HTTP endpoints, auth, validation | Synchronous REST |
| Repository Analyzer | Detect language, framework, dependencies | Direct function call |
| Execution Plan Generator | Convert analysis to build steps | Direct function call |
| Build Orchestrator | Execute builds in containers | Celery task queue |
| Runtime Manager | Container lifecycle management | Celery task queue |
| Health Checker | Verify running instances | HTTP health checks |
| Deployment Manager | State machine orchestration | Coordinates all services |

## Data Models

```
User → Repository → RepositorySnapshot → AnalysisResult → ExecutionPlan
                                                              ↓
Deployment ← RuntimeInstance ← BuildJob ← BuildJob
```

Key invariant: `RepositorySnapshot.commit_sha` is immutable. Deployments always reference snapshots, never mutable branches.

## Deployment State Machine

```
QUEUED → CLONING → ANALYZING → PLANNING → BUILDING → STARTING → HEALTH_CHECKING → RUNNING
   ↓         ↓          ↓          ↓          ↓           ↓              ↓
CANCELLED CLONE_FAILED ANALYSIS  PLAN_FAILED BUILD_FAILED START_FAILED  HEALTH_CHECK_FAILED
                     _FAILED                                              TIMEOUT
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | Python 3.11+, FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 |
| Queue | Redis 7 + Celery 5 |
| Containers | Docker |
| Testing | pytest, httpx |

## API Endpoints

- `POST /api/v1/repositories/analyze` — Analyze a GitHub repository
- `POST /api/v1/deployments` — Create a deployment
- `GET /api/v1/deployments/{id}` — Get deployment details
- `GET /api/v1/deployments/{id}/logs` — Get build logs
- `GET /api/v1/health` — Health check

## Security Model

All repository code is treated as untrusted. Execution happens in isolated Docker containers with:
- CPU limits (1 core)
- Memory limits (512MB)
- Process limits (100 PIDs)
- Network isolation
- Filesystem isolation
- No host access

See `docs/security.md` for complete threat model and security controls.

## ADRs

- ADR-001: Monorepo Architecture
- ADR-002: Docker-First Runtime with Abstraction Layer
- ADR-003: Immutable Commit-Based Deployments
- ADR-004: Deterministic Analyzer Before LLM
