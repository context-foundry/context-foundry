import { Pattern } from '@/types/pattern';
import { Quiz } from '@/types/learning';

/**
 * Content Validation Rules
 *
 * Defines validation rules for AI-generated content to prevent hallucination
 * and ensure accuracy against source patterns.
 */

export interface ValidationRule {
  id: string;
  name: string;
  description: string;
  severity: 'error' | 'warning' | 'info';
  validate: (content: any, pattern: Pattern) => ValidationResult;
}

export interface ValidationResult {
  passed: boolean;
  message?: string;
  details?: string[];
  confidence: number; // 0-100
}

/**
 * Quiz Validation Rules
 */

export const quizValidationRules: ValidationRule[] = [
  {
    id: 'quiz-question-count',
    name: 'Question Count',
    description: 'Quiz must have exactly 5 questions',
    severity: 'error',
    validate: (quiz: Quiz) => {
      const count = quiz.questions?.length || 0;
      return {
        passed: count === 5,
        message: count !== 5 ? `Expected 5 questions, found ${count}` : undefined,
        confidence: count === 5 ? 100 : 0,
      };
    },
  },
  {
    id: 'quiz-option-count',
    name: 'Option Count',
    description: 'Each question must have exactly 4 options',
    severity: 'error',
    validate: (quiz: Quiz) => {
      const invalidQuestions = quiz.questions.filter(
        (q) => q.options.length !== 4
      );

      return {
        passed: invalidQuestions.length === 0,
        message:
          invalidQuestions.length > 0
            ? `${invalidQuestions.length} questions have incorrect option count`
            : undefined,
        details: invalidQuestions.map(
          (q) => `Question "${q.id}" has ${q.options.length} options`
        ),
        confidence: invalidQuestions.length === 0 ? 100 : 50,
      };
    },
  },
  {
    id: 'quiz-correct-answer-valid',
    name: 'Correct Answer Index',
    description: 'Correct answer index must be valid (0-3)',
    severity: 'error',
    validate: (quiz: Quiz) => {
      const invalidQuestions = quiz.questions.filter(
        (q) => q.correctAnswer < 0 || q.correctAnswer > 3
      );

      return {
        passed: invalidQuestions.length === 0,
        message:
          invalidQuestions.length > 0
            ? `${invalidQuestions.length} questions have invalid correct answer index`
            : undefined,
        details: invalidQuestions.map(
          (q) => `Question "${q.id}" has correctAnswer: ${q.correctAnswer}`
        ),
        confidence: invalidQuestions.length === 0 ? 100 : 0,
      };
    },
  },
  {
    id: 'quiz-best-practice-reference',
    name: 'Best Practice Reference',
    description: 'Each explanation must reference source best practices',
    severity: 'warning',
    validate: (quiz: Quiz, pattern: Pattern) => {
      const missingReferences: string[] = [];

      for (const question of quiz.questions) {
        const explanation = question.explanation.toLowerCase();
        const referencesAny = pattern.best_practices.some((bp) =>
          explanation.includes(bp.toLowerCase().substring(0, 20))
        );

        if (!referencesAny) {
          missingReferences.push(question.id);
        }
      }

      return {
        passed: missingReferences.length === 0,
        message:
          missingReferences.length > 0
            ? `${missingReferences.length} questions don't reference best practices`
            : undefined,
        details: missingReferences.map(
          (id) => `Question "${id}" explanation lacks best practice reference`
        ),
        confidence: missingReferences.length === 0 ? 90 : 60,
      };
    },
  },
  {
    id: 'quiz-anti-pattern-usage',
    name: 'Anti-Pattern in Distractors',
    description: 'Incorrect options should reference anti-patterns',
    severity: 'warning',
    validate: (quiz: Quiz, pattern: Pattern) => {
      if (!pattern.anti_patterns || pattern.anti_patterns.length === 0) {
        return { passed: true, confidence: 100 };
      }

      const questionsWithAntiPatterns = quiz.questions.filter((q) => {
        const incorrectOptions = q.options.filter(
          (_, i) => i !== q.correctAnswer
        );
        const allIncorrectText = incorrectOptions.join(' ').toLowerCase();

        return pattern.anti_patterns!.some((ap) =>
          allIncorrectText.includes(ap.toLowerCase().substring(0, 15))
        );
      });

      const coverage =
        (questionsWithAntiPatterns.length / quiz.questions.length) * 100;

      return {
        passed: questionsWithAntiPatterns.length >= 2,
        message:
          questionsWithAntiPatterns.length < 2
            ? `Only ${questionsWithAntiPatterns.length} questions use anti-patterns in distractors`
            : undefined,
        confidence: Math.min(coverage, 90),
      };
    },
  },
  {
    id: 'quiz-no-redundancy',
    name: 'Question Uniqueness',
    description: 'Questions should test different aspects',
    severity: 'warning',
    validate: (quiz: Quiz) => {
      const questions = quiz.questions.map((q) => q.question.toLowerCase());
      const duplicates: string[] = [];

      for (let i = 0; i < questions.length; i++) {
        for (let j = i + 1; j < questions.length; j++) {
          const similarity = calculateSimilarity(questions[i], questions[j]);
          if (similarity > 0.7) {
            duplicates.push(`Q${i + 1} and Q${j + 1} are ${Math.round(similarity * 100)}% similar`);
          }
        }
      }

      return {
        passed: duplicates.length === 0,
        message:
          duplicates.length > 0
            ? `Found ${duplicates.length} similar question pairs`
            : undefined,
        details: duplicates,
        confidence: duplicates.length === 0 ? 85 : 50,
      };
    },
  },
];

