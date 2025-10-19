# The Genesis of Context Foundry: Synthesizing Advanced Context Engineering with Anthropic's Agent Patterns

**How a presentation on context management and Anthropic's agent SDK principles combined to create a practical development workflow**

---

## Introduction

Context Foundry was born from a simple observation: AI coding agents are incredibly powerful, yet frustratingly inconsistent. They excel at prototypes but struggle with production code. They work well on greenfield projects but stumble on complex brownfield codebases. The promise of AI-assisted development felt just out of reach.

Two sources provided the breakthrough that made Context Foundry possible:

1. **Dexter Horthy's "Advanced Context Engineering for Coding Agents"** - A practitioner's field guide showing how a three-person team achieved production-quality results by obsessively managing context
2. **Anthropic's "Building Effective Agents" guide** - Engineering principles for reliable multi-agent systems with proper isolation and verification

Context Foundry is the synthesis of these approaches: Dexter's workflow structure combined with Anthropic's architectural patterns, automated into a tool that makes advanced context engineering accessible to everyone.

---

## Part 1: Dexter Horthy's Context Engineering Revolution

### The Core Problem

Dexter identified what many developers experience but few articulate clearly:

> "The most naive way to use a coding agent is to shout back and forth with it until you run out of context or you give up or you cry. Um, and you say, 'No, do this. No, stop. you're doing it wrong.'"

This cycle of frustration stems from a fundamental truth about LLMs:

> "LLMs are pure functions... the only thing that improves the quality of your outputs is the quality of what you put in, which is your context window."

### The Solution: Frequent Intentional Compaction

Dexter's breakthrough was recognizing that context management isn't a side concern—it's the entire game:

> "Building your entire development workflow around context management... our goal all the time is to keep context utilization under 40%."

The 40% rule isn't arbitrary. It ensures enough headroom for the agent to:
- Load necessary files
- Reason about changes
- Maintain conversation history
- Execute complex edits

Without this buffer, agents thrash—burning tokens on re-reading files and losing track of their objectives.

### The Three-Phase Workflow

Dexter's team adopted a structured approach:

> "We have three phases: research, plan and implement. The research is really like understand how the system works and all the files that matter and perhaps like where a problem is located."

**Research Phase:**
> "This is the output of our research prompt. It's got file names and line numbers so that the agent reading this research knows exactly where to look. It doesn't have to go search 100 files to figure out how things work."

**Planning Phase:**
> "Tell me every single change you're going to make. Not line by line, but like include the files and the snippets of what you're going to change and be very explicit about how we're going to test and verify at every step."

**Implementation Phase:**
> "If the plan is good, I'm never shouting at cloud anymore. And if I'm shouting at cloud, it's because the plan was bad. And the plan is always much shorter than the code changes."

### The Hierarchy of Impact

Dexter revealed a crucial insight about where to focus review effort:

> "A bad line of code is a bad line of code. And a bad part of a plan can be hundreds of bad lines of code. And a bad line of research, a misunderstanding of how the system works and how data flows and where things happen can be thousands of bad lines of code."

This hierarchy suggests reviewing research files and plans provides far more leverage than reviewing generated code line-by-line.

### Spec-First Development

Dexter's team was forced to adopt specification-driven development when faced with 20,000-line PRs:

> "We were forced to adopt spec first development because it was the only way for everyone to stay on the same page. And I actually learned to let go. I still read all the tests, but I no longer read every line of code because I read the specs and I know they're right."

This echoes Sean Grove's insight that Dexter highlighted:

> "The specs, the description of what we want from our software is the important thing... in the future where AI is writing more and more of our code, the specs... are the important thing."

### Real-World Validation

The approach wasn't just theoretical. Dexter demonstrated:

- **Brownfield Success**: "We did get it merged. The PR was so good the CTO did not know I was doing it as a bit and he had merged it by the time we were recording the episode."
- **Complex Problems**: "In 7 hours we shipped 35,000 lines of code... he estimated that was 1 to 2 weeks of work roughly."
- **Production Quality**: "I haven't opened a non-markdown file in an editor in almost two months."

---

## Part 2: Anthropic's Agent SDK Principles

While Dexter provided the workflow structure, Anthropic's engineering guide offered the architectural foundation for building reliable agent systems.

### The Multi-Agent Pattern

Anthropic emphasizes using specialized subagents with isolated context windows:

