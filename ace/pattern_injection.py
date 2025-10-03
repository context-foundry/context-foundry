#!/usr/bin/env python3
"""
Pattern Injector
Inject relevant patterns into Claude prompts for better code generation.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from foundry.patterns.pattern_manager import PatternLibrary


class PatternInjector:
    """Inject relevant patterns into prompts."""

    def __init__(
        self,
        pattern_library: PatternLibrary,
        max_patterns: int = 3,
        min_success_rate: float = 70.0,
        min_relevance: float = 0.6
    ):
        """Initialize pattern injector.

        Args:
            pattern_library: PatternLibrary instance
            max_patterns: Maximum patterns to inject
            min_success_rate: Minimum success rate (0-100)
            min_relevance: Minimum relevance score (0-1)
        """
        self.library = pattern_library
        self.max_patterns = max_patterns
        self.min_success_rate = min_success_rate
        self.min_relevance = min_relevance

    def enhance_prompt(
        self,
        original_prompt: str,
        task_description: str,
        language: Optional[str] = None,
        framework: Optional[str] = None
    ) -> Tuple[str, List[int]]:
        """Add relevant patterns to prompt.

        Args:
            original_prompt: Original prompt text
            task_description: Description of the task for pattern search
            language: Optional language filter
            framework: Optional framework filter

        Returns:
            Tuple of (enhanced_prompt, pattern_ids_used)
        """
        # Search for relevant patterns
        patterns = self.library.search_patterns(
            task_description,
            limit=self.max_patterns * 2,  # Get extra for filtering
            language=language,
            framework=framework,
            min_relevance=self.min_relevance
        )

        if not patterns:
            return original_prompt, []

        # Filter by success rate
        filtered_patterns = []
        for p_id, code, desc, similarity in patterns:
            pattern_data = self.library.apply_pattern(p_id, task_description)
            if pattern_data and pattern_data['success_rate'] >= self.min_success_rate:
                filtered_patterns.append((p_id, code, desc, similarity, pattern_data))

        # Take top N after filtering
        filtered_patterns = filtered_patterns[:self.max_patterns]

        if not filtered_patterns:
            return original_prompt, []

        # Build pattern section
        pattern_section = self._build_pattern_section(filtered_patterns)

        # Inject into prompt
        enhanced = f"""{original_prompt}

{pattern_section}

Consider these patterns when implementing. They've proven successful in similar contexts and can serve as starting points or references.
"""

        # Track usage
        pattern_ids = [p[0] for p in filtered_patterns]
        for p_id in pattern_ids:
            # Record pending usage (will be rated after task completes)
            self.library.db.execute(
                """INSERT INTO pattern_usage (pattern_id, session_id, task_id, rating)
                   VALUES (?, ?, ?, ?)""",
                (p_id, "pending", task_description[:100], 0)
            )
        self.library.db.commit()

        return enhanced, pattern_ids

    def _build_pattern_section(
        self,
        patterns: List[Tuple[int, str, str, float, dict]]
    ) -> str:
        """Build pattern section for prompt.

        Args:
            patterns: List of (id, code, desc, similarity, pattern_data) tuples

        Returns:
            Formatted pattern section
        """
        section = "\n## Relevant Patterns from Past Successes\n\n"
        section += "Based on similar projects, these patterns have been effective:\n\n"

        for i, (p_id, code, desc, similarity, pattern_data) in enumerate(patterns, 1):
            section += f"""### Pattern #{i}: {desc}

- **Success Rate**: {pattern_data['success_rate']:.0f}%
- **Used Successfully**: {pattern_data['usage_count']} times
- **Avg Rating**: {pattern_data['avg_rating']:.1f}/5
- **Relevance to Task**: {similarity * 100:.0f}%

```python
{code}
```

"""

        return section

    def inject_into_scout_prompt(
        self,
        base_prompt: str,
        project_name: str,
        task: str
    ) -> Tuple[str, List[int]]:
        """Inject patterns into Scout phase prompt.

        Args:
            base_prompt: Base Scout prompt
            project_name: Project name
            task: Task description

        Returns:
            Tuple of (enhanced_prompt, pattern_ids)
        """
        # Scout phase focuses on research, so we look for architectural patterns
        search_query = f"architecture research patterns for {task}"

        return self.enhance_prompt(
            base_prompt,
            search_query,
            language="python"  # Default to Python
        )

    def inject_into_architect_prompt(
        self,
        base_prompt: str,
        project_name: str,
        task: str,
        research: str
    ) -> Tuple[str, List[int]]:
        """Inject patterns into Architect phase prompt.

        Args:
            base_prompt: Base Architect prompt
            project_name: Project name
            task: Task description
            research: Research findings from Scout

        Returns:
            Tuple of (enhanced_prompt, pattern_ids)
        """
        # Architect phase focuses on planning, so we look for design patterns
        search_query = f"design planning patterns for {task}"

        return self.enhance_prompt(
            base_prompt,
            search_query,
            language="python"
        )

    def inject_into_builder_prompt(
        self,
        base_prompt: str,
        project_name: str,
        task: str,
        spec: str
    ) -> Tuple[str, List[int]]:
        """Inject patterns into Builder phase prompt.

        Args:
            base_prompt: Base Builder prompt
            project_name: Project name
            task: Task description
            spec: Specification from Architect

        Returns:
            Tuple of (enhanced_prompt, pattern_ids)
        """
        # Builder phase focuses on implementation
        search_query = f"implementation code patterns for {task}"

        return self.enhance_prompt(
            base_prompt,
            search_query,
            language="python"
        )

    def get_pattern_summary(self, pattern_ids: List[int]) -> str:
        """Get summary of patterns used.

        Args:
            pattern_ids: List of pattern IDs

        Returns:
            Formatted summary
        """
        if not pattern_ids:
            return "No patterns used."

        summary = f"Used {len(pattern_ids)} patterns:\n"

        for p_id in pattern_ids:
            pattern = self.library.apply_pattern(p_id)
            if pattern:
                summary += f"  - Pattern #{p_id}: {pattern['description']} "
                summary += f"({pattern['success_rate']:.0f}% success rate)\n"

        return summary


def main():
    """Test pattern injection."""
    print("🧪 Testing Pattern Injector...\n")

    # Initialize library and injector
    lib = PatternLibrary()
    injector = PatternInjector(lib)

    # Test prompt
    base_prompt = """You are implementing a new feature for a web application.

Task: Build a user authentication system

Please provide a complete implementation."""

    task = "Build a user authentication system with email validation"

    print("Original prompt:")
    print("-" * 60)
    print(base_prompt)
    print("-" * 60)

    # Enhance prompt
    enhanced, pattern_ids = injector.enhance_prompt(base_prompt, task)

    print("\n✅ Enhanced prompt:")
    print("-" * 60)
    print(enhanced)
    print("-" * 60)

    print(f"\n📊 Patterns injected: {len(pattern_ids)}")

    if pattern_ids:
        print("\n" + injector.get_pattern_summary(pattern_ids))

    lib.close()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
