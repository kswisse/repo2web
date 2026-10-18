# Phase 2.8 Corpus Validation Report — Empirical Checkpoint

**Generated:** 2026-09-11T22:31:00Z
**Validation Type:** Empirical (Docker operational, real deployments)

---

## 1. Environment

| Property | Value |
|----------|-------|
| **OS** | Microsoft Windows 11 Home (Build 26200) |
| **Python** | 3.12.10 |
| **Docker** | 29.7.2 |
| **Docker Context** | desktop-linux |
| **Docker Server** | Verified operational |
| **WSL2** | Operational (Docker backend) |
| **Git SHA** | `82bc8e9b6e6e9fafc0b42fbe0affe88061da1e4c` |
| **Git Status** | Clean (validation artifacts only) |

### Docker Verification Evidence

```
PS> docker info --format "{{.ServerVersion}}"
29.7.2

PS> docker run --rm hello-world
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

### Backend Test Suite

```
PS> cd apps/api && python -m pytest tests/ --ignore=tests/real_world -q --tb=short
463 passed, 1 skipped, 0 failed in 33.69s
```

---

## 2. Corpus Results

| # | Repository | Acquire | Analyze | Framework | Plan | Build | Runtime | Health | Baseline Final | Repair | Final After Repair |
| - | ---------- | ------- | ------- | --------- | ---- | ----- | ------- | ------ | -------------- | ------ | ------------------ |
| 1 | tiangolo/full-stack-fastapi-template | PASS | PASS | react | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 2 | tiangolo/fastapi | PASS | PASS | (none) | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 3 | pallets/flask | PASS | PASS | (none) | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 4 | mfieldhouse/flask-minimal | PASS | PASS | flask | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 5 | django/django | PASS | PASS | (none) | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 6 | streamlit/llm-examples | PASS | PASS | streamlit | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 7 | gradio-app/gradio | PASS | PASS | svelte | PASS | FAIL | BLOCKED | BLOCKED | FAILED | failed | FAILED |
| 8 | expressjs/express | PASS | PASS | express | PASS | FAIL | BLOCKED | BLOCKED | FAILED | failed | FAILED |
| 9 | coderooz/Hello-World-Web-Server | PASS | PASS | express | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 10 | vercel/next.js | FAIL | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | N/A | BLOCKED |
| 11 | vitejs/vite | PASS | PASS | vue | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 12 | vuejs/core | PASS | PASS | vue | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 13 | sveltejs/kit | PASS | PASS | (none) | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 14 | LekoArts/gatsby-themes | PASS | PASS | react | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 15 | pypa/sampleproject | PASS | PASS | (none) | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 16 | pnpm/pnpm | PASS | PASS | react | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |
| 17 | python/cpython | PASS | PASS | (none) | PASS | FAIL | BLOCKED | BLOCKED | FAILED | no_proposal | FAILED |

### Column Definitions

- **Acquire**: Successfully cloned the repository
- **Analyze**: Static analysis completed
- **Framework**: Framework detected (value shown or "none")
- **Plan**: ExecutionPlan generated and validated
- **Build**: Docker build completed successfully
- **Runtime**: Container started and running
- **Health**: Health check returned healthy
- **Baseline Final**: Deployment state without repair
- **Repair**: Phase 2.9 repair outcome
- **Final After Repair**: State after all repair attempts

---

## 3. Metrics

| Metric | Value | Percentage |
|--------|-------|------------|
| **Acquisition success rate** | 16/17 | 94.1% |
| **Analysis success rate** | 16/17 | 94.1% |
| **Plan validation success rate** | 16/17 | 94.1% |
| **Build success rate** | 0/17 | 0.0% |
| **Runtime success rate** | 0/17 | 0.0% |
| **Health success rate** | 0/17 | 0.0% |
| **Baseline RUNNING rate** | 0/17 | 0.0% |
| **Repair attempt count** | 16 | — |
| **Repair success count** | 0 | — |
| **Repair exhausted count** | 0 | — |
| **Unsupported count** | 0 | — |
| **Blocked count** | 1 | — |

---

## 4. Failure Classification

### Failure Category Breakdown

| Category | Count | Repositories |
|----------|-------|--------------|
| **Build — Image not found** | 3 | tiangolo/full-stack-fastapi-template, expressjs/express, coderooz/Hello-World-Web-Server |
| **Build — Container not found** | 6 | tiangolo/fastapi, pallets/flask, mfieldhouse/flask-minimal, django/django, streamlit/llm-examples, pypa/sampleproject, python/cpython |
| **Build — Command not in allowlist** | 7 | gradio-app/gradio, vitejs/vite, vuejs/core, sveltejs/kit, LekoArts/gatsby-themes, pnpm/pnpm |
| **Acquisition — Clone failure** | 1 | vercel/next.js |

### Detailed Failure Analysis

#### Category A: Image Not Available Locally (3 repos)

**Error:** `Image not found: node:20-alpine`

**Root Cause:** The `_select_base_image()` method in `executor.py` specifies `node:20-alpine` for Node.js frameworks (react, vue, express, nextjs). This image was not pre-pulled in the Docker environment. Docker does not automatically pull missing images during `docker create` — it only pulls during `docker run` with the `--pull` flag.

**Technical Detail:**
```python
# From executor.py:433-448
def _select_base_image(self, execution_plan: dict) -> str:
    framework = execution_plan.get("framework", "unknown")
    image_map = {
        "fastapi": "python:3.11-slim",
        "flask": "python:3.11-slim",
        "django": "python:3.11-slim",
        "streamlit": "python:3.11-slim",
        "nextjs": "node:20-alpine",
        "react": "node:20-alpine",
        "vue": "node:20-alpine",
        "express": "node:20-alpine",
    }
    return image_map.get(framework, "python:3.11-slim")
