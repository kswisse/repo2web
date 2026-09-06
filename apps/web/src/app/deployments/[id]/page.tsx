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
