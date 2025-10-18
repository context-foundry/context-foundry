#!/usr/bin/env python3
"""
Lead Orchestrator Agent - Plans and coordinates all subagents.

Based on Anthropic's multi-agent research system architecture.
Uses extended thinking for planning and coordination.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .models import SubagentTask, WorkflowPlan


class LeadOrchestrator:
    """
    Lead agent that plans and coordinates all subagents.

    Uses extended thinking to:
    - Assess query complexity
    - Decompose into parallelizable tasks
    - Coordinate subagents
    - Synthesize results
    - Adapt based on findings
    """

    PLANNING_PROMPT = """You are the Lead Orchestrator for Context Foundry, an AI development system.

Your role: Analyze the user's request and create a comprehensive workflow plan.

USER REQUEST:
{user_request}

PROJECT CONTEXT:
{project_context}

PLANNING INSTRUCTIONS:

1. ASSESS COMPLEXITY
   - Simple: Basic CRUD app, single service (1-3 subagents)
   - Medium: Multiple services, auth, database (4-7 subagents)
   - Complex: Microservices, real-time, complex logic (8+ subagents)

2. DECOMPOSE RESEARCH (Scout Phase)
   Create 3-5 parallel research tasks:
   - Each explores a different aspect
   - Clear boundaries (no overlap)
   - Specific output format
   - Independent from each other

   Example for "Build e-commerce API":
   - Scout 1: Research product catalog patterns
   - Scout 2: Research payment integration best practices
   - Scout 3: Research order management systems
   - Scout 4: Research authentication for e-commerce
   - Scout 5: Research deployment strategies for Node.js APIs

3. PLAN ARCHITECTURE STRATEGY
   How should Architect approach this?
   - What patterns to prioritize
   - What trade-offs to consider
   - How to structure the codebase

4. DECOMPOSE IMPLEMENTATION (Builder Phase)
   Create 5-10 parallel build tasks:
   - Each is independent (can run simultaneously)
   - Clear interfaces between modules
   - Specific deliverables
   - Test requirements

   Example for "Build e-commerce API":
   - Builder 1: User authentication module + tests
   - Builder 2: Product catalog API + tests
   - Builder 3: Shopping cart logic + tests
   - Builder 4: Order processing + tests
   - Builder 5: Payment integration + tests
   - Builder 6: Database schema + migrations
   - Builder 7: API documentation
   - Builder 8: Deployment configuration

5. PLAN VALIDATION
   Create 3-5 parallel validation tasks:
   - Smoke tests (does it start?)
   - Contract tests (does API match spec?)
   - Security checks (basic vulnerabilities?)
   - Performance checks (acceptable response times?)

6. PARALLELIZATION STRATEGY
   - Which tasks can run in parallel?
   - What dependencies exist?
   - What's the critical path?

Use extended thinking to reason through your plan.
Output your plan as structured JSON with this exact schema:

