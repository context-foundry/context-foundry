import { useEffect, useState, useCallback } from 'react';
import { useJob } from '../contexts/JobContext';
import { useSSE } from '../hooks/useSSE';
import { usePhase } from '../hooks/usePhase';
import { useFileTree } from '../hooks/useFileTree';
import { useLogs } from '../hooks/useLogs';
import { SSEEvent } from '../types/events';
import JobSelector from './JobSelector';
import PhasePipeline from './PhasePipeline';
import PhaseBreakdown from './PhaseBreakdown';
import MetricsPanel from './MetricsPanel';
import FileTree from './FileTree';
import CodePreview from './CodePreview';
import LogFeed from './LogFeed';
import MarkdownViewer from './MarkdownViewer';
import MobileNav from './MobileNav';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

type MobileView = 'phase' | 'files' | 'logs' | 'code';

const defaultLayout = [
  { i: 'metrics', x: 0, y: 0, w: 3, h: 3, minW: 2, minH: 2 },
  { i: 'pipeline', x: 3, y: 0, w: 9, h: 3, minW: 4, minH: 2 },
  { i: 'phase-breakdown', x: 0, y: 3, w: 3, h: 6, minW: 2, minH: 4 },
  { i: 'file-tree', x: 0, y: 9, w: 3, h: 6, minW: 2, minH: 4 },
  { i: 'artifacts', x: 3, y: 3, w: 4, h: 12, minW: 3, minH: 6 },
  { i: 'code-preview', x: 7, y: 3, w: 5, h: 6, minW: 3, minH: 4 },
  { i: 'logs', x: 7, y: 9, w: 5, h: 6, minW: 3, minH: 4 },
];

