import { Pattern, TransformedPattern } from '@/types/pattern';
import { PatternProgress } from '@/types/progress';

/**
 * PatternTransformer - Transform patterns for UI display
 *
 * Provides utilities to transform raw pattern data into UI-friendly formats
 * with display labels, formatting, and progress information.
 */
export class PatternTransformer {
  /**
   * Transform a single pattern for UI display
   * @param pattern - Raw pattern data
   * @param progress - Optional progress data for the pattern
   * @returns Transformed pattern with display labels
   */
  public transformPattern(pattern: Pattern, progress?: PatternProgress): TransformedPattern {
    return {
      ...pattern,
      displayName: this.formatDisplayName(pattern.name),
      categoryLabel: this.formatCategoryLabel(pattern.category),
      difficultyLabel: this.formatDifficultyLabel(pattern.difficulty),
      estimatedTimeLabel: this.formatEstimatedTimeLabel(pattern.estimated_time_minutes),
      completionStatus: progress?.status || 'not-started',
      completionPercentage: progress ? this.calculateCompletionPercentage(progress) : 0,
    };
  }

  /**
   * Transform multiple patterns for UI display
   * @param patterns - Array of raw patterns
   * @param progressMap - Optional map of pattern ID to progress data
   * @returns Array of transformed patterns
   */
  public transformPatterns(
    patterns: Pattern[],
    progressMap?: Record<string, PatternProgress>
  ): TransformedPattern[] {
    return patterns.map((pattern) => {
      const progress = progressMap?.[pattern.id];
      return this.transformPattern(pattern, progress);
    });
  }

  /**
   * Format pattern name for display
   * @param name - Raw pattern name
   * @returns Formatted display name
   */
  private formatDisplayName(name: string): string {
    // Pattern names are already human-readable, just return as-is
    return name;
  }

  /**
   * Format category label with icon emoji
   * @param category - Category name
   * @returns Formatted category label
   */
  private formatCategoryLabel(category: string): string {
    const categoryIcons: Record<string, string> = {
      'Security': '🔒 Security',
      'Architecture': '🏗️ Architecture',
      'Performance': '⚡ Performance',
      'Quality Assurance': '✅ Quality Assurance',
      'UI/UX': '🎨 UI/UX',
      'Testing': '🧪 Testing',
      'Accessibility': '♿ Accessibility',
      'Error Handling': '🚨 Error Handling',
      'Monitoring': '📊 Monitoring',
      'Reliability': '🛡️ Reliability',
    };

    return categoryIcons[category] || category;
  }

  /**
   * Format difficulty label with color and icon
   * @param difficulty - Difficulty level
   * @returns Formatted difficulty label
   */
  private formatDifficultyLabel(difficulty?: string): string {
    if (!difficulty) return 'Not specified';

    const difficultyLabels: Record<string, string> = {
      'beginner': '🟢 Beginner',
      'intermediate': '🟡 Intermediate',
      'advanced': '🔴 Advanced',
    };

    return difficultyLabels[difficulty] || difficulty;
  }

  /**
   * Format estimated time label
   * @param minutes - Estimated time in minutes
   * @returns Formatted time label
   */
  private formatEstimatedTimeLabel(minutes?: number): string {
    if (!minutes) return 'Not specified';

    if (minutes < 60) {
      return `${minutes} min`;
    }

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (remainingMinutes === 0) {
      return `${hours} hr`;
    }

    return `${hours} hr ${remainingMinutes} min`;
  }

  /**
   * Calculate completion percentage based on progress data
   * @param progress - Pattern progress data
   * @returns Completion percentage (0-100)
   */
  private calculateCompletionPercentage(progress: PatternProgress): number {
    if (progress.status === 'completed') return 100;
    if (progress.status === 'not-started') return 0;

    // For in-progress, calculate based on completed activities
    let completedActivities = 0;
    let totalActivities = 3; // Quiz, Scenario, Fill-blank

    if (progress.quizScore !== undefined && progress.quizScore >= 70) {
      completedActivities++;
    }

    if (progress.scenarioCompleted) {
      completedActivities++;
    }

    if (progress.fillBlankScore !== undefined && progress.fillBlankScore >= 70) {
      completedActivities++;
    }

    return Math.round((completedActivities / totalActivities) * 100);
  }

  /**
   * Group patterns by category
   * @param patterns - Array of transformed patterns
   * @returns Map of category to patterns
   */
  public groupByCategory(patterns: TransformedPattern[]): Record<string, TransformedPattern[]> {
    return patterns.reduce((acc, pattern) => {
      const category = pattern.category;
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(pattern);
      return acc;
    }, {} as Record<string, TransformedPattern[]>);
  }

  /**
   * Group patterns by difficulty
   * @param patterns - Array of transformed patterns
   * @returns Map of difficulty to patterns
   */
  public groupByDifficulty(patterns: TransformedPattern[]): Record<string, TransformedPattern[]> {
    return patterns.reduce((acc, pattern) => {
      const difficulty = pattern.difficulty || 'unspecified';
      if (!acc[difficulty]) {
        acc[difficulty] = [];
      }
      acc[difficulty].push(pattern);
      return acc;
    }, {} as Record<string, TransformedPattern[]>);
  }

  /**
   * Sort patterns by completion percentage (descending)
   * @param patterns - Array of transformed patterns
   * @returns Sorted array
   */
  public sortByCompletion(patterns: TransformedPattern[]): TransformedPattern[] {
    return [...patterns].sort((a, b) => {
      const aCompletion = a.completionPercentage || 0;
      const bCompletion = b.completionPercentage || 0;
      return bCompletion - aCompletion;
    });
  }

  /**
   * Sort patterns by name (alphabetical)
   * @param patterns - Array of transformed patterns
   * @param order - Sort order (asc or desc)
   * @returns Sorted array
   */
  public sortByName(patterns: TransformedPattern[], order: 'asc' | 'desc' = 'asc'): TransformedPattern[] {
    return [...patterns].sort((a, b) => {
      const comparison = a.name.localeCompare(b.name);
      return order === 'asc' ? comparison : -comparison;
    });
  }

  /**
   * Sort patterns by difficulty (beginner -> intermediate -> advanced)
   * @param patterns - Array of transformed patterns
   * @returns Sorted array
   */
  public sortByDifficulty(patterns: TransformedPattern[]): TransformedPattern[] {
    const difficultyOrder: Record<string, number> = {
      'beginner': 1,
      'intermediate': 2,
      'advanced': 3,
    };

    return [...patterns].sort((a, b) => {
      const aOrder = difficultyOrder[a.difficulty || ''] || 999;
      const bOrder = difficultyOrder[b.difficulty || ''] || 999;
      return aOrder - bOrder;
    });
  }
}

// Export singleton instance
export const patternTransformer = new PatternTransformer();
