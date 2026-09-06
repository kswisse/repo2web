"use client";

import { useState } from "react";

interface Props {
  url: string;
}

export function DeploymentUrl({ url }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-6">
      <h3 className="text-md font-semibold text-green-900 mb-3">Your App is Running</h3>
      <div className="flex items-center gap-3">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline font-mono text-sm"
        >
          {url}
        </a>
        <button
          onClick={handleCopy}
          className="px-3 py-1 text-sm bg-white border border-green-300 rounded hover:bg-green-50 transition-colors"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
  );
}
