// Phase Tracking Schema for Context Foundry
// Type-safe phase tracking to replace JSON strings

class PhaseInfo {
  session_id string @description("Project directory name")
  current_phase PhaseType @description("Current phase of the build")
  phase_number string @description("Phase number in X/Y format")
  status PhaseStatus @description("Current status of the phase")
  progress_detail string @description("Human-readable progress description")
  test_iteration int @description("Number of test iterations (0 if not testing)")
  phases_completed PhaseType[] @description("List of completed phases")
  started_at string @description("ISO timestamp when phase started")
  last_updated string @description("ISO timestamp of last update")
}

enum PhaseType {
  CodebaseAnalysis @alias("Codebase Analysis")
  Scout
  Architect
  Builder
  Test
  Screenshot
  Documentation
  Deploy
  Feedback
  GitHub @alias("GitHub Integration")
}

enum PhaseStatus {
  Analyzing @alias("analyzing")
  Researching @alias("researching")
  Designing @alias("designing")
  Building @alias("building")
  Testing @alias("testing")
  SelfHealing @alias("self-healing")
  Capturing @alias("capturing")
  Documenting @alias("documenting")
  Deploying @alias("deploying")
  Completed @alias("completed")
  Failed @alias("failed")
}

function CreatePhaseInfo(
  session_id: string,
  phase: PhaseType,
  status: PhaseStatus,
  detail: string,
  iteration: int
) -> PhaseInfo {
  client Claude35Sonnet
  prompt #"
    Create phase tracking information for Context Foundry build:

    Session ID: {{ session_id }}
    Current Phase: {{ phase }}
    Status: {{ status }}
    Progress Detail: {{ detail }}
    Test Iteration: {{ iteration }}

    Generate a complete PhaseInfo object with appropriate timestamps and phase completion tracking.

    Return as structured data matching the PhaseInfo schema.
  "#
}

function ValidatePhaseInfo(json_string: string) -> PhaseInfo {
  client Claude35Sonnet
  prompt #"
    Validate and parse this phase tracking JSON from Context Foundry:

    {{ json_string }}

    Convert it to a valid PhaseInfo object. If any fields are missing or invalid,
    use sensible defaults:
    - session_id: "unknown" if missing
    - test_iteration: 0 if missing
    - phases_completed: [] if missing
    - timestamps: current time if missing

    Return as structured PhaseInfo object.
  "#
}
