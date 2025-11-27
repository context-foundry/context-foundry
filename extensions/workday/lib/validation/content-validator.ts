import { Pattern } from '@/types/pattern';
import { Quiz, Scenario, FillBlankExercise } from '@/types/learning';
import {
  getValidationRules,
  ValidationRule,
  ValidationResult,
} from './validation-rules';
import {
  validateContentSchema,
  validateAIResponse,
  SchemaValidationResult,
} from './schema-validator';

/**
 * Content Validator
 *
 * Validates AI-generated content for accuracy, completeness, and alignment
 * with source patterns. Prevents hallucination through cross-referencing.
 */

export interface ContentValidationReport {
  isValid: boolean;
  overallConfidence: number; // 0-100
  schemaValidation: SchemaValidationResult;
  ruleValidation: {
    totalRules: number;
    passedRules: number;
    failedRules: number;
    results: Array<{
      ruleId: string;
      ruleName: string;
      severity: 'error' | 'warning' | 'info';
      passed: boolean;
      message?: string;
      details?: string[];
      confidence: number;
    }>;
  };
  bestPracticesCovered: string[];
  antiPatternsCovered: string[];
  missingCoverage: string[];
  recommendations: string[];
  shouldRegenerate: boolean;
  regenerationReason?: string;
}

/**
 * Validate quiz content
 * @param quiz - Quiz to validate
 * @param pattern - Source pattern
 * @returns Validation report
 */
export function validateQuiz(quiz: Quiz, pattern: Pattern): ContentValidationReport {
  return validateContent(quiz, pattern, 'quiz');
}

/**
 * Validate scenario content
 * @param scenario - Scenario to validate
 * @param pattern - Source pattern
 * @returns Validation report
 */
export function validateScenario(scenario: Scenario, pattern: Pattern): ContentValidationReport {
  return validateContent(scenario, pattern, 'scenario');
}

/**
 * Validate fill-blank exercise
 * @param exercise - Exercise to validate
 * @param pattern - Source pattern
 * @returns Validation report
 */
export function validateFillBlank(
  exercise: FillBlankExercise,
  pattern: Pattern
): ContentValidationReport {
  return validateContent(exercise, pattern, 'fill-blank');
}

/**
 * Validate AI response string
 * @param response - AI response (JSON string)
 * @param pattern - Source pattern
 * @param contentType - Type of content
 * @returns Validation report
 */
export function validateAIResponseContent(
  response: string,
  pattern: Pattern,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): ContentValidationReport {
  const schemaValidation = validateAIResponse(response, contentType);

  if (!schemaValidation.valid || !schemaValidation.data) {
    return {
      isValid: false,
      overallConfidence: 0,
      schemaValidation,
      ruleValidation: {
        totalRules: 0,
        passedRules: 0,
        failedRules: 0,
        results: [],
      },
      bestPracticesCovered: [],
      antiPatternsCovered: [],
      missingCoverage: pattern.best_practices,
      recommendations: ['Fix schema validation errors before proceeding'],
      shouldRegenerate: true,
      regenerationReason: 'Invalid schema: ' + (schemaValidation.errorMessages?.join('; ') || 'Unknown error'),
    };
  }

  return validateContent(schemaValidation.data, pattern, contentType);
}

/**
 * Core validation function
 * @param content - Content to validate
 * @param pattern - Source pattern
 * @param contentType - Type of content
 * @returns Validation report
 */
function validateContent(
  content: any,
  pattern: Pattern,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): ContentValidationReport {
  // Step 1: Schema validation
  const schemaValidation = validateContentSchema(content, contentType);

  // Step 2: Rule validation
  const rules = getValidationRules(contentType);
  const ruleResults = rules.map((rule) => {
    const result = rule.validate(content, pattern);
    return {
      ruleId: rule.id,
      ruleName: rule.name,
      severity: rule.severity,
      passed: result.passed,
      message: result.message,
      details: result.details,
      confidence: result.confidence,
    };
  });

  const passedRules = ruleResults.filter((r) => r.passed).length;
  const failedRules = ruleResults.filter((r) => !r.passed).length;

  // Step 3: Coverage analysis
  const coverage = analyzeCoverage(content, pattern, contentType);

  // Step 4: Calculate overall confidence
  const avgRuleConfidence =
    ruleResults.reduce((sum, r) => sum + r.confidence, 0) / ruleResults.length || 0;

  const coverageConfidence = calculateCoverageConfidence(coverage, pattern);

  const overallConfidence = schemaValidation.valid
    ? Math.round((avgRuleConfidence + coverageConfidence) / 2)
    : 0;

  // Step 5: Determine if regeneration is needed
  const criticalErrors = ruleResults.filter(
    (r) => !r.passed && r.severity === 'error'
  );

  const shouldRegenerate =
    !schemaValidation.valid || criticalErrors.length > 0 || overallConfidence < 60;

  const regenerationReason = !schemaValidation.valid
    ? 'Schema validation failed'
    : criticalErrors.length > 0
    ? `${criticalErrors.length} critical validation errors`
    : overallConfidence < 60
    ? 'Overall confidence too low'
    : undefined;

  // Step 6: Generate recommendations
  const recommendations = generateRecommendations(
    ruleResults,
    coverage,
    pattern
  );

  return {
    isValid: schemaValidation.valid && criticalErrors.length === 0,
    overallConfidence,
    schemaValidation,
    ruleValidation: {
      totalRules: rules.length,
      passedRules,
      failedRules,
      results: ruleResults,
    },
    bestPracticesCovered: coverage.bestPracticesCovered,
    antiPatternsCovered: coverage.antiPatternsCovered,
    missingCoverage: coverage.missingCoverage,
    recommendations,
    shouldRegenerate,
    regenerationReason,
  };
}

