# Deployment Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployment dashboard where users can enter a GitHub URL, click Deploy, watch deployment progress in real-time, see build/runtime logs, and see the final result.

**Architecture:** Simplified one-step flow using POST `/api/v1/deployments` with `{ "repository_url": "..." }`. Frontend polls for status and logs every 2 seconds while deployment is active. Pipeline visualization shows progress through stages with checkmarks, spinners, and X marks.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, React hooks for polling

## Global Constraints

- No AI repair implementation
- No public URLs (show "Not available" if missing)
- No WebSocket (use polling)
- No billing/auth
- No backend redesign
- Minimal and developer-focused UI
- No excessive animations or marketing-style UI
- WCAG 2.1 AA accessibility compliance
- Mobile-first responsive design

---

## File Structure

### New Files to Create

| File | Responsibility |
|------|---------------|
| `apps/web/src/types/deployment.ts` | Type definitions for deployment states, stages, labels |
| `apps/web/src/lib/api/client.ts` | Generic API client functions (get, post, delete) |
| `apps/web/src/lib/api/deployments.ts` | Deployment-specific API functions |
| `apps/web/src/hooks/useDeployment.ts` | Hook for polling deployment status |
| `apps/web/src/hooks/useDeploymentLogs.ts` | Hook for polling deployment logs |
| `apps/web/src/components/DeploymentForm.tsx` | URL input + Deploy button |
| `apps/web/src/components/DeploymentProgress.tsx` | Pipeline visualization component |
| `apps/web/src/components/DeploymentLogs.tsx` | Monospace log viewer with auto-scroll |
| `apps/web/src/components/DeploymentDetails.tsx` | Repository info, timestamps, framework |
| `apps/web/src/components/DeploymentResult.tsx` | Success/failure prominent display |
| `apps/web/src/app/deployments/[id]/page.tsx` | Deployment detail page |
| `apps/web/src/app/deployments/[id]/layout.tsx` | Layout for deployment pages |
| `apps/web/src/__tests__/components/DeploymentForm.test.tsx` | Tests for DeploymentForm |
| `apps/web/src/__tests__/components/DeploymentProgress.test.tsx` | Tests for DeploymentProgress |
| `apps/web/src/__tests__/components/DeploymentLogs.test.tsx` | Tests for DeploymentLogs |
| `apps/web/src/__tests__/hooks/useDeployment.test.ts` | Tests for useDeployment hook |
| `apps/web/src/__tests__/hooks/useDeploymentLogs.test.ts` | Tests for useDeploymentLogs hook |

### Files to Modify

| File | Changes |
|------|---------|
| `apps/web/src/app/page.tsx` | Simplify to use DeploymentForm only |
| `apps/web/src/lib/api.ts` | Update to use new API client pattern |
| `apps/web/package.json` | Add testing dependencies |

---

## Task 1: Type Definitions

**Files:**
- Create: `apps/web/src/types/deployment.ts`

**Interfaces:**
- Produces: `DeploymentState`, `PIPELINE_STAGES`, `STATE_LABELS`, `STATE_COLORS`, `isTerminalState`, `isActiveState`

- [ ] **Step 1: Create type definitions file**

```typescript
// apps/web/src/types/deployment.ts

export type DeploymentState = 
  | 'queued'
  | 'cloning'
  | 'analyzing'
  | 'planning'
  | 'building'
  | 'starting'
  | 'health_checking'
  | 'running'
  | 'clone_failed'
  | 'analysis_failed'
  | 'plan_failed'
  | 'build_failed'
  | 'start_failed'
  | 'health_check_failed'
  | 'security_blocked'
  | 'timeout'
  | 'cancelled';

export const PIPELINE_STAGES = ['clone', 'analyze', 'plan', 'build', 'start', 'health_check'] as const;

export type PipelineStage = typeof PIPELINE_STAGES[number];

export const STATE_LABELS: Record<DeploymentState, string> = {
  queued: 'Queued',
  cloning: 'Cloning Repository',
  analyzing: 'Analyzing Code',
  planning: 'Generating Plan',
  building: 'Building Application',
  starting: 'Starting Runtime',
  health_checking: 'Checking Health',
  running: 'Application Running',
  clone_failed: 'Clone Failed',
  analysis_failed: 'Analysis Failed',
  plan_failed: 'Plan Failed',
  build_failed: 'Build Failed',
  start_failed: 'Start Failed',
  health_check_failed: 'Health Check Failed',
  security_blocked: 'Security Blocked',
  timeout: 'Timed Out',
  cancelled: 'Cancelled',
};

export const STATE_COLORS: Record<DeploymentState, string> = {
  queued: 'bg-gray-100 text-gray-700',
  cloning: 'bg-blue-100 text-blue-700',
  analyzing: 'bg-blue-100 text-blue-700',
  planning: 'bg-blue-100 text-blue-700',
  building: 'bg-yellow-100 text-yellow-700',
  starting: 'bg-yellow-100 text-yellow-700',
  health_checking: 'bg-yellow-100 text-yellow-700',
  running: 'bg-green-100 text-green-700',
  clone_failed: 'bg-red-100 text-red-700',
  analysis_failed: 'bg-red-100 text-red-700',
  plan_failed: 'bg-red-100 text-red-700',
  build_failed: 'bg-red-100 text-red-700',
  start_failed: 'bg-red-100 text-red-700',
  health_check_failed: 'bg-red-100 text-red-700',
  security_blocked: 'bg-red-100 text-red-700',
  timeout: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-700',
};

export const TERMINAL_STATES: DeploymentState[] = [
  'running',
  'clone_failed',
  'analysis_failed',
  'plan_failed',
  'build_failed',
  'start_failed',
  'health_check_failed',
  'security_blocked',
  'timeout',
  'cancelled',
];

export const ACTIVE_STATES: DeploymentState[] = [
  'queued',
  'cloning',
  'analyzing',
  'planning',
  'building',
  'starting',
  'health_checking',
];

export function isTerminalState(state: DeploymentState): boolean {
  return TERMINAL_STATES.includes(state);
}

export function isActiveState(state: DeploymentState): boolean {
  return ACTIVE_STATES.includes(state);
}

export function getStageForState(state: DeploymentState): PipelineStage | null {
  const stageMap: Partial<Record<DeploymentState, PipelineStage>> = {
    cloning: 'clone',
    analyzing: 'analyze',
    planning: 'plan',
    building: 'build',
    starting: 'start',
    health_checking: 'health_check',
    running: 'health_check',
  };
  return stageMap[state] ?? null;
}
```

