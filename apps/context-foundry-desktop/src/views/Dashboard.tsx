/**
 * Dashboard View
 *
 * Main dashboard showing job list with filters and overview stats.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, CheckCircle, XCircle, Clock, AlertCircle, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'

import { useJobsStore } from '../stores/jobs'
import { useMetricsStore } from '../stores/metrics'
import { useDaemonStore } from '../stores/daemon'
import type { Job, JobStatus } from '../types'

function Dashboard() {
  const { jobs, isLoading, error, statusFilter, setStatusFilter, fetchJobs } = useJobsStore()
  const { metrics } = useMetricsStore()
  const { status: daemonStatus } = useDaemonStore()
  const navigate = useNavigate()

  // Fetch jobs on mount
  useEffect(() => {
    if (daemonStatus?.running) {
      fetchJobs()
    }
  }, [daemonStatus?.running, fetchJobs])

  // If daemon is not running, show connection message
  if (!daemonStatus?.running) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="card text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-status-pending mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Daemon Not Running</h2>
          <p className="text-cf-muted mb-4">
            The Context Foundry daemon is not running. Start it to view jobs.
          </p>
          <button
            onClick={() => useDaemonStore.getState().startDaemon()}
            className="btn btn-primary"
          >
            Start Daemon
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Running"
          value={metrics?.jobs_running ?? 0}
          icon={<Loader2 className="animate-spin" />}
          color="running"
        />
        <StatCard
          label="Pending"
          value={metrics?.jobs_pending ?? 0}
          icon={<Clock />}
          color="pending"
        />
        <StatCard
          label="Succeeded"
          value={metrics?.jobs_succeeded ?? 0}
          icon={<CheckCircle />}
          color="succeeded"
        />
        <StatCard
          label="Failed"
          value={metrics?.jobs_failed ?? 0}
          icon={<XCircle />}
          color="failed"
        />
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <FilterButton
          label="All"
          active={statusFilter === 'all'}
          onClick={() => setStatusFilter('all')}
        />
        <FilterButton
          label="Running"
          active={statusFilter === 'running'}
          onClick={() => setStatusFilter('running')}
        />
        <FilterButton
          label="Pending"
          active={statusFilter === 'pending'}
          onClick={() => setStatusFilter('pending')}
        />
        <FilterButton
          label="Succeeded"
          active={statusFilter === 'succeeded'}
          onClick={() => setStatusFilter('succeeded')}
        />
        <FilterButton
          label="Failed"
          active={statusFilter === 'failed'}
          onClick={() => setStatusFilter('failed')}
        />
      </div>

      {/* Error display */}
      {error && (
        <div className="card bg-status-failed/10 border-status-failed">
          <p className="text-status-failed">{error}</p>
        </div>
      )}

      {/* Job List */}
      <div className="card p-0 overflow-hidden">
        {isLoading && jobs.length === 0 ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-cf-muted" />
            <p className="text-cf-muted mt-2">Loading jobs...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-cf-muted">No jobs found</p>
          </div>
        ) : (
          <div className="divide-y divide-cf-border">
            {jobs.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                onClick={() => navigate(`/job/${job.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Stat card component
interface StatCardProps {
  label: string
  value: number
  icon: React.ReactNode
  color: 'running' | 'pending' | 'succeeded' | 'failed'
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  const colorClasses = {
    running: 'text-status-running',
    pending: 'text-status-pending',
    succeeded: 'text-status-succeeded',
    failed: 'text-status-failed',
  }

  return (
    <div className="card flex items-center gap-4">
      <div className={clsx('p-2 rounded-lg bg-cf-background', colorClasses[color])}>
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-sm text-cf-muted">{label}</p>
      </div>
    </div>
  )
}

// Filter button component
interface FilterButtonProps {
  label: string
  active: boolean
  onClick: () => void
}

function FilterButton({ label, active, onClick }: FilterButtonProps) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
        active
          ? 'bg-cf-primary text-white'
          : 'bg-cf-surface text-cf-muted hover:text-cf-text border border-cf-border'
      )}
    >
      {label}
    </button>
  )
}

// Job row component
interface JobRowProps {
  job: Job
  onClick: () => void
}

function JobRow({ job, onClick }: JobRowProps) {
  return (
    <button
      onClick={onClick}
      className="w-full p-4 flex items-center gap-4 hover:bg-cf-background/50 transition-colors text-left"
    >
      <StatusIcon status={job.status} />

      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{job.task}</p>
        <p className="text-sm text-cf-muted truncate">{job.working_directory}</p>
      </div>

      <div className="text-right">
        {job.current_phase && (
          <p className="text-sm text-cf-muted">{job.current_phase}</p>
        )}
        <p className="text-xs text-cf-muted">
          {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
        </p>
      </div>
    </button>
  )
}

// Status icon component
function StatusIcon({ status }: { status: JobStatus }) {
  const icons: Record<JobStatus, React.ReactNode> = {
    running: <Loader2 className="w-5 h-5 text-status-running animate-spin" />,
    pending: <Clock className="w-5 h-5 text-status-pending" />,
    succeeded: <CheckCircle className="w-5 h-5 text-status-succeeded" />,
    failed: <XCircle className="w-5 h-5 text-status-failed" />,
    cancelled: <AlertCircle className="w-5 h-5 text-status-cancelled" />,
  }

  return icons[status] || <Play className="w-5 h-5 text-cf-muted" />
}

export default Dashboard
