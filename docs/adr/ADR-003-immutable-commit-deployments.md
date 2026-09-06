# ADR-003: Immutable Commit-Based Deployments

## Status

Accepted

## Context

GitHub repositories have mutable branch references (`main`, `master`). Deploying from a branch means the same deployment can produce different results over time as new commits are pushed. This breaks reproducibility.

## Decision

All deployments reference a specific immutable commit SHA, never a mutable branch. The system records the commit SHA at clone time and uses it for all subsequent operations.

## Consequences

**Positive:**
- Deployments are reproducible — same SHA always produces same result
- Audit trail is clear — every deployment maps to exact code version
- Rollbacks are straightforward — point to previous SHA
- No surprise changes from upstream commits

**Negative:**
- Users must explicitly trigger new deployments for new commits
- No automatic deployment on push (can be added in Phase 1)
- Slightly more complex flow — must resolve branch to SHA first

## Implementation

```python
class RepositorySnapshot:
    commit_sha: str  # IMMUTABLE — recorded at clone time
    branch: str      # For reference only, not used for deployment
```

## Future Enhancement

Phase 1 can add webhook-based auto-deployment by:
1. Receiving GitHub webhook on push
2. Resolving new SHA from branch
3. Creating new snapshot with new SHA
4. Triggering deployment pipeline
