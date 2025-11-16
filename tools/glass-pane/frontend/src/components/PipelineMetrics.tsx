import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Phase, PhaseStatus } from '../types/job';
import { formatDuration } from '../utils/formatters';

interface PhaseDetail {
  name: string;
  tokens_used: number;
  percentage: number;
  duration_seconds: number;
  budget_allocated: number;
  over_budget: boolean;
  exit_code: number;
  timestamp: string;
  status?: string;
}

interface PhaseBreakdownData {
  phases: PhaseDetail[];
  total_tokens: number;
  max_context_window: number;
  model: string;
  current_phase?: {
    name: string;
    status: string;
    description: string;
  };
}

interface PipelineMetricsProps {
  jobId: string | null;
  currentPhase: Phase | null;
  status: PhaseStatus;
  description: string;
  jobStatus?: string;
  completedPhases?: Phase[];
  tokensUsed: number;
  startedAt: string | null;
  completedAt: string | null;
  totalFiles: number;
}

const PHASES: Phase[] = [
  Phase.Scout,
  Phase.Architect,
  Phase.Builder,
  Phase.Test,
  Phase.Screenshot,
  Phase.Documentation,
  Phase.Deploy,
];

const PHASE_ICONS: Record<Phase, string> = {
  [Phase.Scout]: '🔍',
  [Phase.Architect]: '📐',
  [Phase.Builder]: '🔨',
  [Phase.Test]: '🧪',
  [Phase.Screenshot]: '📸',
  [Phase.Documentation]: '📝',
  [Phase.Deploy]: '🚀',
};

// Claude Sonnet 4 pricing (blended rate)
const COST_PER_MILLION_TOKENS = 6.0;

