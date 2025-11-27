import { Pattern } from '@/types/pattern';

/**
 * Content Validation Prompt Templates
 *
 * Provides prompts for validating AI-generated content against source patterns
 * to prevent hallucination and ensure accuracy.
 */

/**
 * Generate comprehensive validation prompt
 * @param generatedContent - AI-generated content (JSON string)
 * @param pattern - Source pattern
 * @param contentType - Type of content being validated
 * @returns Validation prompt
 */
export function generateContentValidationPrompt(
  generatedContent: string,
  pattern: Pattern,
  contentType: 'quiz' | 'scenario' | 'fill-blank'
): string {
  return `You are a quality assurance specialist validating AI-generated educational content for accuracy and alignment with source material.

CONTENT TYPE: ${contentType}

SOURCE PATTERN DATA:
ID: ${pattern.id}
Name: ${pattern.name}
Category: ${pattern.category}
Description: ${pattern.description}

BEST PRACTICES (authoritative source):
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

ANTI-PATTERNS (authoritative source):
${(pattern.anti_patterns || []).map((ap, i) => `${i + 1}. ${ap}`).join('\n')}

EXAMPLES (reference context):
${(pattern.examples || []).map((ex, i) => `${i + 1}. ${ex}`).join('\n')}

GENERATED CONTENT TO VALIDATE:
${generatedContent}

VALIDATION TASKS:

1. FACTUAL ACCURACY:
   - Does the content only reference best practices from the source?
   - Are anti-patterns correctly identified and labeled?
   - Is the description consistent with the source pattern?

2. HALLUCINATION CHECK:
   - Are there any Workday features, processes, or terms NOT in the source?
   - Are all examples plausible given the source context?
   - Are technical details accurate or fabricated?

3. ALIGNMENT VERIFICATION:
   - Does the content teach the correct pattern (${pattern.name})?
   - Are learning objectives aligned with best practices?
   - Is the difficulty appropriate for ${pattern.difficulty || 'intermediate'} level?

4. CONTENT QUALITY:
   - Is the language clear and professional?
   - Are there grammatical or formatting errors?
   - Is the structure logically organized?

5. COMPLETENESS:
   - Are all required fields present and valid?
   - Does the content provide sufficient context?
   - Are explanations detailed enough?

SPECIFIC VALIDATION FOR ${contentType.toUpperCase()}:
${getContentTypeSpecificValidation(contentType)}

OUTPUT FORMAT (JSON):
{
  "isValid": true/false,
  "overallConfidence": 0-100,
  "validationResults": {
    "factualAccuracy": {
      "passed": true/false,
      "issues": ["specific issues or empty array"],
      "confidence": 0-100
    },
    "hallucinationCheck": {
      "passed": true/false,
      "issues": ["fabricated content items or empty array"],
      "confidence": 0-100
    },
    "alignmentVerification": {
      "passed": true/false,
      "issues": ["misalignment issues or empty array"],
      "confidence": 0-100
    },
    "contentQuality": {
      "passed": true/false,
      "issues": ["quality issues or empty array"],
      "confidence": 0-100
    },
    "completeness": {
      "passed": true/false,
      "issues": ["missing elements or empty array"],
      "confidence": 0-100
    }
  },
  "bestPracticesCovered": ["list of best practices referenced in content"],
  "antiPatternsCovered": ["list of anti-patterns referenced in content"],
  "missingCoverage": ["best practices or anti-patterns not adequately covered"],
  "recommendations": ["specific improvement suggestions"],
  "shouldRegenerate": true/false,
  "regenerationReason": "explanation if shouldRegenerate is true"
}

Perform thorough validation and respond with detailed results.`;
}

/**
 * Get content-type-specific validation criteria
 * @param contentType - Type of content
 * @returns Validation criteria text
 */
function getContentTypeSpecificValidation(contentType: 'quiz' | 'scenario' | 'fill-blank'): string {
  const criteria: Record<string, string> = {
    quiz: `
- Are there exactly 5 questions?
- Does each question have exactly 4 options?
- Is only one answer marked as correct per question?
- Do explanations reference specific best practices or anti-patterns by name?
- Are incorrect options plausible but clearly wrong?
- Do at least 2 questions include anti-patterns in distractors?
- Are questions testing different aspects (no redundancy)?`,

    scenario: `
- Does the scenario have a clear start node?
- Are there at least 2 decision points?
- Do all decision nodes have 2-4 options?
- Are there success and failure end nodes?
- Do incorrect options reference specific anti-patterns?
- Do correct options align with specific best practices?
- Does feedback explicitly mention which practices apply?
- Are all node IDs unique and properly linked?`,

    'fill-blank': `
- Are blanks clearly marked in the template text?
- Are multiple acceptable answers provided where appropriate?
- Do correct answers reference terminology from best practices?
- Are hints helpful without giving away the answer?
- Is case sensitivity appropriately set?
- Does the exercise test key concepts from the pattern?`,
  };

  return criteria[contentType] || '';
}

