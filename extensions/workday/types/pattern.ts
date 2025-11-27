import { z } from 'zod';

// Zod schema for pattern validation
export const PatternSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  module: z.string().optional(),
  applies_to: z.array(z.string()),
  description: z.string(),
  best_practices: z.array(z.string()),
  anti_patterns: z.array(z.string()).optional(),
  examples: z.array(z.string()).optional(),
  related_patterns: z.array(z.string()).optional(),
  tags: z.array(z.string()).optional(),
  difficulty: z.enum(['beginner', 'intermediate', 'advanced']).optional(),
  estimated_time_minutes: z.number().optional(),
});

export type Pattern = z.infer<typeof PatternSchema>;

// Pattern collection schema
export const PatternCollectionSchema = z.object({
  patterns: z.array(PatternSchema),
  metadata: z.object({
    total_count: z.number(),
    categories: z.array(z.string()),
    modules: z.array(z.string()),
    last_updated: z.string(),
  }).optional(),
});

export type PatternCollection = z.infer<typeof PatternCollectionSchema>;

// Transformed pattern for UI display
export interface TransformedPattern extends Pattern {
  displayName: string;
  categoryLabel: string;
  difficultyLabel: string;
  estimatedTimeLabel: string;
  completionStatus?: 'not-started' | 'in-progress' | 'completed';
  completionPercentage?: number;
}

// Pattern filter criteria
export interface PatternFilterCriteria {
  category?: string;
  module?: string;
  difficulty?: string;
  tags?: string[];
  searchQuery?: string;
  appliesTo?: string;
}

// Pattern sort options
export type PatternSortBy = 'name' | 'category' | 'difficulty' | 'recent' | 'completion';
export type PatternSortOrder = 'asc' | 'desc';

export interface PatternSortOptions {
  sortBy: PatternSortBy;
  order: PatternSortOrder;
}
