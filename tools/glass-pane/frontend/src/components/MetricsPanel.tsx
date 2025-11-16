import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { formatDuration } from '../utils/formatters';

interface MetricsPanelProps {
  tokensUsed: number;
  startedAt: string | null; // ISO 8601 timestamp
  completedAt: string | null; // ISO 8601 timestamp for completed jobs
  totalFiles: number;
  status: string;
}

// Claude Sonnet 4 pricing (blended rate: ~80% input $3/M, ~20% output $15/M)
const COST_PER_MILLION_TOKENS = 6.0;

export default function MetricsPanel({ tokensUsed, startedAt, completedAt, totalFiles, status }: MetricsPanelProps) {
  const [elapsedTime, setElapsedTime] = useState(0);

  // Calculate duration from timestamps
  useEffect(() => {
    if (!startedAt) {
      setElapsedTime(0);
      return;
    }

    const calculateDuration = () => {
      const start = new Date(startedAt).getTime();
      const end = completedAt ? new Date(completedAt).getTime() : Date.now();
      return Math.floor((end - start) / 1000);
    };

    // Set initial duration
    setElapsedTime(calculateDuration());

    // Update every second for running jobs
    if (status === 'running') {
      const interval = setInterval(() => {
        setElapsedTime(calculateDuration());
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [startedAt, completedAt, status]);

  // Calculate approximate cost
  const estimatedCost = (tokensUsed / 1_000_000) * COST_PER_MILLION_TOKENS;

  // Get color based on token usage milestones
  const getTokenColor = () => {
    if (tokensUsed < 50_000) return 'text-green-500';
    if (tokensUsed < 100_000) return 'text-yellow-500';
    return 'text-orange-500';
  };

  const getTokenGradient = () => {
    if (tokensUsed < 50_000) return 'from-green-500 to-green-600';
    if (tokensUsed < 100_000) return 'from-yellow-500 to-orange-500';
    return 'from-orange-500 to-red-500';
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-6">
      <h2 className="text-lg font-semibold text-gray-100">Metrics</h2>

      {/* Total Tokens Used */}
      <div className="p-4 bg-gray-800 rounded-lg">
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span className="text-sm text-gray-400">Total Tokens</span>
          </div>
          <div className="text-right">
            <div className={`text-lg font-semibold ${getTokenColor()}`}>
              {tokensUsed.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500">
              {(tokensUsed / 1000).toFixed(1)}K
            </div>
          </div>
        </div>
      </div>

      {/* Estimated Cost */}
      <div className="p-4 bg-gray-800 rounded-lg">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm text-gray-400">Est. Cost</span>
          </div>
          <span className="text-lg font-semibold text-green-400">
            ${estimatedCost.toFixed(3)}
          </span>
        </div>
      </div>

      {/* Duration */}
      <div className="p-4 bg-gray-800 rounded-lg">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm text-gray-400">Duration</span>
          </div>
          <span className="text-lg font-semibold text-gray-100">
            {formatDuration(elapsedTime)}
          </span>
        </div>
      </div>

      {/* Files Created */}
      <div className="p-4 bg-gray-800 rounded-lg">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            <span className="text-sm text-gray-400">Files Created</span>
          </div>
          <span className="text-lg font-semibold text-gray-100">{totalFiles}</span>
        </div>
      </div>

      {/* Status */}
      <div className="p-4 bg-gray-800 rounded-lg">
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-400">Status</span>
          <span className={`text-sm font-semibold px-3 py-1 rounded-full ${
            status === 'running' ? 'bg-cyan-500/20 text-cyan-400' :
            status === 'completed' ? 'bg-green-500/20 text-green-400' :
            status === 'failed' ? 'bg-red-500/20 text-red-400' :
            'bg-gray-500/20 text-gray-400'
          }`}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </span>
        </div>
      </div>
    </div>
  );
}
