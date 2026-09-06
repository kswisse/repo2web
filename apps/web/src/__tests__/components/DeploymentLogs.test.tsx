import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { DeploymentLogs } from '@/components/DeploymentLogs';
import { DeploymentLogEntry } from '@/lib/api/deployments';

const mockLogs: DeploymentLogEntry[] = [
  {
    id: '1',
    deployment_id: 'test-deployment',
    stage: 'clone',
    level: 'info',
    message: 'Cloning repository...',
    timestamp: new Date().toISOString(),
    sequence: 1,
  },
  {
    id: '2',
    deployment_id: 'test-deployment',
    stage: 'build',
    level: 'info',
    message: 'Building application...',
    timestamp: new Date().toISOString(),
    sequence: 2,
  },
  {
    id: '3',
    deployment_id: 'test-deployment',
    stage: 'build',
    level: 'error',
    message: 'Build failed',
    timestamp: new Date().toISOString(),
    sequence: 3,
  },
];

describe('DeploymentLogs', () => {
  it('renders logs correctly', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    expect(screen.getByText('Cloning repository...')).toBeInTheDocument();
    expect(screen.getByText('Building application...')).toBeInTheDocument();
    expect(screen.getByText('Build failed')).toBeInTheDocument();
  });

  it('shows no logs message when empty', () => {
    render(<DeploymentLogs logs={[]} />);
    
    expect(screen.getByText('No logs yet')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<DeploymentLogs logs={[]} isLoading={true} />);
    
    expect(screen.getByText('Loading logs...')).toBeInTheDocument();
  });

  it('displays stage labels correctly', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    expect(screen.getByText('[CLONE]')).toBeInTheDocument();
    // There are two BUILD logs
    const buildLabels = screen.getAllByText('[BUILD]');
    expect(buildLabels).toHaveLength(2);
  });

  it('applies correct colors for different log levels', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    const errorLog = screen.getByText('Build failed');
    expect(errorLog).toHaveClass('text-red-600');
  });

  it('has auto-scroll button', () => {
    render(<DeploymentLogs logs={mockLogs} />);
    
    expect(screen.getByText('Auto-scroll ON')).toBeInTheDocument();
  });
});
