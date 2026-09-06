'use client';

import { useRouter } from 'next/navigation';
import { Header } from '@/components/Header';
import { DeploymentForm } from '@/components/DeploymentForm';

export default function HomePage() {
  const router = useRouter();

  const handleDeploymentCreated = (deploymentId: string) => {
    router.push(`/deployments/${deploymentId}`);
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Turn GitHub repositories into running apps.
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Paste a GitHub URL, and we&apos;ll analyze, build, and deploy it as a live web application.
          </p>
        </div>

        <DeploymentForm onDeploymentCreated={handleDeploymentCreated} />

        <div className="mt-12 text-center text-sm text-gray-500">
          <p>Supported: React, Vue, Angular, Next.js, Node.js, Python (Flask, Django, FastAPI)</p>
        </div>
      </main>
    </div>
  );
}
