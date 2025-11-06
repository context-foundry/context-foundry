PHASE 2: ARCHITECT (Design & Planning + Pattern Application)


**PHASE TRACKING (START) - MANDATORY FIRST ACTION:**
Update phase: "Architect" (2/7, "designing", "Creating system architecture")
(See PHASE TRACKING TEMPLATE)

0. **CHECK CONTEXT BUDGET (PROACTIVE WARNING):**
   ```bash
   python3 tools/check_context_budget.py --phase architect --check-before
   ```

   Monitor context usage before design phase. If CRITICAL, consider modular architecture.

1. Read Scout findings:
   - Open and carefully read .context-foundry/scout-report.md
   - Understand all requirements and constraints
   - Note all recommendations
   - **Note any flagged risks from pattern library**

2. Apply Architectural Patterns (Self-Learning System - GLOBAL PATTERNS):

   **Read GLOBAL pattern files** using MCP tools:
   - Use `read_global_patterns("common-issues")` to get architectural preventions from ALL past projects
   - These patterns contain architectural solutions that worked across all builds

   If patterns exist and match project type:
   - Apply proven architectural patterns from ANY past successful build
   - Include preventive measures for known issues (learned from all projects)
   - Add dependencies/configurations that prevent common failures

   Example: If Scout flagged CORS risk (learned from past browser app builds):
   - Include http-server in package.json dependencies
   - Add "dev" script to npm scripts
   - Document server requirement in architecture

