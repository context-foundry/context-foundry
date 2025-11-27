import { z } from 'zod';
import { QuizSchema, ScenarioSchema, FillBlankExerciseSchema } from '@/types/learning';

/**
 * Schema Validator
 *
 * Validates AI-generated content against Zod schemas to ensure
 * structural correctness before further validation.
 */

export interface SchemaValidationResult {
  valid: boolean;
  errors?: z.ZodError;
  errorMessages?: string[];
  data?: any;
}

/**
 * Validate quiz content against schema
 * @param content - Quiz content to validate
 * @returns Validation result
 */
export function validateQuizSchema(content: unknown): SchemaValidationResult {
  try {
    const validated = QuizSchema.parse(content);
    return {
      valid: true,
      data: validated,
    };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        valid: false,
        errors: error,
        errorMessages: error.errors.map(
          (err) => `${err.path.join('.')}: ${err.message}`
        ),
      };
    }

    return {
      valid: false,
      errorMessages: ['Unknown validation error'],
    };
  }
}

/**
 * Validate scenario content against schema
 * @param content - Scenario content to validate
 * @returns Validation result
 */
export function validateScenarioSchema(content: unknown): SchemaValidationResult {
  try {
    const validated = ScenarioSchema.parse(content);
    return {
      valid: true,
      data: validated,
    };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        valid: false,
        errors: error,
        errorMessages: error.errors.map(
          (err) => `${err.path.join('.')}: ${err.message}`
        ),
      };
    }

    return {
      valid: false,
      errorMessages: ['Unknown validation error'],
    };
  }
}

/**
 * Validate fill-blank exercise against schema
 * @param content - Fill-blank content to validate
 * @returns Validation result
 */
export function validateFillBlankSchema(content: unknown): SchemaValidationResult {
  try {
    const validated = FillBlankExerciseSchema.parse(content);
    return {
      valid: true,
      data: validated,
    };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        valid: false,
        errors: error,
        errorMessages: error.errors.map(
          (err) => `${err.path.join('.')}: ${err.message}`
        ),
      };
    }

    return {
      valid: false,
      errorMessages: ['Unknown validation error'],
    };
  }
}

/**
 * Validate content against appropriate schema based on type
 * @param content - Content to validate
 * @param contentType - Type of content
 * @returns Validation result
 */
export function validateContentSchema(
  content: unknown,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): SchemaValidationResult {
  switch (contentType) {
    case 'quiz':
      return validateQuizSchema(content);
    case 'scenario':
      return validateScenarioSchema(content);
    case 'fill-blank':
      return validateFillBlankSchema(content);
    default:
      return {
        valid: false,
        errorMessages: [`Unknown content type: ${contentType}`],
      };
  }
}

/**
 * Safe parse JSON string
 * @param jsonString - JSON string to parse
 * @returns Parsed object or null if invalid
 */
export function safeParseJSON(jsonString: string): any | null {
  try {
    return JSON.parse(jsonString);
  } catch (error) {
    console.error('JSON parse error:', error);
    return null;
  }
}

/**
 * Validate and parse JSON response from AI
 * @param response - AI response (potentially JSON)
 * @param contentType - Expected content type
 * @returns Validation result with parsed data
 */
export function validateAIResponse(
  response: string,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): SchemaValidationResult {
  // Try to extract JSON from response (in case AI added extra text)
  const jsonMatch = response.match(/\{[\s\S]*\}/);
  const jsonString = jsonMatch ? jsonMatch[0] : response;

  const parsed = safeParseJSON(jsonString);

  if (!parsed) {
    return {
      valid: false,
      errorMessages: ['Response is not valid JSON'],
    };
  }

  return validateContentSchema(parsed, contentType);
}

/**
 * Partial schema validation (for drafts or incomplete content)
 * @param content - Content to validate
 * @param contentType - Type of content
 * @returns Validation result with partial flag
 */
export function validatePartialContent(
  content: unknown,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): SchemaValidationResult & { partial: boolean } {
  const result = validateContentSchema(content, contentType);

  // Check if content is partially valid (has required root fields)
  if (!result.valid && typeof content === 'object' && content !== null) {
    const obj = content as any;

    const hasBasicFields =
      'patternId' in obj && 'patternName' in obj && 'generatedAt' in obj;

    if (hasBasicFields) {
      return {
        ...result,
        partial: true,
      };
    }
  }

  return {
    ...result,
    partial: false,
  };
}

/**
 * Create detailed error report from validation errors
 * @param errors - Zod errors
 * @returns Human-readable error report
 */
export function createErrorReport(errors: z.ZodError): string {
  const lines: string[] = ['Validation Errors:'];

  for (const error of errors.errors) {
    const path = error.path.join('.') || 'root';
    lines.push(`  - ${path}: ${error.message}`);

    if (error.code === 'invalid_type') {
      lines.push(`    Expected: ${error.expected}, Received: ${error.received}`);
    }
  }

  return lines.join('\n');
}

/**
 * Validate required fields are present
 * @param obj - Object to validate
 * @param requiredFields - Array of required field names
 * @returns Validation result
 */
export function validateRequiredFields(
  obj: any,
  requiredFields: string[]
): SchemaValidationResult {
  const missing: string[] = [];

  for (const field of requiredFields) {
    if (!(field in obj) || obj[field] === undefined || obj[field] === null) {
      missing.push(field);
    }
  }

  if (missing.length > 0) {
    return {
      valid: false,
      errorMessages: missing.map((field) => `Missing required field: ${field}`),
    };
  }

  return {
    valid: true,
    data: obj,
  };
}

/**
 * Validate field types match expected types
 * @param obj - Object to validate
 * @param fieldTypes - Map of field name to expected type
 * @returns Validation result
 */
export function validateFieldTypes(
  obj: any,
  fieldTypes: Record<string, string>
): SchemaValidationResult {
  const errors: string[] = [];

  for (const [field, expectedType] of Object.entries(fieldTypes)) {
    if (field in obj) {
      const actualType = Array.isArray(obj[field]) ? 'array' : typeof obj[field];

      if (actualType !== expectedType) {
        errors.push(
          `Field "${field}" has wrong type: expected ${expectedType}, got ${actualType}`
        );
      }
    }
  }

  if (errors.length > 0) {
    return {
      valid: false,
      errorMessages: errors,
    };
  }

  return {
    valid: true,
    data: obj,
  };
}

/**
 * Quick validation check (lightweight)
 * @param content - Content to validate
 * @param contentType - Content type
 * @returns True if valid structure
 */
export function quickValidate(
  content: unknown,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): boolean {
  if (!content || typeof content !== 'object') {
    return false;
  }

  const obj = content as any;

  // Check basic required fields
  if (!obj.patternId || !obj.patternName) {
    return false;
  }

  // Content-specific checks
  if (contentType === 'quiz') {
    return Array.isArray(obj.questions) && obj.questions.length > 0;
  }

  if (contentType === 'scenario') {
    return Array.isArray(obj.nodes) && obj.nodes.length > 0 && obj.startNodeId;
  }

  if (contentType === 'fill-blank') {
    return Array.isArray(obj.sentences) && obj.sentences.length > 0;
  }

  return false;
}
