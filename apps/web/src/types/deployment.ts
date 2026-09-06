export type DeploymentState = 
  | 'queued'
  | 'cloning'
  | 'analyzing'
  | 'planning'
  | 'building'
  | 'starting'
  | 'health_checking'
  | 'running'
  | 'clone_failed'
  | 'analysis_failed'
  | 'plan_failed'
  | 'build_failed'
  | 'start_failed'
  | 'health_check_failed'
  | 'security_blocked'
  | 'timeout'
  | 'cancelled';

export const PIPELINE_STAGES = ['clone', 'analyze', 'plan', 'build', 'start', 'health_check'] as const;

export type PipelineStage = typeof PIPELINE_STAGES[number];

export const STATE_LABELS: Record<DeploymentState, string> = {
  queued: 'Queued',
  cloning: 'Cloning Repository',
  analyzing: 'Analyzing Code',
  planning: 'Generating Plan',
  building: 'Building Application',
  starting: 'Starting Runtime',
  health_checking: 'Checking Health',
  running: 'Application Running',
  clone_failed: 'Clone Failed',
  analysis_failed: 'Analysis Failed',
  plan_failed: 'Plan Failed',
  build_failed: 'Build Failed',
  start_failed: 'Start Failed',
  health_check_failed: 'Health Check Failed',
  security_blocked: 'Security Blocked',
  timeout: 'Timed Out',
  cancelled: 'Cancelled',
};

export const STATE_COLORS: Record<DeploymentState, string> = {
  queued: 'bg-gray-100 text-gray-700',
  cloning: 'bg-blue-100 text-blue-700',
  analyzing: 'bg-blue-100 text-blue-700',
  planning: 'bg-blue-100 text-blue-700',
  building: 'bg-yellow-100 text-yellow-700',
  starting: 'bg-yellow-100 text-yellow-700',
  health_checking: 'bg-yellow-100 text-yellow-700',
  running: 'bg-green-100 text-green-700',
  clone_failed: 'bg-red-100 text-red-700',
  analysis_failed: 'bg-red-100 text-red-700',
  plan_failed: 'bg-red-100 text-red-700',
  build_failed: 'bg-red-100 text-red-700',
  start_failed: 'bg-red-100 text-red-700',
  health_check_failed: 'bg-red-100 text-red-700',
  security_blocked: 'bg-red-100 text-red-700',
  timeout: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-700',
};

export const TERMINAL_STATES: DeploymentState[] = [
  'running',
  'clone_failed',
  'analysis_failed',
  'plan_failed',
  'build_failed',
  'start_failed',
  'health_check_failed',
  'security_blocked',
  'timeout',
  'cancelled',
];

export const ACTIVE_STATES: DeploymentState[] = [
  'queued',
  'cloning',
  'analyzing',
  'planning',
  'building',
  'starting',
  'health_checking',
];

export function isTerminalState(state: DeploymentState): boolean {
  return TERMINAL_STATES.includes(state);
}

export function isActiveState(state: DeploymentState): boolean {
  return ACTIVE_STATES.includes(state);
}

export function getStageForState(state: DeploymentState): PipelineStage | null {
  const stageMap: Partial<Record<DeploymentState, PipelineStage>> = {
    cloning: 'clone',
    analyzing: 'analyze',
    planning: 'plan',
    building: 'build',
    starting: 'start',
    health_checking: 'health_check',
    running: 'health_check',
    // Failure states map to their corresponding stage
    clone_failed: 'clone',
    analysis_failed: 'analyze',
    plan_failed: 'plan',
    build_failed: 'build',
    start_failed: 'start',
    health_check_failed: 'health_check',
  };
  return stageMap[state] ?? null;
}
