import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { DeploymentProgress } from '@/components/DeploymentProgress';

describe('DeploymentProgress', () => {
  it('renders all pipeline stages', () => {
    render(<DeploymentProgress state="queued" />);
    
    expect(screen.getByText('Clone')).toBeInTheDocument();
    expect(screen.getByText('Analyze')).toBeInTheDocument();
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Build')).toBeInTheDocument();
    expect(screen.getByText('Start')).toBeInTheDocument();
    expect(screen.getByText('Health Check')).toBeInTheDocument();
  });

  it('shows correct status for queued state', () => {
    render(<DeploymentProgress state="queued" />);
    
    const items = screen.getAllByRole('listitem');
    items.forEach((item) => {
      expect(item).toHaveAttribute('aria-label', expect.stringContaining('pending'));
    });
  });

  it('shows correct status for cloning state', () => {
    render(<DeploymentProgress state="cloning" />);
    
    const cloneItem = screen.getByText('Clone').closest('[role="listitem"]');
    expect(cloneItem).toHaveAttribute('aria-label', expect.stringContaining('active'));
  });

  it('shows correct status for building state', () => {
    render(<DeploymentProgress state="building" />);
    
    const cloneItem = screen.getByText('Clone').closest('[role="listitem"]');
    const analyzeItem = screen.getByText('Analyze').closest('[role="listitem"]');
    const planItem = screen.getByText('Plan').closest('[role="listitem"]');
    const buildItem = screen.getByText('Build').closest('[role="listitem"]');
    
    expect(cloneItem).toHaveAttribute('aria-label', expect.stringContaining('completed'));
    expect(analyzeItem).toHaveAttribute('aria-label', expect.stringContaining('completed'));
    expect(planItem).toHaveAttribute('aria-label', expect.stringContaining('completed'));
    expect(buildItem).toHaveAttribute('aria-label', expect.stringContaining('active'));
  });

  it('shows correct status for running state', () => {
    render(<DeploymentProgress state="running" />);
    
    const items = screen.getAllByRole('listitem');
    items.forEach((item) => {
      expect(item).toHaveAttribute('aria-label', expect.stringContaining('completed'));
    });
  });

  it('shows failed status for failed state', () => {
    render(<DeploymentProgress state="build_failed" />);
    
    const buildItem = screen.getByText('Build').closest('[role="listitem"]');
    expect(buildItem).toHaveAttribute('aria-label', expect.stringContaining('failed'));
  });
});