**FLOWISE EXTENSION CHECK** (if Flowise flow detected):

   If CONFIGURATION shows flowise_flow: True, apply Flowise architecture patterns:

   **Flowise Architecture Mode Activated**
   - Flow Type: {flowise_flow_type}
   - Apply proven Flowise patterns for this flow type

   **CRITICAL JSON STRUCTURE REQUIREMENTS**:
   ⚠️ Flowise Agent Flows MUST use the exact node structure from real Flowise exports!

   **🚨🚨🚨 READ THIS FIRST - AUTHORITATIVE PATTERN REFERENCE 🚨🚨🚨**

   **MANDATORY FIRST STEP - Architect MUST execute these Read commands**:

   1. **Read the Authoritative Pattern Reference** (THE SINGLE SOURCE OF TRUTH):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/AGENT_PATTERN_REFERENCE.md
      ```
      This contains:
      - Complete node type definitions (agentAgentflow, conditionAgentAgentflow)
      - All input parameters with descriptions and examples
      - Agent persona patterns and configuration guidelines
      - Edge structure and connection patterns
      - Critical design patterns (intent detection, agent specialization, knowledge integration)
      - Complete implementation checklist
      - Common pitfalls and how to avoid them

   2. **Read FAILURE_PATTERNS.md** (CRITICAL - Learn from past failures):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md
      ```
      **MUST READ THE FULL FILE** to avoid repeating past mistakes:
      - Pattern #1: Meta-description instead of complete flow
      - Pattern #2: Missing agent nodes
      - Pattern #3: Separate config files anti-pattern (+ parallel build splitting variant)
      - Pattern #4: Disconnected agent nodes (scenario count ≠ agent count)
      - Pattern #5: Phantom tool and knowledge references (invented names that don't exist in Flowise)
      - Pattern #6: Incorrect tool JSON structure (using wrong field names causes crashes)

      Each pattern includes: Symptom, Root Cause, Impact, Fix, and Prevention checklist.
      The prevention checklists tell you EXACTLY what to check in your architecture design.

   3. **Read FLOWISE-STRUCTURE-AUTHORITY.md** (Validation checklist):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/prompts/FLOWISE-STRUCTURE-AUTHORITY.md
      ```
      Detailed structural issues and validation checklist

   🚨🚨🚨 **MANDATORY REQUIREMENT: Standard Tools for ALL Flowise Agents** 🚨🚨🚨

   **ARCHITECT MUST EXPLICITLY SPECIFY IN ARCHITECTURE.MD:**
   Every agent node MUST include these 2 standard tools with EXACT structure from Flowise UI:

   1. **currentDateTime**: Provides current date and time for temporal context evaluation
      - Auto-included in AGENT-NODE-TEMPLATE.json
      - NO configuration needed

   2. **searXNG**: Federated meta-search for real-time web information
      - ⚠️ CRITICAL: Capital X, capital NG → "searXNG" (NOT "searxng-search")
      - ⚠️ CRITICAL: Field name "apiBase" (NOT "baseUrl")
      - ⚠️ CRITICAL: Include all required fields: toolName, toolDescription, format, categories, engines, etc.
      - See AGENT-NODE-TEMPLATE.json lines 341-367 for exact structure

   **WHY THIS MATTERS**:
   - These are REAL working tools (not phantom references - see FAILURE_PATTERNS.md Pattern #5)
   - Incorrect structure WILL crash Flowise (see FAILURE_PATTERNS.md Pattern #6)
   - Auto-included in template to prevent manual errors
   - Tested and validated in production Flowise instances

   **ARCHITECT ACTION REQUIRED**:
   In architecture.md, add section:
   ```
   ## Standard Agent Tools
   All agents will include currentDateTime and searXNG tools using the exact structure
   from /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json
   ```

   **Template Files**:
   - ✅ AGENT-NODE-TEMPLATE.json (Read by Builder at line 1073)
   - 📖 START-NODE-TEMPLATE.json (Structure documented in AGENT_PATTERN_REFERENCE.md)

   **Canonical Example**:
   extensions/flowise/templates/Simple Agent Agents.json

   **🚨 MOST IMPORTANT REQUIREMENTS FROM AUTHORITY DOCUMENT**:

   ❌ DO NOT CREATE:
   - ❌ Start nodes without formTitle, formDescription, formInputTypes parameters
   - ❌ outputAnchors IDs with extra suffixes (e.g., "-Start", "-Agent")
   - ❌ agentTools as empty string when tools are configured
   - ❌ agentMessages in inputs as an array (must be empty string "")
   - ❌ Truncated placeholder text in Knowledge fields
   - ❌ Separate `chatOpenAI` or `windowMemory` nodes

   ✅ MUST CREATE:
   - ✅ Start nodes with COMPLETE form input parameters (formTitle, formDescription, formInputTypes)
   - ✅ outputAnchors ID format: `{nodeId}-output-{nodeName}` (NO extra suffixes)
   - ✅ agentTools with agentSelectedToolConfig nested object when tools used
   - ✅ agentMessages as empty string "" in inputs
   - ✅ FULL placeholder text: "...this is useful for the AI to know when and how to search for correct information"
   - ✅ Self-contained `agentAgentflow` nodes with built-in model/memory

   Key Requirements:
   - ✅ Use `type: "agentFlow"` (NOT "customNode")
   - ✅ Use `name: "agentAgentflow"` for agent nodes
   - ✅ Use `category: "Agent Flows"` for agents
   - ✅ Include visual properties: `color`, `hideInput`, `version`
   - ✅ Full input parameter IDs: "nodeId-input-paramName-type"
   - ✅ Full edge handles: "nodeId-output-nodeName-NodeType"
   - ✅ Edge type: "buttonedge" (Flowise standard)
   - ✅ asyncOptions for model selection with `loadMethod: "listModels"`
   - ✅ Built-in memory configuration within agent

   **Example Templates** (for manual reference/debugging, not automatically read):
   /Users/name/homelab/context-foundry/extensions/flowise/templates/
   (15 real Flowise exports for comparison and validation)

   **🎯 PRODUCTION-READY PATTERN TEMPLATES (NEW - USE THESE FIRST):**

   **MANDATORY FIRST STEP - Read Pattern Catalog**:
   ```
   Read /Users/name/homelab/context-foundry/extensions/flowise/templates/afv2-patterns/README.md
   ```

   This directory contains 9 **validated, production-ready** AFv2 pattern templates:

   | Pattern | Use When | Template File |
   |---------|----------|---------------|
   | **Chaining** | Sequential pipeline with artifact handoffs | `01-chaining.json` |
   | **Parallel** | Multi-source research/analysis (concurrent) | `02-parallel.json` |
   | **Routing** | Intent classification to domain agents | `03-routing.json` |
   | **Iteration** | Quality-driven refinement loop | `04-iteration.json` |
   | **Looping** | Test-driven validation retry | `05-looping.json` |
   | **Hierarchy** | Supervisor → Worker → Reviewer orchestration | `06-hierarchy.json` |
   | **Batch Processing** | Process arrays/lists of items | `07-batch-processing.json` |
   | **Conditional Retry** | Score-based validation with retry | `08-conditional-retry.json` |
   | **API Integration** | External HTTP API calls with error handling | `09-api-integration.json` |

   **Pattern Selection Guidance**:
   - **Chaining**: Linear workflows (e.g., OCR → Extract → Transform → Format)
   - **Parallel**: Need multiple sources (e.g., web + KB + analysis)
   - **Routing**: Support tickets, multi-domain chatbots
   - **Iteration**: Improve artifact quality until target score reached
   - **Looping**: Generate → Test → Fix cycle (code, policy compliance)
   - **Hierarchy**: Task delegation to specialist roles
   - **Batch Processing**: Process multiple items in arrays (e.g., sentiment analysis on 10 reviews)
   - **Conditional Retry**: Quality validation with automatic retry and improvement
   - **API Integration**: External API calls with smart retry (5xx) vs fail (4xx) logic

   **Architect Action Required**:
   1. Read afv2-patterns/README.md to understand all 9 patterns
   2. Select the pattern that best matches the workflow type from Scout report
   3. Reference the selected pattern JSON as structural baseline in architecture.md
   4. Document pattern choice and customizations needed

   **Why Use These Templates**:
   - ✅ All templates pass validate_workflow.py (100% pass rate)
   - ✅ FLOWISE-STRUCTURE-AUTHORITY compliant
   - ✅ Pattern #1-13 compliant (no known failure patterns)
   - ✅ Self-contained agents (inline model/memory config)
   - ✅ Fully documented (sticky notes with ALL CAPS prefixes)
   - ✅ Production-tested structure

   **Example Architecture Documentation**:
   ```markdown
   ## Selected Pattern Template
   Pattern: Chaining (01-chaining.json)
   Rationale: User needs sequential document processing (OCR → Extract → Format)

   Customizations Required:
   - Agent 1: OCR extraction instead of generic Chain1
   - Agent 2: Data extraction (keep HIL gate before this step)
   - Agent 3: Format output as JSON
   ```

   Architecture Requirements:
   - Node-level error handling (try/catch, fallbacks)
   - Retry logic for LLM/API calls (exponential backoff)
   - Memory management (size limits, pruning strategy)
   - Tool integration validation (input/output schemas)
   - Prompt engineering (clear, specific, tested)
   - Testing strategy (unit, integration, E2E, load)
   - Monitoring & observability (logging, metrics)
   - Environment configuration (API keys, model settings)

   See Flowise extension patterns for flow-type-specific architectures.

3. Create Architect agent:
   Type: /agents
   Description: "Expert software architect who creates detailed technical specifications, system designs, and implementation plans. I design scalable architectures, define module boundaries, specify APIs, plan testing strategies, and create comprehensive technical documentation that builders can follow precisely. I also apply proven patterns from past successful builds and include preventive measures for known issues."

4. Activate Architect and design:

   **IF CONFIGURATION shows flowise_flow: True (FLOWISE-ONLY MODE):**

   🚨 **FLOWISE-ONLY ARCHITECTURE** 🚨

   **DO NOT design:**
   ❌ Full-stack application architecture
   ❌ React component hierarchies or UI/UX
   ❌ REST/GraphQL API endpoints
   ❌ Database schemas or data models
   ❌ Frontend/backend separation
   ❌ Traditional web app file structures

   **ONLY design:**
   ✅ Flowise JSON workflow structure (nodes + edges arrays)
   ✅ Agent node specifications (personas, tools, memory)
   ✅ Condition routing logic (scenarios → agent mapping)
   ✅ Tool configurations (currentDateTime, searXNG, custom)
   ✅ Memory configuration (built-in agent memory)
   ✅ Prompt templates for each agent
   ✅ Edge connection mappings (source → target → scenarios)

   Based on Scout's Flowise research, create:
   - Flow architecture diagram (text/ASCII showing agent connections via router)
   - Agent specifications table (name, persona, tools, memory strategy)
   - Node structure plan (detailed JSON node planning)
   - Edge definitions (source node ID → target node ID → scenario conditions)
   - Prompt templates for each agent (system prompts)
   - Testing plan (JSON validation, Flowise import testing)
   - File structure (SINGLE workflow.json + README.md + INTEGRATION_GUIDE.md)

   **ELSE (STANDARD APPLICATION):**

   Based on Scout's findings and pattern library, create:
   - Complete system architecture diagram (in text/ASCII)
   - Detailed file and directory structure
   - Module breakdown with responsibilities
   - API/interface designs (if applicable)
   - Data models and schemas
   - **Preventive measures for flagged risks**
   - Step-by-step implementation plan
   - **Comprehensive test plan:**
     * What tests are needed
     * How to run tests
     * Test success criteria
     * Edge cases to test
     * **Integration tests if patterns indicate need**
     * **E2E tests with real browser for SPAs (MANDATORY)**

   **CRITICAL: API CORS Architecture (if Scout flagged CORS issue):**
   - Design backend proxy server architecture:
     * Add Node.js/Express backend for API proxy
     * Store API keys in backend/.env (NOT frontend)
     * Frontend calls backend, backend calls external API
     * Backend adds CORS headers allowing frontend access
   - Document architecture in architecture.md
   - Pattern ID: cors-external-api-backend-proxy

   **CRITICAL: React State Architecture (if using React):**
   - Define state management patterns:
     * When to use useEffect vs useCallback vs useMemo
     * Initialization patterns (mount-only effects with empty deps [])
     * Timestamp/counter patterns for triggering updates
   - **Separate high-frequency from low-frequency state:**
     * Data state (API data, user selections) → Zustand/Redux
     * Display state (animation frames, scroll positions) → refs/Map
     * NEVER update state management store > 10 times/second
   - Document in architecture.md
   - Pattern IDs: react-useeffect-infinite-loop, react-animation-state-separation

5. Save Architecture:
   Create file: .context-foundry/architecture.md
   Include:
   - System architecture overview
   - Complete file structure
   - Module specifications
   - **Applied patterns and preventive measures**
   - Implementation steps (ordered)
   - Testing requirements and procedures
   - Success criteria

6. **Update Phase Status (COMPLETE):**
   Update phase: "Architect" (2/7, "completed", "Architecture design complete")
   Add to phases_completed: ["Scout", "Architect"]

✅ **Architect phase complete.**


6. **BACK PRESSURE: Architecture Soundness Validation (Optional but Recommended)**

   Validate Architect's design is complete and consistent:
   ```bash
   python3 tools/back_pressure/validate_architecture.py .context-foundry/architecture.md
   ```

   **If validation available and FAILS**:
   - Log issues to .context-foundry/architecture-validation-errors.json
   - Review issues and either:
     * Re-run Architect with fixes, OR
     * Note warnings but continue (don't block on minor issues)
   - Maximum 1 validation retry

   **If validation PASSES or unavailable**:
   - Log: "✅ Architecture validated" or "⚠️  Validation skipped"
   - Continue to Phase 2.5 (Parallel Build Planning)

   **Note**: Architecture validation is advisory - minor issues won't block the build.

7. **Update Phase Status (COMPLETE):**
⚡ **NEXT: Parallel Build Planning (MANDATORY) - Do NOT skip**

