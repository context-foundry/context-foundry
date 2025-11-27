import {
  Achievement,
  AchievementType,
  Milestone,
  MILESTONES,
  UserProgress,
  PatternProgress,
} from '@/types/progress';

/**
 * Achievement Calculator
 *
 * Calculates and unlocks achievements based on user progress.
 * Implements milestone tracking and achievement logic.
 */

/**
 * Check and unlock achievements based on progress
 * @param progress - Current user progress
 * @param newProgress - New pattern progress (if applicable)
 * @returns Array of newly unlocked achievements
 */
export function checkAchievements(
  progress: UserProgress,
  newProgress?: PatternProgress
): Achievement[] {
  const unlocked: Achievement[] = [];

  // Check all achievement types
  unlocked.push(...checkFirstPatternAchievement(progress));
  unlocked.push(...checkCategoryMasterAchievements(progress));
  unlocked.push(...checkQuizAceAchievement(progress));
  unlocked.push(...checkScenarioChampionAchievement(progress));
  unlocked.push(...checkPerfectScoreAchievement(progress, newProgress));
  unlocked.push(...checkSpeedLearnerAchievement(progress, newProgress));
  unlocked.push(...checkKnowledgeExplorerAchievement(progress));
  unlocked.push(...checkMilestoneAchievements(progress));

  // Filter out achievements already unlocked
  const existingIds = new Set(progress.achievements.map((a) => a.id));
  return unlocked.filter((a) => !existingIds.has(a.id));
}

/**
 * First Pattern Achievement
 * Unlocked when completing first pattern
 */
function checkFirstPatternAchievement(progress: UserProgress): Achievement[] {
  if (progress.totalPatternsCompleted === 1) {
    return [
      createAchievement({
        type: 'first-pattern',
        name: 'First Steps',
        description: 'Complete your first pattern',
        iconName: 'star',
      }),
    ];
  }
  return [];
}

/**
 * Category Master Achievements
 * Unlocked when completing all patterns in a category
 */
function checkCategoryMasterAchievements(progress: UserProgress): Achievement[] {
  const unlocked: Achievement[] = [];

  // Group patterns by category
  const categoryCounts: Record<string, { completed: number; total: number }> = {};

  for (const [_, patternProgress] of Object.entries(progress.patternsProgress)) {
    // Note: We would need pattern data here to get category
    // For now, this is a placeholder implementation
    // In real implementation, we'd need to cross-reference with pattern parser
  }

  // Check each category for completion
  for (const [category, counts] of Object.entries(categoryCounts)) {
    if (counts.completed === counts.total && counts.total > 0) {
      const existingAchievement = progress.achievements.find(
        (a) => a.type === 'category-master' && a.metadata?.category === category
      );

      if (!existingAchievement) {
        unlocked.push(
          createAchievement({
            type: 'category-master',
            name: `${category} Master`,
            description: `Complete all patterns in ${category} category`,
            iconName: 'trophy',
            metadata: { category },
          })
        );
      }
    }
  }

  return unlocked;
}

/**
 * Quiz Ace Achievement
 * Unlocked when passing 10 quizzes with 90%+ score
 */
function checkQuizAceAchievement(progress: UserProgress): Achievement[] {
  const highScoreQuizzes = Object.values(progress.patternsProgress).filter(
    (p) => p.quizScore !== undefined && p.quizScore >= 90
  ).length;

  if (highScoreQuizzes >= 10) {
    return [
      createAchievement({
        type: 'quiz-ace',
        name: 'Quiz Ace',
        description: 'Score 90% or higher on 10 quizzes',
        iconName: 'graduation-cap',
        metadata: { count: highScoreQuizzes },
      }),
    ];
  }
  return [];
}

/**
 * Scenario Champion Achievement
 * Unlocked when completing 10 scenarios successfully
 */
function checkScenarioChampionAchievement(progress: UserProgress): Achievement[] {
  const successfulScenarios = Object.values(progress.patternsProgress).filter(
    (p) => p.scenarioCompleted && p.scenarioSuccessful === true
  ).length;

  if (successfulScenarios >= 10) {
    return [
      createAchievement({
        type: 'scenario-champion',
        name: 'Scenario Champion',
        description: 'Successfully complete 10 scenarios',
        iconName: 'shield',
        metadata: { count: successfulScenarios },
      }),
    ];
  }
  return [];
}

/**
 * Perfect Score Achievement
 * Unlocked when getting 100% on a quiz
 */
function checkPerfectScoreAchievement(
  progress: UserProgress,
  newProgress?: PatternProgress
): Achievement[] {
  if (newProgress?.quizScore === 100) {
    return [
      createAchievement({
        type: 'perfect-score',
        name: 'Perfect Score',
        description: 'Score 100% on a quiz',
        iconName: 'award',
        metadata: { patternId: newProgress.patternId },
      }),
    ];
  }
  return [];
}

/**
 * Speed Learner Achievement
 * Unlocked when completing a pattern in under estimated time
 */
function checkSpeedLearnerAchievement(
  progress: UserProgress,
  newProgress?: PatternProgress
): Achievement[] {
  // This would require comparing actual time vs estimated time
  // Placeholder implementation
  if (newProgress?.timeSpentMinutes && newProgress.timeSpentMinutes < 10) {
    return [
      createAchievement({
        type: 'speed-learner',
        name: 'Speed Learner',
        description: 'Complete a pattern faster than estimated time',
        iconName: 'zap',
        metadata: { patternId: newProgress.patternId },
      }),
    ];
  }
  return [];
}

