import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { calculateTokenZone } from '../utils/tokenBudget';
import { formatDuration } from '../utils/formatters';

interface MetricsPanelProps {
  tokensUsed: number;
  duration: number;
  totalFiles: number;
  status: string;
}

const TOKEN_BUDGET = 200000;

export default function MetricsPanel({ tokensUsed, duration, totalFiles, status }: MetricsPanelProps) {
  const [elapsedTime, setElapsedTime] = useState(duration);

  // Update elapsed time every second for running jobs
  useEffect(() => {
    if (status === 'running') {
      const interval = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);

      return () => clearInterval(interval);
    } else {
      setElapsedTime(duration);
    }
  }, [status, duration]);

  const tokenPercentage = (tokensUsed / TOKEN_BUDGET) * 100;
  const zone = calculateTokenZone(tokensUsed, TOKEN_BUDGET);

  const getZoneColor = () => {
    switch (zone) {
      case 'green':
        return 'text-green-500';
      case 'yellow':
        return 'text-yellow-500';
      case 'red':
        return 'text-red-500';
      default:
        return 'text-gray-500';
    }
  };

  const getZoneGradient = () => {
    switch (zone) {
      case 'green':
        return 'from-green-500 to-green-600';
      case 'yellow':
        return 'from-yellow-500 to-orange-500';
      case 'red':
        return 'from-red-500 to-red-600';
      default:
        return 'from-gray-500 to-gray-600';
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-6">
      <h2 className="text-lg font-semibold text-gray-100">Metrics</h2>

      {/* Token Budget Gauge */}
      <div>
        <div className="flex justify-between items-baseline mb-2">
          <span className="text-sm text-gray-400">Token Budget</span>
          <span className={`text-sm font-medium ${getZoneColor()}`}>
            {tokenPercentage.toFixed(1)}%
          </span>
        </div>

        {/* Circular Progress */}
        <div className="relative w-32 h-32 mx-auto">
          <svg className="w-full h-full transform -rotate-90">
            {/* Background Circle */}
            <circle
              cx="64"
              cy="64"
              r="56"
              className="stroke-gray-700"
              strokeWidth="8"
              fill="none"
            />
            {/* Progress Circle */}
            <motion.circle
              cx="64"
              cy="64"
              r="56"
              className={`stroke-current bg-gradient-to-br ${getZoneGradient()}`}
              strokeWidth="8"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 56}`}
              initial={{ strokeDashoffset: 2 * Math.PI * 56 }}
              animate={{ strokeDashoffset: 2 * Math.PI * 56 * (1 - tokenPercentage / 100) }}
              transition={{ duration: 1, ease: 'easeOut' }}
              style={{
                filter: 'drop-shadow(0 0 8px currentColor)',
              }}
            />
          </svg>

          {/* Center Text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className={`text-2xl font-bold ${getZoneColor()}`}>
              {(tokensUsed / 1000).toFixed(1)}K
            </div>
            <div className="text-xs text-gray-500">/ {TOKEN_BUDGET / 1000}K</div>
          </div>
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
