/**
 * Context Foundry Desktop - Main Application Component
 *
 * Provides the main layout with routing to different views:
 * - Dashboard: Job list and overview
 * - Job Detail: Detailed view of a specific job
 * - Metrics: System metrics and graphs
 */

import { useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Activity, Settings, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

import { useDaemonStore } from './stores/daemon'
import { useJobsStore } from './stores/jobs'
import { useMetricsStore } from './stores/metrics'

import HealthIndicator from './components/HealthIndicator'
import Dashboard from './views/Dashboard'
import JobDetail from './views/JobDetail'
import Metrics from './views/Metrics'

// Polling interval in milliseconds
const REFRESH_INTERVAL = 5000

function App() {
  const { status, checkStatus, setupEventListeners } = useDaemonStore()
  const { refreshJobs } = useJobsStore()
  const { refresh: refreshMetrics } = useMetricsStore()
  const location = useLocation()

  // Setup event listeners and initial data fetch
  useEffect(() => {
    let cleanup: (() => void) | undefined

    const init = async () => {
      // Setup Tauri event listeners
      cleanup = await setupEventListeners()

      // Initial status check
      await checkStatus()
    }

    init()

    return () => {
      cleanup?.()
    }
  }, [checkStatus, setupEventListeners])

  // Auto-refresh data when daemon is running
  useEffect(() => {
    if (!status?.running) return

    // Initial fetch
    refreshJobs()
    refreshMetrics()

    // Setup polling interval
    const interval = setInterval(() => {
      refreshJobs()
      refreshMetrics()
    }, REFRESH_INTERVAL)

    return () => clearInterval(interval)
  }, [status?.running, refreshJobs, refreshMetrics])

  return (
    <div className="flex h-screen bg-cf-background">
      {/* Sidebar Navigation */}
      <aside className="w-16 flex flex-col items-center py-4 bg-cf-surface border-r border-cf-border">
        <div className="mb-8">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cf-primary to-cf-secondary flex items-center justify-center">
            <span className="text-white font-bold text-lg">CF</span>
          </div>
        </div>

        <nav className="flex flex-col gap-2">
          <NavItem to="/" icon={<LayoutDashboard size={20} />} label="Dashboard" />
          <NavItem to="/metrics" icon={<Activity size={20} />} label="Metrics" />
          <NavItem to="/settings" icon={<Settings size={20} />} label="Settings" />
        </nav>

        <div className="mt-auto">
          <HealthIndicator />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {/* Header */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-cf-border bg-cf-surface/50">
          <h1 className="text-lg font-semibold text-cf-text">
            {getPageTitle(location.pathname)}
          </h1>

          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                refreshJobs()
                refreshMetrics()
              }}
              className="p-2 rounded-lg hover:bg-cf-border transition-colors"
              title="Refresh"
            >
              <RefreshCw size={18} className="text-cf-muted" />
            </button>

            {status && (
              <div className="text-sm text-cf-muted">
                {status.running ? (
                  <span className="text-status-running">Daemon Running</span>
                ) : (
                  <span className="text-status-failed">Daemon Stopped</span>
                )}
              </div>
            )}
          </div>
        </header>

        {/* Page Content */}
        <div className="h-[calc(100%-3.5rem)] overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/job/:jobId" element={<JobDetail />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/settings" element={<SettingsPlaceholder />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

// Navigation item component
interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
}

function NavItem({ to, icon, label }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          'w-10 h-10 flex items-center justify-center rounded-lg transition-colors',
          isActive
            ? 'bg-cf-primary text-white'
            : 'text-cf-muted hover:text-cf-text hover:bg-cf-border'
        )
      }
      title={label}
    >
      {icon}
    </NavLink>
  )
}

// Get page title based on current route
function getPageTitle(pathname: string): string {
  if (pathname === '/') return 'Dashboard'
  if (pathname.startsWith('/job/')) return 'Job Details'
  if (pathname === '/metrics') return 'Metrics'
  if (pathname === '/settings') return 'Settings'
  return 'Context Foundry'
}

// Placeholder for settings page
function SettingsPlaceholder() {
  return (
    <div className="p-6">
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Settings</h2>
        <p className="text-cf-muted">Settings page coming soon.</p>
      </div>
    </div>
  )
}

export default App
