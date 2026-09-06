import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Deployment | Repo2Web',
  description: 'View deployment progress and logs',
};

export default function DeploymentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
