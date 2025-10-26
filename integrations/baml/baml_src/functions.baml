/**
 * BAML Function Definitions (Schema Documentation Only)
 *
 * These function signatures define the interface and return types for
 * operations performed via MCP delegation. They serve as:
 *
 * 1. Type definitions for validation
 * 2. Documentation of expected inputs/outputs
 * 3. Schema contracts between caller and spawned Claude instances
 *
 * IMPLEMENTATION: All functions are implemented via Context Foundry's
 * MCP delegation pattern (see python/examples/mcp_delegation.py).
 * No direct API calls are made.
 */

/**
 * Document Processing Function
 *
 * Analyzes documents (PDF, DOCX) using Agent Skills for structured extraction.
 *
 * @param file_path Path to the document file
 * @param questions List of questions to answer about the document
 * @returns DocumentAnalysis with structured results
 */
function AnalyzeDocument(
  file_path: string,
  questions: string[]
) -> DocumentAnalysis {
  client AnthropicClient
  prompt #"
    You are a document analysis assistant with access to document processing skills.

    DOCUMENT: {{ file_path }}

    QUESTIONS TO ANSWER:
    {% for question in questions %}
    - {{ question }}
    {% endfor %}

    INSTRUCTIONS:
    1. If the document path is provided, use your document reading skills to access the content
    2. Extract structured information that answers each question
    3. Identify the most important findings from the document
    4. Provide a confidence score for your analysis

    Return your analysis in the specified structured format.
  "#
}

/**
 * Data Analysis Function
 *
 * Analyzes datasets using Agent Skills for pattern detection and insights.
 *
 * @param data_source Path or description of the data source
 * @param analysis_type Type of analysis to perform (e.g., "trends", "anomalies", "forecast")
 * @returns DataInsights with trends, anomalies, and recommendations
 */
function AnalyzeDataset(
  data_source: string,
  analysis_type: string
) -> DataInsights {
  client AnthropicClient
  prompt #"
    You are a data analysis assistant with access to data processing skills.

    DATA SOURCE: {{ data_source }}
    ANALYSIS TYPE: {{ analysis_type }}

    INSTRUCTIONS:
    1. Use your data processing skills to access and analyze the dataset
    2. Based on the analysis type, focus on:
       - "trends": Identify patterns over time
       - "anomalies": Detect outliers and unusual patterns
       - "forecast": Predict future values based on historical data
       - "summary": Provide comprehensive statistical summary
    3. Generate actionable recommendations
    4. Suggest appropriate visualizations for the insights

    Return your analysis in the specified structured format.
  "#
}

/**
 * Custom Skill Integration Function
 *
 * Demonstrates how to work with custom Agent Skills in a flexible way.
 *
 * @param task Description of the task to perform
 * @param skill_name Name of the custom skill to use
 * @returns SkillResult with execution details
 */
function ProcessWithCustomSkill(
  task: string,
  skill_name: string
) -> SkillResult {
  client AnthropicClient
  prompt #"
    You are an agent with access to custom skills.

    TASK: {{ task }}
    AVAILABLE SKILL: {{ skill_name }}

    INSTRUCTIONS:
    1. Use the {{ skill_name }} skill to complete the task
    2. Capture the output from the skill execution
    3. Record metadata about how the skill was used
    4. Report whether the execution was successful

    Return the results in the specified structured format.
  "#
}

/**
 * Task Type Analyzer
 *
 * Analyzes a user request to determine what type of task it is
 * and what skills would be needed (progressive disclosure).
 *
 * @param user_request The user's request in natural language
 * @returns TaskAnalysis classifying the request
 */
function AnalyzeTaskType(
  user_request: string
) -> TaskAnalysis {
  client AnthropicClientDev
  prompt #"
    You are a task classification expert.

    USER REQUEST: {{ user_request }}

    INSTRUCTIONS:
    1. Analyze the request to determine what type of task it is
    2. Identify which skills would be needed to complete this task
    3. Provide your confidence in this classification

    TASK TYPES:
    - "document_analysis": Working with PDF, DOCX, or other document files
    - "data_analysis": Analyzing datasets, CSVs, or numerical data
    - "custom_skill": Task requires a specific custom capability
    - "general": General conversation or task not requiring special skills

    AVAILABLE SKILLS:
    - pdf_reader: Read and extract text from PDF files
    - docx_parser: Parse and extract content from DOCX files
    - data_processor: Analyze structured data (CSV, JSON, etc.)
    - visualization: Create chart and graph descriptions
    - custom_tool: Domain-specific custom tools

    Return your analysis in the specified structured format.
  "#
}

/**
 * Progressive Skill Loader
 *
 * Demonstrates progressive disclosure by loading skills only when needed.
 *
 * @param task The task to perform
 * @param available_skills List of skills that could be loaded
 * @returns SkillLoadingResult showing which skills were loaded and why
 */
