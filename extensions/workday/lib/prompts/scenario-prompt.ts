import { Pattern } from '@/types/pattern';

/**
 * Scenario Generation Prompt Templates
 *
 * Provides prompt templates for generating interactive branching scenarios
 * with validation instructions to ensure accuracy and quality.
 */

/**
 * Generate scenario prompt with validation instructions
 * @param pattern - Pattern data
 * @returns Formatted prompt
 */
export function generateScenarioPrompt(pattern: Pattern): string {
  return `You are an expert instructional designer creating an interactive branching scenario for teaching Workday expertise patterns.

PATTERN INFORMATION:
Name: ${pattern.name}
Category: ${pattern.category}
Description: ${pattern.description}

BEST PRACTICES (MUST be referenced in the scenario):
${pattern.best_practices.map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

ANTI-PATTERNS (MUST be shown as incorrect choices):
${(pattern.anti_patterns || []).map((ap, i) => `${i + 1}. ${ap}`).join('\n')}

EXAMPLES FOR CONTEXT:
${(pattern.examples || []).map((ex, i) => `${i + 1}. ${ex}`).join('\n')}

TASK:
Create an interactive branching scenario with 5-7 decision points that teaches this pattern through realistic workplace situations.

REQUIREMENTS:
1. Create a realistic workplace scenario relevant to: ${pattern.applies_to.join(', ')}
2. Each decision node must have 2-4 options
3. At least 2 incorrect options MUST reference anti-patterns from the source data
4. Correct options MUST align with best practices from the source data
5. Include clear feedback explaining why each choice is correct or incorrect
6. Reference specific best practices and anti-patterns by name in feedback
7. Create at least one "success" outcome and one "failure" outcome
8. The scenario should take 5-10 minutes to complete
9. Use professional, realistic dialogue and situations

VALIDATION CHECKLIST (you MUST verify before responding):
- [ ] Every incorrect option references at least one anti-pattern from the source
- [ ] Every correct option aligns with at least one best practice from the source
- [ ] All feedback explicitly mentions which best practice or anti-pattern applies
- [ ] The scenario is realistic and relevant to the specified domains (${pattern.applies_to.join(', ')})
- [ ] No hallucinated features, tools, or processes not mentioned in the pattern data

OUTPUT FORMAT (JSON):
{
  "patternId": "${pattern.id}",
  "patternName": "${pattern.name}",
  "title": "Brief scenario title (max 80 characters)",
  "description": "2-3 sentence scenario setup",
  "nodes": [
    {
      "id": "node-1",
      "type": "start",
      "title": "Scenario title",
      "description": "Detailed scenario description (2-3 paragraphs)",
      "options": [
        {
          "id": "option-1",
          "text": "Option text",
          "nextNodeId": "node-2",
          "isCorrect": true,
          "rationale": "Explanation referencing specific best practice"
        }
      ]
    },
    {
      "id": "node-2",
      "type": "decision",
      "title": "Decision point title",
      "description": "What happens next (1-2 paragraphs)",
      "options": [...]
    },
    {
      "id": "node-end-success",
      "type": "end",
      "title": "Success!",
      "description": "Positive outcome description",
      "isSuccessful": true,
      "feedback": "Summary of what was learned and which best practices were applied"
    },
    {
      "id": "node-end-failure",
      "type": "end",
      "title": "Lesson Learned",
      "description": "Learning opportunity description",
      "isSuccessful": false,
      "feedback": "Explanation of what went wrong and which anti-patterns were triggered"
    }
  ],
  "startNodeId": "node-1",
  "generatedAt": "${new Date().toISOString()}"
}

Generate the scenario now, ensuring all validation criteria are met.`;
}

/**
 * Generate simplified scenario prompt (for faster generation)
 * @param pattern - Pattern data
 * @returns Formatted prompt
 */
export function generateSimpleScenarioPrompt(pattern: Pattern): string {
  return `Create a short interactive scenario (3-4 decision points) teaching "${pattern.name}".

Best Practices (use in correct choices):
${pattern.best_practices.slice(0, 3).map((bp, i) => `${i + 1}. ${bp}`).join('\n')}

Anti-Patterns (use in incorrect choices):
${(pattern.anti_patterns || []).slice(0, 2).map((ap, i) => `${i + 1}. ${ap}`).join('\n')}

Context: ${pattern.description}

Create a realistic workplace scenario for ${pattern.applies_to[0]} with:
- Clear start node with scenario setup
- 2-3 decision nodes with 2-3 options each
- Success and failure end nodes
- Feedback referencing specific practices

Return valid JSON matching this structure:
{
  "patternId": "${pattern.id}",
  "patternName": "${pattern.name}",
  "title": "scenario title",
  "description": "scenario description",
  "nodes": [...],
  "startNodeId": "node-1",
  "generatedAt": "${new Date().toISOString()}"
}`;
}

/**
 * Generate validation prompt for scenario content
 * @param scenarioJSON - Generated scenario JSON
 * @param pattern - Source pattern
 * @returns Validation prompt
 */
export function generateScenarioValidationPrompt(scenarioJSON: string, pattern: Pattern): string {
  return `Validate this generated scenario against the source pattern data.

SOURCE PATTERN:
Name: ${pattern.name}
Best Practices: ${pattern.best_practices.join('; ')}
Anti-Patterns: ${(pattern.anti_patterns || []).join('; ')}

GENERATED SCENARIO:
${scenarioJSON}

VALIDATION CRITERIA:
1. Do all incorrect options reference anti-patterns from the source?
2. Do all correct options align with best practices from the source?
3. Does feedback explicitly reference source best practices/anti-patterns?
4. Is the scenario realistic and free of hallucinations?
5. Are all JSON fields properly formatted?

Respond with JSON:
{
  "isValid": true/false,
  "issues": ["list of specific issues found, or empty array if valid"],
  "confidence": 0-100,
  "recommendations": ["suggested improvements"]
}`;
}

/**
 * Create system message for scenario generation
 * @returns System message content
 */
export function getScenarioSystemMessage(): string {
  return `You are an expert instructional designer specializing in creating engaging, educational branching scenarios for enterprise software training. You have deep expertise in Workday systems and best practices.

Your scenarios are:
- Realistic and grounded in actual workplace situations
- Pedagogically sound with clear learning objectives
- Engaging with authentic dialogue and consequences
- Accurate and factual, never including hallucinated features
- Appropriately challenging for the learner's level

Always validate your output against the source material before responding.`;
}
