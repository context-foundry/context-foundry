import { useEffect, useState, useCallback, useRef } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { useJob } from '../contexts/JobContext';
import { useSSE } from '../hooks/useSSE';
import { usePhase } from '../hooks/usePhase';
import { useFileTree } from '../hooks/useFileTree';
import { useLogs } from '../hooks/useLogs';
import { SSEEvent } from '../types/events';
import JobSelector from './JobSelector';
import PipelineMetrics from './PipelineMetrics';
import FileBrowser from './FileBrowser';
import LogFeed from './LogFeed';
import MarkdownViewer from './MarkdownViewer';
import CodexBrowser from './CodexBrowser';
import Forge from './Forge';

type TabType = 'build' | 'browse' | 'logs' | 'codex' | 'forge';

// Funny rotating subtitles about Context Foundry
const FORGE_SUBTITLES = [
  "Where AI builds your dreams (and sometimes nightmares)",
  "Teaching robots to code since 2024",
  "99.9% uptime, 100% existential dread",
  "Powered by coffee, Claude, and questionable decisions",
  "Watch your app build itself. What could go wrong?",
  "Like Iron Man's workshop, but with more TypeScript errors",
  "The autonomous build system that never sleeps (literally)",
  "Turning 'it works on my machine' into 'it builds autonomously'",
  "Where Scout, Architect, and Builder argue until something works",
  "Forging apps from pure context and determination",
  "Because manually running npm install is so 2023",
  "Your personal army of AI developers (they work for tokens)",
  "Building the future, one hallucination at a time",
  "Where parallel builds race to see who crashes first",
  "The system that reads docs so you don't have to",
  "Autonomous builds: Because sleep is for humans",
  "Watching logs scroll by at 3 AM since day one",
  "Docker containers spinning up faster than your anxiety",
  "Where 'it compiles' is just the beginning",
  "The forge where bugs are features in training",
  "Powered by patterns learned from a thousand failed builds",
  "Because manual deployment is cruel and unusual punishment",
  "Where agents collaborate and occasionally fight",
  "Building apps while you pretend to work",
  "The only forge where the anvil is a database",
];

