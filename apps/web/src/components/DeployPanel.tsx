'use client';

import { useRouter } from 'next/navigation';
import { DeploymentForm } from '@/components/DeploymentForm';

export function DeployPanel() {
  const router = useRouter();

  const handleDeploymentCreated = (deploymentId: string) => {
    router.push(`/deployments/${deploymentId}`);
  };

  return <DeploymentForm onDeploymentCreated={handleDeploymentCreated} />;
}
