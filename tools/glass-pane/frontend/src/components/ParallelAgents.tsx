import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ParallelAgent } from '../types/api';

interface ParallelAgentsProps {
  jobId: string;
  isExpanded: boolean;
  onToggle: () => void;
}

const STATUS_COLORS = {
  in_progress: 'bg-cyan-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
};

const STATUS_ICONS = {
  in_progress: '🔄',
  completed: '✅',
  failed: '❌',
};

const STATUS_LABELS = {
  in_progress: 'In Progress',
  completed: 'Complete',
  failed: 'Failed',
};

function AgentCard({ agent }: { agent: ParallelAgent }) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-800 border border-gray-700 rounded-lg p-3"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{STATUS_ICONS[agent.status]}</span>
            <h4 className="text-sm font-semibold text-white truncate">
              {agent.task_name}
            </h4>
          </div>

          <p className="text-xs text-gray-400 mb-2">{agent.description}</p>

          <div className="flex items-center gap-3 text-xs">
            <div className={`px-2 py-0.5 rounded ${STATUS_COLORS[agent.status]} text-white`}>
              {STATUS_LABELS[agent.status]}
            </div>
            <div className="text-gray-400">Wave {agent.wave}</div>
            {agent.duration && (
              <div className="text-gray-400">{agent.duration.toFixed(1)}s</div>
            )}
            {agent.files.length > 0 && (
              <div className="text-gray-400">{agent.files.length} files</div>
            )}
          </div>

          {/* Error Display */}
          {agent.error && (
            <div className="mt-2 p-2 bg-red-900/30 border border-red-700/50 rounded text-xs text-red-300">
              <strong>Error:</strong> {agent.error}
            </div>
          )}
        </div>

        {/* Expand/Collapse Details Button */}
        {agent.files.length > 0 && (
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="ml-2 px-2 py-1 text-xs text-gray-400 hover:text-white transition-colors"
          >
            {showDetails ? '▼' : '▶'}
          </button>
        )}
      </div>

      {/* Expanded File List */}
      <AnimatePresence>
        {showDetails && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-2 pt-2 border-t border-gray-700"
          >
            <div className="text-xs text-gray-400 mb-1">Files ({agent.files.length}):</div>
            <ul className="space-y-1 max-h-32 overflow-y-auto">
              {agent.files.map((file, idx) => (
                <li key={idx} className="text-xs text-gray-300 font-mono">
                  {file}
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ParallelAgents({ jobId, isExpanded, onToggle }: ParallelAgentsProps) {
  const [agents, setAgents] = useState<ParallelAgent[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasParallelBuild, setHasParallelBuild] = useState(false);

  useEffect(() => {
    if (!isExpanded) return;

    const fetchAgents = async () => {
      try {
        setLoading(true);
        const response = await fetch(
          `http://localhost:8000/api/files/parallel-agents?job_id=${jobId}`
        );

        if (!response.ok) {
          throw new Error('Failed to fetch agents');
        }

        const data = await response.json();
        setAgents(data.agents || []);
        setHasParallelBuild(data.has_parallel_build);
      } catch (error) {
        console.error('Error fetching parallel agents:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();

    // Poll every 2 seconds for updates
    const interval = setInterval(fetchAgents, 2000);

    return () => clearInterval(interval);
  }, [jobId, isExpanded]);

  if (!hasParallelBuild && agents.length === 0) {
    return null; // Don't show if no parallel build
  }

  const inProgressCount = agents.filter(a => a.status === 'in_progress').length;
  const completedCount = agents.filter(a => a.status === 'completed').length;
  const failedCount = agents.filter(a => a.status === 'failed').length;

  return (
    <div className="mt-3 border-t border-gray-700 pt-3">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-800 hover:bg-gray-750 rounded-lg transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{isExpanded ? '▼' : '▶'}</span>
          <span className="font-semibold text-white">
            Parallel Builder Agents ({agents.length})
          </span>
        </div>

        <div className="flex items-center gap-3 text-sm">
          {inProgressCount > 0 && (
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
              <span className="text-cyan-300">{inProgressCount} active</span>
            </div>
          )}
          {completedCount > 0 && (
            <div className="text-green-300">✅ {completedCount}</div>
          )}
          {failedCount > 0 && (
            <div className="text-red-300">❌ {failedCount}</div>
          )}
        </div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-3"
          >
            {loading && agents.length === 0 ? (
              <div className="text-center text-gray-400 py-4">Loading agents...</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {agents.map((agent) => (
                  <AgentCard key={agent.task_id} agent={agent} />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
