import type { Deployment } from '@/lib/api/deployments';

interface DeploymentDetailsProps {
  deployment: Deployment;
}

function formatBytes(bytes?: number): string {
  if (bytes === undefined || bytes === null) return 'N/A';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDuration(seconds?: number): string {
  if (seconds === undefined || seconds === null) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

const HEALTH_STATUS_LABELS: Record<string, string> = {
  healthy: 'Healthy',
  unhealthy: 'Unhealthy',
  pending: 'Pending',
  timeout: 'Timeout',
};

const HEALTH_STATUS_COLORS: Record<string, string> = {
  healthy: 'bg-green-100 text-green-700',
  unhealthy: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
  timeout: 'bg-red-100 text-red-700',
};

export function DeploymentDetails({ deployment }: DeploymentDetailsProps) {
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const metrics = deployment.resource_metrics;

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

      {/* Health Status Section */}
      {(deployment.health_status || deployment.health_response_time_ms !== undefined || deployment.last_health_check_at) && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Health Status</h4>
          <dl className="grid grid-cols-2 gap-4">
            {deployment.health_status && (
              <div>
                <dt className="text-sm text-gray-500">Status</dt>
                <dd>
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${HEALTH_STATUS_COLORS[deployment.health_status] || 'bg-gray-100 text-gray-700'}`}>
                    {HEALTH_STATUS_LABELS[deployment.health_status] || deployment.health_status}
                  </span>
                </dd>
              </div>
            )}
            {deployment.health_response_time_ms !== undefined && deployment.health_response_time_ms !== null && (
              <div>
                <dt className="text-sm text-gray-500">Response Time</dt>
                <dd className="font-medium text-gray-900">{deployment.health_response_time_ms}ms</dd>
              </div>
            )}
            {deployment.last_health_check_at && (
              <div>
                <dt className="text-sm text-gray-500">Last Health Check</dt>
                <dd className="text-gray-900">{formatDate(deployment.last_health_check_at)}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {/* Resource Metrics Section */}
      {metrics && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">Resource Usage</h4>
          <dl className="grid grid-cols-2 gap-4">
            {metrics.cpu_usage_percent !== undefined && metrics.cpu_usage_percent !== null && (
              <div>
                <dt className="text-sm text-gray-500">CPU Usage</dt>
                <dd className="font-medium text-gray-900">{metrics.cpu_usage_percent}%</dd>
              </div>
            )}
            {metrics.memory_percent !== undefined && metrics.memory_percent !== null && (
              <div>
                <dt className="text-sm text-gray-500">Memory Usage</dt>
                <dd className="font-medium text-gray-900">
                  {metrics.memory_percent}% ({formatBytes(metrics.memory_usage_bytes)} / {formatBytes(metrics.memory_limit_bytes)})
                </dd>
              </div>
            )}
            {metrics.uptime_seconds !== undefined && metrics.uptime_seconds !== null && (
              <div>
                <dt className="text-sm text-gray-500">Uptime</dt>
                <dd className="font-medium text-gray-900">{formatDuration(metrics.uptime_seconds)}</dd>
              </div>
            )}
            {metrics.container_status && (
              <div>
                <dt className="text-sm text-gray-500">Container Status</dt>
                <dd className="font-medium text-gray-900 capitalize">{metrics.container_status}</dd>
              </div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}
