Context Foundry MCP Code Execution Roadmap

1. Progressive Tool Discovery
   - Treat each MCP server as a filesystem subtree (e.g., mcp_servers/<server>/<tool>.py).
   - Provide `search_tools` helper with adjustable detail levels so agents can locate relevant tools without loading every schema.
   - Update onboarding docs to teach agents how to explore these folders instead of relying on prompt-injected tool lists.

2. Code-First Tool Orchestration
   - Generate lightweight client stubs (Python/TypeScript) that wrap `call_mcp_tool` per server.
   - Extend the existing execution sandbox so agents author scripts that import these stubs, keeping intermediate data out of the model context.
   - Ensure scripts can run inside the daemon’s locked working directory alongside other phases.

3. Data Filtering & Privacy Guards
   - Encourage agents to summarize or slice large MCP responses in code before logging.
   - Add optional tokenization in the MCP client so sensitive fields are masked unless explicitly requested.
   - Document best practices for logging (e.g., head/tail previews, aggregate metrics).

4. Stateful Skills Library
   - Reserve a `skills/` directory where the daemon stores agent-authored utilities, each with a `SKILL.md` describing inputs/outputs.
   - Auto-discover and surface these skills when similar tasks arrive (e.g., via search or tagging).
   - Consider versioning or promotion workflows so proven scripts become shared assets.

5. Control-Flow Efficiency Patterns
   - Provide examples showing loops, retries, and branching done in code instead of repeated MCP calls (e.g., Slack polling, batch updates).
   - Add linting/hints that nudge agents toward code execution for repetitive tool sequences.
   - Track token savings/latency improvements to justify continued investment.

6. Developer Experience & Infrastructure
   - Scaffold per-project “MCP workspace” folders during initialization (tool tree, stubs, skills).
   - Integrate with the working-directory lock system so MCP scripts respect concurrency rules.
   - Evaluate sandbox hardening (resource limits, monitoring) required for broader code execution.
