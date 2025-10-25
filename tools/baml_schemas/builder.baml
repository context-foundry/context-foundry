// Builder Task Result Schema for Context Foundry
// Structured build outputs with error tracking

class BuildTaskResult {
  task_id string @description("Unique task identifier")
  description string @description("Task description")
  status BuildStatus @description("Task completion status")
  files_created string[] @description("Files created during this task")
  files_modified string[] @description("Files modified during this task")
  errors BuildError[] @description("Errors encountered during build")
  warnings string[] @description("Warnings (non-fatal issues)")
  success bool @description("Overall success flag")
  next_steps string[] @description("Recommended next steps")
  duration_seconds float? @description("Task execution duration")
}

enum BuildStatus {
  success @description("Task completed successfully")
  partial @description("Task partially completed with issues")
  failed @description("Task failed")
}

class BuildError {
  file string @description("File where error occurred")
  line int? @description("Line number (if applicable)")
  message string @description("Error message")
  severity ErrorSeverity @description("Error severity")
  suggestion string? @description("Suggested fix")
}

enum ErrorSeverity {
  error @description("Fatal error, build cannot continue")
  warning @description("Non-fatal warning")
  info @description("Informational message")
}

function ExecuteBuildTask(
  task_id: string,
  task_description: string,
  files_to_create: string[],
  architecture: string
) -> BuildTaskResult {
  client Claude35Sonnet
  prompt #"
    You are a Builder agent for Context Foundry, executing a build task.

    TASK ID: {{ task_id }}
    TASK: {{ task_description }}

    FILES TO CREATE:
    {% for file in files_to_create %}
    - {{ file }}
    {% endfor %}

    ARCHITECTURE CONTEXT:
    {{ architecture }}

    Your job is to:
    1. Create all specified files with complete, working code
    2. Follow the architecture design precisely
    3. Ensure code quality and best practices
    4. Track any errors or warnings
    5. Report files created/modified
    6. Provide next steps if needed

    Execute the task and return structured BuildTaskResult with:
    - All files created
    - Any errors encountered
    - Success status
    - Warnings or recommendations

    Return as structured BuildTaskResult.
  "#
}

function ValidateBuildResult(result_json: string) -> BuildTaskResult {
  client Claude35Sonnet
  prompt #"
    Validate this build task result JSON:

    {{ result_json }}

    Convert to a valid BuildTaskResult object.
    Ensure all required fields are present.
    If any fields are missing, use sensible defaults.

    Return as structured BuildTaskResult.
  "#
}
