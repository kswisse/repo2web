import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeploymentForm } from '@/components/DeploymentForm';

// Mock the API
jest.mock('@/lib/api/deployments', () => ({
  createDeployment: jest.fn(),
}));

import { createDeployment } from '@/lib/api/deployments';

const mockCreateDeployment = createDeployment as jest.MockedFunction<typeof createDeployment>;

describe('DeploymentForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the form with input and button', () => {
    render(<DeploymentForm />);
    
    expect(screen.getByLabelText(/github repository url/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deploy/i })).toBeInTheDocument();
  });

  it('disables deploy button for invalid URLs', async () => {
    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'not-a-valid-url');
    expect(button).toBeDisabled();
  });

  it('enables deploy button for valid GitHub URLs', async () => {
    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    expect(button).toBeEnabled();
  });

  it('calls createDeployment with valid URL', async () => {
    mockCreateDeployment.mockResolvedValueOnce({
      id: 'test-id',
      state: 'queued',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    const onDeploymentCreated = jest.fn();
    render(<DeploymentForm onDeploymentCreated={onDeploymentCreated} />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    await userEvent.click(button);
    
    await waitFor(() => {
      expect(mockCreateDeployment).toHaveBeenCalledWith('https://github.com/user/repo');
    });
    
    await waitFor(() => {
      expect(onDeploymentCreated).toHaveBeenCalledWith('test-id');
    });
  });

  it('displays error message on API failure', async () => {
    mockCreateDeployment.mockRejectedValueOnce(new Error('API error'));

    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    await userEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('API error');
    });
  });

  it('shows loading state during deployment', async () => {
    mockCreateDeployment.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<DeploymentForm />);
    
    const input = screen.getByLabelText(/github repository url/i);
    const button = screen.getByRole('button', { name: /deploy/i });
    
    await userEvent.type(input, 'https://github.com/user/repo');
    await userEvent.click(button);
    
    await waitFor(() => {
      expect(button).toHaveTextContent('Deploying...');
      expect(button).toBeDisabled();
    });
  });
});
