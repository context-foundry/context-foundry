/**
 * Hint Generation Prompts
 *
 * Prompts for generating study hints when users struggle with cards.
 */

import { type FlashCard } from '@/types/card';

/**
 * System prompt for hint generation
 */
export const HINT_SYSTEM_PROMPT = `You are a helpful Workday tutor providing hints to help users remember flashcard answers. Your hints should guide users toward the answer without giving it away directly.

HINT GUIDELINES:
1. Be encouraging and supportive
2. Give a partial clue, not the full answer
3. Use analogies or mnemonics when helpful
4. Keep hints brief (1-2 sentences)`;

/**
 * Generate hint prompt for a card
 */
export function generateHintPrompt(card: FlashCard): string {
  return `A user is struggling to remember the answer to this Workday flashcard. Generate a helpful hint.

QUESTION: ${card.question}

ANSWER (do not reveal directly): ${card.answer}

CATEGORY: ${card.category}
DIFFICULTY: ${card.difficulty}

Generate a hint that:
1. Guides the user toward the answer without revealing it
2. Mentions a key word or concept they should think about
3. Is encouraging and supportive

OUTPUT FORMAT (JSON):
{
  "hint": "Your helpful hint here"
}`;
}

/**
 * Generate progressive hints (increasingly helpful)
 */
export function generateProgressiveHintsPrompt(card: FlashCard): string {
  return `A user is struggling with this Workday flashcard. Generate 3 progressive hints, from subtle to more direct.

QUESTION: ${card.question}

ANSWER (do not reveal directly): ${card.answer}

CATEGORY: ${card.category}

Generate 3 hints:
1. Hint 1: Very subtle (e.g., "Think about the main menu...")
2. Hint 2: More specific (e.g., "It's related to the worker's profile...")
3. Hint 3: Almost direct (e.g., "The first word is 'Personal'...")

OUTPUT FORMAT (JSON):
{
  "hints": [
    "Hint 1 - subtle",
    "Hint 2 - more specific",
    "Hint 3 - almost direct"
  ]
}`;
}

/**
 * Parse hint response
 */
export function parseHintResponse(response: string): string | null {
  try {
    let jsonStr = response;

    const jsonMatch = response.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1].trim();
    }

    const objectMatch = jsonStr.match(/\{[\s\S]*\}/);
    if (objectMatch) {
      jsonStr = objectMatch[0];
    }

    const parsed = JSON.parse(jsonStr);

    if (parsed.hint && typeof parsed.hint === 'string') {
      return parsed.hint.trim();
    }

    if (parsed.hints && Array.isArray(parsed.hints) && parsed.hints.length > 0) {
      return parsed.hints[0].trim();
    }

    return null;
  } catch (error) {
    console.error('Failed to parse hint response:', error);
    return null;
  }
}

/**
 * Parse progressive hints response
 */
export function parseProgressiveHintsResponse(response: string): string[] | null {
  try {
    let jsonStr = response;

    const jsonMatch = response.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1].trim();
    }

    const objectMatch = jsonStr.match(/\{[\s\S]*\}/);
    if (objectMatch) {
      jsonStr = objectMatch[0];
    }

    const parsed = JSON.parse(jsonStr);

    if (parsed.hints && Array.isArray(parsed.hints)) {
      return parsed.hints
        .filter((h: any) => typeof h === 'string')
        .map((h: string) => h.trim());
    }

    return null;
  } catch (error) {
    console.error('Failed to parse progressive hints response:', error);
    return null;
  }
}
