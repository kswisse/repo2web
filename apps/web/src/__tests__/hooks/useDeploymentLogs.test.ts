import { renderHook, waitFor } from '@testing-library/react';
import { useDeploymentLogs } from '@/hooks/useDeploymentLogs';
import { getDeploymentLogs } from '@/lib/api/deployments';

jest.mock('@/lib/api/deployments');

const mockGetDeploymentLogs = getDeploymentLogs as jest.MockedFunction<typeof getDeploymentLogs>;

describe('useDeploymentLogs', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns loading state initially', () => {
    mockGetDeploymentLogs.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useDeploymentLogs('test-id', 'running'));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.logs).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('fetches logs successfully', async () => {
    const mockLogs = [
      {
        id: '1',
        deployment_id: 'test-id',
        stage: 'clone',
        level: 'info',
        message: 'Cloning...',
        timestamp: new Date().toISOString(),
        sequence: 1,
      },
    ];

    mockGetDeploymentLogs.mockResolvedValueOnce({
      logs: mockLogs,
      total: 1,
    });

    const { result } = renderHook(() => useDeploymentLogs('test-id', 'running'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.logs).toEqual(mockLogs);
    expect(result.current.error).toBeNull();
  });

  it('handles errors', async () => {
    mockGetDeploymentLogs.mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() => useDeploymentLogs('test-id', 'running'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.logs).toEqual([]);
    expect(result.current.error).toBe('API error');
  });

  it('does not fetch when deploymentId is null', () => {
    const { result } = renderHook(() => useDeploymentLogs(null, 'running'));

    expect(result.current.isLoading).toBe(false);
    expect(mockGetDeploymentLogs).not.toHaveBeenCalled();
  });
});
