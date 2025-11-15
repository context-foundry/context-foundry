import { useEffect, useState } from 'react';
import { useJob } from '../contexts/JobContext';
import { useSSE } from '../hooks/useSSE';
import { usePhase } from '../hooks/usePhase';
import { useFileTree } from '../hooks/useFileTree';
import { useLogs } from '../hooks/useLogs';
import { SSEEvent } from '../types/events';
import JobSelector from './JobSelector';
import PhasePipeline from './PhasePipeline';
import MetricsPanel from './MetricsPanel';
import FileTree from './FileTree';
import CodePreview from './CodePreview';
import LogFeed from './LogFeed';
import ThoughtProcess from './ThoughtProcess';
import MobileNav from './MobileNav';

type MobileView = 'phase' | 'files' | 'logs' | 'code';

export default function Dashboard() {
  const { currentJob } = useJob();
  const { phaseInfo, updatePhase } = usePhase();
  const { addFile, setFiles } = useFileTree([]);
  const { addLogs } = useLogs(currentJob?.id || null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<MobileView>('phase');
  const [metrics, setMetrics] = useState({
    tokens_used: 0,
    duration: 0,
    files: 0,
  });

  // Handle SSE events
  const handleSSEEvent = (event: SSEEvent) => {
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
        setMetrics(prev => ({ ...prev, files: prev.files + 1 }));
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
      case 'job_status_change':
        // Handle job status change
        break;
      case 'heartbeat':
        // Connection is alive
        break;
    }
  };

  useSSE(currentJob?.id || null, handleSSEEvent);

  // Update files when job changes
  useEffect(() => {
    if (currentJob) {
      // Fetch initial files from session summary
      setFiles([]);
      setMetrics({
        tokens_used: currentJob.tokens_used || 0,
        duration: 0,
        files: currentJob.total_files || 0,
      });

      // Update phase info
      if (currentJob.current_phase) {
        updatePhase({
          phase: currentJob.current_phase,
          status: 'active',
          description: '',
        });
      }
    }
  }, [currentJob, setFiles, updatePhase]);

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
            <JobSelector />
          </div>
        </div>
      </header>

      {/* Desktop Layout (>1024px) */}
      <div className="hidden lg:block">
        <div className="max-w-[1920px] mx-auto p-4">
          <div className="grid grid-cols-12 gap-4">
            {/* Left Column - Metrics */}
            <div className="col-span-3 space-y-4">
              <MetricsPanel
                tokensUsed={metrics.tokens_used}
                duration={metrics.duration}
                totalFiles={metrics.files}
                status={currentJob?.status || 'unknown'}
              />
              <ThoughtProcess jobId={currentJob?.id || null} />
            </div>

            {/* Middle Column - Phase & File Tree */}
            <div className="col-span-4 space-y-4">
              <PhasePipeline
                currentPhase={phaseInfo.phase}
                status={phaseInfo.status}
                description={phaseInfo.description}
              />
              <FileTree onFileSelect={setSelectedFile} />
            </div>

            {/* Right Column - Code & Logs */}
            <div className="col-span-5 space-y-4">
              <CodePreview filePath={selectedFile} />
              <LogFeed jobId={currentJob?.id || null} />
            </div>
          </div>
        </div>
      </div>

      {/* Tablet Layout (768-1024px) */}
      <div className="hidden md:block lg:hidden">
        <div className="max-w-5xl mx-auto p-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-4">
              <MetricsPanel
                tokensUsed={metrics.tokens_used}
                duration={metrics.duration}
                totalFiles={metrics.files}
                status={currentJob?.status || 'unknown'}
              />
              <PhasePipeline
                currentPhase={phaseInfo.phase}
                status={phaseInfo.status}
                description={phaseInfo.description}
              />
              <FileTree onFileSelect={setSelectedFile} />
            </div>
            <div className="space-y-4">
              <CodePreview filePath={selectedFile} />
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
                duration={metrics.duration}
                totalFiles={metrics.files}
                status={currentJob?.status || 'unknown'}
              />
              <PhasePipeline
                currentPhase={phaseInfo.phase}
                status={phaseInfo.status}
                description={phaseInfo.description}
              />
            </div>
          )}
          {mobileView === 'files' && <FileTree onFileSelect={setSelectedFile} />}
          {mobileView === 'logs' && <LogFeed jobId={currentJob?.id || null} />}
          {mobileView === 'code' && <CodePreview filePath={selectedFile} />}
        </div>

        <MobileNav activeView={mobileView} onViewChange={setMobileView} />
      </div>
    </div>
  );
}
