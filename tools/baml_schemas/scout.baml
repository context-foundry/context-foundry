// Scout Report Schema for Context Foundry
// Structured Scout phase outputs with guaranteed schema

class ScoutReport {
  executive_summary string @description("2-3 paragraphs max, concise overview")
  past_learnings_applied string[] @description("Bullet points of applied learnings from pattern library")
  known_risks string[] @description("Risks flagged from pattern library")
  key_requirements string[] @description("Bulleted list of requirements, not essay")
  tech_stack TechStack @description("Technology stack decision with justification")
  architecture_recommendations string[] @description("Top 3-5 critical recommendations only")
  main_challenges Challenge[] @description("Top 3-5 challenges with mitigations")
  testing_approach string @description("Brief testing outline, not comprehensive plan")
  timeline_estimate string @description("Single line estimate (e.g., '2-3 hours')")
}

class TechStack {
  languages string[] @description("Programming languages to use")
  frameworks string[] @description("Frameworks and libraries")
  dependencies string[] @description("Key dependencies")
  justification string @description("Brief justification (2-3 sentences max)")
}

class Challenge {
  description string @description("Challenge description")
  severity Severity @description("Challenge severity level")
  mitigation string @description("Mitigation strategy")
}

enum Severity {
  LOW
  MEDIUM
  HIGH
  CRITICAL
}

function GenerateScoutReport(
  task_description: string,
  codebase_analysis: string,
  past_patterns: string
) -> ScoutReport {
  client Claude35Sonnet
  prompt #"
    You are the Scout agent for Context Foundry, researching requirements for this task:

    TASK:
    {{ task_description }}

    CODEBASE ANALYSIS:
    {{ codebase_analysis }}

    PAST PATTERNS TO CONSIDER:
    {{ past_patterns }}

    Your job is to:
    1. Analyze the task thoroughly
    2. Apply learnings from past patterns
    3. Research best practices for this type of project
    4. Identify technology stack and constraints
    5. Document potential challenges and solutions
    6. Outline testing requirements

    IMPORTANT: Keep it concise! Target 5-10KB output, not 60KB.
    - Executive summary: 2-3 paragraphs max
    - Recommendations: Top 3-5 items only
    - Challenges: Top 3-5 items only
    - Brief justifications, not essays

    Provide comprehensive yet concise research findings as a structured ScoutReport.
  "#
}

function ParseScoutMarkdown(markdown_content: string) -> ScoutReport {
  client Claude35Sonnet
  prompt #"
    Parse this Scout report markdown into a structured ScoutReport object:

    {{ markdown_content }}

    Extract all sections and convert to the ScoutReport schema.
    If any section is missing, infer reasonable defaults.

    Return as structured ScoutReport.
  "#
}
