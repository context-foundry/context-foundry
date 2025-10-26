// Architect Blueprint Schema for Context Foundry
// Architecture design with validated structure

class ArchitectureBlueprint {
  system_overview string @description("Complete system architecture overview")
  file_structure FileStructure[] @description("Detailed file and directory structure")
  modules ModuleSpec[] @description("Module breakdown with responsibilities")
  applied_patterns AppliedPattern[] @description("Patterns applied from pattern library")
  preventive_measures string[] @description("Preventive measures for flagged risks")
  implementation_steps string[] @description("Step-by-step implementation plan, ordered")
  test_plan TestPlan @description("Comprehensive testing strategy")
  success_criteria string[] @description("Clear success criteria for the build")
}

class FileStructure {
  path string @description("File or directory path")
  purpose string @description("Purpose of this file/directory")
  dependencies string[] @description("Dependencies on other files")
}

class ModuleSpec {
  name string @description("Module name")
  responsibility string @description("Module responsibility and scope")
  interfaces string[] @description("Public interfaces/APIs this module exposes")
  dependencies string[] @description("Other modules this depends on")
}

class AppliedPattern {
  pattern_id string @description("Pattern ID from pattern library")
  pattern_name string @description("Human-readable pattern name")
  reason string @description("Why this pattern is being applied")
}

class TestPlan {
  unit_tests string[] @description("Unit tests to implement")
  integration_tests string[] @description("Integration tests to implement")
  e2e_tests string[] @description("End-to-end tests to implement")
  test_framework string @description("Test framework to use (pytest, jest, etc.)")
  success_criteria string[] @description("What constitutes test success")
}

function GenerateArchitecture(
  scout_report_json: string,
  flagged_risks: string[]
) -> ArchitectureBlueprint {
  client GPT4oMini
  prompt #"
    You are the Architect agent for Context Foundry, designing the system architecture.

    SCOUT FINDINGS:
    {{ scout_report_json }}

    FLAGGED RISKS TO ADDRESS:
    {% for risk in flagged_risks %}
    - {{ risk }}
    {% endfor %}

    Your job is to:
    1. Design complete system architecture
    2. Define file and directory structure
    3. Break down into modules with clear responsibilities
    4. Apply proven patterns from pattern library
    5. Include preventive measures for all flagged risks
    6. Create step-by-step implementation plan
    7. Design comprehensive test strategy

    CRITICAL REQUIREMENTS:
    - All flagged risks must have preventive measures
    - Test plan must include unit, integration, AND e2e tests
    - Implementation steps must be ordered and actionable
    - Module boundaries must be clear

    Return detailed technical architecture as ArchitectureBlueprint.
  "#
}

function ParseArchitectureMarkdown(markdown_content: string) -> ArchitectureBlueprint {
  client GPT4oMini
  prompt #"
    Parse this architecture markdown into a structured ArchitectureBlueprint object:

    {{ markdown_content }}

    Extract all sections:
    - System overview
    - File structure
    - Module specifications
    - Applied patterns
    - Preventive measures
    - Implementation steps
    - Test plan
    - Success criteria

    Convert to the ArchitectureBlueprint schema.
    If any section is missing, infer reasonable defaults.

    Return as structured ArchitectureBlueprint.
  "#
}
