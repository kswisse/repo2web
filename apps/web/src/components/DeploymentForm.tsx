'use client';

import { useState } from 'react';
import { createDeployment } from '@/lib/api/deployments';

interface DeploymentFormProps {
  onDeploymentCreated?: (deploymentId: string) => void;
}

export function DeploymentForm({ onDeploymentCreated }: DeploymentFormProps) {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValidUrl = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+/.test(url);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidUrl || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await createDeployment(url);
      onDeploymentCreated?.(response.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create deployment');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Deploy a Repository</h2>
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/user/repo"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-gray-900 placeholder-gray-400"
          disabled={isLoading}
          aria-label="GitHub repository URL"
        />
        <button
          type="submit"
          disabled={!isValidUrl || isLoading}
          className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? 'Deploying...' : 'Deploy'}
        </button>
      </form>
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
