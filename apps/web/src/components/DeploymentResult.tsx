import { isTerminalState, STATE_LABELS, type DeploymentState } from '@/types/deployment';
import type { Deployment } from '@/lib/api/deployments';

interface DeploymentResultProps {
  deployment: Deployment;
  onCancel?: () => void;
  isCancelling?: boolean;
}

export function DeploymentResult({ deployment, onCancel, isCancelling }: DeploymentResultProps) {
  const state = deployment.state as DeploymentState;
  const isTerminal = isTerminalState(state);
  const isRunning = state === 'running';
  const isFailed = state.endsWith('_failed') || state === 'security_blocked' || state === 'timeout';

  if (!isTerminal) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
            <span className="text-blue-700 font-medium">
              {STATE_LABELS[state] || state}
            </span>
          </div>
          {onCancel && (
            <button
              onClick={onCancel}
              disabled={isCancelling}
              className="px-4 py-2 text-sm bg-white border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isCancelling ? 'Cancelling...' : 'Cancel'}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (isRunning) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-green-500 rounded-full" />
          <span className="text-green-700 font-medium">
            {STATE_LABELS.running}
          </span>
        </div>
        <p className="mt-2 text-sm text-green-600">
          Your application is now live and running.
        </p>
      </div>
    );
  }

  if (isFailed) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 bg-red-500 rounded-full" />
          <span className="text-red-700 font-medium">
            {STATE_LABELS[state] || state}
          </span>
        </div>
        {deployment.error_message && (
          <p className="mt-2 text-sm text-red-600">
            {deployment.error_message}
          </p>
        )}
      </div>
    );
  }

  // Cancelled or other terminal states
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
      <div className="flex items-center gap-3">
        <div className="w-3 h-3 bg-gray-400 rounded-full" />
        <span className="text-gray-700 font-medium">
          {STATE_LABELS[state] || state}
        </span>
      </div>
    </div>
  );
}
