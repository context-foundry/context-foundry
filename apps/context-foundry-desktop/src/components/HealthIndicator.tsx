/**
 * Health Indicator Component
 *
 * Displays the daemon health status with a visual indicator.
 * Shows a colored dot that pulses when running.
 */

import { useDaemonStore } from '../stores/daemon'
import clsx from 'clsx'

function HealthIndicator() {
  const { status, isLoading, error } = useDaemonStore()

  // Determine indicator state
  let indicatorClass = 'bg-cf-muted'
  let label = 'Unknown'

  if (isLoading) {
    indicatorClass = 'bg-status-pending animate-pulse'
    label = 'Checking...'
  } else if (error) {
    indicatorClass = 'bg-status-failed'
    label = 'Error'
  } else if (status?.running) {
    indicatorClass = 'bg-status-running animate-pulse-slow'
    label = 'Healthy'
  } else if (status) {
    indicatorClass = 'bg-status-failed'
    label = 'Stopped'
  }

  return (
    <div className="flex flex-col items-center gap-1" title={`Daemon: ${label}`}>
      <div
        className={clsx(
          'w-3 h-3 rounded-full',
          indicatorClass
        )}
      />
      <span className="text-[10px] text-cf-muted">{label}</span>
    </div>
  )
}

export default HealthIndicator
