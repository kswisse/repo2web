# Deployment State Machine

## States

### Active States

| State | Description | Next States |
|-------|-------------|-------------|
| `queued` | Deployment created, waiting for worker | `cloning`, `cancelled` |
| `cloning` | Git clone in progress | `analyzing`, `clone_failed` |
| `analyzing` | Repository structure analysis | `planning`, `analysis_failed` |
| `planning` | Execution plan generation | `building`, `plan_failed` |
| `building` | Container build in progress | `starting`, `build_failed`, `security_blocked` |
| `starting` | Container startup | `health_checking`, `start_failed` |
| `health_checking` | Verifying application health | `running`, `health_check_failed`, `timeout` |

### Terminal States

| State | Description |
|-------|-------------|
| `running` | Application is live and healthy |
| `clone_failed` | Git clone failed |
| `analysis_failed` | Repository analysis failed |
| `plan_failed` | Execution plan generation failed |
| `build_failed` | Container build failed |
| `start_failed` | Container failed to start |
| `health_check_failed` | Health check failed |
| `security_blocked` | Security policy violation |
| `timeout` | Operation timed out |
| `cancelled` | User cancelled |

## Transition Rules

```
queued → cloning           (worker picks up task)
queued → cancelled         (user cancels)
cloning → analyzing        (clone succeeds)
cloning → clone_failed     (clone fails)
analyzing → planning       (analysis succeeds)
analyzing → analysis_failed (analysis fails)
planning → building        (plan generated)
planning → plan_failed     (plan fails)
building → starting        (build succeeds)
building → build_failed    (build step fails)
building → security_blocked (untrusted code detected)
starting → health_checking (container starts)
starting → start_failed    (container fails)
health_checking → running  (health check passes)
health_checking → health_check_failed (health check fails)
health_checking → timeout  (exceeds deadline)
any non-terminal → cancelled (user cancels)
```

## Invalid Transitions

Any transition not listed above is invalid and will be rejected with a `422` error.

Examples of invalid transitions:
- `queued` → `building` (skips intermediate states)
- `running` → `building` (cannot go backwards)
- `build_failed` → `running` (terminal state)
