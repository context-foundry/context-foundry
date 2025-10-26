/**
 * Custom Type Definitions for BAML Functions
 *
 * These types provide compile-time safety for LLM inputs and outputs.
 */

/**
 * Document Analysis Result
 *
 * Structured output from document processing tasks.
 */
class DocumentAnalysis {
  // High-level summary of the document
  summary string

  // Key findings extracted from the document
  key_findings string[]

  // Answers to specific questions about the document
  answers map<string, string>

  // Confidence score (0.0 to 1.0) for the analysis
  confidence_score float

  // Metadata about the analysis
  metadata map<string, string>?
}

/**
 * Data Insights Result
 *
 * Structured output from data analysis tasks.
 */
class DataInsights {
  // Identified trends in the data
  trends string[]

  // Detected anomalies or outliers
  anomalies string[]

  // Actionable recommendations based on the analysis
  recommendations string[]

  // Descriptions of potential visualizations
  visualizations map<string, string>

  // Statistical summary
  statistics map<string, float>?
}

/**
 * Skill Execution Result
 *
 * Result from custom skill invocations.
 */
class SkillResult {
  // Name of the skill that was used
  skill_used string

  // Output from the skill execution
  output string

  // Metadata about the execution
  metadata map<string, string>

  // Whether the skill execution was successful
  success bool

  // Timestamp of execution (ISO 8601 format)
  timestamp string?
}

/**
 * Task Analysis
 *
 * Result from analyzing what type of task is being requested.
 */
class TaskAnalysis {
  // Type of task (e.g., "document_analysis", "data_analysis", "custom")
  task_type string

  // Required skills for this task
  required_skills string[]

  // Confidence in the task classification
  confidence float

  // Additional context about the task
  context string?
}

/**
 * Progressive Skill Loading Result
 *
 * Result from progressive skill disclosure pattern.
 */
class SkillLoadingResult {
  // List of skills that were loaded
  loaded_skills string[]

  // Reason each skill was loaded
  loading_rationale map<string, string>

  // Skills that could have been loaded but weren't necessary
  skipped_skills string[]

  // Performance metrics
  metrics map<string, float>?
}

/**
 * ============================================================================
 * DUAL-PROVIDER TYPES (For Cost-Effective Functions)
 * ============================================================================
 */

/**
 * Text Summary Result
 *
 * Output from summarization tasks (typically using cost-effective providers).
 */
class TextSummary {
  // The condensed summary text
  summary string

  // Number of sentences in the summary
  sentence_count int

  // Key points extracted
  key_points string[]

  // Original text length vs summary length
  compression_ratio float?
}

/**
 * Structured Data Extraction Result
 *
 * Output from data extraction tasks.
 */
class StructuredData {
  // Extracted data fields
  data map<string, string>

  // Fields that were found in the text
  found_fields string[]

  // Fields that were missing
  missing_fields string[]

  // Confidence in extraction accuracy
  confidence float
}

/**
 * Text Classification Result
 *
 * Output from text classification tasks.
 */
class TextClassification {
  // Predicted category
  category string

  // Confidence score (0.0 to 1.0)
  confidence float

  // Brief explanation of classification
  reasoning string

  // Alternative categories considered
  alternatives string[]?
}

/**
 * Task Processing Result
 *
 * Output from smart task processing with provider selection.
 */
class TaskResult {
  // Result of the task
  result string

  // Provider used ("openai" or "anthropic")
  provider_used string

  // Estimated cost of the operation
  estimated_cost_usd float?

  // Processing time in milliseconds
  processing_time_ms int?

  // Whether the task was successful
  success bool
}
