/**
 * Metrics View
 *
 * Displays system metrics and graphs including:
 * - Job statistics
 * - Resource usage
 * - Success rate over time
 */

import { useEffect } from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  Activity,
  Clock,
  TrendingUp,
  Cpu,
  HardDrive,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react'
import { useMetricsStore } from '../stores/metrics'
import { useDaemonStore } from '../stores/daemon'

function Metrics() {
  const { metrics, health, history, isLoading, refresh } = useMetricsStore()
  const { status: daemonStatus } = useDaemonStore()

  // Fetch metrics on mount
  useEffect(() => {
    if (daemonStatus?.running) {
      refresh()
    }
  }, [daemonStatus?.running, refresh])

  // If daemon is not running, show message
  if (!daemonStatus?.running) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <div className="card text-center max-w-md">
          <Activity className="w-12 h-12 text-cf-muted mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Metrics Unavailable</h2>
          <p className="text-cf-muted">
            Start the daemon to view metrics.
          </p>
        </div>
      </div>
    )
  }

  if (isLoading && !metrics) {
    return (
      <div className="p-6 flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-cf-muted" />
      </div>
    )
  }

  // Format history data for charts
  const chartData = history.map((sample, index) => ({
    index,
    jobsRunning: sample.jobsRunning,
    jobsTotal: sample.jobsTotal,
    cpu: sample.cpuPercent ?? 0,
    memory: sample.memoryMb ?? 0,
  }))

  return (
    <div className="p-6 space-y-6">
      {/* Overview Stats */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Uptime"
          value={metrics?.uptime_seconds ? formatUptime(metrics.uptime_seconds) : '--'}
          icon={<Clock />}
          color="primary"
        />
        <MetricCard
          label="Success Rate"
          value={metrics?.success_rate ? `${(metrics.success_rate * 100).toFixed(1)}%` : '--'}
          icon={<TrendingUp />}
          color="succeeded"
        />
        <MetricCard
          label="CPU Usage"
          value={metrics?.cpu_percent ? `${metrics.cpu_percent.toFixed(1)}%` : '--'}
          icon={<Cpu />}
          color="accent"
        />
        <MetricCard
          label="Memory"
          value={metrics?.memory_usage_mb ? `${metrics.memory_usage_mb.toFixed(0)} MB` : '--'}
          icon={<HardDrive />}
          color="secondary"
        />
      </div>

      {/* Job Stats */}
      <div className="grid grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Job Statistics</h3>
          <div className="grid grid-cols-2 gap-4">
            <StatItem
              label="Total Jobs"
              value={metrics?.jobs_total ?? 0}
              icon={<Activity size={16} />}
            />
            <StatItem
              label="Running"
              value={metrics?.jobs_running ?? 0}
              icon={<Loader2 size={16} className="animate-spin" />}
              color="running"
            />
            <StatItem
              label="Succeeded"
              value={metrics?.jobs_succeeded ?? 0}
              icon={<CheckCircle size={16} />}
              color="succeeded"
            />
            <StatItem
              label="Failed"
              value={metrics?.jobs_failed ?? 0}
              icon={<XCircle size={16} />}
              color="failed"
            />
          </div>

          {metrics?.avg_duration_seconds && (
            <div className="mt-4 pt-4 border-t border-cf-border">
              <p className="text-sm text-cf-muted">Average Job Duration</p>
              <p className="text-lg font-semibold">
                {formatDuration(metrics.avg_duration_seconds)}
              </p>
            </div>
          )}
        </div>

        {/* Health Status */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Daemon Health</h3>
          {health ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div
                  className={`w-4 h-4 rounded-full ${
                    health.status === 'healthy'
                      ? 'bg-status-succeeded'
                      : health.status === 'degraded'
                      ? 'bg-status-pending'
                      : 'bg-status-failed'
                  }`}
                />
                <span className="font-medium capitalize">{health.status}</span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-cf-muted">PID</p>
                  <p className="font-mono">{health.pid}</p>
                </div>
                <div>
                  <p className="text-cf-muted">Version</p>
                  <p className="font-mono">{health.version || 'Unknown'}</p>
                </div>
                <div>
                  <p className="text-cf-muted">Uptime</p>
                  <p>{formatUptime(health.uptime_seconds)}</p>
                </div>
                <div>
                  <p className="text-cf-muted">Last Check</p>
                  <p>Just now</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-cf-muted">Health data unavailable</p>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6">
        {/* Jobs Running Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Jobs Running</h3>
          <div className="h-48">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="index" hide />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="jobsRunning"
                    stroke="#22c55e"
                    fill="#22c55e"
                    fillOpacity={0.2}
                    name="Running"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-cf-muted">
                No data yet
              </div>
            )}
          </div>
        </div>

        {/* Resource Usage Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Resource Usage</h3>
          <div className="h-48">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="index" hide />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="cpu"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={false}
                    name="CPU %"
                  />
                  <Line
                    type="monotone"
                    dataKey="memory"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    dot={false}
                    name="Memory MB"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-cf-muted">
                No data yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// Metric card component
interface MetricCardProps {
  label: string
  value: string
  icon: React.ReactNode
  color: 'primary' | 'secondary' | 'accent' | 'succeeded' | 'failed'
}

function MetricCard({ label, value, icon, color }: MetricCardProps) {
  const colorClasses = {
    primary: 'text-cf-primary',
    secondary: 'text-cf-secondary',
    accent: 'text-cf-accent',
    succeeded: 'text-status-succeeded',
    failed: 'text-status-failed',
  }

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-2">
        <div className={colorClasses[color]}>{icon}</div>
        <span className="text-sm text-cf-muted">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  )
}

// Stat item component
interface StatItemProps {
  label: string
  value: number
  icon: React.ReactNode
  color?: 'running' | 'succeeded' | 'failed'
}

function StatItem({ label, value, icon, color }: StatItemProps) {
  const colorClasses = {
    running: 'text-status-running',
    succeeded: 'text-status-succeeded',
    failed: 'text-status-failed',
  }

  return (
    <div className="flex items-center gap-3">
      <div className={color ? colorClasses[color] : 'text-cf-muted'}>{icon}</div>
      <div>
        <p className="text-xl font-bold">{value}</p>
        <p className="text-sm text-cf-muted">{label}</p>
      </div>
    </div>
  )
}

// Format uptime seconds to human readable
function formatUptime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(0)}s`
  }
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    return `${minutes}m`
  }
  if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  return `${days}d ${hours}h`
}

// Format duration in seconds to human readable
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)} seconds`
  }
  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  if (minutes < 60) {
    return `${minutes}m ${secs}s`
  }
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours}h ${mins}m`
}

export default Metrics
