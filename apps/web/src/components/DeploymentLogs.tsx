'use client';

import { useEffect, useRef, useState } from 'react';
import type { DeploymentLogEntry } from '@/lib/api/deployments';

interface DeploymentLogsProps {
  logs: DeploymentLogEntry[];
  isLoading?: boolean;
}

const MAX_VISIBLE_LOGS = 200;

const LEVEL_COLORS: Record<string, string> = {
  info: 'text-gray-700',
  warning: 'text-yellow-600',
  error: 'text-red-600',
  debug: 'text-gray-500',
};

const STAGE_LABELS: Record<string, string> = {
  clone: 'CLONE',
  analyze: 'ANALYZE',
  plan: 'PLAN',
  build: 'BUILD',
  start: 'START',
  health_check: 'HEALTH',
  runtime: 'RUNTIME',
};

export function DeploymentLogs({ logs, isLoading }: DeploymentLogsProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const prevLogCountRef = useRef(logs.length);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAutoScroll && containerRef.current && logs.length > prevLogCountRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
    prevLogCountRef.current = logs.length;
  }, [logs.length, isAutoScroll]);

  // Handle scroll to detect manual scrolling
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setIsAutoScroll(isAtBottom);
  };

  const visibleLogs = logs.slice(-MAX_VISIBLE_LOGS);

  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h3 className="text-md font-semibold text-gray-900">
          Build Logs
          {logs.length > MAX_VISIBLE_LOGS && (
            <span className="text-sm font-normal text-gray-500 ml-2">
              (showing last {MAX_VISIBLE_LOGS} of {logs.length})
            </span>
          )}
        </h3>
        <button
          onClick={() => setIsAutoScroll(!isAutoScroll)}
          className={`text-sm px-3 py-1 rounded ${
            isAutoScroll
              ? 'bg-blue-100 text-blue-700'
              : 'bg-gray-100 text-gray-700'
          }`}
        >
          {isAutoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
        </button>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-96 overflow-y-auto font-mono text-sm p-4 bg-gray-50"
        role="log"
        aria-label="Deployment logs"
      >
        {visibleLogs.length === 0 && !isLoading && (
          <p className="text-gray-500 text-center py-8">No logs yet</p>
        )}
        {visibleLogs.map((log) => (
          <div key={log.id} className="flex items-start gap-2 py-1 hover:bg-gray-100">
            <span className="text-gray-400 text-xs w-20 flex-shrink-0">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={`text-xs font-bold w-16 flex-shrink-0 ${
                LEVEL_COLORS[log.level] || 'text-gray-700'
              }`}
            >
              [{STAGE_LABELS[log.stage] || log.stage.toUpperCase()}]
            </span>
            <span className={`${LEVEL_COLORS[log.level] || 'text-gray-700'} break-words`}>
              {log.message}
            </span>
          </div>
        ))}
        {isLoading && (
          <div className="text-center py-4 text-gray-500">
            Loading logs...
          </div>
        )}
      </div>
    </div>
  );
}
