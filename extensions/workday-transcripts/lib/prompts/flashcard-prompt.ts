/**
 * Flashcard Generation Prompts
 *
 * Prompts for generating flashcard Q&A pairs from transcript content.
 */

import { type ParsedTranscript } from '@/types/transcript';
import { type WorkdayCategory, type ConceptType, type Difficulty } from '@/types/card';

/**
 * System prompt for flashcard generation
 */
export const FLASHCARD_SYSTEM_PROMPT = `You are an expert Workday trainer creating flashcards from training video transcripts. Your flashcards help users memorize key Workday concepts and procedures for certification exams and daily work.

IMPORTANT GUIDELINES:
1. Questions must be factually derived from the transcript content
2. Answers should be concise (1-3 sentences maximum)
3. Use professional, clear language
4. Avoid overly obvious questions about basic UI navigation
5. Focus on concepts that require memory (definitions, procedures, locations)
6. Each card should test ONE specific piece of knowledge`;

/**
 * Generate the user prompt for flashcard generation
 */
export function generateFlashcardPrompt(
  transcript: ParsedTranscript,
  cardCount: number = 8
): string {
  const { metadata, content } = transcript;

  return `Generate ${cardCount} flashcard Q&A pairs from this Workday training transcript.

TRANSCRIPT METADATA:
- Title: ${metadata.title}
- Category: ${metadata.category}
- Topic: ${getCategoryTopic(metadata.category)}

TRANSCRIPT CONTENT:
${truncateContent(content, 6000)}

REQUIREMENTS:
1. Create a mix of concept types:
   - Definition: "What is X?" (test understanding of terms)
   - Procedure: "How do you X?" (test step-by-step knowledge)
   - Fact: "Where/When can you X?" (test location/timing knowledge)
2. Difficulty distribution: 2 easy, 4-5 medium, 1-2 hard
3. Questions should be self-contained (understandable without the transcript)
4. Answers should be specific and verifiable from the transcript

OUTPUT FORMAT (JSON):
{
  "cards": [
    {
      "question": "What is the purpose of the worker profile in Workday?",
      "answer": "The worker profile provides a centralized view of employee information including personal details, job history, compensation, and time off balances.",
      "conceptType": "definition",
      "difficulty": "easy"
    },
    {
      "question": "How do you initiate a job change for a worker in Workday?",
      "answer": "Navigate to the worker's profile, select Related Actions, then choose Job Change from the available options. Complete the required fields and submit for approval.",
      "conceptType": "procedure",
      "difficulty": "medium"
    }
  ]
}

Generate exactly ${cardCount} cards in the JSON format above.`;
}

/**
 * Generate prompt for multiple choice options
 */
export function generateOptionsPrompt(
  question: string,
  correctAnswer: string,
  category: WorkdayCategory
): string {
  return `Generate 3 plausible but incorrect answer options for this Workday flashcard question.

QUESTION: ${question}
CORRECT ANSWER: ${correctAnswer}
CATEGORY: ${category}

REQUIREMENTS:
1. Options should be plausible (related to Workday)
2. Options should be clearly incorrect to someone who knows the answer
3. Options should be similar in length to the correct answer
4. Avoid obviously wrong or silly answers

OUTPUT FORMAT (JSON):
{
  "options": [
    "Incorrect option 1",
    "Incorrect option 2",
    "Incorrect option 3"
  ]
}`;
}

/**
 * Get category-specific topic description
 */
function getCategoryTopic(category: WorkdayCategory): string {
  const topics: Record<WorkdayCategory, string> = {
    HCM: 'Human Capital Management - core HR functions, worker management, organizational structure',
    Recruiting: 'Talent acquisition - job requisitions, candidate management, hiring workflows',
    Learning: 'Learning management - courses, programs, enrollments, training administration',
    Analytics: 'Reporting and analytics - dashboards, reports, discovery boards, data visualization',
    General: 'Platform fundamentals - navigation, search, general system features',
  };

  return topics[category];
}

/**
 * Truncate content to fit within token limits
 */
function truncateContent(content: string, maxLength: number): string {
  if (content.length <= maxLength) {
    return content;
  }

  // Try to truncate at a sentence boundary
  const truncated = content.slice(0, maxLength);
  const lastPeriod = truncated.lastIndexOf('.');

  if (lastPeriod > maxLength * 0.8) {
    return truncated.slice(0, lastPeriod + 1);
  }

  return truncated + '...';
}

/**
 * Parse flashcard response from GPT
 */
export function parseFlashcardResponse(response: string): {
  cards: Array<{
    question: string;
    answer: string;
    conceptType: ConceptType;
    difficulty: Difficulty;
  }>;
} | null {
  try {
    // Extract JSON from response (handle markdown code blocks)
    let jsonStr = response;

    const jsonMatch = response.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1].trim();
    }

    // Try to find JSON object
    const objectMatch = jsonStr.match(/\{[\s\S]*\}/);
    if (objectMatch) {
      jsonStr = objectMatch[0];
    }

    const parsed = JSON.parse(jsonStr);

    // Validate structure
    if (!parsed.cards || !Array.isArray(parsed.cards)) {
      console.error('Invalid response structure: missing cards array');
      return null;
    }

    // Validate and clean each card
    const validCards = parsed.cards
      .filter((card: any) => {
        return (
          typeof card.question === 'string' &&
          typeof card.answer === 'string' &&
          card.question.length > 0 &&
          card.answer.length > 0
        );
      })
      .map((card: any) => ({
        question: card.question.trim(),
        answer: card.answer.trim(),
        conceptType: validateConceptType(card.conceptType),
        difficulty: validateDifficulty(card.difficulty),
      }));

    return { cards: validCards };
  } catch (error) {
    console.error('Failed to parse flashcard response:', error);
    return null;
  }
}

/**
 * Validate concept type
 */
function validateConceptType(type: string): ConceptType {
  const validTypes: ConceptType[] = ['definition', 'procedure', 'fact', 'comparison'];

  if (validTypes.includes(type as ConceptType)) {
    return type as ConceptType;
  }

  return 'definition'; // Default
}

/**
 * Validate difficulty
 */
function validateDifficulty(difficulty: string): Difficulty {
  const validDifficulties: Difficulty[] = ['easy', 'medium', 'hard'];

  if (validDifficulties.includes(difficulty as Difficulty)) {
    return difficulty as Difficulty;
  }

  return 'medium'; // Default
}

/**
 * Estimate token count (rough approximation)
 */
export function estimateTokens(text: string): number {
  // Rough estimate: ~4 characters per token for English text
  return Math.ceil(text.length / 4);
}
