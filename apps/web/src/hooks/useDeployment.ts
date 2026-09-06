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