/**
 * Scenario Validation Rules
 */

export const scenarioValidationRules: ValidationRule[] = [
  {
    id: 'scenario-start-node',
    name: 'Start Node Exists',
    description: 'Scenario must have a valid start node',
    severity: 'error',
    validate: (scenario: any) => {
      const hasStartNode = scenario.nodes.some(
        (n: any) => n.id === scenario.startNodeId
      );

      return {
        passed: hasStartNode,
        message: hasStartNode
          ? undefined
          : `Start node "${scenario.startNodeId}" not found in nodes`,
        confidence: hasStartNode ? 100 : 0,
      };
    },
  },
  {
    id: 'scenario-end-nodes',
    name: 'End Nodes',
    description: 'Scenario must have success and failure end nodes',
    severity: 'error',
    validate: (scenario: any) => {
      const endNodes = scenario.nodes.filter((n: any) => n.type === 'end');
      const hasSuccess = endNodes.some((n: any) => n.isSuccessful === true);
      const hasFailure = endNodes.some((n: any) => n.isSuccessful === false);

      return {
        passed: hasSuccess && hasFailure,
        message:
          !hasSuccess || !hasFailure
            ? 'Missing success or failure end node'
            : undefined,
        details: [
          `Success nodes: ${hasSuccess ? 'yes' : 'no'}`,
          `Failure nodes: ${hasFailure ? 'yes' : 'no'}`,
        ],
        confidence: hasSuccess && hasFailure ? 100 : 50,
      };
    },
  },
  {
    id: 'scenario-decision-options',
    name: 'Decision Options',
    description: 'Decision nodes must have 2-4 options',
    severity: 'error',
    validate: (scenario: any) => {
      const decisionNodes = scenario.nodes.filter(
        (n: any) => n.type === 'decision' || n.type === 'start'
      );

      const invalid = decisionNodes.filter(
        (n: any) =>
          !n.options || n.options.length < 2 || n.options.length > 4
      );

      return {
        passed: invalid.length === 0,
        message:
          invalid.length > 0
            ? `${invalid.length} decision nodes have invalid option count`
            : undefined,
        details: invalid.map(
          (n: any) =>
            `Node "${n.id}" has ${n.options?.length || 0} options`
        ),
        confidence: invalid.length === 0 ? 100 : 0,
      };
    },
  },
  {
    id: 'scenario-feedback-references',
    name: 'Feedback References Practices',
    description: 'Feedback should reference best practices or anti-patterns',
    severity: 'warning',
    validate: (scenario: any, pattern: Pattern) => {
      const allOptions = scenario.nodes
        .filter((n: any) => n.options)
        .flatMap((n: any) => n.options);

      const withoutReferences = allOptions.filter((opt: any) => {
        if (!opt.rationale) return true;

        const rationale = opt.rationale.toLowerCase();
        const referencesPattern =
          pattern.best_practices.some((bp) =>
            rationale.includes(bp.toLowerCase().substring(0, 15))
          ) ||
          (pattern.anti_patterns || []).some((ap) =>
            rationale.includes(ap.toLowerCase().substring(0, 15))
          );

        return !referencesPattern;
      });

      return {
        passed: withoutReferences.length === 0,
        message:
          withoutReferences.length > 0
            ? `${withoutReferences.length} options lack practice references in feedback`
            : undefined,
        confidence: withoutReferences.length === 0 ? 85 : 60,
      };
    },
  },
  {
    id: 'scenario-anti-pattern-usage',
    name: 'Anti-Pattern in Incorrect Choices',
    description: 'Incorrect options should reference anti-patterns',
    severity: 'warning',
    validate: (scenario: any, pattern: Pattern) => {
      if (!pattern.anti_patterns || pattern.anti_patterns.length === 0) {
        return { passed: true, confidence: 100 };
      }

      const incorrectOptions = scenario.nodes
        .filter((n: any) => n.options)
        .flatMap((n: any) =>
          n.options.filter((o: any) => o.isCorrect === false)
        );

      const withAntiPatterns = incorrectOptions.filter((opt: any) => {
        const text = (opt.text + ' ' + opt.rationale).toLowerCase();
        return pattern.anti_patterns!.some((ap) =>
          text.includes(ap.toLowerCase().substring(0, 15))
        );
      });

      const coverage = incorrectOptions.length > 0
        ? (withAntiPatterns.length / incorrectOptions.length) * 100
        : 0;

      return {
        passed: withAntiPatterns.length >= 2,
        message:
          withAntiPatterns.length < 2
            ? `Only ${withAntiPatterns.length} incorrect options use anti-patterns`
            : undefined,
        confidence: Math.min(coverage, 90),
      };
    },
  },
];

