/**
 * Data Analysis Example (TypeScript)
 */

import { existsSync } from 'fs';
import { loadConfig } from '../shared/config.js';
import { retryWithBackoff, DataAnalysisError, createLogger } from '../shared/utils.js';

const logger = createLogger();

export type AnalysisType = 'trends' | 'anomalies' | 'forecast' | 'summary';

export interface DataInsights {
  trends: string[];
  anomalies: string[];
  recommendations: string[];
  visualizations: Record<string, string>;
  statistics?: Record<string, number>;
}

export async function analyzeDataset(
  dataSource: string,
  analysisType: AnalysisType = 'summary'
): Promise<DataInsights> {
  return retryWithBackoff(async () => {
    logger.info(`Analyzing dataset: ${dataSource}`);
    logger.info(`Analysis type: ${analysisType}`);

    try {
      // NOTE: Requires BAML client generation
      // const result = await b.AnalyzeDataset({ data_source: dataSource, analysis_type: analysisType });

      const result: DataInsights = {
        trends: [
          `Placeholder trend analysis for ${analysisType}`,
          'Run baml-cli generate to enable real API calls',
        ],
        anomalies: ['No anomalies detected (placeholder)'],
        recommendations: [
          `Based on ${analysisType} analysis, consider...`,
          'Investigate seasonal patterns',
        ],
        visualizations: {
          time_series: `${analysisType}_over_time.png`,
          distribution: 'distribution_histogram.png',
        },
        statistics: { mean: 42.0, median: 40.0, std_dev: 12.5 },
      };

      logger.info(`Analysis complete. Found ${result.trends.length} trends`);
      return result;
    } catch (error) {
      logger.error(`Data analysis failed: ${error}`);
      throw new DataAnalysisError(`Failed to analyze dataset: ${error}`);
    }
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig();

  analyzeDataset('sample.csv', 'trends')
    .then(result => {
      console.log('\nTrends:');
      result.trends.forEach(t => console.log(`  • ${t}`));
      console.log('\nRecommendations:');
      result.recommendations.forEach(r => console.log(`  • ${r}`));
    })
    .catch(err => {
      logger.error(`Example failed: ${err}`);
      process.exit(1);
    });
}
