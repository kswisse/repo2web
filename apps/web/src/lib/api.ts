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