/**
 * Knowledge Explorer Achievement
 * Unlocked when attempting patterns from 5+ different categories
 */
function checkKnowledgeExplorerAchievement(progress: UserProgress): Achievement[] {
  // Placeholder - would need pattern data to determine categories
  // For now, just check if user has attempted many patterns
  if (Object.keys(progress.patternsProgress).length >= 15) {
    return [
      createAchievement({
        type: 'knowledge-explorer',
        name: 'Knowledge Explorer',
        description: 'Explore patterns from multiple categories',
        iconName: 'compass',
      }),
    ];
  }
  return [];
}

/**
 * Milestone Achievements
 * Unlocked at 10, 25, 50, 100, 169 completed patterns
 */
function checkMilestoneAchievements(progress: UserProgress): Achievement[] {
  const unlocked: Achievement[] = [];

  for (const milestone of MILESTONES) {
    if (progress.totalPatternsCompleted >= milestone.targetCount) {
      const existingAchievement = progress.achievements.find(
        (a) => a.id === milestone.id
      );

      if (!existingAchievement) {
        unlocked.push(
          createAchievement({
            type: milestone.id as AchievementType,
            name: milestone.name,
            description: milestone.description,
            iconName: milestone.iconName,
            metadata: { targetCount: milestone.targetCount },
          })
        );
      }
    }
  }

  return unlocked;
}

/**
 * Create achievement object
 * @param params - Achievement parameters
 * @returns Achievement object
 */
function createAchievement(params: {
  type: AchievementType;
  name: string;
  description: string;
  iconName: string;
  metadata?: Record<string, any>;
}): Achievement {
  return {
    id: `${params.type}-${Date.now()}`,
    type: params.type,
    name: params.name,
    description: params.description,
    iconName: params.iconName,
    unlockedAt: Date.now(),
    metadata: params.metadata,
  };
}

/**
 * Calculate milestones with current progress
 * @param progress - User progress
 * @returns Array of milestones with progress
 */
export function calculateMilestones(progress: UserProgress): Milestone[] {
  return MILESTONES.map((milestone) => ({
    ...milestone,
    currentCount: progress.totalPatternsCompleted,
    completed: progress.totalPatternsCompleted >= milestone.targetCount,
    completedAt: progress.achievements.find((a) => a.id === milestone.id)?.unlockedAt,
  }));
}

/**
 * Get next milestone to achieve
 * @param progress - User progress
 * @returns Next milestone or null if all completed
 */
export function getNextMilestone(progress: UserProgress): Milestone | null {
  const milestones = calculateMilestones(progress);
  const incomplete = milestones.filter((m) => !m.completed);

  if (incomplete.length === 0) return null;

  return incomplete[0]; // First incomplete milestone
}

/**
 * Calculate progress percentage to next milestone
 * @param progress - User progress
 * @returns Progress percentage (0-100)
 */
export function getMilestoneProgress(progress: UserProgress): number {
  const next = getNextMilestone(progress);

  if (!next) return 100; // All milestones completed

  return Math.round(
    (progress.totalPatternsCompleted / next.targetCount) * 100
  );
}

/**
 * Check if user is eligible for certificate
 * @param progress - User progress
 * @param milestoneId - Milestone ID
 * @returns True if eligible
 */
export function isCertificateEligible(
  progress: UserProgress,
  milestoneId: string
): boolean {
  const milestone = MILESTONES.find((m) => m.id === milestoneId);

  if (!milestone || !milestone.certificateEligible) {
    return false;
  }

  const achieved = progress.achievements.find((a) => a.id === milestoneId);

  return achieved !== undefined;
}

/**
 * Get all certificate-eligible milestones that are completed
 * @param progress - User progress
 * @returns Array of completed certificate-eligible milestones
 */
export function getCompletedCertificateMilestones(
  progress: UserProgress
): Milestone[] {
  const milestones = calculateMilestones(progress);

  return milestones.filter(
    (m) => m.certificateEligible && m.completed
  );
}

/**
 * Calculate achievement statistics
 * @param progress - User progress
 * @returns Achievement statistics
 */
export function getAchievementStats(progress: UserProgress): {
  totalUnlocked: number;
  totalAvailable: number;
  categoryMasters: number;
  milestones: number;
  special: number;
} {
  const totalAvailable = MILESTONES.length + 20; // Estimate of all possible achievements

  const categoryMasters = progress.achievements.filter(
    (a) => a.type === 'category-master'
  ).length;

  const milestones = progress.achievements.filter((a) =>
    a.type.startsWith('milestone-')
  ).length;

  const special = progress.achievements.filter(
    (a) =>
      !a.type.startsWith('milestone-') && a.type !== 'category-master'
  ).length;

  return {
    totalUnlocked: progress.achievements.length,
    totalAvailable,
    categoryMasters,
    milestones,
    special,
  };
}

/**
 * Get recently unlocked achievements
 * @param progress - User progress
 * @param limit - Maximum number of recent achievements
 * @returns Array of recent achievements
 */
export function getRecentAchievements(
  progress: UserProgress,
  limit: number = 5
): Achievement[] {
  return [...progress.achievements]
    .sort((a, b) => b.unlockedAt - a.unlockedAt)
    .slice(0, limit);
}
