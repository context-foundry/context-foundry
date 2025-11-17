// Build Planning Schema for Context Foundry
// Type-safe build task planning for parallel builds

class BuildTask {
  task_id string @description("Unique identifier for this task (e.g., 'task-1')")
  name string @description("Human-readable task name")
  description string @description("Detailed description of what this task does")
  working_directory string @description("Directory where build commands execute (relative to project root)")
  build_commands string[] @description("Shell commands to execute for this task")
  dependencies string[] @description("Array of task_ids that must complete before this task starts. Empty array [] means task can run immediately in parallel.")
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

    **🚀 PARALLEL BUILDS SIGNIFICANTLY SPEED UP DEVELOPMENT - FAVOR PARALLEL WHEN POSSIBLE!**

    **CRITICAL RULES:**
    1. If scout_parallel_recommendation is false, return:
       - parallel_build_enabled: false
       - tasks: [] (empty array)
       - Set all estimates to 0

    2. If scout_parallel_recommendation is true:
       - parallel_build_enabled: true
       - **MAXIMIZE PARALLELIZATION** - split work into as many independent tasks as possible
       - Identify independent modules that can build in parallel
       - Define tasks with proper dependencies
       - **ENSURE NO CYCLIC DEPENDENCIES** (task A depends on B, B depends on A)
       - **Default to empty dependencies []** - only add dependencies when truly required
       - Tasks with empty dependencies [] run in parallel (THIS IS GOOD!)
       - Integration/config tasks depend on their inputs

    **⚡ PARALLELIZATION OPPORTUNITIES:**
    - Frontend + Backend: ALWAYS 2 separate parallel tasks (no dependencies between them)
    - Multiple services: Each service = separate parallel task
    - Separate apps in monorepo: Each app = parallel task (unless sharing build artifacts)
    - Independent libraries: Each lib = parallel task
    - Database migrations + app code: Usually independent (parallel)

    **Common Patterns:**
    - Full-stack (frontend + backend): 2 parallel tasks with dependencies: []
    - Microservices: N parallel service tasks + 1 deploy task
    - Monorepo with shared lib: 1 lib task → N app tasks depend on it
    - Frontend + Backend + Database: 3 parallel tasks (usually independent)

    **Example Dependency Graphs:**
    - Independent modules (MOST COMMON): dependencies: []
    - Integration tasks: dependencies: ["task-1", "task-2"]
    - Apps using shared lib: dependencies: ["shared-lib-task"]

    **⚠️ IMPORTANT: Don't over-constrain dependencies!**
    - Frontend does NOT depend on backend build (they're separate artifacts)
    - Backend does NOT depend on frontend build
    - Only add dependencies when module B needs module A's build output

    Calculate accurate time estimates:
    - total_estimated_sequential: sum of all task durations
    - total_estimated_parallel: length of critical path (longest dependency chain)
    - time_savings_percent: ((sequential - parallel) / sequential) * 100

    Return as structured BuildPlan object.
  "#
}
