# Repo2Web

## Mục tiêu

Chuyển GitHub repository thành web app chạy được: clone → analyze → build trong Docker container → health check → expose URL.

## Trạng thái hiện tại

- **Phase 2.9 hoàn thành** (AI/Deterministic Repair)
- **Security: DONE** — 220 tests, sandbox, SSRF, secrets, network policy, audit logging
- **Analyzer: DONE** — 13 modules, 94.1% analysis success trên 17 repo thật
- **Frontend: DONE** — Next.js, deployment form + progress tracker + log viewer
- **Backend API: DONE** — FastAPI, 5+ endpoints, Celery async, PostgreSQL
- **Docker build pipeline: BROKEN** — 0/17 repos build thành công

## Blocker hiện tại

1. **Docker daemon chưa chạy** — cần mở Docker Desktop trước
2. **Build command allowlist quá chặt** — `pnpm build`, `yarn build` bị block trong `executor.py`
3. **Missing `node:20-alpine` image** — `_select_base_image()` trả về nhưng chưa auto-pull
4. **Framework detection accuracy: 30.8%** — 3 failure classes (framework-as-repo, monorepo misidentification, false positive)
5. **20+ diagnostic files uncommitted** — các file `diagnose_*.py`, `test_debug_*.py` cần cleanup
6. **Container execution failures** — 6 Python repos fail "Container not found"

## Kiến trúc

```
GitHub URL → Clone → Analyze → ExecutionPlan → Docker Build → Docker Runtime → Health Check → Live URL
```

- Backend: FastAPI + PostgreSQL 16 + Redis 7 + Celery 5 + Docker SDK
- Frontend: Next.js 14 + TypeScript + Tailwind CSS
- Security: All repo code là untrusted, chạy trong sandboxed container

## Backend modules (`apps/api/app/`)

| Module | Vai trò |
|--------|---------|
| `core/` | Config, database, JWT security, exceptions |
| `api/v1/` | Endpoints: health, repositories, deployments |
| `analyzer/` | 13 modules: file_inventory, manifest_parser, framework_detector, entrypoint_detector, port_detector, env_detector, dependency_detector, compatibility, plan_builder, plan_validator |
| `runtime/` | Docker container lifecycle, build executor, health checker, cleanup |
| `orchestrator/` | 8-stage pipeline, state machine (20 states), repair loop integration |
| `security/` | Sandbox, network policy, SSRF, secrets, repository policy, docker security, audit |
| `repair/` | Deterministic repair provider, bounded retry loop, proposal validator |
| `repository/` | Git clone, immutable commit snapshot |
| `models/` | 10 SQLAlchemy models (user, repo, snapshot, deployment, build, etc.) |
| `services/` | Business logic layer (repository, deployment, build, runtime, etc.) |
| `tasks/` | Celery async tasks (deploy, build, analyze, runtime) |

## Frontend (`apps/web/src/`)

| Component | Vai trò |
|-----------|---------|
| `app/page.tsx` | Landing page, deployment form |
| `app/deployments/[id]/page.tsx` | Deployment detail: progress, logs, result |
| `components/` | 12 components: Header, DeploymentForm, DeploymentProgress, DeploymentLogs, etc. |
| `hooks/` | useDeployment, useDeploymentLogs (polling 2s) |
| `lib/api/` | API client + TypeScript interfaces |

## Tests

- Backend: 544 tests
- Security: 220 tests
- Frontend: Jest tests cho hooks + components

## Commands

```bash
# Backend
cd apps/api
pytest tests/ -v                     # Run backend tests
ruff check app/                      # Lint
uvicorn app.main:app --reload        # Dev server

# Frontend
cd apps/web
npm test                             # Run frontend tests
npm run dev                          # Dev server

# Infrastructure
docker-compose up                    # Start all services
docker ps                            # Verify Docker running
```

## Security principles

- Mọi repository là untrusted code
- Code chỉ chạy trong Docker container sandboxed
- Immutable commit SHA deployments (không dùng mutable branch refs)
- No Docker socket exposed, no privileged containers
- All capabilities dropped, non-root execution (1000:1000)
- Resource limits: CPU 1 core, memory 512MB, 100 PIDs
- Network isolation, filesystem isolation, no host access
