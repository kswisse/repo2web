# Repo2Web API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

All endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <token>
```

## Endpoints

### Health Check

```
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "postgres": "connected",
  "redis": "connected"
}
```

### Analyze Repository

```
POST /api/v1/repositories/analyze
```

**Request:**
```json
{
  "url": "https://github.com/user/repo",
  "branch": "main"  // optional
}
```

**Response:**
```json
{
  "repository_id": "uuid",
  "snapshot_id": "uuid",
  "status": "queued"
}
```

**Errors:**
- `422` — Invalid GitHub URL
- `429` — Rate limit exceeded

### Create Deployment

```
POST /api/v1/deployments
```

**Request:**
```json
{
  "repository_id": "uuid",
  "snapshot_id": "uuid"
}
```

**Response:**
```json
{
  "id": "uuid",
  "repository_id": "uuid",
  "snapshot_id": "uuid",
  "state": "queued",
  "created_at": "2026-09-05T00:00:00Z",
  "updated_at": "2026-09-05T00:00:00Z"
}
```

### Get Deployment

```
GET /api/v1/deployments/{deployment_id}
```

**Response:**
```json
{
  "id": "uuid",
  "repository_id": "uuid",
  "snapshot_id": "uuid",
  "state": "running",
  "created_at": "2026-09-05T00:00:00Z",
  "updated_at": "2026-09-05T00:05:00Z",
  "completed_at": null,
  "build_job": { ... },
  "analysis": { ... }
}
```

### Get Deployment Logs

```
GET /api/v1/deployments/{deployment_id}/logs?page=1&page_size=50
```

**Response:**
```json
{
  "logs": [
    {
      "id": "uuid",
      "timestamp": "2026-09-05T00:01:00Z",
      "level": "info",
      "message": "Cloning repository..."
    }
  ],
  "total": 42
}
```

## Deployment States

| State | Description |
|-------|-------------|
| `queued` | Deployment created, waiting for worker |
| `cloning` | Cloning repository |
| `analyzing` | Analyzing repository structure |
| `planning` | Generating execution plan |
| `building` | Building application |
| `starting` | Starting container |
| `health_checking` | Verifying application health |
| `running` | Application is live |
| `*_failed` | Various failure states |
| `cancelled` | User cancelled |

## Error Responses

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "detail": "Invalid GitHub URL"
  }
}
```
