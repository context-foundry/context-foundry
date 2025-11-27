import { z } from 'zod';

// ============================================================================
// QUIZ TYPES
// ============================================================================

export const QuizQuestionSchema = z.object({
  id: z.string(),
  question: z.string(),
  options: z.array(z.string()),
  correctAnswer: z.number(), // Index of correct option
  explanation: z.string(),
  difficulty: z.enum(['easy', 'medium', 'hard']).optional(),
});

export type QuizQuestion = z.infer<typeof QuizQuestionSchema>;

export const QuizSchema = z.object({
  patternId: z.string(),
  patternName: z.string(),
  questions: z.array(QuizQuestionSchema),
  passingScore: z.number().min(0).max(100).default(70),
  totalPoints: z.number(),
  generatedAt: z.string(),
  cacheSource: z.enum(['tier1', 'tier2', 'tier3', 'generated']).optional(),
});

export type Quiz = z.infer<typeof QuizSchema>;

export interface QuizState {
  currentQuestionIndex: number;
  answers: Record<number, number>; // Question index -> selected option index
  score: number | null;
  completed: boolean;
  startedAt: number;
  completedAt: number | null;
}

export interface QuizResult {
  score: number;
  totalQuestions: number;
  correctAnswers: number;
  passed: boolean;
  timeTaken: number; // seconds
  questionResults: Array<{
    question: QuizQuestion;
    selectedAnswer: number;
    isCorrect: boolean;
  }>;
}

// ============================================================================
// SCENARIO TYPES
// ============================================================================

export const DecisionOptionSchema = z.object({
  id: z.string(),
  text: z.string(),
  nextNodeId: z.string(),
  isCorrect: z.boolean().optional(),
  rationale: z.string().optional(),
});

export type DecisionOption = z.infer<typeof DecisionOptionSchema>;

export const ScenarioNodeSchema = z.object({
  id: z.string(),
  type: z.enum(['start', 'decision', 'outcome', 'end']),
  title: z.string(),
  description: z.string(),
  options: z.array(DecisionOptionSchema).optional(),
  isSuccessful: z.boolean().optional(), // For outcome nodes
  feedback: z.string().optional(),
  imageUrl: z.string().optional(),
});

export type ScenarioNode = z.infer<typeof ScenarioNodeSchema>;

export const ScenarioSchema = z.object({
  patternId: z.string(),
  patternName: z.string(),
  title: z.string(),
  description: z.string(),
  nodes: z.array(ScenarioNodeSchema),
  startNodeId: z.string(),
  generatedAt: z.string(),
  cacheSource: z.enum(['tier1', 'tier2', 'tier3', 'generated']).optional(),
});

export type Scenario = z.infer<typeof ScenarioSchema>;

export interface ScenarioState {
  currentNodeId: string;
  pathTaken: string[]; // Node IDs in order
  decisionsCorrect: number;
  decisionsTotal: number;
  completed: boolean;
  successful: boolean | null;
  startedAt: number;
  completedAt: number | null;
}

// ============================================================================
// FILL-IN-THE-BLANK TYPES
// ============================================================================

export const FillBlankExerciseSchema = z.object({
  patternId: z.string(),
  patternName: z.string(),
  sentences: z.array(z.object({
    id: z.string(),
    template: z.string(), // Text with {{blank}} markers
    blanks: z.array(z.object({
      id: z.string(),
      correctAnswers: z.array(z.string()), // Multiple acceptable answers
      hint: z.string().optional(),
      caseSensitive: z.boolean().default(false),
    })),
    explanation: z.string().optional(),
  })),
  generatedAt: z.string(),
  cacheSource: z.enum(['tier1', 'tier2', 'tier3', 'generated']).optional(),
});

export type FillBlankExercise = z.infer<typeof FillBlankExerciseSchema>;

export interface FillBlankState {
  answers: Record<string, string>; // Blank ID -> user answer
  completed: boolean;
  score: number | null;
  startedAt: number;
  completedAt: number | null;
}

// ============================================================================
// LEARNING MODULE TYPES
// ============================================================================

export type LearningModuleType = 'quiz' | 'scenario' | 'fill-blank';

export interface LearningModule {
  type: LearningModuleType;
  patternId: string;
  content: Quiz | Scenario | FillBlankExercise;
}

// ============================================================================
// HINT TYPES
// ============================================================================

export interface HintRequest {
  patternId: string;
  context: string; // Current question/scenario context
  userProgress: string; // What user has attempted so far
}

export interface HintResponse {
  hint: string;
  relatedConcepts: string[];
  costEstimate: number;
}

// ============================================================================
// VALIDATION TYPES
// ============================================================================

export interface ValidationFeedback {
  isCorrect: boolean;
  message: string;
  explanation?: string;
  relatedBestPractices?: string[];
}
