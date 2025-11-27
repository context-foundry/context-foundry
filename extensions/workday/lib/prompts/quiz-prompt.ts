import { Pattern } from '@/types/pattern';

/**
 * Quiz Generation Prompt Templates
 *
 * Provides prompt templates for generating multiple-choice quizzes
 * with 5 questions and a 70% passing score.
 */

/**
 * Generate quiz prompt with validation instructions
 * @param pattern - Pattern data
 * @returns Formatted prompt
 */
export function generateQuizPrompt(pattern: Pattern): string {
  return `You are an expert assessment designer creating a multiple-choice quiz for Workday expertise patterns.

PATTERN INFORMATION:
Name: ${pattern.name}
Category: ${pattern.category}
Difficulty: ${pattern.difficulty || 'intermediate'}
Description: ${pattern.description}

BEST PRACTICES (quiz questions MUST test understanding of these):
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

ANTI-PATTERNS (use in distractors):
${(pattern.anti_patterns || []).map((ap, i) => `${i + 1}. ${ap}`).join('\n')}

EXAMPLES FOR CONTEXT:
${(pattern.examples || []).map((ex, i) => `${i + 1}. ${ex}`).join('\n')}

TASK:
Create a 5-question multiple-choice quiz that comprehensively tests understanding of this pattern.

REQUIREMENTS:
1. Exactly 5 questions covering different aspects of the pattern
2. Each question has exactly 4 options (A, B, C, D)
3. Only one correct answer per question
4. Questions must directly test best practices from the source data
5. Incorrect options should be plausible but clearly wrong
6. At least 2 incorrect options should reference anti-patterns from the source
7. Provide detailed explanations that reference specific best practices
8. Mix question types: scenario-based, definition, application, comparison
9. Passing score is 70% (4 out of 5 questions correct)
10. Questions should be appropriate for ${pattern.difficulty || 'intermediate'} difficulty

VALIDATION CHECKLIST (you MUST verify before responding):
- [ ] Each question tests a different best practice from the source
- [ ] All explanations reference specific best practices or anti-patterns by name
- [ ] Incorrect options are realistic distractors, not obviously wrong
- [ ] No hallucinated Workday features or processes not in the source
- [ ] Question difficulty matches pattern difficulty level
- [ ] All 5 questions are unique and non-redundant

QUESTION DIFFICULTY DISTRIBUTION:
${pattern.difficulty === 'beginner' ? '- 3 easy (recall/understanding), 2 medium (application)' : ''}
${pattern.difficulty === 'intermediate' ? '- 2 easy (recall), 2 medium (application), 1 hard (analysis)' : ''}
${pattern.difficulty === 'advanced' ? '- 1 easy (recall), 2 medium (application), 2 hard (analysis/evaluation)' : ''}

OUTPUT FORMAT (JSON):
{
  "patternId": "${pattern.id}",
  "patternName": "${pattern.name}",
  "questions": [
    {
      "id": "q1",
      "question": "Question text (clear, specific, unambiguous)",
      "options": [
        "Option A text",
        "Option B text",
        "Option C text",
        "Option D text"
      ],
      "correctAnswer": 0,
      "explanation": "Detailed explanation referencing specific best practice or anti-pattern from source",
      "difficulty": "easy"
    },
    {
      "id": "q2",
      "question": "...",
      "options": [...],
      "correctAnswer": 1,
      "explanation": "...",
      "difficulty": "medium"
    }
  ],
  "passingScore": 70,
  "totalPoints": 100,
  "generatedAt": "${new Date().toISOString()}"
}

Generate the quiz now, ensuring all validation criteria are met.`;
}

/**
 * Generate adaptive quiz prompt (adjusts difficulty based on previous performance)
 * @param pattern - Pattern data
 * @param previousScore - User's previous score on similar patterns (0-100)
 * @returns Formatted prompt
 */
export function generateAdaptiveQuizPrompt(pattern: Pattern, previousScore?: number): string {
  const targetDifficulty = previousScore === undefined
    ? pattern.difficulty || 'intermediate'
    : previousScore >= 90
    ? 'advanced'
    : previousScore >= 70
    ? 'intermediate'
    : 'beginner';

  return `Create a 5-question multiple-choice quiz for "${pattern.name}" at ${targetDifficulty} difficulty.

Best Practices (test these):
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

Anti-Patterns (use in wrong answers):
${(pattern.anti_patterns || []).slice(0, 3).map((ap, i) => `${i + 1}. ${ap}`).join('\n')}

Requirements:
- 5 questions, 4 options each
- Questions appropriate for ${targetDifficulty} learners
- Reference specific best practices in explanations
- Passing score: 70% (4/5 correct)

Return valid JSON:
{
  "patternId": "${pattern.id}",
  "patternName": "${pattern.name}",
  "questions": [
    {
      "id": "q1",
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correctAnswer": 0,
      "explanation": "...",
      "difficulty": "easy|medium|hard"
    }
  ],
  "passingScore": 70,
  "totalPoints": 100,
  "generatedAt": "${new Date().toISOString()}"
}`;
}

/**
 * Generate validation prompt for quiz content
 * @param quizJSON - Generated quiz JSON
 * @param pattern - Source pattern
 * @returns Validation prompt
 */
export function generateQuizValidationPrompt(quizJSON: string, pattern: Pattern): string {
  return `Validate this generated quiz against the source pattern data.

SOURCE PATTERN:
Name: ${pattern.name}
Best Practices: ${pattern.best_practices.join('; ')}
Anti-Patterns: ${(pattern.anti_patterns || []).join('; ')}

GENERATED QUIZ:
${quizJSON}

VALIDATION CRITERIA:
1. Are there exactly 5 questions?
2. Does each question have exactly 4 options?
3. Does each explanation reference specific best practices or anti-patterns?
4. Are questions testing different aspects (no redundancy)?
5. Are incorrect options plausible distractors?
6. Is the quiz free of hallucinated content?

Respond with JSON:
{
  "isValid": true/false,
  "issues": ["list of specific issues found, or empty array if valid"],
  "questionCoverage": ["which best practices are tested"],
  "missingCoverage": ["which best practices are not tested"],
  "confidence": 0-100
}`;
}

/**
 * Create system message for quiz generation
 * @returns System message content
 */
export function getQuizSystemMessage(): string {
  return `You are an expert assessment designer specializing in creating high-quality multiple-choice assessments for enterprise software training. You have expertise in Workday systems and instructional design principles.

Your quizzes are:
- Pedagogically sound with clear learning objectives
- Free from ambiguous or trick questions
- Realistic with plausible distractors
- Appropriately challenging for the target audience
- Accurate and factual, never including hallucinated content
- Comprehensive in coverage of the source material

You always validate your questions against the source best practices before responding.`;
}

/**
 * Generate hint prompt for quiz question
 * @param question - Quiz question
 * @param pattern - Source pattern
 * @returns Hint prompt
 */
export function generateQuizHintPrompt(question: string, pattern: Pattern): string {
  return `A learner is struggling with this question about "${pattern.name}":

QUESTION: ${question}

Provide a helpful hint that:
1. Guides thinking without giving away the answer
2. References relevant best practices: ${pattern.best_practices.slice(0, 2).join('; ')}
3. Encourages critical thinking
4. Is 1-2 sentences maximum

Respond with JSON:
{
  "hint": "Your helpful hint here",
  "relatedConcepts": ["concept1", "concept2"]
}`;
}
