# Development Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 20+
- Git

## Quick Start

### 1. Clone and start services

```bash
git clone <repo-url>
cd repo2web
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- FastAPI on port 8000
- Celery worker

### 2. Run database migrations

```bash
cd apps/api
alembic upgrade head
```

### 3. Start the frontend

```bash
cd apps/web
npm install
npm run dev
```

Frontend runs at http://localhost:3000

### 4. Access API docs

Visit http://localhost:8000/docs for Swagger UI

## Environment Variables

Copy `.env.example` to `.env` in `apps/api/`:

```bash
cp apps/api/.env.example apps/api/.env
```

Key variables:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `SECRET_KEY` — JWT signing key
- `DEBUG` — Enable debug mode

## Running Tests

```bash
cd apps/api
pytest tests/ -v
```

## Project Structure

```
repo2web/
├── apps/
│   ├── web/           # Next.js frontend
│   └── api/           # FastAPI backend
├── docs/              # Documentation
├── docker-compose.yml # Local dev stack
└── README.md
```

## Development Workflow

1. Create a feature branch
2. Make changes
3. Run tests
4. Submit PR

## API Development

The API uses FastAPI with async SQLAlchemy. Key patterns:

- **Endpoints** in `app/api/v1/`
- **Services** in `app/services/`
- **Models** in `app/models/`
- **Schemas** in `app/schemas/`

## Frontend Development

The frontend uses Next.js 14 with App Router:

- **Pages** in `src/app/`
- **Components** in `src/components/`
- **API client** in `src/lib/api.ts`
- **Types** in `src/lib/types.ts`
