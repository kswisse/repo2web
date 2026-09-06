export interface Repository {
  id: string;
  url: string;
  name: string;
  default_branch: string;
  created_at: string;
  updated_at: string;
}

export interface AnalysisResult {
  repository_id: string;
  framework: string;
  language: string[];
  confidence: number;
  warnings: string[];
}

export interface Deployment {
  id: string;
  repository_id: string;
  snapshot_id: string;
  status: DeploymentStatus;
  url?: string;
  created_at: string;
  updated_at: string;
}

export type DeploymentStatus =
  | "queued"
  | "cloning"
  | "analyzing"
  | "planning"
  | "building"
  | "starting"
  | "health_checking"
  | "running"
  | "clone_failed"
  | "analysis_failed"
  | "plan_failed"
  | "build_failed"
  | "start_failed"
  | "health_check_failed"
  | "security_blocked"
  | "timeout"
  | "cancelled";

export interface BuildLog {
  id: string;
  step_name: string;
  status: string;
  level: string;
  message: string;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  duration_ms: number;
  created_at: string;
}
