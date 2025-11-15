import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface PhaseDetail {
  name: string;
  tokens_used: number;
  percentage: number;
  duration_seconds: number;
  budget_allocated: number;
  over_budget: boolean;
  exit_code: number;
  timestamp: string;
}

interface PhaseBreakdownData {
  phases: PhaseDetail[];
  total_tokens: number;
  max_context_window: number;
  model: string;
}

interface PhaseBreakdownProps {
  jobId: string | null;
}

export default function PhaseBreakdown({ jobId }: PhaseBreakdownProps) {
  const [data, setData] = useState<PhaseBreakdownData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setData(null);
      return;
    }

    const fetchPhaseDetails = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/jobs/${jobId}/phases/detailed`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        setData(result);
      } catch (err) {
        console.error('Failed to fetch phase details:', err);
        setError('Failed to load phase breakdown');
        setData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchPhaseDetails();
  }, [jobId]);

  if (!jobId) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">Phase Breakdown</h2>
        <p className="text-gray-500 text-sm">Select a job to view phase details</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">Phase Breakdown</h2>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
        </div>
      </div>
    );
  }

  if (error || !data || data.phases.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">Phase Breakdown</h2>
        <p className="text-gray-500 text-sm">{error || 'No phase data available'}</p>
      </div>
    );
  }

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes}m ${secs}s`;
  };

  const formatPhaseName = (name: string): string => {
    return name
      .replace('phase_', '')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getPhaseIcon = (name: string): string => {
    if (name.includes('scout')) return '🔍';
    if (name.includes('architect')) return '📐';
    if (name.includes('builder')) return '🔨';
    if (name.includes('test')) return '🧪';
    if (name.includes('deploy')) return '🚀';
    return '⚙️';
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-gray-400">
          {data.model}
        </div>
      </div>

      {/* Overall Summary */}
      <div className="mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">Total Tokens Across All Phases</span>
          <span className="text-lg font-semibold text-cyan-400">
            {data.total_tokens.toLocaleString()} tokens
          </span>
        </div>
        <div className="mt-1 text-xs text-gray-500">
          Note: Each phase runs in its own context window with individual budgets
        </div>
      </div>

      {/* Phase List */}
      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
        {data.phases.map((phase, index) => {
          const phasePercentage = phase.budget_allocated > 0
            ? (phase.tokens_used / phase.budget_allocated) * 100
            : 0;

          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className="bg-gray-800 border border-gray-700 rounded-lg p-3 hover:border-gray-600 transition-colors"
            >
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div className="text-2xl flex-shrink-0">
                  {getPhaseIcon(phase.name)}
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <h3 className="font-medium text-gray-100">
                        {formatPhaseName(phase.name)}
                      </h3>
                      <p className="text-xs text-gray-500">
                        {formatDuration(phase.duration_seconds)}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-sm font-semibold text-cyan-400">
                        {phase.tokens_used.toLocaleString()}
                      </div>
                      <div className="text-xs text-gray-500">
                        {phasePercentage.toFixed(1)}% of budget
                      </div>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="relative">
                    <div className="w-full bg-gray-700 rounded-full h-1.5 overflow-hidden">
                      <motion.div
                        className={`h-full ${
                          phase.over_budget
                            ? 'bg-red-500'
                            : phasePercentage > 80
                            ? 'bg-yellow-500'
                            : 'bg-cyan-500'
                        }`}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(phasePercentage, 100)}%` }}
                        transition={{ duration: 0.8, delay: index * 0.05 }}
                      />
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs text-gray-600">
                        Budget: {phase.budget_allocated.toLocaleString()}
                      </span>
                      {phase.over_budget && (
                        <span className="text-xs text-red-400 font-medium">
                          Over Budget
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
