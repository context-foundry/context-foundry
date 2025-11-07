/**
 * Document Processing Example (TypeScript)
 *
 * Demonstrates BAML + Anthropic Agent Skills for document analysis.
 */

import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';
import { loadConfig } from '../shared/config.js';
import { retryWithBackoff, DocumentProcessingError, createLogger } from '../shared/utils.js';

const logger = createLogger();

/**
 * Document Analysis Result
 */
export interface DocumentAnalysis {
  summary: string;
  key_findings: string[];
  answers: Record<string, string>;
  confidence_score: number;
  metadata?: Record<string, string>;
}

/**
 * Analyze a document using BAML + Anthropic Agent Skills.
 */
export async function analyzeDocument(
  filePath: string,
  questions: string[]
): Promise<DocumentAnalysis> {
  return retryWithBackoff(async () => {
    // Validate file exists
    if (!existsSync(filePath)) {
      throw new Error(`Document not found: ${filePath}`);
    }

    logger.info(`Analyzing document: ${filePath}`);
    logger.info(`Questions: ${questions.join(', ')}`);

    try {
      // NOTE: Requires BAML client generation
      // Uncomment after running: baml-cli generate
      // import { b } from '../../baml_client/index.js';
      // const result = await b.AnalyzeDocument({
      //   file_path: filePath,
      //   questions: questions
      // });

      // Placeholder response
      const result: DocumentAnalysis = {
        summary: `Analysis of document: ${filePath}`,
        key_findings: [
          'This is a placeholder response',
          'Run baml-cli generate to enable real API calls',
          'BAML provides type-safe prompting',
        ],
        answers: Object.fromEntries(questions.map(q => [q, `Answer to: ${q}`])),
        confidence_score: 0.85,
        metadata: {
          file_name: filePath.split('/').pop() || '',
          questions_count: questions.length.toString(),
        },
      };

      logger.info(`Analysis complete. Confidence: ${result.confidence_score}`);
      return result;
    } catch (error) {
      logger.error(`Document processing failed: ${error}`);
      throw new DocumentProcessingError(`Failed to analyze document: ${error}`);
    }
  });
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig();

  const testFile = resolve(__dirname, '../../../test_data/sample.pdf');
  const questions = [
    'What is the main topic?',
    'What are the key findings?',
  ];

  analyzeDocument(testFile, questions)
    .then(result => {
      console.log('\n' + '='.repeat(60));
      console.log('DOCUMENT ANALYSIS RESULTS');
      console.log('='.repeat(60));
      console.log(`\nSummary:\n${result.summary}\n`);
      console.log('Key Findings:');
      result.key_findings.forEach(f => console.log(`  • ${f}`));
      console.log(`\nConfidence: ${(result.confidence_score * 100).toFixed(0)}%`);
      console.log('\n' + '='.repeat(60));
    })
    .catch(err => {
      logger.error(`Example failed: ${err}`);
      process.exit(1);
    });
}
