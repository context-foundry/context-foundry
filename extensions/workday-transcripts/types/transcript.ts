import { z } from 'zod';
import { WorkdayCategorySchema } from './card';

/**
 * Transcript metadata extracted from filename
 */
export const TranscriptMetadataSchema = z.object({
  id: z.string(), // Generated hash from filename
  filename: z.string(),
  title: z.string(), // Extracted from filename
  category: WorkdayCategorySchema,
  date: z.string(), // YYYY-MM-DD extracted from filename
  lineCount: z.number().int().min(0),
  characterCount: z.number().int().min(0),
  conceptCount: z.number().int().min(0).optional(),
  cardCount: z.number().int().min(0).optional(),
});

export type TranscriptMetadata = z.infer<typeof TranscriptMetadataSchema>;

/**
 * A concept extracted from transcript content
 */
export const ConceptSchema = z.object({
  id: z.string(),
  name: z.string(),
  definition: z.string().optional(),
  context: z.string(), // Surrounding text for context
  transcriptId: z.string(),
});

export type Concept = z.infer<typeof ConceptSchema>;

/**
 * A procedure/how-to extracted from transcript
 */
export const ProcedureSchema = z.object({
  id: z.string(),
  name: z.string(), // e.g., "How to hire a worker"
  steps: z.array(z.string()),
  context: z.string(),
  transcriptId: z.string(),
});

export type Procedure = z.infer<typeof ProcedureSchema>;

/**
 * Fully parsed transcript with extracted content
 */
export const ParsedTranscriptSchema = z.object({
  metadata: TranscriptMetadataSchema,
  content: z.string(), // Raw transcript text
  concepts: z.array(ConceptSchema),
  procedures: z.array(ProcedureSchema),
});

export type ParsedTranscript = z.infer<typeof ParsedTranscriptSchema>;

/**
 * Transcript file for loading
 */
export const TranscriptFileSchema = z.object({
  filename: z.string(),
  path: z.string(),
  content: z.string(),
  metadata: TranscriptMetadataSchema,
});

export type TranscriptFile = z.infer<typeof TranscriptFileSchema>;

/**
 * Category mapping patterns for filename detection
 */
export const CATEGORY_PATTERNS: Record<string, RegExp> = {
  HCM: /Workday HCM/i,
  Recruiting: /Workday Recruiting/i,
  Learning: /Workday Learning/i,
  Analytics: /Analytics and Reporting/i,
  General: /Learn with Workday/i,
};

/**
 * Extract category from transcript filename
 */
export function extractCategoryFromFilename(
  filename: string
): z.infer<typeof WorkdayCategorySchema> {
  for (const [category, pattern] of Object.entries(CATEGORY_PATTERNS)) {
    if (pattern.test(filename)) {
      return category as z.infer<typeof WorkdayCategorySchema>;
    }
  }
  return 'General';
}

/**
 * Extract date from transcript filename
 * Expected format: "... - YYYY-MM-DD.txt"
 */
export function extractDateFromFilename(filename: string): string {
  const dateMatch = filename.match(/(\d{4}-\d{2}-\d{2})/);
  return dateMatch ? dateMatch[1] : new Date().toISOString().split('T')[0];
}

/**
 * Extract title from transcript filename
 * Expected format: "Workday - TITLE Category - DATE.txt"
 */
export function extractTitleFromFilename(filename: string): string {
  // Remove "Workday - " prefix
  let title = filename.replace(/^Workday - /, '');

  // Remove category suffix (e.g., "Workday HCM", "Workday Recruiting")
  title = title.replace(
    / (Workday HCM|Workday Recruiting|Workday Learning|Analytics and Reporting|Learn with Workday)/,
    ''
  );

  // Remove date suffix
  title = title.replace(/ - \d{4}-\d{2}-\d{2}\.txt$/, '');

  // Remove .txt extension if still present
  title = title.replace(/\.txt$/, '');

  return title.trim();
}

/**
 * Generate a stable ID from filename
 */
export function generateTranscriptId(filename: string): string {
  // Create a simple hash from the filename
  let hash = 0;
  for (let i = 0; i < filename.length; i++) {
    const char = filename.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return `transcript_${Math.abs(hash).toString(16)}`;
}

/**
 * Create transcript metadata from filename and content
 */
export function createTranscriptMetadata(
  filename: string,
  content: string
): TranscriptMetadata {
  return {
    id: generateTranscriptId(filename),
    filename,
    title: extractTitleFromFilename(filename),
    category: extractCategoryFromFilename(filename),
    date: extractDateFromFilename(filename),
    lineCount: content.split('\n').length,
    characterCount: content.length,
  };
}
