import { z } from 'zod';

// ============================================================================
// PROGRESS TRACKING TYPES
// ============================================================================

export const PatternProgressSchema = z.object({
  patternId: z.string(),
  patternName: z.string(),
  status: z.enum(['not-started', 'in-progress', 'completed']),
  quizScore: z.number().min(0).max(100).optional(),
  quizAttempts: z.number().default(0),
  scenarioCompleted: z.boolean().default(false),
  scenarioSuccessful: z.boolean().optional(),
  fillBlankScore: z.number().min(0).max(100).optional(),
  lastAccessed: z.number(), // Unix timestamp
  completedAt: z.number().optional(), // Unix timestamp
  timeSpentMinutes: z.number().default(0),
});

export type PatternProgress = z.infer<typeof PatternProgressSchema>;

// ============================================================================
// ACHIEVEMENT TYPES
// ============================================================================

export type AchievementType =
  | 'first-pattern'
  | 'category-master'
  | 'quiz-ace'
  | 'scenario-champion'
  | 'perfect-score'
  | 'speed-learner'
  | 'knowledge-explorer'
  | 'milestone-10'
  | 'milestone-25'
  | 'milestone-50'
  | 'milestone-100'
  | 'milestone-169';

export const AchievementSchema = z.object({
  id: z.string(),
  type: z.string() as z.ZodType<AchievementType>,
  name: z.string(),
  description: z.string(),
  iconName: z.string(),
  unlockedAt: z.number(), // Unix timestamp
  metadata: z.record(z.any()).optional(), // Extra data like category name, score, etc.
});

export type Achievement = z.infer<typeof AchievementSchema>;

// ============================================================================
// MILESTONE TYPES
// ============================================================================

export interface Milestone {
  id: string;
  name: string;
  description: string;
  targetCount: number;
  currentCount: number;
  completed: boolean;
  completedAt?: number;
  iconName: string;
  certificateEligible: boolean;
}

export const MILESTONES: Readonly<Omit<Milestone, 'currentCount' | 'completed' | 'completedAt'>[]> = [
  {
    id: 'milestone-10',
    name: 'Getting Started',
    description: 'Complete 10 patterns',
    targetCount: 10,
    iconName: 'rocket',
    certificateEligible: false,
  },
  {
    id: 'milestone-25',
    name: 'Apprentice',
    description: 'Complete 25 patterns',
    targetCount: 25,
    iconName: 'award',
    certificateEligible: true,
  },
  {
    id: 'milestone-50',
    name: 'Practitioner',
    description: 'Complete 50 patterns',
    targetCount: 50,
    iconName: 'medal',
    certificateEligible: true,
  },
  {
    id: 'milestone-100',
    name: 'Expert',
    description: 'Complete 100 patterns',
    targetCount: 100,
    iconName: 'crown',
    certificateEligible: true,
  },
  {
    id: 'milestone-169',
    name: 'Master',
    description: 'Complete all 169 patterns',
    targetCount: 169,
    iconName: 'trophy',
    certificateEligible: true,
  },
] as const;

// ============================================================================
// USER PROGRESS STATE
// ============================================================================

export const UserProgressSchema = z.object({
  userId: z.string().default('default'), // Support for future multi-user
  patternsProgress: z.record(PatternProgressSchema), // Pattern ID -> Progress
  achievements: z.array(AchievementSchema),
  totalPatternsCompleted: z.number().default(0),
  totalQuizzesPassed: z.number().default(0),
  totalScenariosCompleted: z.number().default(0),
  totalTimeSpentMinutes: z.number().default(0),
  averageQuizScore: z.number().default(0),
  currentStreak: z.number().default(0), // Days in a row
  longestStreak: z.number().default(0),
  lastActivityDate: z.number().optional(), // Unix timestamp
  createdAt: z.number(), // Unix timestamp
  updatedAt: z.number(), // Unix timestamp
});

export type UserProgress = z.infer<typeof UserProgressSchema>;

// ============================================================================
// PROGRESS ACTIONS
// ============================================================================

export type ProgressAction =
  | { type: 'COMPLETE_QUIZ'; payload: { patternId: string; patternName: string; score: number; timeTaken: number } }
  | { type: 'COMPLETE_SCENARIO'; payload: { patternId: string; patternName: string; successful: boolean; timeTaken: number } }
  | { type: 'COMPLETE_FILL_BLANK'; payload: { patternId: string; patternName: string; score: number; timeTaken: number } }
  | { type: 'COMPLETE_PATTERN'; payload: { patternId: string; patternName: string } }
  | { type: 'UNLOCK_ACHIEVEMENT'; payload: Achievement }
  | { type: 'UPDATE_TIME_SPENT'; payload: { patternId: string; minutes: number } }
  | { type: 'SYNC_PROGRESS'; payload: UserProgress }
  | { type: 'RESET_PROGRESS' };

// ============================================================================
// CERTIFICATE TYPES
// ============================================================================

export interface CertificateData {
  userName: string;
  milestoneName: string;
  milestoneDescription: string;
  patternsCompleted: number;
  averageScore: number;
  completionDate: string;
  certificateId: string;
}

export interface CertificateRequest {
  milestoneId: string;
  userName: string;
}
