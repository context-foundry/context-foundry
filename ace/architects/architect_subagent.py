#!/usr/bin/env python3
"""
Architect Subagent - Creates system architecture from research findings.

Based on Anthropic's multi-agent system architecture.
Takes compressed scout findings and creates comprehensive architecture plan.
"""

from typing import Dict, Any, Optional

from ..orchestrator.models import SubagentTask, SubagentResult


class ArchitectSubagent:
    """
    Architect subagent that creates system architecture.

    Takes research findings from scouts and creates:
    - System overview and design decisions
    - File structure and module breakdown
    - API designs and data models
    - Testing strategy
    - Implementation order
    """

    SUBAGENT_PROMPT = """You are an Architect subagent for Context Foundry.

TASK: Create a comprehensive system architecture based on research findings.

USER REQUEST:
{user_request}

SCOUT RESEARCH FINDINGS:
{scout_findings}

ARCHITECT STRATEGY:
{architect_strategy}

CREATE A COMPLETE ARCHITECTURE DOCUMENT INCLUDING:

1. **System Overview**
   - High-level architecture description
   - Technology stack choices with rationale
   - Key design decisions and trade-offs

2. **File Structure**
   Provide complete directory structure:
   ```
   project/
   ├── src/
   │   ├── module1/
   │   │   ├── __init__.py
   │   │   └── core.py
   │   ├── module2/
   ├── tests/
   │   ├── test_module1.py
   ├── docs/
   └── README.md
   ```

3. **Module Breakdown**
   For each module:
   - Purpose and responsibilities
   - Public interfaces/APIs
   - Dependencies (internal and external)
   - Clear boundaries (what it does NOT do)

4. **API Design** (if applicable)
   - Endpoint definitions
   - Request/response formats
   - Authentication/authorization
   - Error handling strategy

5. **Data Models**
   - Schema definitions
   - Relationships between entities
   - Validation rules
   - Storage strategy

6. **Testing Strategy**
   - Unit test requirements for each module
   - Integration test approach
   - Test coverage goals
   - Testing tools/frameworks

7. **Implementation Order**
   Suggest task breakdown for builders:
   - Which modules to build first (dependencies)
   - Which can be built in parallel
   - Recommended builder task assignments

8. **Deployment Considerations**
   - Environment setup
   - Dependencies and installation
   - Configuration management
   - Build/deploy steps

Provide a clear, actionable architecture that builders can follow independently."""

    def __init__(self, ai_client, task: SubagentTask, scout_findings: str, workflow_complexity: str = None):
        """Initialize Architect subagent.

        Args:
            ai_client: AIClient instance (provider-agnostic)
            task: SubagentTask to execute
            scout_findings: Compressed findings from scout phase
            workflow_complexity: Optional workflow complexity assessment
        """
        self.ai_client = ai_client
        self.task = task
        self.scout_findings = scout_findings
        self.workflow_complexity = workflow_complexity

        # Use architect provider/model from AIClient configuration
        self.provider_name = ai_client.config.architect.provider
        self.model_name = ai_client.config.architect.model

        # Apply model routing if enabled
        if ai_client.model_router:
            routing_decision = ai_client.model_router.get_model_for_task(
                phase='architect',
                task=task,
                workflow_complexity=workflow_complexity
            )
            if routing_decision.model != self.model_name:
                print(f"   🔀 Model routing: {self.model_name} → {routing_decision.model}")
                print(f"      Reason: {routing_decision.reason}")
                self.model_name = routing_decision.model

        self.provider = ai_client.registry.get(self.provider_name)

    def execute(self) -> SubagentResult:
        """
        Execute the architecture planning task.

        Returns:
            SubagentResult with architecture document
        """

        print(f"   🏗️  {self.task.id}: Creating architecture...")

        try:
            # Build kwargs conditionally to avoid passing unsupported parameters
            call_kwargs = {
                'model': self.model_name,
                'max_tokens': 12000,
                'messages': [{
                    "role": "user",
                    "content": self.SUBAGENT_PROMPT.format(
                        user_request=self.task.objective,
                        scout_findings=self.scout_findings,
                        architect_strategy=self.task.boundaries or "Follow best practices and proven patterns"
                    )
                }]
            }

            # Only add thinking parameter for Anthropic
            if self.provider_name == 'anthropic':
                call_kwargs['thinking'] = {
                    "type": "enabled",
                    "budget_tokens": 4000
                }

            response = self.provider.call_api(**call_kwargs)

            # Extract architecture document (ProviderResponse.content is already a string)
            architecture = response.content

            # Calculate token usage
            token_usage = response.input_tokens + response.output_tokens

            print(f"   ✅ {self.task.id}: Architecture complete ({token_usage:,} tokens)")

            return SubagentResult(
                task_id=self.task.id,
                task_type=self.task.type,
                success=True,
                findings=architecture,
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
