// Pattern Extraction Schema for Workday Extension

class Pattern {
  pattern_id string @description("Unique ID in kebab-case (e.g., 'workday-hcm-hire')")
  category string @description("Category: business-process, security, integration, reporting")
  description string @description("Brief description of the pattern")
  applies_to string[] @description("Modules or features this applies to (e.g., 'hcm', 'recruiting')")
  node_types string[] @description("Workday tasks or business objects involved")
  best_practices string[] @description("List of best practices extracted from text")
  anti_patterns string[] @description("List of things to avoid")
  common_issues CommonIssue[] @description("Common issues and solutions")
}

class CommonIssue {
  issue_id string @description("Unique ID for the issue")
  description string @description("Description of the problem")
  solution string @description("How to fix or prevent it")
}

function ExtractPatterns(transcript_text: string) -> Pattern[] {
  client GPT4oMini
  prompt #"
    Analyze the following Workday training transcript and extract architectural patterns, best practices, and common issues.

    TRANSCRIPT:
    {{ transcript_text }}

    For EACH pattern you find, you MUST provide ALL of these fields:
    - pattern_id: Unique ID in kebab-case
    - category: One of "business-process", "security", "integration", or "reporting"
    - description: Brief description
    - applies_to: Array of modules like ["hcm"], ["learning"], ["reporting"], etc.
    - node_types: Array of Workday tasks/objects (e.g., ["Contract Contingent Worker", "Hire Employee"])
    - best_practices: Array of best practice strings (or empty array [])
    - anti_patterns: Array of anti-pattern strings (or empty array [])
    - common_issues: Array of issue objects with issue_id, description, solution (or empty array [])

    Return a JSON array of Pattern objects with ALL fields present.
    If no patterns found, return [].
  "#
}