/**
 * General Content Validation Rules
 */

export const generalValidationRules: ValidationRule[] = [
  {
    id: 'pattern-id-match',
    name: 'Pattern ID Match',
    description: 'Content patternId must match source pattern',
    severity: 'error',
    validate: (content: any, pattern: Pattern) => {
      const matches = content.patternId === pattern.id;
      return {
        passed: matches,
        message: matches
          ? undefined
          : `Pattern ID mismatch: expected ${pattern.id}, got ${content.patternId}`,
        confidence: matches ? 100 : 0,
      };
    },
  },
  {
    id: 'no-hallucinated-features',
    name: 'No Hallucinated Features',
    description: 'Content should not include fabricated Workday features',
    severity: 'error',
    validate: (content: any) => {
      const contentStr = JSON.stringify(content).toLowerCase();

      // Known hallucination indicators
      const suspiciousTerms = [
        'workday premium',
        'workday pro',
        'workday enterprise plus',
        'workday ai assistant',
        'workday chatbot',
        'version 2025',
        'release 45',
      ];

      const found = suspiciousTerms.filter((term) =>
        contentStr.includes(term)
      );

      return {
        passed: found.length === 0,
        message:
          found.length > 0
            ? 'Potential hallucinated Workday features detected'
            : undefined,
        details: found.map((term) => `Suspicious term: "${term}"`),
        confidence: found.length === 0 ? 90 : 30,
      };
    },
  },
];

/**
 * Calculate text similarity (simple word overlap)
 * @param text1 - First text
 * @param text2 - Second text
 * @returns Similarity score (0-1)
 */
function calculateSimilarity(text1: string, text2: string): number {
  const words1 = new Set(text1.split(/\s+/));
  const words2 = new Set(text2.split(/\s+/));

  const intersection = new Set([...words1].filter((w) => words2.has(w)));
  const union = new Set([...words1, ...words2]);

  return intersection.size / union.size;
}

/**
 * Get all validation rules for content type
 * @param contentType - Type of content
 * @returns Array of validation rules
 */
export function getValidationRules(
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): ValidationRule[] {
  const specificRules =
    contentType === 'quiz'
      ? quizValidationRules
      : contentType === 'scenario'
      ? scenarioValidationRules
      : [];

  return [...generalValidationRules, ...specificRules];
}