- [ ] **Step 2: Verify file is created correctly**

Run: `cat apps/web/src/types/deployment.ts`
Expected: File contains all type definitions

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/types/deployment.ts
git commit -m "feat: add deployment type definitions"
```

---

## Task 2: API Client

**Files:**
- Create: `apps/web/src/lib/api/client.ts`
- Create: `apps/web/src/lib/api/deployments.ts`

**Interfaces:**
- Produces: `apiGet`, `apiPost`, `apiDelete`, `createDeployment`, `getDeployment`, `getDeploymentLogs`, `cancelDeployment`

- [ ] **Step 1: Create generic API client**

```typescript
// apps/web/src/lib/api/client.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(res.status, error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(res.status, error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(res.status, error.detail || `API error: ${res.status}`);
  }
  return res.json();
}
```

- [ ] **Step 2: Create deployment API functions**

```typescript
// apps/web/src/lib/api/deployments.ts

import { apiGet, apiPost, apiDelete } from './client';

export interface Deployment {
  id: string;
  repository_id?: string;
  snapshot_id?: string;
  state: string;
  repository_url?: string;
  commit_sha?: string;
  framework?: string;
  port?: number;
  start_command?: string;
  error_message?: string;
  error_stage?: string;
  container_id?: string;
  build_container_id?: string;
  snapshot_path?: string;
  celery_task_id?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  cloned_at?: string;
  analyzed_at?: string;
  plan_generated_at?: string;
  build_started_at?: string;
  build_completed_at?: string;
  runtime_started_at?: string;
  health_checked_at?: string;
}

export interface DeploymentLogEntry {
  id: string;
  deployment_id: string;
  stage: string;
  level: string;
  message: string;
  timestamp: string;
  sequence: number;
}

export interface DeploymentLogsResponse {
  logs: DeploymentLogEntry[];
  total: number;
}

export interface CreateDeploymentResponse {
  id: string;
  state: string;
  repository_url?: string;
  created_at: string;
  updated_at: string;
}

export async function createDeployment(url: string): Promise<CreateDeploymentResponse> {
  return apiPost('/api/v1/deployments', { repository_url: url });
}

export async function getDeployment(id: string): Promise<Deployment> {
  return apiGet(`/api/v1/deployments/${id}`);
}

export async function getDeploymentLogs(
  id: string,
  limit: number = 100
): Promise<DeploymentLogsResponse> {
  return apiGet(`/api/v1/deployments/${id}/logs?limit=${limit}`);
}

export async function cancelDeployment(id: string): Promise<Deployment> {
  return apiDelete(`/api/v1/deployments/${id}`);
}
```

- [ ] **Step 3: Verify files are created correctly**

Run: `cat apps/web/src/lib/api/client.ts && cat apps/web/src/lib/api/deployments.ts`
Expected: Both files contain correct API functions

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/api/
git commit -m "feat: add API client and deployment API functions"
```

---

## Task 3: Deployment Hooks

**Files:**
- Create: `apps/web/src/hooks/useDeployment.ts`
- Create: `apps/web/src/hooks/useDeploymentLogs.ts`

**Interfaces:**
- Consumes: `Deployment`, `DeploymentLogEntry`, `getDeployment`, `getDeploymentLogs`, `isActiveState`
- Produces: `useDeployment`, `useDeploymentLogs`

- [ ] **Step 1: Create useDeployment hook**

```typescript
// apps/web/src/hooks/useDeployment.ts

'use client';

import { useState, useEffect, useCallback } from 'react';
import { getDeployment, type Deployment } from '@/lib/api/deployments';
import { isActiveState, type DeploymentState } from '@/types/deployment';

interface UseDeploymentResult {
  deployment: Deployment | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useDeployment(id: string | null): UseDeploymentResult {
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDeployment = useCallback(async () => {
    if (!id) return;
    
    try {
      const data = await getDeployment(id);
      setDeployment(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch deployment');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!id) {
      setIsLoading(false);
      return;
    }

    fetchDeployment();
  }, [id, fetchDeployment]);

  useEffect(() => {
    if (!id || !deployment) return;

    // Poll while deployment is in an active state
    if (!isActiveState(deployment.state as DeploymentState)) {
      return;
    }

    const interval = setInterval(fetchDeployment, 2000);
    return () => clearInterval(interval);
  }, [id, deployment?.state, fetchDeployment]);

  return {
    deployment,
    isLoading,
    error,
    refetch: fetchDeployment,
  };
}
```

- [ ] **Step 2: Create useDeploymentLogs hook**