/**
 * Generate quick validation prompt (lightweight check)
 * @param generatedContent - Content to validate
 * @param pattern - Source pattern
 * @returns Quick validation prompt
 */
export function generateQuickValidationPrompt(
  generatedContent: string,
  pattern: Pattern
): string {
  return `Quick validation check for AI-generated content about "${pattern.name}".

SOURCE BEST PRACTICES: ${pattern.best_practices.join('; ')}
SOURCE ANTI-PATTERNS: ${(pattern.anti_patterns || []).join('; ')}

GENERATED CONTENT:
${generatedContent.substring(0, 1000)}...

Check:
1. Does content reference source best practices? (Yes/No)
2. Are anti-patterns correctly used? (Yes/No)
3. Any obvious hallucinations? (Yes/No)

Respond with JSON:
{
  "isValid": true/false,
  "confidence": 0-100,
  "criticalIssues": ["list or empty array"]
}`;
}

/**
 * Generate cross-reference validation prompt
 * @param content - Generated content
 * @param pattern - Source pattern
 * @param referenceField - Field to cross-reference ('best_practices' or 'anti_patterns')
 * @returns Cross-reference prompt
 */
export function generateCrossReferencePrompt(
  content: string,
  pattern: Pattern,
  referenceField: 'best_practices' | 'anti_patterns'
): string {
  const references = referenceField === 'best_practices'
    ? pattern.best_practices
    : (pattern.anti_patterns || []);

  return `Cross-reference check: Does the generated content correctly use ${referenceField}?

AUTHORITATIVE ${referenceField.toUpperCase()}:
${references.map((item, i) => `${i + 1}. ${item}`).join('\n')}

GENERATED CONTENT:
${content}

For each ${referenceField.replace('_', ' ')} item:
1. Is it referenced in the content? (Yes/No/Partial)
2. Is it used correctly? (Yes/No/N/A)
3. Are there any distortions or misrepresentations? (Yes/No/N/A)

Respond with JSON:
{
  "references": [
    {
      "sourceItem": "original text",
      "referenced": true/false,
      "usedCorrectly": true/false,
      "notes": "any issues or 'OK'"
    }
  ],
  "overallAlignment": 0-100,
  "issues": ["list of misalignments or empty array"]
}`;
}

/**
 * Generate hallucination detection prompt
 * @param content - Generated content
 * @param pattern - Source pattern
 * @returns Hallucination detection prompt
 */
export function generateHallucinationDetectionPrompt(
  content: string,
  pattern: Pattern
): string {
  return `Detect hallucinated or fabricated content in this AI-generated output.

AUTHORITATIVE SOURCE SCOPE:
- Pattern: ${pattern.name}
- Description: ${pattern.description}
- Domain: ${pattern.applies_to.join(', ')}
- Category: ${pattern.category}

GENERATED CONTENT:
${content}

HALLUCINATION DETECTION:

1. WORKDAY-SPECIFIC TERMS:
   - Are any Workday features, modules, or terms mentioned that weren't in the source?
   - List any suspicious Workday-specific vocabulary

2. TECHNICAL DETAILS:
   - Are there specific technical processes or steps not from the source?
   - Are API endpoints, configuration settings, or technical specs fabricated?

3. EXAMPLES AND SCENARIOS:
   - Do examples stay within the scope of ${pattern.applies_to.join(', ')}?
   - Are scenarios realistic or overly specific without source basis?

4. STATISTICS AND METRICS:
   - Are there any numbers, percentages, or metrics not from the source?

Respond with JSON:
{
  "hallucinationsDetected": true/false,
  "confidence": 0-100,
  "suspiciousContent": [
    {
      "text": "suspicious content snippet",
      "reason": "why it's suspicious",
      "severity": "low|medium|high"
    }
  ],
  "recommendation": "approve|review|reject"
}`;
}

/**
 * Create system message for validation
 * @returns System message content
 */
export function getValidationSystemMessage(): string {
  return `You are a quality assurance specialist with expertise in educational content validation and fact-checking. Your role is to ensure AI-generated content is:

1. Factually accurate and grounded in source material
2. Free from hallucinations or fabricated information
3. Pedagogically sound and aligned with learning objectives
4. Professional and appropriate for enterprise training

You have a critical eye for:
- Detecting when content deviates from authoritative sources
- Identifying fabricated features, processes, or terminology
- Verifying logical consistency and accuracy
- Ensuring content quality meets professional standards

You always provide specific, actionable feedback with clear evidence.`;
}
