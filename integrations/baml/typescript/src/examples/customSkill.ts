/**
 * Custom Skill Example (TypeScript)
 */

import { loadConfig } from '../shared/config.js';
import { retryWithBackoff, SkillExecutionError, createLogger } from '../shared/utils.js';

const logger = createLogger();

export interface SkillResult {
  skill_used: string;
  output: string;
  metadata: Record<string, string>;
  success: boolean;
  timestamp?: string;
}

export async function processWithCustomSkill(
  task: string,
  skillName: string
): Promise<SkillResult> {
  return retryWithBackoff(async () => {
    logger.info(`Processing task with skill: ${skillName}`);

    try {
      // NOTE: Requires BAML client
      // const result = await b.ProcessWithCustomSkill({ task, skill_name: skillName });

      const result: SkillResult = {
        skill_used: skillName,
        output: `Placeholder output from ${skillName} skill`,
        metadata: { task, execution_time_ms: '150' },
        success: true,
        timestamp: new Date().toISOString(),
      };

      logger.info(`Skill execution ${result.success ? 'succeeded' : 'failed'}`);
      return result;
    } catch (error) {
      logger.error(`Skill execution failed: ${error}`);
      throw new SkillExecutionError(`Failed to execute skill ${skillName}: ${error}`);
    }
  });
}

export async function progressiveSkillLoading(
  task: string,
  availableSkills: string[]
): Promise<any> {
  logger.info(`Progressive skill loading for task: ${task}`);

  const result = {
    loaded_skills: ['pdf_reader'],
    loading_rationale: { pdf_reader: 'Task mentions PDF' },
    skipped_skills: availableSkills.filter(s => s !== 'pdf_reader'),
    metrics: { efficiency_ratio: 0.25 },
  };

  logger.info(`Loaded ${result.loaded_skills.length} of ${availableSkills.length} skills`);
  return result;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  processWithCustomSkill('Calculate factorial of 10', 'calculator')
    .then(result => {
      console.log(`\nSkill: ${result.skill_used}`);
      console.log(`Output: ${result.output}`);
      console.log(`Success: ${result.success}`);
    })
    .catch(err => {
      logger.error(`Example failed: ${err}`);
      process.exit(1);
    });
}