```typescript
// apps/web/src/hooks/useDeploymentLogs.ts

'use client';

import { useState, useEffect, useCallback } from 'react';
import { getDeploymentLogs, type DeploymentLogEntry } from '@/lib/api/deployments';
import { getDeployment, isActiveState, type DeploymentState } from '@/types/deployment';

interface UseDeploymentLogsResult {
  logs: DeploymentLogEntry[];
  isLoading: boolean;
  error: string | null;
}

export function useDeploymentLogs(
  deploymentId: string | null,
  deploymentState?: string | null
): UseDeploymentLogsResult {
  const [logs, setLogs] = useState<DeploymentLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    if (!deploymentId) return;
    
    try {
      const data = await getDeploymentLogs(deploymentId, 200);
      setLogs(data.logs);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs');
    } finally {
      setIsLoading(false);
    }
  }, [deploymentId]);

  useEffect(() => {
    if (!deploymentId) {
      setIsLoading(false);
      return;
    }

    fetchLogs();
  }, [deploymentId, fetchLogs]);

  useEffect(() => {
    if (!deploymentId || !deploymentState) return;

    // Poll while deployment is in an active state
    if (!isActiveState(deploymentState as DeploymentState)) {
      return;
    }

    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, [deploymentId, deploymentState, fetchLogs]);

  return {
    logs,
    isLoading,
    error,
  };
}
```

- [ ] **Step 3: Verify files are created correctly**

Run: `cat apps/web/src/hooks/useDeployment.ts && cat apps/web/src/hooks/useDeploymentLogs.ts`
Expected: Both hooks are created with correct logic

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/hooks/
git commit -m "feat: add deployment polling hooks"
```

---

## Task 4: DeploymentForm Component

**Files:**
- Create: `apps/web/src/components/DeploymentForm.tsx`

**Interfaces:**
- Consumes: `createDeployment`
- Produces: `DeploymentForm`

- [ ] **Step 1: Create DeploymentForm component**

```typescript
// apps/web/src/components/DeploymentForm.tsx

'use client';

import { useState } from 'react';
import { createDeployment } from '@/lib/api/deployments';

interface DeploymentFormProps {
  onDeploymentCreated?: (deploymentId: string) => void;
}

