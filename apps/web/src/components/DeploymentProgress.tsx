import { 
  PIPELINE_STAGES, 
  getStageForState, 
  isTerminalState,
  type DeploymentState,
  type PipelineStage 
} from '@/types/deployment';

interface DeploymentProgressProps {
  state: DeploymentState;
  errorStage?: string | null;
}

const STAGE_LABELS: Record<PipelineStage, string> = {
  clone: 'Clone',
  analyze: 'Analyze',
  plan: 'Plan',
  build: 'Build',
  start: 'Start',
  health_check: 'Health Check',
};

function getStageStatus(
  stage: PipelineStage,
  currentState: DeploymentState,
  errorStage?: string | null
): 'completed' | 'active' | 'failed' | 'pending' {
  const currentStage = getStageForState(currentState);
  
  // If deployment failed at this stage
  if (errorStage === stage || 
      (currentState.includes('_failed') && currentStage === stage)) {
    return 'failed';
  }
  
  // If deployment is in terminal state and succeeded
  if (currentState === 'running' && stage === 'health_check') {
    return 'completed';
  }
  
  // Find stage index
  const stageIndex = PIPELINE_STAGES.indexOf(stage);
  const currentStageIndex = currentStage ? PIPELINE_STAGES.indexOf(currentStage) : -1;
  
  if (stageIndex < currentStageIndex) {
    return 'completed';
  } else if (stageIndex === currentStageIndex) {
    return 'active';
  } else {
    return 'pending';
  }
}

export function DeploymentProgress({ state, errorStage }: DeploymentProgressProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-md font-semibold text-gray-900 mb-4">Pipeline Progress</h3>
      <div className="space-y-3">
        {PIPELINE_STAGES.map((stage) => {
          const status = getStageStatus(stage, state, errorStage);
          return (
            <div
              key={stage}
              className="flex items-center gap-3"
              role="listitem"
              aria-label={`${STAGE_LABELS[stage]}: ${status}`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center ${
                  status === 'completed'
                    ? 'bg-green-500'
                    : status === 'active'
                    ? 'bg-blue-500'
                    : status === 'failed'
                    ? 'bg-red-500'
                    : 'bg-gray-200'
                }`}
                aria-hidden="true"
              >
                {status === 'completed' && (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {status === 'active' && (
                  <svg className="w-4 h-4 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                )}
                {status === 'failed' && (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                {status === 'pending' && (
                  <div className="w-2 h-2 bg-gray-400 rounded-full" />
                )}
              </div>
              <span
                className={`text-sm font-medium ${
                  status === 'completed'
                    ? 'text-green-700'
                    : status === 'active'
                    ? 'text-blue-700'
                    : status === 'failed'
                    ? 'text-red-700'
                    : 'text-gray-500'
                }`}
              >
                {STAGE_LABELS[stage]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
