/**
 * Hint Generation Prompt Template
 *
 * Prompts for GPT-4o-mini to generate contextual hints for quiz questions.
 * Cost-effective hint generation (10x cheaper than GPT-4o).
 */

import { Pattern } from '@/types/pattern';

export interface HintPromptParams {
  pattern: Pattern;
  questionText: string;
  questionId: string;
  userAnswer?: string;
}

/**
 * Generate a hint prompt for GPT-4o-mini
 * @param params - Hint generation parameters
 * @returns Formatted prompt string
 */
export function generateHintPrompt(params: HintPromptParams): string {
  const { pattern, questionText, userAnswer } = params;

  return `You are a helpful Workday expertise tutor. Generate a contextual hint to help a learner answer a quiz question about Workday patterns.

# Pattern Context
**Pattern ID**: ${pattern.id}
**Pattern Name**: ${pattern.name}
**Category**: ${pattern.category}
**Description**: ${pattern.description}

# Best Practices
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

${pattern.anti_patterns && pattern.anti_patterns.length > 0 ? `
# Anti-Patterns to Avoid
${pattern.anti_patterns.map((ap, i) => `${i + 1}. ${ap}`).join('\n')}
` : ''}

# Question
${questionText}

${userAnswer ? `# User's Current Answer
${userAnswer}
` : ''}

# Task
Generate a helpful hint that:
1. **Guides without revealing** - Don't give the answer directly
2. **Points to relevant concepts** - Reference specific best practices or anti-patterns
3. **Encourages thinking** - Ask guiding questions or suggest what to consider
4. **Is concise** - Maximum 2-3 sentences
5. **Is supportive** - Use encouraging, positive language

${userAnswer ? 'If the user\'s answer seems incorrect, gently guide them toward the right direction without explicitly stating the correct answer.' : ''}

Return ONLY the hint text (no JSON, no formatting, just the plain hint message).`;
}

/**
 * Generate a follow-up hint prompt (if user requests another hint)
 * @param params - Hint generation parameters with previous hint
 * @returns Formatted prompt string
 */
export function generateFollowUpHintPrompt(
  params: HintPromptParams & { previousHint: string }
): string {
  const { pattern, questionText, userAnswer, previousHint } = params;

  return `You previously gave this hint:
"${previousHint}"

The learner is requesting another hint for the same question.

# Question
${questionText}

${userAnswer ? `# User's Current Answer
${userAnswer}
` : ''}

# Pattern Best Practices
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

# Task
Generate a MORE SPECIFIC hint that:
1. **Provides additional guidance** - Don't repeat the previous hint
2. **Narrows down the options** - Be slightly more direct than before
3. **References specific practices** - Point to 1-2 specific best practices
4. **Still doesn't reveal the answer** - Let them make the final connection
5. **Is concise** - Maximum 2-3 sentences

Return ONLY the hint text.`;
}

/**
 * Generate a hint for scenario-based questions
 * @param params - Scenario hint parameters
 * @returns Formatted prompt string
 */
export function generateScenarioHintPrompt(
  params: HintPromptParams & { scenarioContext: string }
): string {
  const { pattern, questionText, scenarioContext } = params;

  return `You are helping a learner navigate a Workday scenario-based learning exercise.

# Pattern Context
**Pattern**: ${pattern.name}
**Description**: ${pattern.description}

# Scenario Context
${scenarioContext}

# Decision Point
${questionText}

# Best Practices for This Pattern
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

# Task
Generate a strategic hint that:
1. **Considers consequences** - Help them think about the outcomes of each choice
2. **References best practices** - Point to relevant guidelines without being prescriptive
3. **Encourages analysis** - Ask them to consider specific factors
4. **Is contextual** - Relate to the specific scenario situation
5. **Is concise** - Maximum 2-3 sentences

Return ONLY the hint text.`;
}

/**
 * Cost-effective hint generation configuration
 */
export const HINT_GENERATION_CONFIG = {
  model: 'gpt-4o-mini', // 10x cheaper than GPT-4o
  temperature: 0.7, // Slightly creative but still focused
  maxTokens: 150, // Keep hints concise
  frequencyPenalty: 0.3, // Reduce repetition
  presencePenalty: 0.3, // Encourage diverse phrasing
} as const;

/**
 * Estimate cost for hint generation
 * @param hintCount - Number of hints to generate
 * @returns Estimated cost in USD
 */
export function estimateHintCost(hintCount: number): number {
  // GPT-4o-mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
  const avgInputTokens = 400; // Prompt with pattern context
  const avgOutputTokens = 100; // Hint response

  const inputCost = (avgInputTokens / 1_000_000) * 0.15;
  const outputCost = (avgOutputTokens / 1_000_000) * 0.60;

  return (inputCost + outputCost) * hintCount;
}
