'use client';

import { useState, useEffect, useCallback } from 'react';
import { getDeploymentLogs, type DeploymentLogEntry } from '@/lib/api/deployments';
import { isActiveState, type DeploymentState } from '@/types/deployment';

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
