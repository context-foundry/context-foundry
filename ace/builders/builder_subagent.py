#!/usr/bin/env python3
"""
Builder Subagent - Executes focused implementation tasks in parallel.

Key principles from Anthropic:
- Each subagent has clear boundaries
- Independent execution with own context
- Tests written first (TDD)
- Results stored in filesystem to avoid "game of telephone"
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from ..orchestrator.models import SubagentTask, SubagentResult


class BuilderSubagent:
    """
    Individual Builder subagent that implements a specific module.

    Implements one module/feature independently with tests.
    """

    SUBAGENT_PROMPT = """You are a Builder subagent for Context Foundry implementing a specific module.

TASK:
{objective}

OUTPUT FORMAT:
{output_format}

MODULE BOUNDARIES:
{boundaries}

ARCHITECT'S GUIDANCE:
{architect_guidance}

INSTRUCTIONS:
1. Write tests FIRST (test-driven development approach)
2. Implement the module to pass those tests
3. Keep code focused on YOUR module only - don't duplicate other modules
4. Document interfaces clearly for other modules
5. Use best practices and clean code principles
6. Include error handling and edge cases

CRITICAL: Describe the files you would create using this format:

FILE: path/to/file.py
```python
# file content here
```

FILE: path/to/test_file.py
```python
# test content here
```

Begin implementation now. Provide complete, working code with file paths."""

    def __init__(
        self,
        ai_client,
        task: SubagentTask,
        project_dir: Path,
        architect_result: Optional[Dict] = None
    ):
        """Initialize Builder subagent.

        Args:
            ai_client: AIClient instance (provider-agnostic)
            task: SubagentTask to execute
            project_dir: Project directory for writing files
            architect_result: Optional architect guidance
        """
        self.ai_client = ai_client
        self.task = task
        self.project_dir = Path(project_dir)
        self.architect_result = architect_result or {}
        self.files_written = []

        # Use builder provider/model from AIClient configuration
        self.provider_name = ai_client.config.builder.provider
        self.model_name = ai_client.config.builder.model

        # Apply model routing if enabled
        if ai_client.model_router:
            routing_decision = ai_client.model_router.get_model_for_task(
                phase='builder',
                task=task,
                context={
                    'has_dependencies': len(task.dependencies) > 0 if hasattr(task, 'dependencies') else False
                }
            )
            if routing_decision.model != self.model_name:
                print(f"   🔀 Model routing: {self.model_name} → {routing_decision.model}")
                print(f"      Reason: {routing_decision.reason}")
                self.model_name = routing_decision.model

        self.provider = ai_client.registry.get(self.provider_name)

    def execute(self) -> SubagentResult:
        """Execute the build task with TDD approach.

        Returns:
            SubagentResult with files written
        """

        print(f"   🔨 {self.task.id}: Starting implementation...")

        try:
            # Build kwargs conditionally to avoid passing unsupported parameters
            call_kwargs = {
                'model': self.model_name,
                'max_tokens': 16000,
                'messages': [{
                    "role": "user",
                    "content": self.SUBAGENT_PROMPT.format(
                        objective=self.task.objective,
                        output_format=self.task.output_format,
                        boundaries=self.task.boundaries or "Implement your module independently",
                        architect_guidance=self.architect_result.get('summary', 'Follow best practices')
                    )
                }]
            }

            # Only add thinking parameter for Anthropic
            if self.provider_name == 'anthropic':
                call_kwargs['thinking'] = {
                    "type": "enabled",
                    "budget_tokens": 5000
                }

            response = self.provider.call_api(**call_kwargs)

            # Extract implementation (ProviderResponse.content is already a string)
            implementation = response.content

            # Parse and write files
            files_written = self._parse_and_write_files(implementation)

            # Calculate token usage
            token_usage = response.input_tokens + response.output_tokens

            print(f"   ✅ {self.task.id}: Implementation complete ({len(files_written)} files, {token_usage:,} tokens)")

            return SubagentResult(
                task_id=self.task.id,
                task_type=self.task.type,
                success=True,
                findings=implementation,
                files_written=files_written,
                token_usage=token_usage,
                metadata={
                    'input_tokens': response.input_tokens,
                    'output_tokens': response.output_tokens,
                    'file_count': len(files_written),
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
                files_written=self.files_written,
                metadata={'exception': str(e)}
            )

    def _parse_and_write_files(self, implementation: str) -> list[str]:
        """Parse implementation text and write files to disk.

        Args:
            implementation: Text containing FILE: markers and code blocks

        Returns:
            List of file paths written
        """
        files_written = []
        lines = implementation.split('\n')
        current_file = None
        current_content = []
        in_code_block = False

        for line in lines:
            # Check for FILE: marker
            if line.strip().startswith('FILE:'):
                # Save previous file if exists
                if current_file and current_content:
                    self._write_file(current_file, '\n'.join(current_content))
                    files_written.append(str(current_file))

                # Start new file
                file_path = line.replace('FILE:', '').strip()
                current_file = self.project_dir / file_path
                current_content = []
                in_code_block = False

            # Check for code block markers
            elif line.strip().startswith('```'):
                if in_code_block:
                    # End of code block
                    in_code_block = False
                else:
                    # Start of code block
                    in_code_block = True
            elif in_code_block and current_file:
                # Add line to current file content
                current_content.append(line)

        # Save last file
        if current_file and current_content:
            self._write_file(current_file, '\n'.join(current_content))
            files_written.append(str(current_file))

        return files_written

    def _write_file(self, file_path: Path, content: str):
        """Write content to file, creating directories as needed.

        Args:
            file_path: Path to write to
            content: Content to write
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        self.files_written.append(str(file_path))
        print(f"      📝 Wrote: {file_path.relative_to(self.project_dir)}")
