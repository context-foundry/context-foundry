/**
 * Token budget calculation utilities.
 *
 * Context Foundry uses a 200K token budget with zone-based indicators:
 * - Green: 0-40% (0-80K tokens) - SMART zone
 * - Yellow: 40-70% (80K-140K tokens) - EFFICIENT zone
 * - Red: 70-100% (140K-200K tokens) - DANGER zone
 */

export const TOKEN_BUDGET_TOTAL = 200_000

export enum TokenZone {
  SMART = 'smart',
  EFFICIENT = 'efficient',
  DANGER = 'danger',
}

export interface TokenBudgetInfo {
  used: number
  total: number
  percentage: number
  zone: TokenZone
  color: string
  remaining: number
}

/**
 * Calculate token budget zone based on usage percentage.
 *
 * @param percentage - Usage percentage (0-100)
 * @returns Token zone
 */
export function getTokenZone(percentage: number): TokenZone {
  if (percentage < 40) return TokenZone.SMART
  if (percentage < 70) return TokenZone.EFFICIENT
  return TokenZone.DANGER
}

/**
 * Get color for token zone.
 *
 * @param zone - Token zone
 * @returns Tailwind CSS color class
 */
export function getZoneColor(zone: TokenZone): string {
  switch (zone) {
    case TokenZone.SMART:
      return 'text-green-500'
    case TokenZone.EFFICIENT:
      return 'text-yellow-500'
    case TokenZone.DANGER:
      return 'text-red-500'
  }
}

/**
 * Get background color for token zone.
 *
 * @param zone - Token zone
 * @returns Tailwind CSS background color class
 */
export function getZoneBackgroundColor(zone: TokenZone): string {
  switch (zone) {
    case TokenZone.SMART:
      return 'bg-green-500'
    case TokenZone.EFFICIENT:
      return 'bg-yellow-500'
    case TokenZone.DANGER:
      return 'bg-red-500'
  }
}

/**
 * Calculate comprehensive token budget information.
 *
 * @param tokensUsed - Number of tokens used
 * @param totalBudget - Total token budget (default: 200K)
 * @returns Token budget information
 */
export function calculateTokenBudget(
  tokensUsed: number,
  totalBudget: number = TOKEN_BUDGET_TOTAL
): TokenBudgetInfo {
  const percentage = (tokensUsed / totalBudget) * 100
  const zone = getTokenZone(percentage)
  const color = getZoneColor(zone)
  const remaining = Math.max(0, totalBudget - tokensUsed)

  return {
    used: tokensUsed,
    total: totalBudget,
    percentage,
    zone,
    color,
    remaining,
  }
}

/**
 * Get zone label for display.
 *
 * @param zone - Token zone
 * @returns Human-readable zone label
 */
export function getZoneLabel(zone: TokenZone): string {
  switch (zone) {
    case TokenZone.SMART:
      return 'SMART'
    case TokenZone.EFFICIENT:
      return 'EFFICIENT'
    case TokenZone.DANGER:
      return 'DANGER'
  }
}

/**
 * Check if token usage is in danger zone.
 *
 * @param tokensUsed - Number of tokens used
 * @param totalBudget - Total token budget
 * @returns True if in danger zone
 */
export function isInDangerZone(
  tokensUsed: number,
  totalBudget: number = TOKEN_BUDGET_TOTAL
): boolean {
  const percentage = (tokensUsed / totalBudget) * 100
  return percentage >= 70
}

/**
 * Calculate the token usage zone based on percentage
 * @param tokensUsed - Number of tokens currently used
 * @param totalTokens - Total token budget
 * @returns Zone classification: 'green' (<40%), 'yellow' (40-70%), 'red' (>70%)
 */
export function calculateTokenZone(
  tokensUsed: number,
  totalTokens: number
): 'green' | 'yellow' | 'red' {
  if (totalTokens === 0) return 'green'; // Edge case: prevent division by zero

  const percentage = (tokensUsed / totalTokens) * 100;

  if (percentage < 40) return 'green';  // SMART zone
  if (percentage < 70) return 'yellow'; // EFFICIENT zone
  return 'red';                         // DANGER zone
}

/**
 * Calculate token budget percentage
 * @param tokensUsed - Number of tokens currently used
 * @param totalTokens - Total token budget
 * @returns Percentage (0-100)
 */
export function calculateTokenPercentage(
  tokensUsed: number,
  totalTokens: number
): number {
  if (totalTokens === 0) return 0;
  return Math.round((tokensUsed / totalTokens) * 100);
}
