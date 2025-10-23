// Utility functions

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with proper precedence
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format date to readable string
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(d);
}

/**
 * Format datetime to readable string
 */
export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(d);
}

/**
 * Format time to readable string
 */
export function formatTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  }).format(d);
}

/**
 * Get match status badge color
 */
export function getMatchStatusColor(status: string): string {
  switch (status) {
    case 'scheduled':
      return 'bg-blue-100 text-blue-800';
    case 'in_progress':
      return 'bg-green-100 text-green-800';
    case 'completed':
      return 'bg-gray-100 text-gray-800';
    case 'cancelled':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

/**
 * Get match status display text
 */
export function getMatchStatusText(status: string): string {
  switch (status) {
    case 'scheduled':
      return 'Scheduled';
    case 'in_progress':
      return 'Live';
    case 'completed':
      return 'Completed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return status;
  }
}

/**
 * Truncate text to specified length
 */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return text.slice(0, length) + '...';
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null;
      func(...args);
    };

    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);
  };
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate password strength
 */
export function isValidPassword(password: string): {
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push('Password must be at least 8 characters');
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

/**
 * Get player names for display
 */
export function getPlayerNames(match: {
  player1Name: string;
  player2Name: string;
  player3Name?: string;
  player4Name?: string;
  matchType: 'singles' | 'doubles';
}): {
  team1: string;
  team2: string;
} {
  if (match.matchType === 'singles') {
    return {
      team1: match.player1Name,
      team2: match.player2Name,
    };
  }

  return {
    team1: match.player3Name
      ? `${match.player1Name} / ${match.player3Name}`
      : match.player1Name,
    team2: match.player4Name
      ? `${match.player2Name} / ${match.player4Name}`
      : match.player2Name,
  };
}

/**
 * Format score display
 */
export function formatScore(
  player1Score: number,
  player2Score: number,
  isTiebreak = false
): string {
  if (isTiebreak) {
    return `${player1Score}-${player2Score}`;
  }

  // Convert points to tennis score
  const scoreMap: { [key: number]: string } = {
    0: '0',
    1: '15',
    2: '30',
    3: '40',
  };

  // Handle deuce and advantage
  if (player1Score >= 3 && player2Score >= 3) {
    if (player1Score === player2Score) {
      return 'Deuce';
    }
    if (player1Score > player2Score) {
      return 'Ad In';
    }
    return 'Ad Out';
  }

  return `${scoreMap[player1Score] || player1Score}-${scoreMap[player2Score] || player2Score}`;
}