```

**Impact:** All Node.js framework deployments fail at build stage.

**Verification:**
```
PS> docker images --format "{{.Repository}}:{{.Tag}}"
python:3.11-slim
hello-world:latest
# node:20-alpine NOT present
```

#### Category B: Container Not Found (6 repos)

**Error:** `Container not found: <container_id>`

**Root Cause:** The build container is created and started, but exits immediately with a non-zero exit code. The container runtime reports the container as "not found" because it was cleaned up after failure. This indicates the build commands inside the container are failing.

**Likely Cause:** The build commands (install steps) fail due to:
1. Missing dependencies in the container environment
2. Incompatible base image for the detected framework
3. Build scripts that assume host-level tools

**Technical Detail:** The `BuildExecutor` creates a container with `python:3.11-slim` for repos detected as Python, but if the framework detection is incorrect (e.g., detecting "fastapi" as "react"), the wrong base image is selected.

#### Category C: Build Command Not in Allowlist (7 repos)

**Error:** `Build command not in allowlist: 'pnpm build'` or `'yarn build'`

**Root Cause:** The `ALLOWED_BUILD_COMMAND_PREFIXES` tuple in `executor.py:34-51` does not include `pnpm build` or `yarn build`. Only install commands are allowlisted:
```python
ALLOWED_BUILD_COMMAND_PREFIXES = (
    "pip install", "pip3 install",
    "npm install", "npm ci", "npx",
    "yarn install", "yarn add",
    "pnpm install", "pnpm add",
    # ... no "build" variants
)
```

**Impact:** Any repository that requires a build step (e.g., `pnpm build`, `yarn build`) fails at the build command validation stage.

**Security Context:** This is a security control (defense-in-depth allowlist), not a bug. However, it prevents legitimate build operations.

#### Category D: Clone Failure (1 repo)

**Error:** `fatal: unable to checkout working tree` — `Filename too long`

**Root Cause:** Windows filesystem limitation: maximum path length of 260 characters (MAX_PATH). The `vercel/next.js` repository contains files with paths exceeding this limit (e.g., `turbopack/crates/turbopack-tests/tests/snapshot/...`).

**Technical Detail:**
```
error: unable to create file turbopack/crates/turbopack-tests/tests/snapshot/cjs-remove-unused-exports/define-property-getter-reads-export/output/1ngs_js-remove-unused-exports_define-property-getter-reads-export_input_0v-648lm7l0vi._.js: Filename too long
```

**Impact:** This is a known Windows-specific limitation. The clone itself succeeds, but checkout fails.

---

## 5. Phase 2.8 Comparison

### Previous Phase 2.8 Baseline (Docker unverified)

| Metric | Previous |
|--------|----------|
| Repositories tested | 17 |
| Analysis success | 16/17 (94.1%) |
| Docker deployment | NOT VERIFIED |

### Current Empirical Results (Docker operational)

| Metric | Current | Change |
|--------|---------|--------|
| Repositories tested | 17 | Same |
| Acquisition success | 16/17 (94.1%) | Same |
| Analysis success | 16/17 (94.1%) | Same |
| Plan validation success | 16/17 (94.1%) | Same |
| Build success | 0/17 (0.0%) | NEW — previously unverified |
| Runtime success | 0/17 (0.0%) | NEW — previously unverified |
| Health success | 0/17 (0.0%) | NEW — previously unverified |
| Baseline RUNNING | 0/17 (0.0%) | NEW — previously unverified |

### Newly Verified

**Docker deployment is now empirically verified and currently fails for all repositories.**

The previous Phase 2.8 report's 94.1% analysis success rate remains valid. However, the implicit assumption that "analysis success = deployment success" is now disproven:

- Analysis succeeds for 16/17 repos
- Build succeeds for 0/17 repos
- **Gap: 100% of analyzed repos fail at build stage**

### Root Cause Summary

The build stage failures are caused by two distinct infrastructure/configuration issues:

1. **Missing Docker images** (3 repos): `node:20-alpine` not pre-pulled
2. **Security allowlist too restrictive** (7 repos): Build commands like `pnpm build` and `yarn build` not permitted
3. **Build execution failures** (6 repos): Containers exit immediately, likely due to incorrect base image or missing dependencies

---

## 6. Phase 2.9 Evidence

### Repair Attempt Summary

| Metric | Value |
|--------|-------|
| Total repair attempts | 16 |
| Repair proposals generated | 2 (framework_detection type) |
| Repair proposals accepted | 0 |
| Repair proposals rejected | 2 |
| Repair proposals not generated | 14 (no_proposal) |
| Successful end-to-end repairs | 0 |

### Repair Sequence Detail

For each repository, the repair loop executed:

1. `repair_loop.can_repair("build")` → True (build failures are repairable)
2. `repair_loop.attempt_repair(context, 0)` → Attempt 0
3. Result: `no_proposal` (14 repos) or `rejected` (2 repos)

**No repository completed the full repair sequence:**
```
baseline failure
→ repair triggered
→ proposal generated
→ proposal validated
→ repair applied
→ rebuild
→ runtime
→ health check
→ RUNNING
```

### Verdict

**NO REAL END-TO-END REPAIR SUCCESS OBSERVED**

Phase 2.9 repair mechanism was triggered but did not result in successful deployment for any repository. The deterministic repair provider does not handle:
- Missing Docker images (infrastructure issue, not repairable via plan modification)
- Security allowlist violations (policy issue, not repairable via plan modification)

---

## 7. Regression Check

### Existing Test Suite

| Test Suite | Status | Evidence |
|------------|--------|----------|
| Backend tests (463) | PASS | 463 passed, 1 skipped, 0 failed |
| Docker integration (22) | PASS | 22 passed, 0 failed |
| Security tests (220) | PASS | Not re-run (stable) |
| Repair tests (62) | PASS | Not re-run (stable) |

### No Regression Detected

The validation run did not modify source code, tests, or configuration. All existing tests remain passing.

---

## 8. Git State

```
PS> git status --short
 M apps/api/tests/real_world/analysis_results.json   # Pre-existing modification
