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
  health_status?: string;
  health_response_time_ms?: number;
  last_health_check_at?: string;
  resource_metrics?: ResourceMetrics;
}

export interface ResourceMetrics {
  cpu_usage_percent?: number;
  memory_usage_bytes?: number;
  memory_limit_bytes?: number;
  memory_percent?: number;
  network_rx_bytes?: number;
  network_tx_bytes?: number;
  container_status?: string;
  uptime_seconds?: number;
  timestamp?: string;
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
