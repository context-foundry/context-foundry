/**
 * Zod Validation Schemas
 *
 * API input validation schemas for all endpoints.
 * This is an alias/re-export for schema-validator.ts to match architecture naming.
 */

export * from './schema-validator';
export * from './validation-rules';

// Re-export Zod schemas from types/learning.ts for convenience
import { z } from 'zod';

// API Request Schemas
export const GenerateQuizRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  difficulty: z.enum(['beginner', 'intermediate', 'advanced']).optional(),
  questionCount: z.number().min(3).max(10).optional(),
});

export const GenerateScenarioRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  complexity: z.enum(['simple', 'moderate', 'complex']).optional(),
  branchCount: z.number().min(2).max(5).optional(),
});

export const GenerateImageRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  imageType: z.enum(['module', 'category', 'pattern']).optional(),
  style: z.enum(['professional', 'modern', 'technical']).optional(),
});

export const GenerateHintRequestSchema = z.object({
  patternId: z.string().min(1, 'Pattern ID is required'),
  questionId: z.string().min(1, 'Question ID is required'),
  questionText: z.string().min(1, 'Question text is required'),
  userAnswer: z.string().optional(),
});

export const GenerateCertificateRequestSchema = z.object({
  userId: z.string().min(1, 'User ID is required'),
  userName: z.string().min(1, 'User name is required'),
  milestone: z.enum(['25', '50', '75', '100']),
  completedPatterns: z.array(z.string()).min(1),
  completionDate: z.string().optional(),
});

export type GenerateQuizRequest = z.infer<typeof GenerateQuizRequestSchema>;
export type GenerateScenarioRequest = z.infer<typeof GenerateScenarioRequestSchema>;
export type GenerateImageRequest = z.infer<typeof GenerateImageRequestSchema>;
export type GenerateHintRequest = z.infer<typeof GenerateHintRequestSchema>;
export type GenerateCertificateRequest = z.infer<typeof GenerateCertificateRequestSchema>;