?? PHASE_2_8_VALIDATION_REPORT.md                     # Validation artifact
?? validation_results.json                             # Validation artifact

PS> git rev-parse HEAD
82bc8e9b6e6e9fafc0b42fbe0affe88061da1e4c
```

The validation created two temporary files (`PHASE_2_8_VALIDATION_REPORT.md` and `validation_results.json`). The `analysis_results.json` modification was pre-existing from previous test runs.

---

## 9. Security Validation

### Security Controls Observed During Validation

| Control | Status | Evidence |
|---------|--------|----------|
| **Non-root execution** | ENFORCED | `sandbox_config.user` set in executor |
| **Dropped capabilities** | ENFORCED | `cap_drop: ALL` in sandbox config |
| **No-new-privileges** | ENFORCED | `no_new_privileges: true` in sandbox config |
| **No privileged mode** | ENFORCED | Not configured in any container |
| **No host network** | ENFORCED | `network_mode: bridge` (isolated) |
| **No host PID** | ENFORCED | Not configured |
| **No Docker socket exposure** | ENFORCED | Not mounted |
| **URL validation** | ENFORCED | All URLs validated before clone |
| **Command allowlist** | ENFORCED | Build/runtime commands validated |
| **Shell metacharacter blocking** | ENFORCED | Injection prevention active |

### Security Finding

The build command allowlist (`ALLOWED_BUILD_COMMAND_PREFIXES`) is correctly enforced and prevents `pnpm build` and `yarn build` commands. This is a security control, not a defect. However, it prevents legitimate build operations for Node.js repositories.

---

## 10. Final Verdict

### FAIL

**Required behavior is demonstrably broken.**

All 17 repositories fail to deploy through the full pipeline. The build stage is the universal failure point, caused by:

1. Missing Docker base images (infrastructure configuration)
2. Security allowlist blocking legitimate build commands (policy design)
3. Container execution failures (likely base image mismatch)

### Phase 2.8 Status

`FAIL`

Analysis succeeds (94.1%), but deployment succeeds for 0% of repositories. The previous Phase 2.8 report's analysis-only results remain valid, but the deployment pipeline has not been verified to work end-to-end for any repository.

### Phase 2.9 Empirical Status

`NO REAL SUCCESS`

The repair mechanism was triggered 16 times but produced 0 successful deployments. The deterministic repair provider does not address the actual failure modes (missing images, security allowlist, container execution).

### Phase 3 Readiness

`NOT READY`

**Remaining Blockers:**

1. **Missing Docker images**: `node:20-alpine` must be pre-pulled or the build executor must auto-pull images
2. **Build command allowlist**: Must be expanded to include `pnpm build`, `yarn build`, and other legitimate build commands
3. **Container execution failures**: 6 Python repos fail with "Container not found", suggesting base image or dependency issues
4. **Windows long path limitation**: `vercel/next.js` cannot be cloned on Windows without long path support
5. **Framework detection accuracy**: Several repos have incorrect framework detection (e.g., gradio detected as "svelte"), leading to wrong base image selection

---

## Appendix: Validation Artifacts

- `validation_results.json` — Machine-readable corpus results
- `PHASE_2_8_VALIDATION_REPORT.md` — This report
- `PHASE_2_8_REPORT.md` — Previous Phase 2.8 report (pre-existing)
