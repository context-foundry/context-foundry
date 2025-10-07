#!/usr/bin/env python3
"""
Scout Subagent - Executes focused research tasks in parallel.

Each subagent:
- Has its own context window
- Explores a specific aspect independently
- Uses interleaved thinking after tool results
- Returns compressed findings to Lead Orchestrator

Based on Anthropic's multi-agent research system architecture.
"""

import os
from typing import Dict, Any, Optional
from anthropic import Anthropic

from ..orchestrator.models import SubagentTask, SubagentResult


class ScoutSubagent:
    """
    Individual Scout subagent that researches a specific topic.

    Based on Anthropic's pattern:
    - Independent context window
    - Interleaved thinking for evaluation
    - Compress findings before returning
    """

    SUBAGENT_PROMPT = """You are a Scout subagent for Context Foundry. Your objective is focused research.

TASK:
{objective}

OUTPUT FORMAT:
{output_format}

RECOMMENDED SOURCES:
{sources}

TASK BOUNDARIES:
{boundaries}

INSTRUCTIONS:
1. Research best practices and patterns for this specific topic
2. Use your knowledge and reasoning to gather comprehensive information
3. Focus on actionable insights and recommendations
4. Stay within your task boundaries - don't duplicate work from other subagents
5. Be thorough but concise

Important: Your findings will be used by the Architect to make implementation decisions.
Provide comprehensive research with specific recommendations.

Begin your research now and provide a detailed report."""

    def __init__(self, client: Optional[Anthropic], task: SubagentTask):
        """Initialize Scout subagent.

        Args:
            client: Anthropic client instance
            task: SubagentTask to execute
        """
        if client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            client = Anthropic(api_key=api_key)

        self.client = client
        self.task = task
        self.model = os.getenv("SCOUT_MODEL", "claude-sonnet-4-20250514")

    def execute(self) -> SubagentResult:
        """
        Execute the research task with interleaved thinking.

        Returns:
            SubagentResult with compressed findings
        """

        print(f"   🔍 {self.task.id}: Starting research...")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                thinking={
                    "type": "enabled",
                    "budget_tokens": 3000
                },
                messages=[{
                    "role": "user",
                    "content": self.SUBAGENT_PROMPT.format(
                        objective=self.task.objective,
                        output_format=self.task.output_format,
                        sources=", ".join(self.task.sources) if self.task.sources else "General best practices",
                        boundaries=self.task.boundaries or "Focus on your specific objective only"
                    )
                }]
            )

            # Extract findings
            findings = ""
            for block in response.content:
                if block.type == "text":
                    findings += block.text

            # Calculate token usage
            token_usage = response.usage.input_tokens + response.usage.output_tokens

            print(f"   ✅ {self.task.id}: Research complete ({token_usage:,} tokens)")

            return SubagentResult(
                task_id=self.task.id,
                task_type=self.task.type,
                success=True,
                findings=findings,
                token_usage=token_usage,
                metadata={
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens
                }
            )

        except Exception as e:
            print(f"   ❌ {self.task.id} failed: {e}")
            return SubagentResult(
                task_id=self.task.id,
                task_type=self.task.type,
                success=False,
                error=str(e),
                metadata={'exception': str(e)}
            )
