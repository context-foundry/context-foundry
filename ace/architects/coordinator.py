#!/usr/bin/env python3
"""
Architect Coordinator - Manages architect execution.

Unlike scouts/builders, typically runs single architect for architectural coherence.
Multiple architects could lead to conflicting design decisions.
"""

from typing import Dict, Optional

from ..orchestrator.models import SubagentTask, PhaseResult
from .architect_subagent import ArchitectSubagent


class ArchitectCoordinator:
    """
    Coordinates architect execution.

    Runs single architect (not parallel) because:
    - Architecture needs coherent vision
    - Multiple architects might conflict on design decisions
    - Compression of findings happens before architect phase
    """

    def __init__(self, ai_client):
        """Initialize coordinator.

        Args:
            ai_client: AIClient instance (provider-agnostic)
        """
        self.ai_client = ai_client

    def execute(
        self,
        user_request: str,
        scout_findings: str,
        architect_strategy: str
    ) -> PhaseResult:
        """
        Execute architect to create system architecture.

        Args:
            user_request: Original user request/task description
            scout_findings: Compressed findings from scout phase
            architect_strategy: Strategy guidance from lead orchestrator

        Returns:
            PhaseResult with architecture document
        """

        print(f"\n🚀 Launching Architect...")

        # Create architect task
        task = SubagentTask(
            id="architect_main",
            type="architect",
            objective=user_request,
            output_format="Complete architecture document with file structure, modules, and implementation plan",
            tools=["reasoning"],
            boundaries=architect_strategy
        )

        # Execute architect
        architect = ArchitectSubagent(self.ai_client, task, scout_findings)
        result = architect.execute()

        if result.success:
            print(f"✅ Architect phase complete")
        else:
            print(f"   ❌ Architect failed: {result.error}")

        return PhaseResult(
            phase_name='architect',
            success=result.success,
            subagent_results=[result],
            total_tokens=result.token_usage,
            error=result.error
        )