export default function PipelineMetrics({
  jobId,
  currentPhase,
  status,
  description,
  jobStatus,
  completedPhases = [],
  tokensUsed,
  startedAt,
  completedAt,
  totalFiles,
}: PipelineMetricsProps) {
  const [phaseData, setPhaseData] = useState<PhaseBreakdownData | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Fetch phase breakdown data
  useEffect(() => {
    if (!jobId) {
      setPhaseData(null);
      return;
    }

    const fetchPhaseDetails = async () => {
      try {
        const response = await fetch(`/api/jobs/${jobId}/phases/detailed`);
        if (response.ok) {
          const result = await response.json();
          setPhaseData(result);
        }
      } catch (err) {
        console.error('Failed to fetch phase details:', err);
      }
    };

    fetchPhaseDetails();
  }, [jobId]);

  // Calculate elapsed time
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

    setElapsedTime(calculateDuration());

    if (jobStatus === 'running') {
      const interval = setInterval(() => {
        setElapsedTime(calculateDuration());
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [startedAt, completedAt, jobStatus]);

  const getPhaseStatus = (phase: Phase): PhaseStatus => {
    // Terminal job states
    if (jobStatus === 'succeeded' || jobStatus === 'failed' || jobStatus === 'cancelled') {
      if (completedPhases.includes(phase)) {
        return jobStatus === 'failed' ? PhaseStatus.Failed : PhaseStatus.Completed;
      }
      return PhaseStatus.Pending;
    }

    // Check current active phase FIRST (before checking completedPhases)
    if (currentPhase && phase === currentPhase) {
      return status; // Return the active status
    }

    // Then check if completed
    if (completedPhases.includes(phase)) {
      return PhaseStatus.Completed;
    }

    // Fallback to pending
    return PhaseStatus.Pending;
  };

  const getPhaseData = (phase: Phase) => {
    if (!phaseData?.phases) return null;

    const phaseName = phase.toLowerCase();
    return phaseData.phases.find(p =>
      p.name.toLowerCase().includes(phaseName)
    );
  };

  const formatPhaseName = (phase: Phase): string => {
    return phase;
  };

  const calculateCost = (tokens: number): number => {
    return (tokens / 1_000_000) * COST_PER_MILLION_TOKENS;
  };

  const totalCost = calculateCost(tokensUsed);

  return (
    <div className="h-full flex flex-col">
      {/* Overall Summary Bar */}
      <div className="bg-gradient-to-r from-gray-800 to-gray-900 border border-gray-700 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-100">Build Pipeline</h2>
          <span className={`text-xs font-semibold px-3 py-1 rounded-full ${
            jobStatus === 'running' ? 'bg-cyan-500/20 text-cyan-400' :
            jobStatus === 'succeeded' ? 'bg-green-500/20 text-green-400' :
            jobStatus === 'failed' ? 'bg-red-500/20 text-red-400' :
            'bg-gray-500/20 text-gray-400'
          }`}>
            {jobStatus?.charAt(0).toUpperCase() + jobStatus?.slice(1) || 'Unknown'}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Total Duration</div>
            <div className="text-lg font-semibold text-cyan-400">{formatDuration(elapsedTime)}</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Total Tokens</div>
            <div className="text-lg font-semibold text-purple-400">{tokensUsed.toLocaleString()}</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Total Cost</div>
            <div className="text-lg font-semibold text-green-400">${totalCost.toFixed(3)}</div>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-xs text-gray-400 mb-1">Files Created</div>
            <div className="text-lg font-semibold text-orange-400">{totalFiles}</div>
          </div>
        </div>
      </div>

      {/* Phase Bars */}
      <div className="flex-1 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3 auto-rows-fr content-start overflow-auto">
        {PHASES.map((phase) => {
          const phaseStatus = getPhaseStatus(phase);
          const phaseDetail = getPhaseData(phase);
          const isActive = phaseStatus === PhaseStatus.Active;
          const isCompleted = phaseStatus === PhaseStatus.Completed;
          const isFailed = phaseStatus === PhaseStatus.Failed;
          const isPending = phaseStatus === PhaseStatus.Pending;

          const phaseTokens = phaseDetail?.tokens_used || 0;
          const phaseDuration = phaseDetail?.duration_seconds || 0;
          const phaseCost = calculateCost(phaseTokens);

          return (
            <motion.div
              key={phase}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: PHASES.indexOf(phase) * 0.1 }}
              className={`bg-gray-800 border rounded-lg p-4 flex flex-col min-h-[360px] ${
                isActive ? 'border-cyan-500 shadow-lg shadow-cyan-500/20' :
                isCompleted ? 'border-green-500/50' :
                isFailed ? 'border-red-500/50' :
                'border-gray-700'
              }`}
            >
              {/* Phase Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div>
                    <div className={`text-sm font-semibold ${
                      isActive ? 'text-cyan-400' :
                      isCompleted ? 'text-green-400' :
                      isFailed ? 'text-red-400' :
                      'text-gray-400'
                    }`}>
                      {formatPhaseName(phase)}
                    </div>
                  </div>
                </div>
                <div className="text-xs">
                  {isCompleted && <span className="text-green-400">✓</span>}
                  {isFailed && <span className="text-red-400">✗</span>}
                  {isActive && (
                    <motion.div
                      className="w-2 h-2 bg-cyan-400 rounded-full"
                      animate={{ opacity: [1, 0.3, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                  )}
                  {isPending && <span className="text-gray-600">○</span>}
                </div>
              </div>

              {/* Status Badge */}
              <div className="mb-3">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  isActive ? 'bg-cyan-500/20 text-cyan-400' :
                  isCompleted ? 'bg-green-500/20 text-green-400' :
                  isFailed ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-700 text-gray-500'
                }`}>
                  {isCompleted && 'Complete'}
                  {isActive && 'In Progress'}
                  {isFailed && 'Failed'}
                  {isPending && 'Pending'}
                </span>
              </div>

              {/* Metrics */}
              {(isCompleted || isActive) && phaseDetail && (
                <div className="space-y-2">
                  {/* Tokens */}
                  <div className="bg-gray-900/50 rounded p-2">
                    <div className="text-xs text-gray-500 mb-1">Tokens</div>
                    <div className="text-sm font-semibold text-purple-400">
                      {phaseTokens.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-600">
                      of {(phaseDetail.budget_allocated / 1000).toFixed(0)}K budget
                    </div>
                  </div>

                  {/* Duration */}
                  <div className="bg-gray-900/50 rounded p-2">
                    <div className="text-xs text-gray-500 mb-1">Duration</div>
                    <div className="text-sm font-semibold text-cyan-400">
                      {formatDuration(phaseDuration)}
                    </div>
                  </div>

                  {/* Cost */}
                  <div className="bg-gray-900/50 rounded p-2">
                    <div className="text-xs text-gray-500 mb-1">Cost</div>
                    <div className="text-sm font-semibold text-green-400">
                      ${phaseCost.toFixed(3)}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {phaseDetail.budget_allocated > 0 && (
                    <div className="mt-2">
                      <div className="w-full bg-gray-700 rounded-full h-1.5 overflow-hidden">
                        <motion.div
                          className={`h-full ${
                            phaseDetail.over_budget ? 'bg-red-500' :
                            (phaseTokens / phaseDetail.budget_allocated) * 100 > 80 ? 'bg-yellow-500' :
                            'bg-cyan-500'
                          }`}
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min((phaseTokens / phaseDetail.budget_allocated) * 100, 100)}%` }}
                          transition={{ duration: 0.8 }}
                        />
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        {phaseTokens.toLocaleString()} / {phaseDetail.budget_allocated.toLocaleString()} tokens ({((phaseTokens / phaseDetail.budget_allocated) * 100).toFixed(0)}%)
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Pending state */}
              {isPending && (
                <div className="text-center text-gray-600 text-xs py-2">
                  Waiting...
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Current Phase Description */}
      {description && (
        <div className="mt-4 p-3 bg-gray-800 rounded-lg border border-gray-700">
          <div className="text-xs text-gray-400 mb-1">Current Activity</div>
          <p className="text-sm text-gray-300">
            {typeof description === 'string' ? description : JSON.stringify(description)}
          </p>
        </div>
      )}
    </div>
  );
}
