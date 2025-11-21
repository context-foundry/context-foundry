// Build Planning Schema for Context Foundry
// Type-safe build task planning for parallel builds

enum AgentProvider {
  Claude
  Gemini
}

class BuildTask {
  task_id string @description("Unique identifier for this task (e.g., 'task-1')")
  name string @description("Human-readable task name")
  description string @description("Detailed description of what this task does")
  working_directory string @description("Directory where build commands execute (relative to project root)")
  agent_instruction string @description("REQUIRED: Natural language instruction for the AI Agent. Tell the agent what to build for this specific task.")
  provider AgentProvider @description("REQUIRED: MUST be set to 'Claude' for ALL tasks. Do NOT use Gemini.")
  build_commands string[] @description("DEPRECATED: Leave empty [] or only simple commands like mkdir. Agent will write code, not shell scripts.")
  dependencies string[] @description("Array of task_ids that must complete before this task starts.")
  estimated_duration_minutes int @description("Estimated time to complete this task in minutes")
}

class BuildPlan {
  parallel_build_enabled bool @description("Whether parallel build is enabled (true if Scout recommended parallel)")
  tasks BuildTask[] @description("List of build tasks with dependencies")
  total_estimated_sequential int @description("Total time if all tasks run sequentially (sum of all durations)")
  total_estimated_parallel int @description("Total time with parallel execution (critical path length)")
  time_savings_percent int @description("Percentage time saved by running in parallel vs sequential")
}

function CreateBuildPlan(
  architecture_summary: string,
  scout_parallel_recommendation: bool,
  scout_reasoning: string,
  project_type: string
) -> BuildPlan {
  client GPT4
  prompt #"
    You are the Architect agent creating a build execution plan for Context Foundry.

    Project Type: {{ project_type }}
    Architecture Summary:
    {{ architecture_summary }}

    Scout Parallel Build Recommendation: {{ scout_parallel_recommendation }}
    Scout Reasoning: {{ scout_reasoning }}

    Create a comprehensive build plan with tasks and dependencies.

    **UNIFIED AGENTIC BUILD ARCHITECTURE:**
    - You define TASKS.
    - The system spawns INTELLIGENT AGENTS to execute those tasks.
    - **REQUIRED**: You MUST provide `agent_instruction` for EVERY task (natural language instruction)
    - **REQUIRED**: You MUST provide `provider` for EVERY task (set to "Claude")
    - DO NOT write complex shell scripts in `build_commands`. The Agent will write the code.
    - build_commands is DEPRECATED - leave empty [] or use only for simple commands like "mkdir"

    **CRITICAL RULES:**
    1. If scout_parallel_recommendation is FALSE (Sequential Mode):
       - parallel_build_enabled: false
       - Create EXACTLY ONE task that covers the entire project.
       - agent_instruction: "Implement the entire project according to architecture.md"

    2. If scout_parallel_recommendation is TRUE (Parallel Mode):
       - parallel_build_enabled: true
       - **MAXIMIZE PARALLELIZATION** - split work into as many independent tasks as possible
       - Identify independent modules that can build in parallel
       - Define tasks with proper dependencies
       - **ENSURE NO CYCLIC DEPENDENCIES**
       - **Default to empty dependencies []** - only add dependencies when truly required

    **🤖 PROVIDER SELECTION:**
    - **IMPORTANT**: Always set provider to "Claude" for ALL tasks.
    - Use Claude Code for every single task regardless of complexity.
    - Do NOT use Gemini or any other provider.

    **⚡ PARALLELIZATION OPPORTUNITIES:**
    - Frontend + Backend: ALWAYS 2 separate parallel tasks (no dependencies between them)
    - Multiple services: Each service = separate parallel task
    - Separate apps in monorepo: Each app = parallel task
    - Independent libraries: Each lib = parallel task

    **Example Dependency Graphs:**
    - Independent modules (MOST COMMON): dependencies: []
    - Integration tasks: dependencies: ["task-1", "task-2"]

    **⚠️ IMPORTANT: Don't over-constrain dependencies!**
    - Frontend does NOT depend on backend build (they're separate artifacts)
    - Backend does NOT depend on frontend build

    Calculate accurate time estimates:
    - total_estimated_sequential: sum of all task durations
    - total_estimated_parallel: length of critical path (longest dependency chain)
    - time_savings_percent: ((sequential - parallel) / sequential) * 100

    **EXAMPLE TASK FORMAT (REQUIRED):**
    {
      "task_id": "task-1",
      "name": "Build Frontend",
      "description": "Create React frontend application",
      "working_directory": ".",
      "agent_instruction": "Create a React frontend with components in src/components/, implement routing, and add styling. Follow the architecture.md specifications.",
      "provider": "Claude",
      "build_commands": [],
      "dependencies": [],
      "estimated_duration_minutes": 5
    }

    Return as structured BuildPlan object.
  "#
}