function LoadSkillsProgressively(
  task: string,
  available_skills: string[]
) -> SkillLoadingResult {
  client AnthropicClientDev
  prompt #"
    You are a skill management expert practicing progressive disclosure.

    TASK: {{ task }}

    AVAILABLE SKILLS:
    {% for skill in available_skills %}
    - {{ skill }}
    {% endfor %}

    INSTRUCTIONS:
    1. Analyze the task to determine which skills are ACTUALLY needed
    2. Load only the minimum necessary skills (progressive disclosure)
    3. Explain why each skill was loaded
    4. List skills that could have been loaded but weren't necessary
    5. This reduces cognitive load and improves performance

    PROGRESSIVE DISCLOSURE PRINCIPLE:
    Don't overwhelm the agent with all available skills upfront.
    Introduce capabilities only when the task requires them.

    Return your decisions in the specified structured format.
  "#
}

/**
 * ============================================================================
 * DUAL-PROVIDER FUNCTIONS (Cost-Effective with OpenAI)
 * ============================================================================
 */

/**
 * Generate Summary (Cost-Effective with OpenAI)
 *
 * Uses GPT-4o-mini for simple text summarization at 20x lower cost than Claude.
 *
 * Cost: ~$0.0015 per 10K tokens (vs $0.30 with Claude)
 *
 * @param text Text to summarize
 * @param max_sentences Maximum sentences in summary
 * @returns TextSummary with condensed version
 */
function GenerateSummary(
  text: string,
  max_sentences: int
) -> TextSummary {
  client OpenAIClient
  prompt #"
    You are a summarization assistant.

    TEXT TO SUMMARIZE:
    {{ text }}

    INSTRUCTIONS:
    1. Read the text carefully
    2. Extract the most important information
    3. Create a concise summary with no more than {{ max_sentences }} sentences
    4. Preserve key facts and main points
    5. Use clear, simple language

    Return the summary in the specified format.
  "#
}

/**
 * Extract Structured Data (Cost-Effective with OpenAI)
 *
 * Uses GPT-4o-mini for simple data extraction from text.
 * Perfect for high-volume batch processing.
 *
 * @param text Text containing data to extract
 * @param schema Description of the data structure to extract
 * @returns StructuredData with extracted information
 */
function ExtractStructuredData(
  text: string,
  schema: string
) -> StructuredData {
  client OpenAIClient
  prompt #"
    You are a data extraction assistant.

    TEXT:
    {{ text }}

    SCHEMA TO EXTRACT:
    {{ schema }}

    INSTRUCTIONS:
    1. Parse the text carefully
    2. Extract data matching the specified schema
    3. Validate extracted data for completeness
    4. Handle missing fields gracefully

    Return the extracted data in the specified structured format.
  "#
}

/**
 * Classify Text (Cost-Effective with OpenAI)
 *
 * Uses GPT-4o-mini for text classification tasks.
 * Ideal for high-volume content moderation, tagging, or categorization.
 *
 * @param text Text to classify
 * @param categories List of possible categories
 * @returns TextClassification with predicted category and confidence
 */
function ClassifyText(
  text: string,
  categories: string[]
) -> TextClassification {
  client OpenAIClient
  prompt #"
    You are a text classification assistant.

    TEXT TO CLASSIFY:
    {{ text }}

    POSSIBLE CATEGORIES:
    {% for category in categories %}
    - {{ category }}
    {% endfor %}

    INSTRUCTIONS:
    1. Analyze the text content
    2. Determine which category best fits
    3. Provide a confidence score (0.0 to 1.0)
    4. Explain your reasoning briefly

    Return the classification in the specified format.
  "#
}

/**
 * Hybrid Function: Choose Provider Based on Task Complexity
 *
 * This demonstrates intelligent provider selection:
 * - Uses OpenAI for simple tasks (cost-effective)
 * - Falls back to Claude for complex tasks (higher quality)
 *
 * @param task Description of the task
 * @param complexity Estimated complexity ("simple", "moderate", "complex")
 * @returns TaskResult with appropriate provider used
 */
function SmartProcessTask(
  task: string,
  complexity: string
) -> TaskResult {
  // Start with cost-effective OpenAI
  client OpenAIClient
  prompt #"
    You are an intelligent task processor.

    TASK: {{ task }}
    COMPLEXITY: {{ complexity }}

    INSTRUCTIONS:
    1. Process the task according to the requirements
    2. If complexity is "simple", use efficient processing
    3. For "complex" tasks, apply advanced reasoning
    4. Track which approach was used

    COST OPTIMIZATION:
    This function uses GPT-4o-mini for cost savings.
    For complex tasks requiring Agent Skills, use AnalyzeDocument or AnalyzeDataset instead.

    Return the result in the specified format.
  "#
}
