# Repo2Web

Convert GitHub repositories into runnable web applications.

## Architecture

```
GitHub URL
→ immutable commit SHA
→ static repository analysis
→ ExecutionPlan
→ controlled Docker build
→ controlled Docker runtime
→ health check
→ async Celery deployment
→ PostgreSQL persistence
→ frontend deployment dashboard
```

## Stack

- **Backend**: FastAPI, PostgreSQL, Redis, Celery, Docker
- **Frontend**: Next.js, TypeScript, Tailwind CSS
- **Infrastructure**: Docker Compose

## Principles

- Every repository is untrusted code
- Arbitrary repository code executes only inside controlled Docker environments
- Immutable commit SHA deployments (never mutable branch refs)
- Modular monolith with dependency inversion
- Docker-first runtime with security sandboxing

## Getting Started

### Prerequisites

- Docker Desktop
- Python 3.12+
- Node.js 18+

### Development

```bash
# Backend
cd apps/api
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd apps/web
npm install
npm run dev
```

### Docker Compose

```bash
docker-compose up
```

## Security

- No Docker socket exposed to deployed containers
- All capabilities dropped
- Non-root runtime execution
- Resource limits enforced (memory, CPU)
- No privileged containers
- No host networking or PID namespace

## API

```
POST   /api/v1/deployments          # Create deployment
GET    /api/v1/deployments/{id}     # Get deployment status
GET    /api/v1/deployments/{id}/logs # Get deployment logs
DELETE /api/v1/deployments/{id}     # Cancel deployment
```

## Project Structure

```
repo2web/
├── apps/
│   ├── api/           # FastAPI backend
│   │   ├── app/
│   │   │   ├── analyzer/      # Repository analysis
│   │   │   ├── api/           # API endpoints
│   │   │   ├── core/          # Config, database, security
│   │   │   ├── infrastructure/# Concrete implementations
│   │   │   ├── models/        # SQLAlchemy models
│   │   │   ├── orchestrator/  # Deployment orchestration
│   │   │   ├── repository/    # Git operations
│   │   │   ├── runtime/       # Container execution
│   │   │   ├── schemas/       # Pydantic schemas
│   │   │   ├── security/      # Security controls
│   │   │   ├── services/      # Business logic
│   │   │   └── tasks/         # Celery tasks
│   │   ├── alembic/           # Database migrations
│   │   └── tests/             # Test suite
│   └── web/           # Next.js frontend
│       └── src/
│           ├── app/           # Pages
│           ├── components/    # UI components
│           ├── hooks/         # React hooks
│           └── lib/           # API client, types
├── infrastructure/    # Infrastructure configs
└── packages/          # Shared packages
```

## License

MIT
