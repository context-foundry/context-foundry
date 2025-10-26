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
