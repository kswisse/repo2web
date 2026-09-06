# ADR-001: Monorepo Architecture

## Status

Accepted

## Context

Repo2Web consists of a Next.js frontend and a FastAPI backend that share type definitions and API contracts. We need a project structure that supports:

- Shared types between frontend and backend
- Atomic commits across service boundaries
- Single CI/CD pipeline
- Easy refactoring when boundaries shift during Phase 0

## Decision

Use a monorepo structure with `apps/web` and `apps/api` as separate applications, with shared packages in `packages/shared`.

## Consequences

**Positive:**
- Shared API types ensure frontend/backend contract compliance
- Single repository for all code simplifies development
- Atomic commits prevent broken builds
- Easier to refactor service boundaries

**Negative:**
- Requires discipline to avoid tight coupling between apps
- Larger repository size
- May need tooling (Turborepo) for task orchestration at scale

## Alternatives Considered

- **Polyrepo:** Separate repositories for frontend/backend. Rejected because it makes shared types difficult and complicates cross-service changes.
- **Multi-package with shared library:** Similar to monorepo but with explicit package boundaries. Considered but monorepo is simpler for Phase 0.