{{
  "complexity_assessment": "Simple|Medium|Complex - brief explanation",
  "estimated_duration": "time estimate",
  "scout_tasks": [
    {{
      "id": "scout_1",
      "type": "scout",
      "objective": "research objective",
      "output_format": "what format to return",
      "tools": ["web_search", "read_documentation"],
      "sources": ["list of recommended sources"],
      "boundaries": "what NOT to research",
      "priority": 1
    }}
  ],
  "architect_strategy": "how architect should approach planning",
  "builder_tasks": [
    {{
      "id": "builder_1",
      "type": "builder",
      "objective": "what to build",
      "output_format": "code files with tests",
      "tools": ["write_file", "read_file"],
      "sources": [],
      "boundaries": "scope limits",
      "priority": 1,
      "dependencies": []
    }}
  ],
  "validation_tasks": [
    {{
      "id": "validator_1",
      "type": "validator",
      "objective": "what to validate",
      "output_format": "pass/fail with details",
      "tools": ["run_tests", "check_syntax"],
      "sources": [],
      "boundaries": "validation scope",
      "priority": 1
    }}
  ],
  "parallelization_strategy": "explanation of parallel execution strategy"
}}"""

    def __init__(self, ai_client):
        """Initialize Lead Orchestrator.

        Args:
            ai_client: AIClient instance (provider-agnostic)
        """
        self.ai_client = ai_client

        # Use architect provider/model for orchestration (strategic planning)
        self.provider_name = ai_client.config.architect.provider
        self.model_name = ai_client.config.architect.model
        self.provider = ai_client.registry.get(self.provider_name)

    def plan_workflow(self, user_request: str, project_context: Optional[Dict] = None) -> WorkflowPlan:
        """
        Use extended thinking to create a comprehensive workflow plan.

        Args:
            user_request: User's request/description
            project_context: Optional project context

        Returns:
            WorkflowPlan with all subagent tasks defined
        """

        print("\n" + "="*80)
        print("🧠 LEAD ORCHESTRATOR - PLANNING WORKFLOW")
        print("="*80)
        print(f"\nRequest: {user_request}")
        print("\nUsing extended thinking to analyze and plan...")

        # Prepare context
        context_str = json.dumps(project_context or {}, indent=2)

        # Call AI provider with extended thinking (if supported)
        # Build kwargs conditionally to avoid passing unsupported parameters
        call_kwargs = {
            'model': self.model_name,
            'max_tokens': 16000,
            'messages': [{
                "role": "user",
                "content": self.PLANNING_PROMPT.format(
                    user_request=user_request,
                    project_context=context_str
                )
            }]
        }

        # Only add thinking parameter for Anthropic (extended thinking feature)
        if self.provider_name == 'anthropic':
            call_kwargs['thinking'] = {
                "type": "enabled",
                "budget_tokens": 10000
            }

        response = self.provider.call_api(**call_kwargs)

        # Extract plan content
        # ProviderResponse.content is a string (already unified by provider)
        plan_content = response.content

        print(f"\n📋 Planning Complete")
        print(f"   Tokens: {response.input_tokens} in / {response.output_tokens} out")

        # Parse the plan
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in plan_content:
                json_start = plan_content.find("```json") + 7
                json_end = plan_content.find("```", json_start)
                plan_content = plan_content[json_start:json_end].strip()
            elif "```" in plan_content:
                json_start = plan_content.find("```") + 3
                json_end = plan_content.find("```", json_start)
                plan_content = plan_content[json_start:json_end].strip()

            plan_json = json.loads(plan_content)
            workflow_plan = self._parse_workflow_plan(plan_json)

            self._print_workflow_summary(workflow_plan)

            return workflow_plan

        except json.JSONDecodeError as e:
            print(f"\n❌ Failed to parse plan JSON: {e}")
            print(f"Raw response:\n{plan_content[:500]}...")
            raise ValueError("Lead Orchestrator failed to produce valid JSON plan")

    def _parse_workflow_plan(self, plan_json: Dict) -> WorkflowPlan:
        """Parse JSON plan into WorkflowPlan dataclass."""

        scout_tasks = [
            SubagentTask(**task) for task in plan_json.get('scout_tasks', [])
        ]

        builder_tasks = [
            SubagentTask(**task) for task in plan_json.get('builder_tasks', [])
        ]

        validation_tasks = [
            SubagentTask(**task) for task in plan_json.get('validation_tasks', [])
        ]

        return WorkflowPlan(
            complexity_assessment=plan_json.get('complexity_assessment', 'Unknown'),
            scout_tasks=scout_tasks,
            architect_strategy=plan_json.get('architect_strategy', ''),
            builder_tasks=builder_tasks,
            validation_tasks=validation_tasks,
            estimated_duration=plan_json.get('estimated_duration', 'Unknown'),
            parallelization_strategy=plan_json.get('parallelization_strategy', '')
        )

    def _print_workflow_summary(self, plan: WorkflowPlan):
        """Print human-readable workflow summary."""

        print(f"\n📊 Complexity: {plan.complexity_assessment}")
        print(f"⏱️  Estimated Duration: {plan.estimated_duration}")

        print(f"\n🔍 Scout Phase: {len(plan.scout_tasks)} parallel research tasks")
        for task in plan.scout_tasks:
            print(f"   └─ {task.id}: {task.objective[:60]}...")

        print(f"\n🔨 Builder Phase: {len(plan.builder_tasks)} parallel build tasks")
        for task in plan.builder_tasks:
            print(f"   └─ {task.id}: {task.objective[:60]}...")

        print(f"\n✅ Validation Phase: {len(plan.validation_tasks)} parallel checks")
        for task in plan.validation_tasks:
            print(f"   └─ {task.id}: {task.objective[:60]}...")

        print(f"\n🔀 Parallelization Strategy:")
        print(f"   {plan.parallelization_strategy}")

    def compress_findings(self, findings: list[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compress findings from multiple subagents.

        Key insight from Anthropic: Subagents facilitate compression by
        operating in parallel with their own context windows, then condensing
        the most important tokens for the lead agent.

        Args:
            findings: List of findings from subagents

        Returns:
            Compressed summary dict
        """

        print("\n📦 Compressing subagent findings...")

        # Concatenate all findings
        all_findings = "\n\n".join([
            f"### {finding.get('task_id', 'unknown')}\n{finding.get('findings', finding.get('error', 'No findings'))}"
            for finding in findings
        ])

        # Use LLM to compress
        compression_prompt = f"""Compress these research findings into a concise summary.

FINDINGS FROM {len(findings)} SUBAGENTS:
{all_findings}

Create a structured summary that:
1. Highlights key patterns and best practices
2. Identifies common themes across findings
3. Notes any conflicts or trade-offs
4. Provides actionable recommendations
5. Stays under 2000 tokens

Output the compressed summary now."""

        # Build kwargs (no thinking needed for compression - simpler task)
        response = self.provider.call_api(
            model=self.model_name,
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": compression_prompt
            }]
        )

        compressed_summary = response.content

        # Calculate compression stats
        original_tokens = len(all_findings.split())
        compressed_tokens = len(compressed_summary.split())
        compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 0

        print(f"   Compressed {original_tokens} tokens → {compressed_tokens} tokens")
        print(f"   Compression ratio: {compression_ratio:.1%}")

        return {
            'compressed_summary': compressed_summary,
            'raw_findings': findings,
            'compression_ratio': compression_ratio,
            'original_tokens': original_tokens,
            'compressed_tokens': compressed_tokens
        }


def test_lead_orchestrator():
    """Test the Lead Orchestrator."""
    print("🧪 Testing Lead Orchestrator")
    print("=" * 60)

    # Import AIClient for testing
    from ace.ai_client import AIClient
    from ace.cost_tracker import CostTracker

    # Create AI client
    ai_client = AIClient(cost_tracker=CostTracker())

    orchestrator = LeadOrchestrator(ai_client)

    # Test planning
    print("\n1. Testing workflow planning...")
    plan = orchestrator.plan_workflow(
        user_request="Build a REST API with user authentication and a simple blog post CRUD system",
        project_context={"name": "test-blog-api", "language": "python"}
    )

    print(f"\n✅ Plan created:")
    print(f"   Scout tasks: {len(plan.scout_tasks)}")
    print(f"   Builder tasks: {len(plan.builder_tasks)}")
    print(f"   Validation tasks: {len(plan.validation_tasks)}")

    print("\n✅ Lead Orchestrator test complete!")


if __name__ == "__main__":
    test_lead_orchestrator()
