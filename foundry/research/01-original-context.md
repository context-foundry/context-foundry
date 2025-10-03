# Context Foundry: Original Research and Development

## The Anti-Vibe Philosophy
We're building the ANTI-VIBE system: a spec-first workflow that automates **research → planning → execution** with tight context control, tests, and checkpoints. This turns fuzzy requests into small, reviewable PRs—on rails.

## Core Innovation: Advanced Context Engineering

### The Problem We're Solving
1. **Context bloating** from endless conversational iterations degrades AI performance
2. **Lost specifications** mean prompts are discarded after code generation
3. **Impossible code review** occurs when developers face 20,000-line AI-generated PRs

### The Solution: Three-Phase Workflow
1. **Scout Phase**: Research the codebase, produce compact research artifact (max 5K tokens)
2. **Architect Phase**: Create reviewable spec/plan with tasks and success criteria
3. **Builder Phase**: Implement in small chunks with tests, auto-compaction, and human checkpoints

### Key Principles (from Dex/HumanLayer)
- Keep context under 40% utilization ALWAYS
- Specs are permanent, code is disposable
- Human review at maximum leverage points (planning phase)
- Continuous compaction prevents context bloat
- A bad line in the plan = thousands of bad lines of code

### The ACE Engine (Automated Context Engineering)
- **Dynamic context selection** (AST parsing + embeddings + knowledge graph)
- **Structured information landscapes** (XML-structured outputs)
- **Memory systems** (short-term, semantic, procedural, episodic)
- **Subagent isolation** for context control (200K token windows returning 1-2K summaries)

## Implementation Architecture

### Phase 1: Scout (Research)
- Explores codebase without making changes
- Follows execution paths
- Maps dependencies
- Outputs: RESEARCH.md artifact

### Phase 2: Architect (Planning)
- Generates multi-layered specifications
- Creates technical plans with alternatives
- Decomposes into testable tasks
- Outputs: SPEC.md, PLAN.md, TASKS.md

### Phase 3: Builder (Implementation)
- Executes tasks sequentially
- Maintains 40-60% context utilization
- Runs tests after each task
- Creates git checkpoints
- Outputs: Code + Tests + Documentation

## Real-World Validation
- Dex's BAML case study: 300K line Rust codebase, PR merged in 1 hour
- 35K LOC in 7 hours (vs. 3-5 day estimate)
- Boundary CEO: 35,000 lines of code in 7 hours
- AgentCoder: 96.3% pass@1 on HumanEval

## The Ralph Wiggum Strategy
Jeff Huntley's approach: Run the SAME prompt in a loop overnight with fresh context each time. Progress files persist, context resets, continuous forward progress.

## Original Transcript Highlights

### The Context Problem (00:00-02:00)
The fundamental issue with conversational AI coding: each iteration adds more context, degrading performance. Traditional chat-based coding leads to bloated context windows and lost specifications.

### The Solution: Assembly Line Approach (02:00-05:00)
- **Separate research from implementation** - scouts gather info, builders execute
- **Spec-first development** - plans are reviewed before any code is written
- **Automatic compaction** - continuous context optimization
- **Test-driven checkpoints** - validate each step before proceeding

### Advanced Context Engineering (05:00-08:00)
The ACE framework manages context through:
1. **Layered memory systems** - different types of memory for different purposes
2. **Dynamic context selection** - only load what's needed for current task
3. **Structured outputs** - XML/JSON for machine-parseable results
4. **Token budgets** - hard limits on context size per phase

### Real Implementation Patterns (08:00-11:00)
- **Scout agents** run with 200K token windows but return 1-2K summaries
- **Architect agents** create multi-layered specs (high-level → detailed)
- **Builder agents** work in isolation with checkpoints
- **Compactor agents** continuously optimize context

### The Future Vision (11:00-14:32)
Building toward fully autonomous coding workflows:
- Human review only at high-leverage planning phase
- Automatic PR generation with small, reviewable chunks
- Continuous integration of new patterns into knowledge base
- Self-improving system that learns from each project

## Key Quotes

> "A bad line in your plan is a thousand bad lines in your code." - Dex

> "The context window is not unlimited—treat it like a precious resource." - HumanLayer

> "Specs are permanent, code is disposable." - Anti-Vibe Philosophy

> "Run the same prompt in a loop overnight with fresh context each time." - Ralph Wiggum Strategy

## Critical Success Factors

1. **Context discipline** - Never exceed 40% utilization in any phase
2. **Artifact permanence** - Research and specs persist across sessions
3. **Human checkpoints** - Review at planning phase, not implementation
4. **Test-driven flow** - Tests validate each task completion
5. **Continuous compaction** - Automatic context optimization

## Next Steps for Implementation

1. Set up foundational structure (directory layout, git integration)
2. Create core agent definitions (Scout, Architect, Builder, Inspector, Compactor)
3. Build workflow orchestration system
4. Implement context monitoring and compaction
5. Add checkpoint and artifact management
6. Create example workflows and patterns
7. Test with real-world projects

## Sources & Attribution

- **[Dexter Horthy's HumanLayer Demo](https://youtu.be/IS_y40zY-hc?si=ZMg7I3FKILvI8Fff)** - "Anti-vibe coding" methodology and 35K LOC in 7 hours demonstration
- **[Anthropic's Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)** - Context management patterns and subagent orchestration techniques
