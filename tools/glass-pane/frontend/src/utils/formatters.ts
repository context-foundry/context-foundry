/**
 * Utility functions for formatting data in the UI.
 */

/**
 * Format ISO 8601 timestamp to readable date/time.
 *
 * @param isoString - ISO 8601 timestamp
 * @returns Formatted date/time string
 */
export function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return isoString
  }
}

/**
 * Format relative time (e.g., "2 minutes ago").
 *
 * @param isoString - ISO 8601 timestamp
 * @returns Relative time string
 */
export function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSec = Math.floor(diffMs / 1000)
    const diffMin = Math.floor(diffSec / 60)
    const diffHour = Math.floor(diffMin / 60)
    const diffDay = Math.floor(diffHour / 24)

    if (diffSec < 60) return `${diffSec}s ago`
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHour < 24) return `${diffHour}h ago`
    return `${diffDay}d ago`
  } catch {
    return isoString
  }
}

/**
 * Format duration in seconds to readable string (e.g., "1h 23m 45s").
 *
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  const parts: string[] = []

  if (hours > 0) parts.push(`${hours}h`)
  if (minutes > 0) parts.push(`${minutes}m`)
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`)

  return parts.join(' ')
}

/**
 * Calculate elapsed time between two timestamps.
 *
 * @param startTime - Start timestamp (ISO 8601)
 * @param endTime - End timestamp (ISO 8601) or null for current time
 * @returns Elapsed seconds
 */
export function calculateElapsedSeconds(
  startTime: string,
  endTime: string | null = null
): number {
  try {
    const start = new Date(startTime)
    const end = endTime ? new Date(endTime) : new Date()
    return Math.floor((end.getTime() - start.getTime()) / 1000)
  } catch {
    return 0
  }
}

/**
 * Format file size in bytes to readable string (e.g., "1.5 KB").
 *
 * @param bytes - File size in bytes
 * @returns Formatted size string
 */
export function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`
}

/**
 * Format number with thousand separators.
 *
 * @param num - Number to format
 * @returns Formatted number string
 */
export function formatNumber(num: number): string {
  return num.toLocaleString('en-US')
}

/**
 * Format token count with K/M suffix.
 *
 * @param tokens - Token count
 * @returns Formatted token string (e.g., "18.5K", "1.2M")
 */
export function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`
  }
  return tokens.toString()
}

/**
 * Format percentage with one decimal place.
 *
 * @param value - Current value
 * @param total - Total value
 * @returns Formatted percentage string
 */
export function formatPercentage(value: number, total: number): string {
  if (total === 0) return '0%'
  return `${((value / total) * 100).toFixed(1)}%`
}

/**
 * Format bytes into human-readable string
 * @param bytes - Number of bytes
 * @returns Formatted string (e.g., "1.46 KB")
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  // Prevent array out of bounds
  const sizeIndex = Math.min(i, sizes.length - 1);

  const value = bytes / Math.pow(k, sizeIndex);

  // Format based on whether it's a whole number or not
  const formatted = Number.isInteger(value)
    ? value.toString()
    : value.toFixed(2);

  return `${formatted} ${sizes[sizeIndex]}`;
}
