"use client";

import { useState } from "react";

interface Props {
  onAnalyze: (url: string) => void;
  isLoading: boolean;
}

export function RepositoryInput({ onAnalyze, isLoading }: Props) {
  const [url, setUrl] = useState("");

  const isValidUrl = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+/.test(url);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isValidUrl && !isLoading) {
      onAnalyze(url);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 max-w-2xl mx-auto">
      <input
        type="text"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://github.com/user/repo"
        className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-gray-900 placeholder-gray-400"
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={!isValidUrl || isLoading}
        className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? "Analyzing..." : "Analyze"}
      </button>
    </form>
  );
}