> "We recommend creating dedicated agents through subagents for specific, well-defined tasks. This separation offers multiple benefits:
> - **Focused context**: Each agent maintains only information relevant to its specific task
> - **Specialized prompts**: Agents can be optimized for particular operations without compromising the main workflow
> - **Parallel execution**: Independent agents can run concurrently
> - **Easier debugging**: Issues can be isolated to specific agent responsibilities"

This directly addresses Dexter's observation about inline compaction with subagents:

> "Sub agents... they're really about context control... the sub agent goes and finds where the file is, returns it to the parent agent. The parent agent can get right to work without having to have the context burden of all of that reading and searching."

### The Core Agentic Loop

Anthropic describes the fundamental pattern all agents should follow:

**Gather → Plan → Act → Verify**

Each phase has a specific purpose:
- **Gather**: Collect necessary information through tool calls
- **Plan**: Break complex tasks into smaller steps
- **Act**: Execute one step at a time
- **Verify**: Check results before proceeding

This maps directly to Dexter's Research → Plan → Implement workflow, with an added emphasis on verification at each stage.

### Context Management Strategies

Anthropic provides concrete guidance on maintaining manageable context:

> "Monitor context window usage and implement strategies to manage it:
> - Track token counts across conversations
> - Implement context window limits with graceful degradation
> - Use conversation summarization for long interactions
> - Archive completed work to separate storage"

The recommendation to maintain context headroom aligns perfectly with Dexter's 40% rule.

### Reliability Through Verification

Anthropic emphasizes that agents must verify their own work:

> "Don't assume tool calls succeed based on their parameters. Always verify both:
> - **Direct results**: Did the operation complete as intended?
> - **Side effects**: Did the change produce the expected system-wide effects?"

This principle ensures quality without requiring humans to review every line of generated code—exactly what Dexter's team achieved by focusing review on specs and plans.

### Continuous Improvement

Anthropic recommends learning from successful patterns:

> "Build reusable tools and processes to improve agent performance over time... As you identify successful patterns, extract them into reusable components."

This concept of pattern extraction and reuse would become central to Context Foundry's design.

---

## Part 3: The Synthesis - How Context Foundry Was Built

Context Foundry implements both Dexter's workflow structure and Anthropic's architectural patterns in an automated, accessible tool.

### The Three-Agent Architecture

**Scout Agent** = Dexter's Research Phase
- Gathers comprehensive understanding of requirements
- Maps out the problem space
- Outputs structured `RESEARCH.md` with findings

**Architect Agent** = Dexter's Planning Phase
- Creates detailed specifications (`SPEC.md`)
- Designs implementation approach (`PLAN.md`)
- Breaks work into tasks (`TASKS.md`)

**Builder Agent** = Dexter's Implementation Phase
- Executes tasks sequentially
- Follows the plan created by Architect
- Implements actual code files

Each agent uses Anthropic's recommended subagent pattern—isolated context windows, specialized prompts, and focused responsibilities.

### Automated Context Engineering (ACE)

Dexter's 40% rule is implemented in the `SmartCompactor` class:

```python
class SmartCompactor:
    def should_compact(self, usage_pct: float) -> bool:
        """Check if context needs compaction (>40% threshold)"""
        return usage_pct > 40.0
```

When context utilization exceeds 40%, ACE automatically:
1. Identifies completed work in conversation history
2. Summarizes it concisely
3. Replaces verbose history with compact summaries
4. Maintains trajectory and key decisions

This implements Dexter's principle of "intentional compaction":

> "Be very intentional with what you commit to the file system and the agents memory... we use that to onboard the next agent into whatever we were working on."

### The Gather → Plan → Act → Verify Loop

Each Context Foundry agent follows Anthropic's core loop:

**Scout (Gather):**
```python
def _run_scout(self):
    """Research phase: Understand requirements and constraints"""
    # Gather information
    response = self.client.call_claude(scout_prompt, ...)

    # Save research output
    research_file = self._save_phase_output("RESEARCH", response)

    return research_file
```

**Architect (Plan):**
```python
def _run_architect(self, research_file):
    """Planning phase: Create detailed specifications"""
    # Plan based on research
    response = self.client.call_claude(architect_prompt, ...)

    # Extract SPEC, PLAN, TASKS
    self._extract_architect_outputs(response)
```

**Builder (Act):**
```python
def _run_builder_with_tasks(self, tasks):
    """Implementation phase: Execute tasks sequentially"""
    for task in tasks:
        # Act on one task
        response = self.client.call_claude(builder_prompt, ...)

        # Verify result
        files_created = self._extract_and_save_code(response)
        if not files_created:
            logger.warning("No code files extracted")
```

### Human-in-the-Loop Verification

