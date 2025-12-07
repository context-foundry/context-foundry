/**
 * Job Detail View
 *
 * Detailed view of a specific job showing:
 * - Job info and status
 * - Phase timeline (tree view)
 * - Event timeline
 */

import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'
import clsx from 'clsx'
import { format, formatDistanceToNow } from 'date-fns'

import { useJobsStore } from '../stores/jobs'
import type { JobStatus, PhaseNode, TimelineEvent } from '../types'

function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const {
    selectedJob,
    selectedJobTree,
    selectedJobTimeline,
    isLoading,
    error,
    selectJob,
    clearSelectedJob,
  } = useJobsStore()

  // Fetch job details on mount
  useEffect(() => {
    if (jobId) {
      selectJob(jobId)
    }

    return () => {
      clearSelectedJob()
    }
  }, [jobId, selectJob, clearSelectedJob])

  if (isLoading && !selectedJob) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-cf-muted" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="card bg-status-failed/10 border-status-failed">
          <p className="text-status-failed">{error}</p>
        </div>
      </div>
    )
  }

  if (!selectedJob) {
    return (
      <div className="p-6">
        <div className="card text-center">
          <p className="text-cf-muted">Job not found</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/')}
          className="p-2 rounded-lg hover:bg-cf-border transition-colors"
        >
          <ArrowLeft size={20} className="text-cf-muted" />
        </button>

        <div className="flex-1">
          <h2 className="text-xl font-semibold">{selectedJob.task}</h2>
          <p className="text-sm text-cf-muted">{selectedJob.working_directory}</p>
        </div>

        <StatusBadge status={selectedJob.status} />
      </div>

      {/* Job Info */}
      <div className="grid grid-cols-3 gap-4">
        <InfoCard label="Job ID" value={selectedJob.id} />
        <InfoCard
          label="Created"
          value={format(new Date(selectedJob.created_at), 'PPp')}
        />
        <InfoCard
          label="Duration"
          value={
            selectedJob.completed_at
              ? formatDistanceToNow(new Date(selectedJob.started_at || selectedJob.created_at))
              : 'In progress...'
          }
        />
      </div>

      {/* Error display */}
      {selectedJob.error && (
        <div className="card bg-status-failed/10 border-status-failed">
          <div className="flex items-start gap-3">
            <XCircle className="w-5 h-5 text-status-failed mt-0.5" />
            <div>
              <p className="font-medium text-status-failed">Error</p>
              <p className="text-sm text-cf-muted mt-1">{selectedJob.error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Two column layout */}
      <div className="grid grid-cols-2 gap-6">
        {/* Phase Tree */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Phases</h3>
          {selectedJobTree?.phases ? (
            <div className="space-y-2">
              {selectedJobTree.phases.map((phase, index) => (
                <PhaseRow key={index} phase={phase} />
              ))}
            </div>
          ) : (
            <p className="text-cf-muted">No phase data available</p>
          )}
        </div>

        {/* Event Timeline */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Timeline</h3>
          {selectedJobTimeline?.events && selectedJobTimeline.events.length > 0 ? (
            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {selectedJobTimeline.events.map((event, index) => (
                <TimelineEventRow key={index} event={event} />
              ))}
            </div>
          ) : (
            <p className="text-cf-muted">No timeline events available</p>
          )}
        </div>
      </div>
    </div>
  )
}

// Status badge component
function StatusBadge({ status }: { status: JobStatus }) {
  const classes: Record<JobStatus, string> = {
    running: 'status-running',
    pending: 'status-pending',
    succeeded: 'status-succeeded',
    failed: 'status-failed',
    cancelled: 'status-cancelled',
  }

  return (
    <span className={clsx('status-badge', classes[status])}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// Info card component
interface InfoCardProps {
  label: string
  value: string
}

function InfoCard({ label, value }: InfoCardProps) {
  return (
    <div className="card">
      <p className="text-sm text-cf-muted">{label}</p>
      <p className="font-medium truncate" title={value}>
        {value}
      </p>
    </div>
  )
}

// Phase row component
function PhaseRow({ phase }: { phase: PhaseNode }) {
  return (
    <div className="border border-cf-border rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 p-3 bg-cf-background/50">
        <PhaseStatusIcon status={phase.status} />
        <span className="font-medium flex-1">{phase.name}</span>
        <ChevronRight size={16} className="text-cf-muted" />
      </div>

      {phase.tasks && phase.tasks.length > 0 && (
        <div className="divide-y divide-cf-border">
          {phase.tasks.map((task, index) => (
            <div key={index} className="flex items-center gap-3 p-2 pl-8 text-sm">
              <TaskStatusIcon status={task.status} />
              <span className="flex-1 truncate">{task.name}</span>
              {task.duration_seconds && (
                <span className="text-cf-muted">
                  {formatDuration(task.duration_seconds)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Phase status icon
function PhaseStatusIcon({ status }: { status: JobStatus }) {
  const icons: Record<JobStatus, React.ReactNode> = {
    running: <Loader2 size={18} className="text-status-running animate-spin" />,
    pending: <Clock size={18} className="text-status-pending" />,
    succeeded: <CheckCircle size={18} className="text-status-succeeded" />,
    failed: <XCircle size={18} className="text-status-failed" />,
    cancelled: <AlertCircle size={18} className="text-status-cancelled" />,
  }

  return icons[status] || <Clock size={18} className="text-cf-muted" />
}

// Task status icon (smaller)
function TaskStatusIcon({ status }: { status: JobStatus }) {
  const icons: Record<JobStatus, React.ReactNode> = {
    running: <Loader2 size={14} className="text-status-running animate-spin" />,
    pending: <Clock size={14} className="text-status-pending" />,
    succeeded: <CheckCircle size={14} className="text-status-succeeded" />,
    failed: <XCircle size={14} className="text-status-failed" />,
    cancelled: <AlertCircle size={14} className="text-status-cancelled" />,
  }

  return icons[status] || <Clock size={14} className="text-cf-muted" />
}

// Timeline event row
function TimelineEventRow({ event }: { event: TimelineEvent }) {
  const typeColors: Record<string, string> = {
    phase_start: 'text-cf-primary',
    phase_end: 'text-cf-secondary',
    task_start: 'text-cf-accent',
    task_end: 'text-cf-accent',
    error: 'text-status-failed',
    info: 'text-cf-muted',
  }

  return (
    <div className="flex gap-3 text-sm">
      <div className="text-cf-muted whitespace-nowrap">
        {format(new Date(event.timestamp), 'HH:mm:ss')}
      </div>
      <div className={clsx('flex-1', typeColors[event.type] || 'text-cf-text')}>
        {event.message || `${event.type}: ${event.phase || event.task || ''}`}
      </div>
    </div>
  )
}

// Format duration in seconds to human readable
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`
  }
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs.toFixed(0)}s`
}

export default JobDetail
