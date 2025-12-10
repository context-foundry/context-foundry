/**
 * Transcript Parser
 *
 * Extracts structured content (concepts, procedures) from
 * conversational training video transcripts.
 */

import {
  type ParsedTranscript,
  type Concept,
  type Procedure,
  type TranscriptFile,
} from '@/types/transcript';

/**
 * Parse a transcript file into structured content
 */
export function parseTranscript(transcript: TranscriptFile): ParsedTranscript {
  const { content, metadata } = transcript;

  // Extract concepts and procedures
  const concepts = extractConcepts(content, metadata.id);
  const procedures = extractProcedures(content, metadata.id);

  // Update metadata with counts
  const updatedMetadata = {
    ...metadata,
    conceptCount: concepts.length,
  };

  return {
    metadata: updatedMetadata,
    content,
    concepts,
    procedures,
  };
}

/**
 * Extract concept definitions from transcript content
 *
 * Looks for patterns like:
 * - "X is a/an Y that..."
 * - "The X allows you to..."
 * - "X refers to..."
 * - "X means..."
 */
export function extractConcepts(content: string, transcriptId: string): Concept[] {
  const concepts: Concept[] = [];
  const sentences = splitIntoSentences(content);

  // Patterns for concept definitions
  const definitionPatterns = [
    /^(?:The\s+)?(\w+(?:\s+\w+)*)\s+is\s+(?:a|an|the)\s+(.+?)(?:\.|$)/i,
    /^(?:The\s+)?(\w+(?:\s+\w+)*)\s+allows?\s+(?:you\s+to\s+)?(.+?)(?:\.|$)/i,
    /^(?:The\s+)?(\w+(?:\s+\w+)*)\s+(?:refers?\s+to|means?)\s+(.+?)(?:\.|$)/i,
    /^(?:In\s+Workday,?\s+)?(?:the\s+)?(\w+(?:\s+\w+)*)\s+(?:is\s+used\s+to|helps?\s+(?:you\s+)?to?)\s+(.+?)(?:\.|$)/i,
  ];

  // Keywords that indicate Workday-specific concepts
  const workdayKeywords = [
    'workday', 'worker', 'position', 'supervisory', 'organization',
    'requisition', 'candidate', 'recruiting', 'learning', 'course',
    'program', 'enrollment', 'offering', 'report', 'dashboard',
    'worklet', 'analytics', 'discovery board', 'worksheet', 'HCM',
    'hire', 'terminate', 'transfer', 'job change', 'contingent',
    'business process', 'task', 'inbox', 'to do',
  ];

  for (let i = 0; i < sentences.length; i++) {
    const sentence = sentences[i].trim();

    // Skip very short sentences
    if (sentence.length < 20) continue;

    // Check if sentence contains Workday keywords
    const hasWorkdayContent = workdayKeywords.some((keyword) =>
      sentence.toLowerCase().includes(keyword)
    );

    if (!hasWorkdayContent) continue;

    // Try to match definition patterns
    for (const pattern of definitionPatterns) {
      const match = sentence.match(pattern);
      if (match) {
        const name = match[1].trim();
        const definition = match[2]?.trim();

        // Get surrounding context (previous and next sentences)
        const contextStart = Math.max(0, i - 1);
        const contextEnd = Math.min(sentences.length, i + 2);
        const context = sentences.slice(contextStart, contextEnd).join(' ');

        concepts.push({
          id: generateConceptId(transcriptId, name),
          name,
          definition,
          context,
          transcriptId,
        });

        break; // Only match first pattern
      }
    }
  }

  // Deduplicate by name
  const uniqueConcepts = deduplicateConcepts(concepts);

  return uniqueConcepts;
}

/**
 * Extract procedures (how-to steps) from transcript content
 *
 * Looks for patterns like:
 * - "To X, you need to..." / "To X, first..."
 * - "Step 1: ... Step 2: ..."
 * - "First, ... Then, ... Finally, ..."
 */
