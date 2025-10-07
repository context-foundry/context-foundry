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

    def __init__(self, ai_client, task: SubagentTask):
        """Initialize Scout subagent.

        Args:
            ai_client: AIClient instance (provider-agnostic)
            task: SubagentTask to execute
        """
        self.ai_client = ai_client
        self.task = task

        # Use scout provider/model from AIClient configuration
        self.provider_name = ai_client.config.scout.provider
        self.model_name = ai_client.config.scout.model
        self.provider = ai_client.registry.get(self.provider_name)

    def execute(self) -> SubagentResult:
        """
        Execute the research task with interleaved thinking.

        Returns:
            SubagentResult with compressed findings
        """

        print(f"   🔍 {self.task.id}: Starting research...")

        try:
            # Build kwargs conditionally to avoid passing unsupported parameters
            call_kwargs = {
                'model': self.model_name,
                'max_tokens': 8000,
                'messages': [{
                    "role": "user",
                    "content": self.SUBAGENT_PROMPT.format(
                        objective=self.task.objective,
                        output_format=self.task.output_format,
                        sources=", ".join(self.task.sources) if self.task.sources else "General best practices",
                        boundaries=self.task.boundaries or "Focus on your specific objective only"
                    )
                }]
            }

            # Only add thinking parameter for Anthropic
            if self.provider_name == 'anthropic':
                call_kwargs['thinking'] = {
                    "type": "enabled",
                    "budget_tokens": 3000
                }

            response = self.provider.call_api(**call_kwargs)

            # Extract findings (ProviderResponse.content is already a string)
            findings = response.content

            # Calculate token usage
            token_usage = response.input_tokens + response.output_tokens

            print(f"   ✅ {self.task.id}: Research complete ({token_usage:,} tokens)")

            return SubagentResult(
                task_id=self.task.id,
                task_type=self.task.type,
                success=True,
                findings=findings,
                token_usage=token_usage,
                metadata={
                    'input_tokens': response.input_tokens,
                    'output_tokens': response.output_tokens,
                    'provider': self.provider_name,
                    'model': self.model_name
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