/**
 * Analyze best practice and anti-pattern coverage
 * @param content - Content to analyze
 * @param pattern - Source pattern
 * @param contentType - Type of content
 * @returns Coverage analysis
 */
function analyzeCoverage(
  content: any,
  pattern: Pattern,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): {
  bestPracticesCovered: string[];
  antiPatternsCovered: string[];
  missingCoverage: string[];
} {
  const contentText = JSON.stringify(content).toLowerCase();

  const bestPracticesCovered = pattern.best_practices.filter((bp) =>
    contentText.includes(bp.toLowerCase().substring(0, 20))
  );

  const antiPatternsCovered = (pattern.anti_patterns || []).filter((ap) =>
    contentText.includes(ap.toLowerCase().substring(0, 20))
  );

  const missingCoverage = pattern.best_practices.filter(
    (bp) => !bestPracticesCovered.includes(bp)
  );

  return {
    bestPracticesCovered,
    antiPatternsCovered,
    missingCoverage,
  };
}

/**
 * Calculate confidence score based on coverage
 * @param coverage - Coverage analysis
 * @param pattern - Source pattern
 * @returns Confidence score (0-100)
 */
function calculateCoverageConfidence(
  coverage: {
    bestPracticesCovered: string[];
    antiPatternsCovered: string[];
    missingCoverage: string[];
  },
  pattern: Pattern
): number {
  const totalBestPractices = pattern.best_practices.length;
  const coverageRatio = coverage.bestPracticesCovered.length / totalBestPractices;

  // Base confidence from coverage ratio
  let confidence = coverageRatio * 100;

  // Bonus for using anti-patterns
  if (pattern.anti_patterns && pattern.anti_patterns.length > 0) {
    const antiPatternRatio =
      coverage.antiPatternsCovered.length / pattern.anti_patterns.length;
    confidence = confidence * 0.8 + antiPatternRatio * 100 * 0.2;
  }

  return Math.min(Math.round(confidence), 100);
}

/**
 * Generate recommendations based on validation results
 * @param ruleResults - Rule validation results
 * @param coverage - Coverage analysis
 * @param pattern - Source pattern
 * @returns Array of recommendations
 */
function generateRecommendations(
  ruleResults: Array<{
    ruleId: string;
    ruleName: string;
    severity: 'error' | 'warning' | 'info';
    passed: boolean;
    message?: string;
  }>,
  coverage: {
    bestPracticesCovered: string[];
    antiPatternsCovered: string[];
    missingCoverage: string[];
  },
  pattern: Pattern
): string[] {
  const recommendations: string[] = [];

  // Recommendations from failed rules
  const errors = ruleResults.filter((r) => !r.passed && r.severity === 'error');
  const warnings = ruleResults.filter((r) => !r.passed && r.severity === 'warning');

  if (errors.length > 0) {
    recommendations.push(
      `Fix ${errors.length} critical error(s): ${errors.map((e) => e.ruleName).join(', ')}`
    );
  }

  if (warnings.length > 0) {
    recommendations.push(
      `Address ${warnings.length} warning(s) for better quality: ${warnings.map((w) => w.ruleName).join(', ')}`
    );
  }

  // Coverage recommendations
  if (coverage.missingCoverage.length > 0) {
    recommendations.push(
      `Include references to: ${coverage.missingCoverage.slice(0, 2).join('; ')}${coverage.missingCoverage.length > 2 ? '...' : ''}`
    );
  }

  if (
    pattern.anti_patterns &&
    pattern.anti_patterns.length > 0 &&
    coverage.antiPatternsCovered.length === 0
  ) {
    recommendations.push('Add anti-patterns to incorrect options/choices');
  }

  // If no issues, provide positive feedback
  if (recommendations.length === 0) {
    recommendations.push('Content validation passed all checks');
  }

  return recommendations;
}

/**
 * Quick validation check (fast, less thorough)
 * @param content - Content to validate
 * @param pattern - Source pattern
 * @param contentType - Type of content
 * @returns True if content passes basic checks
 */
export function quickValidate(
  content: any,
  pattern: Pattern,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): boolean {
  // Schema check
  const schema = validateContentSchema(content, contentType);
  if (!schema.valid) return false;

  // Pattern ID check
  if (content.patternId !== pattern.id) return false;

  // Basic coverage check
  const contentText = JSON.stringify(content).toLowerCase();
  const hasBestPractice = pattern.best_practices.some((bp) =>
    contentText.includes(bp.toLowerCase().substring(0, 15))
  );

  return hasBestPractice;
}

/**
 * Validate content and log results
 * @param content - Content to validate
 * @param pattern - Source pattern
 * @param contentType - Type of content
 * @returns Validation report
 */
export function validateAndLog(
  content: any,
  pattern: Pattern,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): ContentValidationReport {
  const report = validateContent(content, pattern, contentType);

  if (process.env.NODE_ENV === 'development') {
    console.log('[Content Validator]', {
      contentType,
      patternId: pattern.id,
      isValid: report.isValid,
      confidence: report.overallConfidence,
      passed: `${report.ruleValidation.passedRules}/${report.ruleValidation.totalRules}`,
      coverage: `${report.bestPracticesCovered.length}/${pattern.best_practices.length}`,
      shouldRegenerate: report.shouldRegenerate,
    });

    if (!report.isValid) {
      console.warn('[Content Validator] Failed rules:', {
        errors: report.ruleValidation.results
          .filter((r) => !r.passed && r.severity === 'error')
          .map((r) => r.ruleName),
        warnings: report.ruleValidation.results
          .filter((r) => !r.passed && r.severity === 'warning')
          .map((r) => r.ruleName),
      });
    }
  }

  return report;
}
