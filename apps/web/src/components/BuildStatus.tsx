"use client";

import { useEffect, useState } from "react";
import { getDeploymentLogs, type DeploymentLogEntry } from "@/lib/api/deployments";

interface Props {
  deploymentId: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-200",
  running: "bg-blue-500",
  success: "bg-green-500",
  failed: "bg-red-500",
};

export function BuildStatus({ deploymentId }: Props) {
  const [logs, setLogs] = useState<DeploymentLogEntry[]>([]);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const data = await getDeploymentLogs(deploymentId);
        setLogs(data.logs);
      } catch {}
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [deploymentId]);

  if (logs.length === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-md font-semibold text-gray-900 mb-3">Build Logs</h3>
      <div className="space-y-2 max-h-64 overflow-y-auto font-mono text-sm">
        {logs.map((log) => (
          <div key={log.id} className="flex items-start gap-2">
            <div className={`w-2 h-2 rounded-full mt-1.5 ${STATUS_COLORS[log.level] || "bg-gray-300"}`} />
            <span className="text-gray-700">{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