export function extractProcedures(content: string, transcriptId: string): Procedure[] {
  const procedures: Procedure[] = [];
  const paragraphs = content.split(/\n\n+/);

  // Pattern for "How to" titles
  const howToPattern = /how\s+to\s+(\w+(?:\s+\w+)*)/gi;

  // Step indicator patterns
  const stepPatterns = [
    /(?:^|\.\s+)(?:first|step\s*1)[,:\s]+([^.]+)/gi,
    /(?:^|\.\s+)(?:then|next|step\s*\d)[,:\s]+([^.]+)/gi,
    /(?:^|\.\s+)(?:finally|lastly|step\s*\d)[,:\s]+([^.]+)/gi,
  ];

  // Find "How to" sections
  for (let i = 0; i < paragraphs.length; i++) {
    const paragraph = paragraphs[i];

    // Find procedure titles
    const titleMatches = paragraph.matchAll(howToPattern);

    for (const match of titleMatches) {
      const procedureName = `How to ${match[1]}`;

      // Look for steps in this and subsequent paragraphs
      const searchText = paragraphs.slice(i, Math.min(i + 3, paragraphs.length)).join(' ');
      const steps = extractSteps(searchText);

      if (steps.length > 0) {
        procedures.push({
          id: generateProcedureId(transcriptId, procedureName),
          name: procedureName,
          steps,
          context: paragraph,
          transcriptId,
        });
      }
    }
  }

  return procedures;
}

/**
 * Extract numbered or sequential steps from text
 */
function extractSteps(text: string): string[] {
  const steps: string[] = [];

  // Try numbered steps first (Step 1, Step 2, etc.)
  const numberedPattern = /step\s*(\d+)[:\s]+([^.]+(?:\.[^.]+)?)/gi;
  const numberedMatches = text.matchAll(numberedPattern);

  for (const match of numberedMatches) {
    steps.push(match[2].trim());
  }

  if (steps.length > 0) return steps;

  // Try sequential words (First, Then, Finally)
  const sequentialPatterns = [
    /first[,:\s]+([^.]+)/i,
    /(?:then|next)[,:\s]+([^.]+)/gi,
    /(?:finally|lastly)[,:\s]+([^.]+)/i,
  ];

  for (const pattern of sequentialPatterns) {
    const matches = text.matchAll(pattern);
    for (const match of matches) {
      const step = match[1].trim();
      if (step.length > 10 && !steps.includes(step)) {
        steps.push(step);
      }
    }
  }

  return steps;
}

/**
 * Split text into sentences
 */
function splitIntoSentences(text: string): string[] {
  // Simple sentence splitting (handles most cases)
  return text
    .replace(/\n+/g, ' ')
    .split(/(?<=[.!?])\s+/)
    .filter((s) => s.trim().length > 0);
}

/**
 * Generate a unique ID for a concept
 */
function generateConceptId(transcriptId: string, name: string): string {
  const normalizedName = name.toLowerCase().replace(/\s+/g, '_');
  return `concept_${transcriptId}_${normalizedName}`.slice(0, 100);
}

/**
 * Generate a unique ID for a procedure
 */
function generateProcedureId(transcriptId: string, name: string): string {
  const normalizedName = name.toLowerCase().replace(/\s+/g, '_');
  return `procedure_${transcriptId}_${normalizedName}`.slice(0, 100);
}

/**
 * Deduplicate concepts by name (keep first occurrence with most context)
 */
function deduplicateConcepts(concepts: Concept[]): Concept[] {
  const seen = new Map<string, Concept>();

  for (const concept of concepts) {
    const key = concept.name.toLowerCase();
    const existing = seen.get(key);

    if (!existing || (concept.context.length > existing.context.length)) {
      seen.set(key, concept);
    }
  }

  return Array.from(seen.values());
}

/**
 * Extract key topics from transcript content
 * (simpler than full concept extraction, for categorization)
 */
export function extractKeyTopics(content: string): string[] {
  const topics: string[] = [];

  // Common Workday topic patterns
  const topicPatterns = [
    /(?:the\s+)?(\w+\s+(?:profile|menu|screen|page|task|process|report|dashboard))/gi,
    /(?:the\s+)?(\w+\s+(?:inbox|to-?do|list|queue))/gi,
    /(?:manage|create|update|view|access)\s+(?:the\s+)?(\w+(?:\s+\w+)*)/gi,
  ];

  for (const pattern of topicPatterns) {
    const matches = content.matchAll(pattern);
    for (const match of matches) {
      const topic = (match[1] || match[0]).trim();
      if (topic.length > 3 && !topics.includes(topic.toLowerCase())) {
        topics.push(topic.toLowerCase());
      }
    }
  }

  return topics.slice(0, 20); // Limit to top 20 topics
}
