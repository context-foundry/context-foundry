import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Phase, PhaseStatus } from '../types/job';
import { formatDuration } from '../utils/formatters';
import ParallelAgents from './ParallelAgents';

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
    parallel_build_info?: {
      parallel_mode: boolean;
      total_tasks: number;
      current_wave: number;
      max_wave: number;
      tasks_per_wave: Record<string, number>;
      max_concurrent_agents: number;
    };
  };
  deployment?: {
    status: string; // "success", "skipped", "failed"
    reason?: string; // Error/skip reason
    commit_sha?: string;
    repository_url?: string;
    local_commit_created?: boolean;
    attempted_at?: string;
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
  projectName?: string;
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
  projectName,
}: PipelineMetricsProps) {
  const [phaseData, setPhaseData] = useState<PhaseBreakdownData | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [agentsExpanded, setAgentsExpanded] = useState(false);

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

    // Poll for updates while job is running
    if (jobStatus === 'running') {
      const interval = setInterval(fetchPhaseDetails, 5000); // Refresh every 5 seconds
      return () => clearInterval(interval);
    }
  }, [jobId, jobStatus]);

  // Calculate elapsed time
  useEffect(() => {
    if (!startedAt) {
      setElapsedTime(0);
      return;
    }

    const calculateDuration = () => {
      const start = new Date(startedAt).getTime();
      const end = completedAt ? new Date(completedAt).getTime() : Date.now();
      const duration = Math.floor((end - start) / 1000);
      // Prevent negative durations from bad timestamp data
      return Math.max(0, duration);
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
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-100">
              Build Pipeline{projectName ? `: ${projectName}` : ''}
            </h2>
            {phaseData?.deployment && (
              <div className="flex items-center gap-2">
                {phaseData.deployment.status === 'success' && phaseData.deployment.repository_url && (
                  <a
                    href={phaseData.deployment.repository_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-sm text-green-400 hover:text-green-300 transition-colors"
                    title="View on GitHub"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                      <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                    </svg>
                    <span>✓ Deployed</span>
                  </a>
                )}
                {phaseData.deployment.status === 'skipped' && (
                  <div className="flex items-center gap-1.5 text-sm text-yellow-400" title={phaseData.deployment.reason}>
                    <span>⚠️</span>
                    <span>Deployment Skipped</span>
                  </div>
                )}
                {phaseData.deployment.status === 'failed' && (
                  <div className="flex items-center gap-1.5 text-sm text-red-400" title={phaseData.deployment.reason}>
                    <span>✗</span>
                    <span>Deployment Failed</span>
                  </div>
                )}
              </div>
            )}
          </div>
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

        {/* Parallel Build Info */}
        {phaseData?.current_phase?.parallel_build_info?.parallel_mode && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-cyan-900/30 border border-cyan-700/50 rounded-md">
              <span className="text-cyan-400">🚀</span>
              <span className="text-sm text-cyan-300 font-medium">Parallel Build Active</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-md">
              <span className="text-xs text-gray-400">Wave</span>
              <span className="text-sm text-white font-bold">
                {phaseData.current_phase.parallel_build_info.current_wave}/{phaseData.current_phase.parallel_build_info.max_wave}
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-900/30 border border-purple-700/50 rounded-md">
              <span className="text-purple-400">⚡</span>
              <span className="text-sm text-purple-300 font-medium">
                {phaseData.current_phase.parallel_build_info.max_concurrent_agents} agents max
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-md">
              <span className="text-xs text-gray-400">Tasks</span>
              <span className="text-sm text-white font-bold">
                {phaseData.current_phase.parallel_build_info.total_tasks}
              </span>
            </div>
          </div>
        )}

        {/* Parallel Builder Agents (expandable) - shows for both active and completed parallel builds */}
        {jobId && (
          <ParallelAgents
            jobId={jobId}
            isExpanded={agentsExpanded}
            onToggle={() => setAgentsExpanded(!agentsExpanded)}
          />
        )}
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

              {/* Active phase without metrics yet */}
              {isActive && !phaseDetail && (
                <div className="text-center py-6">
                  <motion.div
                    className="text-3xl mb-2"
                    animate={{ rotate: [0, 360] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  >
                    {PHASE_ICONS[phase]}
                  </motion.div>
                  <div className="text-xs text-cyan-400">
                    In Progress
                  </div>
                  {description && phase.toLowerCase() === currentPhase?.toLowerCase() && (
                    <div className="text-xs text-gray-500 mt-2">
                      {description}
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

      {/* Deployment Status Details */}
      {phaseData?.deployment && (phaseData.deployment.status === 'skipped' || phaseData.deployment.status === 'failed') && (
        <div className={`mt-4 p-4 rounded-lg border ${
          phaseData.deployment.status === 'skipped'
            ? 'bg-yellow-900/20 border-yellow-700/50'
            : 'bg-red-900/20 border-red-700/50'
        }`}>
          <div className="flex items-start gap-2 mb-2">
            <span className="text-lg">{phaseData.deployment.status === 'skipped' ? '⚠️' : '❌'}</span>
            <div className="flex-1">
              <div className="text-sm font-semibold text-gray-100 mb-1">
                Deployment {phaseData.deployment.status === 'skipped' ? 'Skipped' : 'Failed'}
              </div>
              {phaseData.deployment.reason && (
                <p className={`text-sm mb-3 ${
                  phaseData.deployment.status === 'skipped' ? 'text-yellow-300' : 'text-red-300'
                }`}>
                  {phaseData.deployment.reason}
                </p>
              )}

              {phaseData.deployment.local_commit_created && phaseData.deployment.commit_sha && (
                <div className="bg-gray-900/50 rounded p-2 mb-3">
                  <div className="text-xs text-gray-400 mb-1">Local Commit Created</div>
                  <code className="text-xs text-cyan-400 font-mono">{phaseData.deployment.commit_sha.substring(0, 8)}</code>
                </div>
              )}

              {/* Actionable fix instructions for common errors */}
              {phaseData.deployment.reason?.includes('public_repo scope') && (
                <div className="bg-gray-900/80 rounded-lg p-3 border border-gray-700">
                  <div className="text-xs font-semibold text-gray-300 mb-2">How to Fix</div>
                  <ol className="text-xs text-gray-400 space-y-1 list-decimal list-inside">
                    <li>Run: <code className="text-cyan-400 bg-gray-800 px-1 rounded">gh auth login --scopes public_repo</code></li>
                    <li>Re-authenticate with GitHub CLI</li>
                    <li>Manually push the commit: <code className="text-cyan-400 bg-gray-800 px-1 rounded">git push</code></li>
                  </ol>
                </div>
              )}
              {phaseData.deployment.reason?.includes('No GitHub token') && (
                <div className="bg-gray-900/80 rounded-lg p-3 border border-gray-700">
                  <div className="text-xs font-semibold text-gray-300 mb-2">How to Fix</div>
                  <ol className="text-xs text-gray-400 space-y-1 list-decimal list-inside">
                    <li>Run: <code className="text-cyan-400 bg-gray-800 px-1 rounded">gh auth login</code></li>
                    <li>Follow prompts to authenticate with GitHub</li>
                    <li>Ensure you grant the <code className="text-cyan-400">public_repo</code> scope</li>
                  </ol>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
