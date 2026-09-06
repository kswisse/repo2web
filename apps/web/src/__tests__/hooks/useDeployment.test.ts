import { renderHook, waitFor } from '@testing-library/react';
import { useDeployment } from '@/hooks/useDeployment';
import { getDeployment } from '@/lib/api/deployments';

jest.mock('@/lib/api/deployments');

const mockGetDeployment = getDeployment as jest.MockedFunction<typeof getDeployment>;

describe('useDeployment', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns loading state initially', () => {
    mockGetDeployment.mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useDeployment('test-id'));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.deployment).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('fetches deployment successfully', async () => {
    const mockDeployment = {
      id: 'test-id',
      state: 'running',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    mockGetDeployment.mockResolvedValueOnce(mockDeployment);

    const { result } = renderHook(() => useDeployment('test-id'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deployment).toEqual(mockDeployment);
    expect(result.current.error).toBeNull();
  });

  it('handles errors', async () => {
    mockGetDeployment.mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() => useDeployment('test-id'));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.deployment).toBeNull();
    expect(result.current.error).toBe('API error');
  });

  it('does not fetch when id is null', () => {
    const { result } = renderHook(() => useDeployment(null));

    expect(result.current.isLoading).toBe(false);
    expect(mockGetDeployment).not.toHaveBeenCalled();
  });
});