Following Anthropic's verification principles, Context Foundry includes critical checkpoints:

**After Scout:**
```python
def _review_research(self, research_file):
    """Human reviews research before proceeding"""
    print(f"📄 Research complete: {research_file}")
    if not self._get_user_approval("Proceed to planning?"):
        return False
```

**After Architect:**
```python
def _review_architect_outputs(self):
    """Human reviews SPEC/PLAN/TASKS before building"""
    print("📋 Review the files above...")
    print("💡 You can edit them directly before approving!")

    if not self._get_user_approval("Proceed to build?"):
        return False
```

This implements Dexter's insight about the hierarchy of impact—catching problems at the research or planning stage prevents thousands of bad lines of code.

### Pattern Library for Continuous Improvement

Anthropic's recommendation to "extract successful patterns into reusable components" is implemented through the Pattern Manager:

```python
class PatternManager:
    def extract_pattern(self, task_desc, spec, plan, tasks):
        """Learn from successful builds"""
        pattern = {
            "task_type": self._classify_task(task_desc),
            "specification": spec,
            "planning_approach": plan,
            "task_breakdown": tasks,
            "timestamp": datetime.now()
        }
        self.library.append(pattern)
```

When building similar projects, Context Foundry retrieves relevant patterns:

```python
def find_relevant_patterns(self, task_desc, top_k=3):
    """Find patterns similar to current task"""
    # Use semantic similarity to find matching patterns
    similar_patterns = self._semantic_search(task_desc, top_k)
    return similar_patterns
```

These patterns are injected into the Architect's prompt, allowing it to learn from previous successful builds—exactly as Anthropic recommends.

### Spec-First by Default

Context Foundry enforces Dexter's spec-first philosophy through its workflow:

1. **Scout produces research** (understanding the problem)
2. **Architect produces specs** (defining the solution)
3. **Human reviews and edits specs** (ensures correctness)
4. **Builder follows specs** (implementation is deterministic)

Users can edit `SPEC.md`, `PLAN.md`, and `TASKS.md` files before approving them, ensuring the "source code" (the specifications) is correct before any implementation begins.

### Addressing the Stanford Study Concerns

Dexter referenced the Stanford study showing AI-generated code leads to rework and struggles with complex/brownfield tasks. Context Foundry addresses this through:

**Reducing Rework:**
- Checkpoint reviews catch problems early
- Specs are shorter and easier to verify than code
- Tests are written alongside implementation

**Handling Complexity:**
- Scout phase maps complex systems before changes
- Architect breaks complex tasks into manageable steps
- Builder executes incrementally with verification

**Brownfield Support:**
- Scout analyzes existing codebases
- Research includes file locations and line numbers
- Pattern library learns from previous work in similar codebases

---

## Conclusion: A Workflow, Not Just a Tool

Dexter's closing insight captures why Context Foundry exists:

> "I kind of maybe think coding agents are going to get a little bit commoditized, but the team and the workflow transformation will be the hard part. Getting your team to embrace new ways of communicating and structuring how you work is going to be really, really hard."

Context Foundry doesn't just automate Dexter's workflow—it makes the workflow transformation accessible. By combining:

- **Dexter's practical wisdom** about context management, the 40% rule, and spec-first development
- **Anthropic's engineering principles** for multi-agent systems, verification, and continuous improvement

...we created a tool that embodies advanced context engineering without requiring users to become experts.

The result is a development workflow where:
- **Prompts don't need to be perfect** (the 80/20 rule applies)
- **Refinement happens through structured checkpoints** (not endless chat iterations)
- **Specifications are the source code** (implementation follows deterministically)
- **Context is managed automatically** (40% utilization maintained)
- **Quality improves over time** (pattern library learns from success)

As Dexter demonstrated by shipping 6 PRs in a single day without opening a code editor, and as Anthropic's principles suggest, the future of AI-assisted development isn't about replacing developers—it's about empowering them to work at a higher level of abstraction.

Context Foundry is our contribution to that future.

---

## References

1. **Dexter Horthy** - "Advanced Context Engineering for Coding Agents" presentation at AI Engineer conference
2. **Anthropic** - ["Building Effective Agents" engineering guide](https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/building_effective_agents/building_effective_agents.ipynb)
3. **Human Layer** - Dexter Horthy's company exploring workflow transformation for AI-assisted development
4. **12 Factor Agents** - Original manifesto on principles of reliable LLM applications (April 2022)

---

*Context Foundry is open source and available at: https://github.com/snedea/context-foundry*

*Generated: 2025-10-04*