export function DeploymentForm({ onDeploymentCreated }: DeploymentFormProps) {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValidUrl = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+/.test(url);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidUrl || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await createDeployment(url);
      onDeploymentCreated?.(response.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create deployment');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Deploy a Repository</h2>
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/user/repo"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-gray-900 placeholder-gray-400"
          disabled={isLoading}
          aria-label="GitHub repository URL"
        />
        <button
          type="submit"
          disabled={!isValidUrl || isLoading}
          className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Deploying...' : 'Deploy'}
        </button>
      </form>
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify file is created correctly**

Run: `cat apps/web/src/components/DeploymentForm.tsx`
Expected: Component is created with correct form handling

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/DeploymentForm.tsx
git commit -m "feat: add DeploymentForm component"
```

---

## Task 5: DeploymentProgress Component

**Files:**
- Create: `apps/web/src/components/DeploymentProgress.tsx`

**Interfaces:**
- Consumes: `DeploymentState`, `PIPELINE_STAGES`, `getStageForState`, `isTerminalState`
- Produces: `DeploymentProgress`

- [ ] **Step 1: Create DeploymentProgress component**

```typescript
// apps/web/src/components/DeploymentProgress.tsx

import { 
  PIPELINE_STAGES, 
  getStageForState, 
  isTerminalState,
  type DeploymentState,
  type PipelineStage 
} from '@/types/deployment';

interface DeploymentProgressProps {
  state: DeploymentState;
  errorStage?: string | null;
}

const STAGE_LABELS: Record<PipelineStage, string> = {
  clone: 'Clone',
  analyze: 'Analyze',
  plan: 'Plan',
  build: 'Build',
  start: 'Start',
  health_check: 'Health Check',
};

function getStageStatus(
  stage: PipelineStage,
  currentState: DeploymentState,
  errorStage?: string | null
): 'completed' | 'active' | 'failed' | 'pending' {
  const currentStage = getStageForState(currentState);
  
  // If deployment failed at this stage
  if (errorStage === stage || 
      (currentState.includes('_failed') && currentStage === stage)) {
    return 'failed';
  }
  
  // If deployment is in terminal state and succeeded
  if (currentState === 'running' && stage === 'health_check') {
    return 'completed';
  }
  
  // Find stage index
  const stageIndex = PIPELINE_STAGES.indexOf(stage);
  const currentStageIndex = currentStage ? PIPELINE_STAGES.indexOf(currentStage) : -1;
  
  if (stageIndex < currentStageIndex) {
    return 'completed';
  } else if (stageIndex === currentStageIndex) {
    return 'active';
  } else {
    return 'pending';
  }
}

export function DeploymentProgress({ state, errorStage }: DeploymentProgressProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-md font-semibold text-gray-900 mb-4">Pipeline Progress</h3>
      <div className="space-y-3">
        {PIPELINE_STAGES.map((stage) => {
          const status = getStageStatus(stage, state, errorStage);
          return (
            <div
              key={stage}
              className="flex items-center gap-3"
              role="listitem"
              aria-label={`${STAGE_LABELS[stage]}: ${status}`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center ${
                  status === 'completed'
                    ? 'bg-green-500'
                    : status === 'active'
                    ? 'bg-blue-500'
                    : status === 'failed'
                    ? 'bg-red-500'
                    : 'bg-gray-200'
                }`}
                aria-hidden="true"
              >
                {status === 'completed' && (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {status === 'active' && (
                  <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                )}
                {status === 'failed' && (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                {status === 'pending' && (
                  <div className="w-2 h-2 bg-gray-400 rounded-full" />
                )}
              </div>
              <span
                className={`text-sm font-medium ${
                  status === 'completed'
                    ? 'text-green-700'
                    : status === 'active'
                    ? 'text-blue-700'
                    : status === 'failed'
                    ? 'text-red-700'
                    : 'text-gray-500'
                }`}
              >
                {STAGE_LABELS[stage]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify file is created correctly**

Run: `cat apps/web/src/components/DeploymentProgress.tsx`
Expected: Component is created with correct pipeline visualization

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/DeploymentProgress.tsx
git commit -m "feat: add DeploymentProgress component"
```

---

## Task 6: DeploymentLogs Component

**Files:**
- Create: `apps/web/src/components/DeploymentLogs.tsx`

**Interfaces:**
- Consumes: `DeploymentLogEntry[]`
- Produces: `DeploymentLogs`

- [ ] **Step 1: Create DeploymentLogs component**

```typescript
// apps/web/src/components/DeploymentLogs.tsx

'use client';

import { useEffect, useRef, useState } from 'react';
import type { DeploymentLogEntry } from '@/lib/api/deployments';

interface DeploymentLogsProps {
  logs: DeploymentLogEntry[];
  isLoading?: boolean;
}

const MAX_VISIBLE_LOGS = 200;

const LEVEL_COLORS: Record<string, string> = {
  info: 'text-gray-700',
  warning: 'text-yellow-600',
  error: 'text-red-600',
  debug: 'text-gray-500',
};

const STAGE_LABELS: Record<string, string> = {
  clone: 'CLONE',
  analyze: 'ANALYZE',
  plan: 'PLAN',
  build: 'BUILD',
  start: 'START',
  health_check: 'HEALTH',
  runtime: 'RUNTIME',
};

export function DeploymentLogs({ logs, isLoading }: DeploymentLogsProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const prevLogCountRef = useRef(logs.length);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAutoScroll && containerRef.current && logs.length > prevLogCountRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
    prevLogCountRef.current = logs.length;
  }, [logs.length, isAutoScroll]);

  // Handle scroll to detect manual scrolling
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setIsAutoScroll(isAtBottom);
  };

  const visibleLogs = logs.slice(-MAX_VISIBLE_LOGS);

  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h3 className="text-md font-semibold text-gray-900">
          Build Logs
          {logs.length > MAX_VISIBLE_LOGS && (
            <span className="text-sm font-normal text-gray-500 ml-2">
              (showing last {MAX_VISIBLE_LOGS} of {logs.length})
            </span>
          )}
        </h3>
        <button
          onClick={() => setIsAutoScroll(!isAutoScroll)}
          className={`text-sm px-3 py-1 rounded ${
            isAutoScroll
              ? 'bg-blue-100 text-blue-700'
              : 'bg-gray-100 text-gray-700'
          }`}
        >
          {isAutoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
        </button>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-96 overflow-y-auto font-mono text-sm p-4 bg-gray-50"
        role="log"
        aria-label="Deployment logs"
      >
        {visibleLogs.length === 0 && !isLoading && (
          <p className="text-gray-500 text-center py-8">No logs yet</p>
        )}
        {visibleLogs.map((log) => (
          <div key={log.id} className="flex items-start gap-2 py-1 hover:bg-gray-100">
            <span className="text-gray-400 text-xs w-20 flex-shrink-0">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={`text-xs font-bold w-16 flex-shrink-0 ${
                LEVEL_COLORS[log.level] || 'text-gray-700'
              }`}
            >
              [{STAGE_LABELS[log.stage] || log.stage.toUpperCase()}]
            </span>
            <span className={`${LEVEL_COLORS[log.level] || 'text-gray-700'} break-words`}>
              {log.message}
            </span>
          </div>
        ))}
        {isLoading && (
          <div className="text-center py-4 text-gray-500">
            Loading logs...
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify file is created correctly**

Run: `cat apps/web/src/components/DeploymentLogs.tsx`
Expected: Component is created with correct log viewer functionality

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/DeploymentLogs.tsx
git commit -m "feat: add DeploymentLogs component"
```

---

## Task 7: DeploymentDetails Component

**Files:**
- Create: `apps/web/src/components/DeploymentDetails.tsx`

**Interfaces:**
- Consumes: `Deployment`
- Produces: `DeploymentDetails`

- [ ] **Step 1: Create DeploymentDetails component**

```typescript
// apps/web/src/components/DeploymentDetails.tsx

import type { Deployment } from '@/lib/api/deployments';

interface DeploymentDetailsProps {
  deployment: Deployment;
}

export function DeploymentDetails({ deployment }: DeploymentDetailsProps) {
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-md font-semibold text-gray-900 mb-4">Deployment Details</h3>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-sm text-gray-500">Repository URL</dt>
          <dd className="font-medium text-gray-900 break-all">
            {deployment.repository_url || 'N/A'}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-gray-500">Commit SHA</dt>
          <dd className="font-mono text-sm text-gray-900">
            {deployment.commit_sha?.slice(0, 8) || 'N/A'}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-gray-500">Framework</dt>
          <dd className="font-medium text-gray-900">
            {deployment.framework || 'N/A'}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-gray-500">Port</dt>
          <dd className="font-medium text-gray-900">
            {deployment.port || 'N/A'}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-gray-500">Created At</dt>
          <dd className="text-gray-900">{formatDate(deployment.created_at)}</dd>
        </div>
        <div>
          <dt className="text-sm text-gray-500">Updated At</dt>
          <dd className="text-gray-900">{formatDate(deployment.updated_at)}</dd>
        </div>
        {deployment.completed_at && (
          <div>
            <dt className="text-sm text-gray-500">Completed At</dt>
            <dd className="text-gray-900">{formatDate(deployment.completed_at)}</dd>
          </div>
        )}
        {deployment.error_message && (
          <div className="col-span-2">
            <dt className="text-sm text-gray-500">Error</dt>
            <dd className="text-red-600 text-sm">{deployment.error_message}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
```

- [ ] **Step 2: Verify file is created correctly**

Run: `cat apps/web/src/components/DeploymentDetails.tsx`
Expected: Component is created with correct details display

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/DeploymentDetails.tsx
git commit -m "feat: add DeploymentDetails component"
```

---

## Task 8: DeploymentResult Component

**Files:**
- Create: `apps/web/src/components/DeploymentResult.tsx`

**Interfaces:**
- Consumes: `Deployment`, `isTerminalState`, `STATE_LABELS`
- Produces: `DeploymentResult`

- [ ] **Step 1: Create DeploymentResult component**

```typescript
// apps/web/src/components/DeploymentResult.tsx

import { isTerminalState, STATE_LABELS, type DeploymentState } from '@/types/deployment';
import type { Deployment } from '@/lib/api/deployments';

interface DeploymentResultProps {
  deployment: Deployment;
  onCancel?: () => void;
  isCancelling?: boolean;
}

export function DeploymentResult({ deployment, onCancel, isCancelling }: DeploymentResultProps) {
  const state = deployment.state as DeploymentState;
  const isTerminal = isTerminalState(state);
  const isRunning = state === 'running';
  const isFailed = state.endsWith('_failed') || state === 'security_blocked' || state === 'timeout';

  if (!isTerminal) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
            <span className="text-blue-700 font-medium">
              {STATE_LABELS[state] || state}
            </span>
          </div>
          {onCancel && (
            <button
              onClick={onCancel}
              disabled={isCancelling}
              className="px-4 py-2 text-sm bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isCancelling ? 'Cancelling...' : 'Cancel'}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (isRunning) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-green-500 rounded-full" />
          <span className="text-green-700 font-medium">
            {STATE_LABELS.running}
          </span>
        </div>
        <p className="mt-2 text-sm text-green-600">
          Your application is now live and running.
        </p>
      </div>
    );
  }

  if (isFailed) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-red-500 rounded-full" />
          <span className="text-red-700 font-medium">
            {STATE_LABELS[state] || state}
          </span>
        </div>
        {deployment.error_message && (
          <p className="mt-2 text-sm text-red-600">
            {deployment.error_message}
          </p>
        )}
      </div>
    );
  }

  // Cancelled or other terminal states
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
      <div className="flex items-center gap-3">
        <div className="w-3 h-3 bg-gray-400 rounded-full" />
        <span className="text-gray-700 font-medium">
          {STATE_LABELS[state] || state}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify file is created correctly**

Run: `cat apps/web/src/components/DeploymentResult.tsx`
Expected: Component is created with correct result display

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/DeploymentResult.tsx
git commit -m "feat: add DeploymentResult component"
```

---

## Task 9: Deployment Detail Page

**Files:**
- Create: `apps/web/src/app/deployments/[id]/layout.tsx`
- Create: `apps/web/src/app/deployments/[id]/page.tsx`

**Interfaces:**
- Consumes: `useDeployment`, `useDeploymentLogs`, `DeploymentProgress`, `DeploymentLogs`, `DeploymentDetails`, `DeploymentResult`
- Produces: Deployment detail page

- [ ] **Step 1: Create layout for deployment pages**

```typescript
// apps/web/src/app/deployments/[id]/layout.tsx

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Deployment | Repo2Web',
  description: 'View deployment progress and logs',
};

export default function DeploymentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
```

- [ ] **Step 2: Create deployment detail page**

```typescript
// apps/web/src/app/deployments/[id]/page.tsx

'use client';

import { useParams, useRouter } from 'next/navigation';
import { useDeployment } from '@/hooks/useDeployment';
import { useDeploymentLogs } from '@/hooks/useDeploymentLogs';
import { DeploymentProgress } from '@/components/DeploymentProgress';
import { DeploymentLogs } from '@/components/DeploymentLogs';
import { DeploymentDetails } from '@/components/DeploymentDetails';
import { DeploymentResult } from '@/components/DeploymentResult';
import { Header } from '@/components/Header';
import { cancelDeployment } from '@/lib/api/deployments';
import { useState } from 'react';

export default function DeploymentPage() {
  const params = useParams();
  const router = useRouter();
  const deploymentId = params.id as string;

  const { deployment, isLoading, error, refetch } = useDeployment(deploymentId);
  const { logs, isLoading: logsLoading } = useDeploymentLogs(
    deploymentId,
    deployment?.state
  );
  const [isCancelling, setIsCancelling] = useState(false);

  const handleCancel = async () => {
    if (!deployment) return;
    setIsCancelling(true);
    try {
      await cancelDeployment(deployment.id);
      await refetch();
    } catch (err) {
      console.error('Failed to cancel deployment:', err);
    } finally {
      setIsCancelling(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12">
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="mt-4 text-gray-600">Loading deployment...</p>
          </div>
        </main>
      </div>
    );
  }

  if (error || !deployment) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12">
          <div className="text-center py-12">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Deployment Not Found</h1>
            <p className="text-gray-600 mb-6">
              {error || 'The deployment you are looking for does not exist.'}
            </p>
            <button
              onClick={() => router.push('/')}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12">
        <div className="mb-6">
          <button
            onClick={() => router.push('/')}
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Dashboard
          </button>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">Deployment Details</h1>

        <div className="space-y-6">
          <DeploymentResult
            deployment={deployment}
            onCancel={handleCancel}
            isCancelling={isCancelling}
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <DeploymentProgress
              state={deployment.state as any}
              errorStage={deployment.error_stage}
            />
            <DeploymentDetails deployment={deployment} />
          </div>

          <DeploymentLogs logs={logs} isLoading={logsLoading} />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Verify files are created correctly**

Run: `cat apps/web/src/app/deployments/\\[id\\]/layout.tsx && cat apps/web/src/app/deployments/\\[id\\]/page.tsx`
Expected: Both files are created with correct content

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/deployments/
git commit -m "feat: add deployment detail page"
```

---

## Task 10: Update Landing Page

**Files:**
- Modify: `apps/web/src/app/page.tsx`

**Interfaces:**
- Consumes: `DeploymentForm`
- Produces: Updated landing page

- [ ] **Step 1: Update landing page to use DeploymentForm**

```typescript
// apps/web/src/app/page.tsx

'use client';

import { useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { DeploymentForm } from '@/components/DeploymentForm';

export default function HomePage() {
  const router = useRouter();

  const handleDeploymentCreated = (deploymentId: string) => {
    router.push(`/deployments/${deploymentId}`);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Turn GitHub repositories into running apps.
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Paste a GitHub URL, and we&apos;ll analyze, build, and deploy it as a live web application.
          </p>
        </div>

        <DeploymentForm onDeploymentCreated={handleDeploymentCreated} />

        <div className="mt-12 text-center text-sm text-gray-500">
          <p>Supported: React, Vue, Angular, Next.js, Node.js, Python (Flask, Django, FastAPI)</p>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Verify file is updated correctly**

Run: `cat apps/web/src/app/page.tsx`
Expected: Page uses DeploymentForm and redirects to deployment detail page

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/page.tsx
git commit -m "feat: update landing page to use DeploymentForm"
```

---

## Task 11: Update Old API File

**Files:**
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Consumes: New API client
- Produces: Updated old API file or removal

- [ ] **Step 1: Update or remove old API file**

The old `apps/web/src/lib/api.ts` file contains functions that are now in `apps/web/src/lib/api/deployments.ts`. We should update it to re-export from the new location for backward compatibility.

```typescript
// apps/web/src/lib/api.ts

// Re-export from new location for backward compatibility
export { 
  createDeployment, 
  getDeployment, 
  getDeploymentLogs,
  cancelDeployment,
  type Deployment,
  type DeploymentLogEntry,
  type DeploymentLogsResponse,
  type CreateDeploymentResponse,
} from './api/deployments';

// Keep old analyze function for compatibility
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function analyzeRepository(url: string): Promise<{
  repository_id: string;
  snapshot_id: string;
  status: string;
}> {
  const response = await fetch(`${API_BASE}/api/v1/repositories/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.error?.detail || 'Analysis failed');
  }
  return response.json();
}
```

- [ ] **Step 2: Verify file is updated correctly**

Run: `cat apps/web/src/lib/api.ts`
Expected: File re-exports from new location and keeps analyze function

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "refactor: update old API file to re-export from new location"
```

---

## Task 12: Add Testing Dependencies

**Files:**
- Modify: `apps/web/package.json`

**Interfaces:**
- Consumes: Current package.json
- Produces: Updated package.json with testing dependencies

- [ ] **Step 1: Update package.json with testing dependencies**

```json
{
  "name": "repo2web-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "dependencies": {
    "next": "14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.2.0",
    "@testing-library/react": "^14.1.2",
    "@testing-library/user-event": "^14.5.2",
    "@types/jest": "^29.5.11",
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "autoprefixer": "^10.4.17",
    "eslint": "^8.56.0",
    "eslint-config-next": "14.1.0",
    "jest": "^29.7.0",
    "jest-environment-jsdom": "^29.7.0",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "ts-jest": "^29.1.1",
    "typescript": "^5.3.3"
  }
}
```

- [ ] **Step 2: Install dependencies**

Run: `cd apps/web && npm install`
Expected: Dependencies are installed successfully

- [ ] **Step 3: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "feat: add testing dependencies"
```

---

## Task 13: Jest Configuration

**Files:**
- Create: `apps/web/jest.config.js`
- Create: `apps/web/jest.setup.js`

**Interfaces:**
- Produces: Jest configuration

- [ ] **Step 1: Create Jest configuration**

```javascript
// apps/web/jest.config.js

const nextJest = require('next/jest')

const createJestConfig = nextJest({
  dir: './',
})

/** @type {import('jest').Config} */
const customJestConfig = {
  setupFilesAfterSetup: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testPathIgnorePatterns: ['<rootDir>/node_modules/', '<rootDir>/.next/'],
}

module.exports = createJestConfig(customJestConfig)
```

- [ ] **Step 2: Create Jest setup file**

```javascript
// apps/web/jest.setup.js

import '@testing-library/jest-dom'
```

- [ ] **Step 3: Verify files are created correctly**

Run: `cat apps/web/jest.config.js && cat apps/web/jest.setup.js`
Expected: Both configuration files are created

- [ ] **Step 4: Commit**

```bash
git add apps/web/jest.config.js apps/web/jest.setup.js
git commit -m "feat: add Jest configuration"
```

---

## Task 14: Write Tests for DeploymentForm

**Files:**
- Create: `apps/web/src/__tests__/components/DeploymentForm.test.tsx`

**Interfaces:**
- Consumes: `DeploymentForm`
- Produces: Test file

- [ ] **Step 1: Create test file for DeploymentForm**

```typescript
// apps/web/src/__tests__/components/DeploymentForm.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeploymentForm } from '@/components/DeploymentForm';

// Mock the API
jest.mock('@/lib/api/deployments', () => ({
  createDeployment: jest.fn(),
}));

import { createDeployment } from '@/lib/api/deployments';

const mockCreateDeployment = createDeployment as jest.MockedFunction<typeof createDeployment>;

describe('DeploymentForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the form with input and button', () => {
    render(<DeploymentForm />);
    
    expect(screen.getByLabelText(/github repository url/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deploy/i })).toBeInTheDocument();
  });

  it('disables deploy button for invalid URLs', async () => {
    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'not-a-valid-url');
    expect(button).toBeDisabled();
  });

  it('enables deploy button for valid GitHub URLs', async () => {
    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    expect(button).toBeEnabled();
  });

  it('calls createDeployment with valid URL', async () => {
    mockCreateDeployment.mockResolvedValueOnce({
      id: 'test-id',
      state: 'queued',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    const onDeploymentCreated = jest.fn();
    render(<DeploymentForm onDeploymentCreated={onDeploymentCreated} />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    await userEvent.click(button);
    
    await waitFor(() => {
      expect(mockCreateDeployment).toHaveBeenCalledWith('https://github.com/user/repo');
    });
    
    await waitFor(() => {
      expect(onDeploymentCreated).toHaveBeenCalledWith('test-id');
    });
  });

  it('displays error message on API failure', async () => {
    mockCreateDeployment.mockRejectedValueOnce(new Error('API error'));

    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    await userEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('API error');
    });
  });

  it('shows loading state during deployment', async () => {
    mockCreateDeployment.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    await userEvent.click(button);
    
    await waitFor(() => {
      expect(button).toHaveTextContent('Deploying...');
      expect(button).toBeDisabled();
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd apps/web && npm test -- --testPathPattern=DeploymentForm`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/__tests__/components/DeploymentForm.test.tsx
git commit -m "test: add tests for DeploymentForm component"
```

---

## Task 15: Write Tests for DeploymentProgress

**Files:**
- Create: `apps/web/src/__tests__/components/DeploymentProgress.test.tsx`

**Interfaces:**
- Consumes: `DeploymentProgress`
- Produces: Test file

- [ ] **Step 1: Create test file for DeploymentProgress**

```typescript
// apps/web/src/__tests__/components/DeploymentProgress.test.tsx

import { render, screen } from '@testing-library/react';
import { DeploymentProgress } from '@/components/DeploymentProgress';
import { DeploymentState } from '@/types/deployment';

describe('DeploymentProgress', () => {
  it('renders all pipeline stages', () => {
    render(<DeploymentProgress state="queued" />);
    
    expect(screen.getByText('Clone')).toBeInTheDocument();
    expect(screen.getByText('Analyze')).toBeInTheDocument();
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Build')).toBeInTheDocument();
    expect(screen.getByText('Start')).toBeInTheDocument();
    expect(screen.getByText('Health Check')).toBeInTheDocument();
  });

  it('shows correct status for queued state', () => {
    render(<DeploymentProgress state="queued" />);
    
    const items = screen.getAllByRole('listitem');
    items.forEach((item) => {
      expect(item).toHaveTextContent('pending');
    });
  });

  it('shows correct status for cloning state', () => {
    render(<DeploymentProgress state="cloning" />);
    
    const cloneItem = screen.getByText('Clone').closest('[role="listitem"]');
    expect(cloneItem).toHaveTextContent('active');
  });

  it('shows correct status for building state', () => {
    render(<DeploymentProgress state="building" />);
    
    const cloneItem = screen.getByText('Clone').closest('[role="listitem"]');
    const analyzeItem = screen.getByText('Analyze').closest('[role="listitem"]');
    const planItem = screen.getByText('Plan').closest('[role="listitem"]');
    const buildItem = screen.getByText('Build').closest('[role="listitem"]');
    
    expect(cloneItem).toHaveTextContent('completed');
    expect(analyzeItem).toHaveTextContent('completed');
    expect(planItem).toHaveTextContent('completed');
    expect(buildItem).toHaveTextContent('active');
  });

  it('shows correct status for running state', () => {
    render(<DeploymentProgress state="running" />);
    
    const items = screen.getAllByRole('listitem');
    items.forEach((item) => {
      expect(item).toHaveTextContent('completed');
    });
  });

  it('shows failed status for failed state', () => {
    render(<DeploymentProgress state="build_failed" />);
    
    const buildItem = screen.getByText('Build').closest('[role="listitem"]');
    expect(buildItem).toHaveTextContent('failed');
  });
});
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd apps/web && npm test -- --testPathPattern=DeploymentProgress`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/__tests__/components/DeploymentProgress.test.tsx
git commit -m "test: add tests for DeploymentProgress component"
```

---

## Task 16: Write Tests for DeploymentLogs

**Files:**
- Create: `apps/web/src/__tests__/components/DeploymentLogs.test.tsx`

**Interfaces:**
- Consumes: `DeploymentLogs`
- Produces: Test file

- [ ] **Step 1: Create test file for DeploymentLogs**

```typescript
// apps/web/src/__tests__/components/DeploymentLogs.test.tsx

import { render, screen } from '@testing-library/react';
import { DeploymentLogs } from '@/components/DeploymentLogs';
import { DeploymentLogEntry } from '@/lib/api/deployments';

const mockLogs: DeploymentLogEntry[] = [
  {
    id: '1',
    deployment_id: 'test-deployment',
    stage: 'clone',
    level: 'info',
    message: 'Cloning repository...',
    timestamp: new Date().toISOString(),
    sequence: 1,
  },
  {
    id: '2',
    deployment_id: 'test-deployment',
    stage: 'build',
    level: 'info',
    message: 'Building application...',
    timestamp: new Date().toISOString(),
    sequence: 2,
  },
  {
    id: '3',
    deployment_id: 'test-deployment',
    stage: 'build',
    level: 'error',
    message: 'Build failed',
    timestamp: new Date().toISOString(),
    sequence: 3,
  },
];

describe('DeploymentLogs', () => {
  it('renders logs correctly', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    expect(screen.getByText('Cloning repository...')).toBeInTheDocument();
    expect(screen.getByText('Building application...')).toBeInTheDocument();
    expect(screen.getByText('Build failed')).toBeInTheDocument();
  });

  it('shows no logs message when empty', () => {
    render(<DeploymentLogs logs={[]} />);
    
    expect(screen.getByText('No logs yet')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<DeploymentLogs logs={[]} isLoading={true} />);
    
    expect(screen.getByText('Loading logs...')).toBeInTheDocument();
  });

  it('displays stage labels correctly', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    expect(screen.getByText('[CLONE]')).toBeInTheDocument();
    expect(screen.getByText('[BUILD]')).toBeInTheDocument();
  });

  it('applies correct colors for different log levels', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    const errorLog = screen.getByText('Build failed');
    expect(errorLog).toHaveClass('text-red-600');
  });

  it('has auto-scroll button', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    expect(screen.getByText('Auto-scroll ON')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd apps/web && npm test -- --testPathPattern=DeploymentLogs`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/__tests__/components/DeploymentLogs.test.tsx
git commit -m "test: add tests for DeploymentLogs component"
```

---

## Task 17: Write Tests for Hooks

**Files:**
- Create: `apps/web/src/__tests__/hooks/useDeployment.test.ts`
- Create: `apps/web/src/__tests__/hooks/useDeploymentLogs.test.ts`

**Interfaces:**
- Consumes: `useDeployment`, `useDeploymentLogs`
- Produces: Test files

- [ ] **Step 1: Create test file for useDeployment hook**

```typescript
// apps/web/src/__tests__/hooks/useDeployment.test.ts

import { renderHook, waitFor } from '@testing-library/react';
import { useDeployment } from '@/hooks/useDeployment';
import { getDeployment } from '@/lib/api/deployments';

jest.mock('@/lib/api/deployments');

const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;

describe('useDeployment', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns loading state initially', () => {
    mockGetDeployment.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useDeployment('test-id'));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.deployment).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('fetches deployment successfully', async () => {
    const mockDeployment = {
      id: 'test-id',
      state: 'running',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    mockGetDeployment.mockResolvedValueOnce(mockDeployment);

    const { result } = renderHook(() => useDeployment('test-id'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deployment).toEqual(mockDeployment);
    expect(result.current.error).toBeNull();
  });

  it('handles errors', async () => {
    mockGetDeployment.mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() => useDeployment('test-id'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deployment).toBeNull();
    expect(result.current.error).toBe('API error');
  });

  it('does not fetch when id is null', () => {
    const { result } = renderHook(() => useDeployment(null));

    expect(result.current.isLoading).toBe(false);
    expect(mockGetDeployment).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Create test file for useDeploymentLogs hook**

```typescript
// apps/web/src/__tests__/hooks/useDeploymentLogs.test.ts

import { renderHook, waitFor } from '@testing-library/react';
import { useDeploymentLogs } from '@/hooks/useDeploymentLogs';
import { getDeploymentLogs } from '@/lib/api/deployments';

jest.mock('@/lib/api/deployments');

const mockGetDeploymentLogs = getDeploymentLogs as jest.MockedFunction<typeof getDeploymentLogs>;

describe('useDeploymentLogs', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns loading state initially', () => {
    mockGetDeploymentLogs.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useDeploymentLogs('test-id', 'running'));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.logs).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('fetches logs successfully', async () => {
    const mockLogs = [
      {
        id: '1',
        deployment_id: 'test-id',
        stage: 'clone',
        level: 'info',
        message: 'Cloning...',
        timestamp: new Date().toISOString(),
        sequence: 1,
      },
    ];

    mockGetDeploymentLogs.mockResolvedValueOnce({
      logs: mockLogs,
      total: 1,
    });

    const { result } = renderHook(() => useDeploymentLogs('test-id', 'running'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.logs).toEqual(mockLogs);
    expect(result.current.error).toBeNull();
  });

  it('handles errors', async () => {
    mockGetDeploymentLogs.mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() => useDeploymentLogs('test-id', 'running'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.logs).toEqual([]);
    expect(result.current.error).toBe('API error');
  });

  it('does not fetch when deploymentId is null', () => {
    const { result } = renderHook(() => useDeploymentLogs(null, 'running'));

    expect(result.current.isLoading).toBe(false);
    expect(mockGetDeploymentLogs).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd apps/web && npm test -- --testPathPattern=hooks`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/__tests__/hooks/
git commit -m "test: add tests for deployment hooks"
```

---

## Task 18: Verify Build Works

**Files:**
- No new files

**Interfaces:**
- Consumes: All created files
- Produces: Verified build

- [ ] **Step 1: Run build to verify everything compiles**

Run: `cd apps/web && npm run build`
Expected: Build completes successfully

- [ ] **Step 2: Run all tests**

Run: `cd apps/web && npm test`
Expected: All tests pass

- [ ] **Step 3: Run lint**

Run: `cd apps/web && npm run lint`
Expected: No lint errors

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete deployment dashboard implementation"
```

---

## Summary

This plan implements a complete deployment dashboard with:

1. **Type definitions** for deployment states and stages
2. **API client** for communicating with the backend
3. **React hooks** for polling deployment status and logs
4. **UI components** for form, progress, logs, details, and result
5. **Deployment detail page** with full functionality
6. **Landing page** updated to use new flow
7. **Comprehensive tests** for all components and hooks
8. **Build verification** to ensure everything works

The implementation follows the simplified one-step flow: enter URL → deploy → view progress → see result.
