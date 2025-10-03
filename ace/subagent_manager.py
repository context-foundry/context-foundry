#!/usr/bin/env python3
"""
Subagent Manager for Context Foundry
Spawns isolated Claude instances for specific tasks with dedicated context windows.
Returns concise summaries to main agent to preserve context.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from anthropic import Anthropic


@dataclass
class SubagentTask:
    """Task definition for a subagent."""
    task_id: str
    task_type: str  # 'scout', 'architect', 'builder', 'explorer'
    description: str
    context: Dict
    max_tokens_response: int = 8000
    target_summary_tokens: int = 2000


@dataclass
class SubagentResult:
    """Result from a subagent execution."""
    task_id: str
    task_type: str
    full_response: str
    summary: str
    tokens_used: int
    summary_tokens: int
    metadata: Dict
    success: bool
    error: Optional[str] = None


class SubagentManager:
    """
    Manages isolated subagents for exploration and implementation.

    Each subagent:
    - Gets 200K token context window
    - Operates independently
    - Returns 1-2K token summary to main agent
    - Can run in parallel

    This allows the main agent to delegate deep exploration without consuming its context.
    """

    SUBAGENT_CONTEXT_WINDOW = 200000
    DEFAULT_SUMMARY_LENGTH = 2000
    MAX_PARALLEL_AGENTS = 5

    def __init__(self, session_id: str, log_dir: Optional[Path] = None):
        """Initialize subagent manager.

        Args:
            session_id: Session identifier
            log_dir: Directory for subagent logs
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.session_id = session_id

        self.log_dir = log_dir or Path(f"logs/subagents/{session_id}")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Track subagents
        self.active_subagents: Dict[str, SubagentResult] = {}
        self.completed_subagents: List[SubagentResult] = []

    def spawn_scout(
        self,
        research_topic: str,
        context: Dict,
        task_id: Optional[str] = None
    ) -> SubagentResult:
        """Spawn a scout subagent for research and exploration.

        Args:
            research_topic: What to research
            context: Additional context for the scout
            task_id: Optional task ID (generated if not provided)

        Returns:
            SubagentResult with research summary
        """
        task_id = task_id or f"scout_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        task = SubagentTask(
            task_id=task_id,
            task_type="scout",
            description=research_topic,
            context=context,
            max_tokens_response=8000,
            target_summary_tokens=1500
        )

        prompt = self._build_scout_prompt(research_topic, context)
        return self._execute_subagent(task, prompt)

    def spawn_architect(
        self,
        planning_task: str,
        research_context: str,
        task_id: Optional[str] = None
    ) -> SubagentResult:
        """Spawn an architect subagent for detailed planning.

        Args:
            planning_task: Planning task description
            research_context: Research from scout phase
            task_id: Optional task ID

        Returns:
            SubagentResult with planning summary
        """
        task_id = task_id or f"architect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        task = SubagentTask(
            task_id=task_id,
            task_type="architect",
            description=planning_task,
            context={"research": research_context},
            max_tokens_response=8000,
            target_summary_tokens=2000
        )

        prompt = self._build_architect_prompt(planning_task, research_context)
        return self._execute_subagent(task, prompt)

    def spawn_builder(
        self,
        implementation_task: str,
        spec: str,
        task_id: Optional[str] = None
    ) -> SubagentResult:
        """Spawn a builder subagent for implementation.

        Args:
            implementation_task: What to implement
            spec: Specification to implement
            task_id: Optional task ID

        Returns:
            SubagentResult with implementation summary
        """
        task_id = task_id or f"builder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        task = SubagentTask(
            task_id=task_id,
            task_type="builder",
            description=implementation_task,
            context={"spec": spec},
            max_tokens_response=8000,
            target_summary_tokens=1500
        )

        prompt = self._build_builder_prompt(implementation_task, spec)
        return self._execute_subagent(task, prompt)

    def spawn_explorer(
        self,
        exploration_task: str,
        focus_areas: List[str],
        task_id: Optional[str] = None
    ) -> SubagentResult:
        """Spawn an explorer subagent for open-ended investigation.

        Args:
            exploration_task: What to explore
            focus_areas: Areas to focus on
            task_id: Optional task ID

        Returns:
            SubagentResult with exploration findings
        """
        task_id = task_id or f"explorer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        task = SubagentTask(
            task_id=task_id,
            task_type="explorer",
            description=exploration_task,
            context={"focus_areas": focus_areas},
            max_tokens_response=8000,
            target_summary_tokens=2000
        )

        prompt = self._build_explorer_prompt(exploration_task, focus_areas)
        return self._execute_subagent(task, prompt)

    def spawn_parallel(
        self,
        tasks: List[Tuple[str, str, Dict]]
    ) -> List[SubagentResult]:
        """Spawn multiple subagents in parallel.

        Args:
            tasks: List of (task_type, description, context) tuples
                  task_type: 'scout', 'architect', 'builder', 'explorer'

        Returns:
            List of SubagentResult objects
        """
        print(f"🚀 Spawning {len(tasks)} parallel subagents...")

        results = []
        with ThreadPoolExecutor(max_workers=min(len(tasks), self.MAX_PARALLEL_AGENTS)) as executor:
            # Submit tasks
            future_to_task = {}
            for i, (task_type, description, context) in enumerate(tasks):
                task_id = f"{task_type}_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                if task_type == "scout":
                    future = executor.submit(self.spawn_scout, description, context, task_id)
                elif task_type == "architect":
                    future = executor.submit(self.spawn_architect, description, context.get("research", ""), task_id)
                elif task_type == "builder":
                    future = executor.submit(self.spawn_builder, description, context.get("spec", ""), task_id)
                elif task_type == "explorer":
                    future = executor.submit(self.spawn_explorer, description, context.get("focus_areas", []), task_id)
                else:
                    raise ValueError(f"Unknown task type: {task_type}")

                future_to_task[future] = (task_type, description)

            # Collect results
            for future in as_completed(future_to_task):
                task_type, description = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    print(f"   ✅ {task_type}: {description[:50]}...")
                except Exception as e:
                    print(f"   ❌ {task_type} failed: {e}")
                    # Create error result
                    results.append(SubagentResult(
                        task_id=f"failed_{task_type}",
                        task_type=task_type,
                        full_response="",
                        summary=f"Task failed: {str(e)}",
                        tokens_used=0,
                        summary_tokens=0,
                        metadata={},
                        success=False,
                        error=str(e)
                    ))

        print(f"✅ Parallel execution complete: {len([r for r in results if r.success])}/{len(results)} succeeded")
        return results

    def collect_summaries(
        self,
        results: Optional[List[SubagentResult]] = None
    ) -> str:
        """Collect and format summaries from subagents.

        Args:
            results: Optional list of results. If None, uses completed_subagents.

        Returns:
            Formatted summary text
        """
        results = results or self.completed_subagents

        if not results:
            return "No subagent results available."

        summary_lines = ["# Subagent Results Summary\n"]

        # Group by type
        by_type = {}
        for result in results:
            if result.task_type not in by_type:
                by_type[result.task_type] = []
            by_type[result.task_type].append(result)

        # Format by type
        for task_type in sorted(by_type.keys()):
            summary_lines.append(f"\n## {task_type.capitalize()} Results\n")

            for result in by_type[task_type]:
                status = "✅" if result.success else "❌"
                summary_lines.append(f"### {status} {result.task_id}")
                summary_lines.append(f"**Tokens**: {result.summary_tokens:,} (from {result.tokens_used:,} total)\n")
                summary_lines.append(result.summary)
                summary_lines.append("")

        # Total stats
        total_tokens = sum(r.tokens_used for r in results)
        total_summary_tokens = sum(r.summary_tokens for r in results)
        compression_ratio = (1 - total_summary_tokens / total_tokens) * 100 if total_tokens > 0 else 0

        summary_lines.append(f"\n---\n**Total Stats**:")
        summary_lines.append(f"- Subagents: {len(results)} ({len([r for r in results if r.success])} successful)")
        summary_lines.append(f"- Total tokens consumed: {total_tokens:,}")
        summary_lines.append(f"- Summary tokens: {total_summary_tokens:,}")
        summary_lines.append(f"- Compression ratio: {compression_ratio:.1f}%")

        return "\n".join(summary_lines)

    def _execute_subagent(self, task: SubagentTask, prompt: str) -> SubagentResult:
        """Execute a subagent task.

        Args:
            task: SubagentTask definition
            prompt: Prompt for the subagent

        Returns:
            SubagentResult
        """
        print(f"   🤖 Executing subagent: {task.task_id} ({task.task_type})")

        try:
            # Call Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=task.max_tokens_response,
                messages=[{"role": "user", "content": prompt}]
            )

            full_response = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Generate summary
            summary = self._generate_summary(full_response, task)

            # Estimate summary tokens (rough)
            summary_tokens = len(summary.split()) * 1.3  # Rough token estimate

            # Save full response to log
            self._save_subagent_log(task, full_response, summary, tokens_used)

            # Create result
            result = SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                full_response=full_response,
                summary=summary,
                tokens_used=tokens_used,
                summary_tokens=int(summary_tokens),
                metadata={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "timestamp": datetime.now().isoformat()
                },
                success=True
            )

            self.completed_subagents.append(result)
            print(f"   ✅ {task.task_id} complete: {tokens_used:,} tokens -> {int(summary_tokens):,} summary tokens")

            return result

        except Exception as e:
            print(f"   ❌ {task.task_id} failed: {e}")
            return SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                full_response="",
                summary=f"Error: {str(e)}",
                tokens_used=0,
                summary_tokens=0,
                metadata={"error": str(e)},
                success=False,
                error=str(e)
            )

    def _generate_summary(self, full_response: str, task: SubagentTask) -> str:
        """Generate concise summary of full response.

        Args:
            full_response: Full response from subagent
            task: Original task

        Returns:
            Concise summary
        """
        # Build summarization prompt
        summary_prompt = f"""Summarize this {task.task_type} subagent output in {task.target_summary_tokens} tokens or less.

ORIGINAL TASK: {task.description}

FULL OUTPUT:
{full_response}

Provide a concise summary that captures the essential information, key decisions, and critical findings. This summary will be used by the main agent, so preserve all important details while being extremely concise."""

        # Call Claude for summary
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=task.target_summary_tokens,
                messages=[{"role": "user", "content": summary_prompt}]
            )

            return response.content[0].text

        except Exception as e:
            # Fallback: truncate full response
            print(f"   ⚠️  Summary generation failed, using truncation: {e}")
            words = full_response.split()
            target_words = task.target_summary_tokens * 0.75  # Rough conversion
            return " ".join(words[:int(target_words)]) + "..."

    def _build_scout_prompt(self, research_topic: str, context: Dict) -> str:
        """Build prompt for scout subagent."""
        context_str = json.dumps(context, indent=2)

        return f"""You are a Scout subagent for Context Foundry. Your job is to research and explore.

RESEARCH TOPIC: {research_topic}

CONTEXT:
{context_str}

YOUR TASK:
1. Research best practices and approaches for this topic
2. Identify relevant technologies, libraries, and tools
3. Explore potential architectures and design patterns
4. Note potential challenges and considerations
5. Provide actionable recommendations

Be thorough but focused. Your findings will guide the implementation.

OUTPUT: Provide a comprehensive research report with your findings and recommendations."""

    def _build_architect_prompt(self, planning_task: str, research: str) -> str:
        """Build prompt for architect subagent."""
        return f"""You are an Architect subagent for Context Foundry. Your job is detailed planning.

PLANNING TASK: {planning_task}

RESEARCH FROM SCOUT:
{research}

YOUR TASK:
1. Create detailed technical specifications
2. Design the architecture and component structure
3. Break down into implementable tasks
4. Identify dependencies and sequencing
5. Define success criteria and testing approach

Be specific and actionable. Your plan will guide the builders.

OUTPUT: Provide a complete architectural plan with task breakdown."""

    def _build_builder_prompt(self, implementation_task: str, spec: str) -> str:
        """Build prompt for builder subagent."""
        return f"""You are a Builder subagent for Context Foundry. Your job is implementation.

IMPLEMENTATION TASK: {implementation_task}

SPECIFICATION:
{spec}

YOUR TASK:
1. Write tests FIRST (TDD approach)
2. Implement the functionality per spec
3. Ensure code quality and best practices
4. Include error handling and edge cases
5. Document the implementation

Provide complete, working code with file paths.

OUTPUT: Provide full implementation with tests and documentation."""

    def _build_explorer_prompt(self, exploration_task: str, focus_areas: List[str]) -> str:
        """Build prompt for explorer subagent."""
        focus_str = "\n".join(f"- {area}" for area in focus_areas)

        return f"""You are an Explorer subagent for Context Foundry. Your job is open-ended investigation.

EXPLORATION TASK: {exploration_task}

FOCUS AREAS:
{focus_str}

YOUR TASK:
1. Investigate the focus areas in depth
2. Discover patterns, insights, and opportunities
3. Identify potential issues or improvements
4. Explore alternative approaches
5. Provide recommendations

Be creative and thorough. Your insights will inform strategic decisions.

OUTPUT: Provide detailed exploration findings with actionable insights."""

    def _save_subagent_log(
        self,
        task: SubagentTask,
        full_response: str,
        summary: str,
        tokens_used: int
    ):
        """Save subagent execution log.

        Args:
            task: SubagentTask
            full_response: Full response
            summary: Summary
            tokens_used: Tokens used
        """
        log_file = self.log_dir / f"{task.task_id}.json"

        log_data = {
            "task": asdict(task),
            "full_response": full_response,
            "summary": summary,
            "tokens_used": tokens_used,
            "timestamp": datetime.now().isoformat()
        }

        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        # Also save markdown version
        md_file = self.log_dir / f"{task.task_id}.md"
        md_content = f"""# Subagent Log: {task.task_id}

**Type**: {task.task_type}
**Description**: {task.description}
**Tokens Used**: {tokens_used:,}
**Timestamp**: {datetime.now().isoformat()}

## Full Response

{full_response}

## Summary

{summary}
"""
        md_file.write_text(md_content)


def test_subagent_manager():
    """Test subagent manager."""
    print("🧪 Testing Subagent Manager")
    print("=" * 60)

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set - skipping live test")
        print("✅ Subagent Manager loaded successfully (not tested)")
        return

    # Create manager
    manager = SubagentManager("test_session")

    # Test single scout
    print("\n1. Testing single scout subagent...")
    scout_result = manager.spawn_scout(
        "Research best practices for Python async programming",
        {"language": "python", "framework": "asyncio"}
    )
    print(f"   Success: {scout_result.success}")
    print(f"   Summary preview: {scout_result.summary[:200]}...")

    # Test parallel execution
    print("\n2. Testing parallel subagents...")
    parallel_tasks = [
        ("scout", "Research database options for Python", {"language": "python"}),
        ("explorer", "Explore API design patterns", {"focus_areas": ["REST", "GraphQL"]})
    ]

    results = manager.spawn_parallel(parallel_tasks)
    print(f"   Results: {len(results)}")

    # Collect summaries
    print("\n3. Collecting summaries...")
    summaries = manager.collect_summaries(results)
    print(f"   Summary length: {len(summaries)} chars")

    print("\n✅ Subagent Manager test complete!")


if __name__ == "__main__":
    test_subagent_manager()
