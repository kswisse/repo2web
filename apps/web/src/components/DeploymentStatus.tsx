import type { Deployment } from "@/lib/types";

interface Props {
  deployment: Deployment;
}

const STATE_LABELS: Record<string, string> = {
  queued: "Queued",
  cloning: "Cloning",
  analyzing: "Analyzing",
  planning: "Planning",
  building: "Building",
  starting: "Starting",
  health_checking: "Checking Health",
  running: "Running",
  clone_failed: "Clone Failed",
  analysis_failed: "Analysis Failed",
  plan_failed: "Plan Failed",
  build_failed: "Build Failed",
  start_failed: "Start Failed",
  health_check_failed: "Health Check Failed",
  security_blocked: "Security Blocked",
  timeout: "Timeout",
  cancelled: "Cancelled",
};

const STATE_COLORS: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  cloning: "bg-blue-100 text-blue-700",
  analyzing: "bg-blue-100 text-blue-700",
  planning: "bg-blue-100 text-blue-700",
  building: "bg-yellow-100 text-yellow-700",
  starting: "bg-yellow-100 text-yellow-700",
  health_checking: "bg-yellow-100 text-yellow-700",
  running: "bg-green-100 text-green-700",
  clone_failed: "bg-red-100 text-red-700",
  analysis_failed: "bg-red-100 text-red-700",
  plan_failed: "bg-red-100 text-red-700",
  build_failed: "bg-red-100 text-red-700",
  start_failed: "bg-red-100 text-red-700",
  health_check_failed: "bg-red-100 text-red-700",
  security_blocked: "bg-red-100 text-red-700",
  timeout: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-700",
};

export function DeploymentStatus({ deployment }: Props) {
  const colorClass = STATE_COLORS[deployment.status] || "bg-gray-100 text-gray-700";

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-md font-semibold text-gray-900 mb-3">Deployment Status</h3>
      <div className="flex items-center gap-3">
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${colorClass}`}>
          {STATE_LABELS[deployment.status] || deployment.status}
        </span>
        <span className="text-sm text-gray-500">
          ID: {deployment.id.slice(0, 8)}...
        </span>
      </div>
    </div>
  );
}