export default function Dashboard() {
  const { currentJob, setCurrentJob, refreshJob } = useJob();
  const { phaseInfo, updatePhase } = usePhase();
  const { addFile, setFiles, visibleNodes, toggleDirectory, collapseAll, searchQuery, setSearchQuery } = useFileTree([]);
  const { addLogs } = useLogs(currentJob?.id || null);
  const [activeTab, setActiveTab] = useState<TabType>('forge');
  const [metrics, setMetrics] = useState({
    tokens_used: 0,
  });
  const [completedPhases, setCompletedPhases] = useState<import('../types/job').Phase[]>([]);

  // Rotate subtitle every hour
  const [subtitleIndex, setSubtitleIndex] = useState(() =>
    Math.floor(Math.random() * FORGE_SUBTITLES.length)
  );

  // Handle SSE events
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    switch (event.type) {
      case 'phase_update': {
        const phaseData = event.data as import('../types/events').PhaseUpdateData;
        updatePhase({
          phase: phaseData.phase,
          status: phaseData.status,
          description: phaseData.description
        });
        break;
      }
      case 'file_created': {
        const fileData = event.data as import('../types/events').FileCreatedData;
        addFile(fileData.path);
        // File count is tracked in currentJob.total_files, updated via API polling
        break;
      }
      case 'log_batch': {
        const logData = event.data as import('../types/events').LogBatchData;
        addLogs(logData.logs);
        break;
      }
      case 'metrics_update': {
        const metricsData = event.data as import('../types/events').MetricsUpdateData;
        setMetrics(metricsData);
        break;
      }
      case 'job_status_change': {
        const statusData = event.data as import('../types/events').JobStatusChangeData;
        // Update current job status and refresh full job data
        if (currentJob) {
          setCurrentJob({
            ...currentJob,
            status: statusData.status,
          });
          // Re-fetch complete job data to update all metrics and phase info
          refreshJob();
        }
        break;
      }
      case 'markdown_update': {
        const markdownData = event.data as import('../types/events').MarkdownUpdateData;
        // Notify MarkdownViewer component to refresh
        if ((window as any).__markdownViewerHandler) {
          (window as any).__markdownViewerHandler(markdownData);
        }
        break;
      }
      case 'heartbeat':
        // Connection is alive
        break;
    }
  }, [updatePhase, addFile, setMetrics, addLogs, currentJob, setCurrentJob, refreshJob]);

  useSSE(currentJob?.id || null, handleSSEEvent);

  // Rotate subtitle every hour (3600000ms)
  useEffect(() => {
    const interval = setInterval(() => {
      setSubtitleIndex((prev) => (prev + 1) % FORGE_SUBTITLES.length);
    }, 3600000); // 1 hour

    return () => clearInterval(interval);
  }, []);

  // Update files when job changes
  useEffect(() => {
    if (currentJob) {
      // Reset state
      setFiles([]);
      setMetrics({
        tokens_used: currentJob.tokens_used || 0,
      });

      // Fetch existing files from working directory
      fetch(`/api/files/list?job_id=${currentJob.id}`)
        .then(res => res.json())
        .then(data => {
          if (data.files && data.files.length > 0) {
            // Add all existing files to the tree
            data.files.forEach((filePath: string) => {
              addFile(filePath);
            });
          }
        })
        .catch(err => {
          console.error('Failed to load existing files:', err);
        });

      // Fetch phase details for all jobs (running or completed)
      fetch(`/api/jobs/${currentJob.id}/phases/detailed`)
        .then(res => res.json())
        .then(data => {
          // Update current phase info from current_phase field
          if (data.current_phase) {
            updatePhase({
              phase: data.current_phase.name,
              status: data.current_phase.status || 'active',
              description: data.current_phase.description || '',
            });
          } else if (currentJob.current_phase) {
            // Fallback to job's current_phase field
            updatePhase({
              phase: currentJob.current_phase,
              status: 'active',
              description: '',
            });
          }

          // Update completed phases for pipeline display
          const phases: import('../types/job').Phase[] = [];
          if (data.phases) {
            data.phases.forEach((p: { name: string }) => {
              const phaseName = p.name.toLowerCase();
              if (phaseName.includes('scout')) phases.push('Scout' as import('../types/job').Phase);
              else if (phaseName.includes('architect')) phases.push('Architect' as import('../types/job').Phase);
              else if (phaseName.includes('builder')) phases.push('Builder' as import('../types/job').Phase);
              else if (phaseName.includes('test')) phases.push('Test' as import('../types/job').Phase);
              else if (phaseName.includes('screenshot')) phases.push('Screenshot' as import('../types/job').Phase);
              else if (phaseName.includes('documentation')) phases.push('Documentation' as import('../types/job').Phase);
              else if (phaseName.includes('deploy')) phases.push('Deploy' as import('../types/job').Phase);
            });
          }
          // Remove duplicates
          setCompletedPhases([...new Set(phases)]);
        })
        .catch(err => console.error('Failed to fetch phase details:', err));
    }
  }, [currentJob, setFiles, updatePhase]);


  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-[1920px] mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
                Forge
              </h1>
              <p className="text-sm text-gray-400">{FORGE_SUBTITLES[subtitleIndex]}</p>
            </div>
            <div className="flex items-center gap-4">
              <JobSelector />
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-2 border-b border-gray-800">
            <button
              onClick={() => setActiveTab('forge')}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                activeTab === 'forge'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Forge
            </button>
            <button
              onClick={() => setActiveTab('build')}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                activeTab === 'build'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Build
            </button>
            <button
              onClick={() => setActiveTab('browse')}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                activeTab === 'browse'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Browse
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                activeTab === 'logs'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Logs
            </button>
            <button
              onClick={() => setActiveTab('codex')}
              className={`px-4 py-2 text-sm font-medium transition-colors relative ${
                activeTab === 'codex'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              Codex
            </button>
          </div>
        </div>
      </header>

      {/* Tab Content */}
      <div className="max-w-[1920px] mx-auto p-4">
        {activeTab === 'build' && (
          <div className="grid grid-cols-12 gap-4">
            {/* Pipeline with Metrics - Full Width */}
            <div className="col-span-12">
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4" style={{height: '1000px'}}>
                <PipelineMetrics
                  jobId={currentJob?.id || null}
                  currentPhase={phaseInfo.phase}
                  status={phaseInfo.status}
                  description={phaseInfo.description}
                  jobStatus={currentJob?.status}
                  completedPhases={completedPhases}
                  tokensUsed={metrics.tokens_used}
                  startedAt={currentJob?.started_at || null}
                  completedAt={currentJob?.completed_at || null}
                  totalFiles={currentJob?.total_files || 0}
                  projectName={currentJob?.project_name}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'browse' && (
          <div style={{height: '1400px'}}>
            <PanelGroup direction="vertical">
              {/* Build Files - Top Panel */}
              <Panel defaultSize={50} minSize={20}>
                <div className="h-full bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                  <MarkdownViewer jobId={currentJob?.id || null} />
                </div>
              </Panel>

              {/* Resize Handle */}
              <PanelResizeHandle className="h-2 bg-gray-800 hover:bg-cyan-500/50 transition-colors cursor-row-resize flex items-center justify-center group">
                <div className="w-12 h-1 bg-gray-700 rounded-full group-hover:bg-cyan-500 transition-colors" />
              </PanelResizeHandle>

              {/* Project Files - Bottom Panel */}
              <Panel defaultSize={50} minSize={20}>
                <div className="h-full bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                  <FileBrowser
                    visibleNodes={visibleNodes}
                    toggleDirectory={toggleDirectory}
                    collapseAll={collapseAll}
                    searchQuery={searchQuery}
                    setSearchQuery={setSearchQuery}
                    jobId={currentJob?.id}
                  />
                </div>
              </Panel>
            </PanelGroup>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg" style={{height: '1200px'}}>
            <LogFeed jobId={currentJob?.id || null} />
          </div>
        )}

        {activeTab === 'codex' && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg" style={{height: '1200px'}}>
            <CodexBrowser />
          </div>
        )}

        {activeTab === 'forge' && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg h-[calc(100vh-200px)]">
            <Forge />
          </div>
        )}
      </div>

      {/* Mobile Nav (if needed) - keeping for compatibility */}
    </div>
  );
}