export default function Dashboard() {
  const { currentJob, setCurrentJob, refreshJob } = useJob();
  const { phaseInfo, updatePhase } = usePhase();
  const { addFile, setFiles, visibleNodes, toggleDirectory, collapseAll, searchQuery, setSearchQuery } = useFileTree([]);
  const { addLogs } = useLogs(currentJob?.id || null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<MobileView>('phase');
  const [metrics, setMetrics] = useState({
    tokens_used: 0,
  });
  const [completedPhases, setCompletedPhases] = useState<import('../types/job').Phase[]>([]);
  const [layout, setLayout] = useState(() => {
    const saved = localStorage.getItem('dashboard-layout');
    return saved ? JSON.parse(saved) : defaultLayout;
  });

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
            });
          }
          // Remove duplicates
          setCompletedPhases([...new Set(phases)]);
        })
        .catch(err => console.error('Failed to fetch phase details:', err));
    }
  }, [currentJob, setFiles, updatePhase]);

  const handleLayoutChange = (newLayout: any) => {
    setLayout(newLayout);
    localStorage.setItem('dashboard-layout', JSON.stringify(newLayout));
  };

  const resetLayout = () => {
    setLayout(defaultLayout);
    localStorage.setItem('dashboard-layout', JSON.stringify(defaultLayout));
  };

  const autoArrangeLayout = () => {
    // Optimal layout for typical workflow:
    // Top: Status overview (metrics + pipeline)
    // Left: Navigation and breakdown (phase-breakdown + file-tree)
    // Center: Main content (artifacts)
    // Right: Code and logs (code-preview + logs)
    const optimizedLayout = [
      { i: 'metrics', x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
      { i: 'pipeline', x: 3, y: 0, w: 9, h: 2, minW: 4, minH: 2 },
      { i: 'phase-breakdown', x: 0, y: 2, w: 3, h: 6, minW: 2, minH: 4 },
      { i: 'file-tree', x: 0, y: 8, w: 3, h: 6, minW: 2, minH: 4 },
      { i: 'artifacts', x: 3, y: 2, w: 5, h: 12, minW: 3, minH: 6 },
      { i: 'code-preview', x: 8, y: 2, w: 4, h: 6, minW: 3, minH: 4 },
      { i: 'logs', x: 8, y: 8, w: 4, h: 6, minW: 3, minH: 4 },
    ];
    setLayout(optimizedLayout);
    localStorage.setItem('dashboard-layout', JSON.stringify(optimizedLayout));
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-[1920px] mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
                Glass Pane
              </h1>
              <p className="text-sm text-gray-400">Context Foundry Build Monitor</p>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={autoArrangeLayout}
                className="px-3 py-1.5 text-sm bg-cyan-600 hover:bg-cyan-500 border border-cyan-500 rounded-lg transition-colors"
                title="Auto arrange tiles optimally"
              >
                Auto Arrange
              </button>
              <button
                onClick={resetLayout}
                className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors"
                title="Reset dashboard layout"
              >
                Reset Layout
              </button>
              <JobSelector />
            </div>
          </div>
        </div>
      </header>

      {/* Desktop Layout (>1024px) - Draggable Grid */}
      <div className="hidden lg:block">
        <div className="max-w-[1920px] mx-auto p-4">
          <GridLayout
            className="layout"
            layout={layout}
            cols={12}
            rowHeight={50}
            width={1880}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".drag-handle"
            compactType={null}
            preventCollision={false}
          >
            <div key="metrics" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Metrics</span>
              </div>
              <div className="p-4 overflow-auto flex-1">
                <MetricsPanel
                  tokensUsed={metrics.tokens_used}
                  startedAt={currentJob?.started_at || null}
                  completedAt={currentJob?.completed_at || null}
                  totalFiles={currentJob?.total_files || 0}
                  status={currentJob?.status || 'unknown'}
                />
              </div>
            </div>

            <div key="pipeline" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Pipeline</span>
              </div>
              <div className="p-4 overflow-auto flex-1">
                <PhasePipeline
                  currentPhase={phaseInfo.phase}
                  status={phaseInfo.status}
                  description={phaseInfo.description}
                  jobStatus={currentJob?.status}
                  completedPhases={completedPhases}
                />
              </div>
            </div>

            <div key="phase-breakdown" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Phase Breakdown</span>
              </div>
              <div className="overflow-auto flex-1">
                <PhaseBreakdown jobId={currentJob?.id || null} />
              </div>
            </div>

            <div key="file-tree" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">File Tree</span>
              </div>
              <div className="overflow-auto flex-1">
                <FileTree
                  onFileSelect={setSelectedFile}
                  visibleNodes={visibleNodes}
                  toggleDirectory={toggleDirectory}
                  collapseAll={collapseAll}
                  searchQuery={searchQuery}
                  setSearchQuery={setSearchQuery}
                />
              </div>
            </div>

            <div key="artifacts" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Artifacts</span>
              </div>
              <div className="overflow-auto flex-1">
                <MarkdownViewer jobId={currentJob?.id || null} />
              </div>
            </div>

            <div key="code-preview" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Code Preview</span>
              </div>
              <div className="overflow-auto flex-1">
                <CodePreview filePath={selectedFile} jobId={currentJob?.id} />
              </div>
            </div>

            <div key="logs" className="bg-gray-900 border border-gray-800 rounded-lg flex flex-col h-full">
              <div className="drag-handle cursor-move bg-gray-800 px-4 py-2 border-b border-gray-700 flex items-center gap-2 flex-shrink-0">
                <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                </svg>
                <span className="text-sm font-medium text-gray-400">Logs</span>
              </div>
              <div className="overflow-auto flex-1">
                <LogFeed jobId={currentJob?.id || null} />
              </div>
            </div>
          </GridLayout>
        </div>
      </div>

      {/* Tablet Layout (768-1024px) */}
      <div className="hidden md:block lg:hidden">
        <div className="max-w-5xl mx-auto p-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-4">
              <MetricsPanel
                tokensUsed={metrics.tokens_used}
                startedAt={currentJob?.started_at || null}
                completedAt={currentJob?.completed_at || null}
                totalFiles={currentJob?.total_files || 0}
                status={currentJob?.status || 'unknown'}
              />
              <PhasePipeline
                currentPhase={phaseInfo.phase}
                status={phaseInfo.status}
                description={phaseInfo.description}
                jobStatus={currentJob?.status}
                completedPhases={completedPhases}
              />
              <PhaseBreakdown jobId={currentJob?.id || null} />
              <FileTree
                onFileSelect={setSelectedFile}
                visibleNodes={visibleNodes}
                toggleDirectory={toggleDirectory}
                collapseAll={collapseAll}
                searchQuery={searchQuery}
                setSearchQuery={setSearchQuery}
              />
            </div>
            <div className="space-y-4">
              <CodePreview filePath={selectedFile} jobId={currentJob?.id} />
              <LogFeed jobId={currentJob?.id || null} />
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Layout (<768px) */}
      <div className="md:hidden pb-16">
        <div className="p-4">
          {mobileView === 'phase' && (
            <div className="space-y-4">
              <MetricsPanel
                tokensUsed={metrics.tokens_used}
                startedAt={currentJob?.started_at || null}
                completedAt={currentJob?.completed_at || null}
                totalFiles={currentJob?.total_files || 0}
                status={currentJob?.status || 'unknown'}
              />
              <PhasePipeline
                currentPhase={phaseInfo.phase}
                status={phaseInfo.status}
                description={phaseInfo.description}
                jobStatus={currentJob?.status}
                completedPhases={completedPhases}
              />
              <PhaseBreakdown jobId={currentJob?.id || null} />
            </div>
          )}
          {mobileView === 'files' && (
            <FileTree
              onFileSelect={setSelectedFile}
              visibleNodes={visibleNodes}
              toggleDirectory={toggleDirectory}
              collapseAll={collapseAll}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
            />
          )}
          {mobileView === 'logs' && <LogFeed jobId={currentJob?.id || null} />}
          {mobileView === 'code' && <CodePreview filePath={selectedFile} jobId={currentJob?.id} />}
        </div>

        <MobileNav activeView={mobileView} onViewChange={setMobileView} />
      </div>
    </div>
  );
}
