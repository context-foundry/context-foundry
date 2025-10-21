#!/usr/bin/env python3
"""
Pattern Injector
Inject relevant patterns into Claude prompts for better code generation.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

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

    def load_global_common_issues(self, tech_stack: List[str]) -> List[Dict[str, Any]]:
        """Load relevant patterns from ~/.context-foundry/patterns/common-issues.json.

        Filters patterns by:
        - tech_stack matching (any overlap with pattern's tech_stack)
        - auto_apply: true
        - severity (returns HIGH > MEDIUM > LOW priority)

        Args:
            tech_stack: List of technologies (e.g., ["typescript", "express", "socket.io"])

        Returns:
            List of matching pattern dictionaries, sorted by severity
        """
        try:
            # Load global common-issues patterns
            global_pattern_file = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"

            if not global_pattern_file.exists():
                return []

            with open(global_pattern_file, 'r') as f:
                data = json.load(f)

            patterns = data.get("patterns", [])

            # Normalize tech stack for matching (lowercase)
            tech_stack_lower = [t.lower() for t in tech_stack]

            # Filter patterns
            matching_patterns = []
            for pattern in patterns:
                # Check auto_apply flag
                if not pattern.get("auto_apply", False):
                    continue

                # Check tech_stack overlap
                pattern_tech_stack = [t.lower() for t in pattern.get("tech_stack", [])]
                if not any(tech in pattern_tech_stack for tech in tech_stack_lower):
                    continue

                matching_patterns.append(pattern)

            # Sort by severity: HIGH > MEDIUM > LOW
            severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            matching_patterns.sort(
                key=lambda p: severity_order.get(p.get("severity", "LOW"), 999)
            )

            return matching_patterns

        except Exception as e:
            print(f"Warning: Failed to load common-issues patterns: {e}")
            return []

    def format_common_issues_section(self, patterns: List[Dict[str, Any]]) -> str:
        """Format common-issues patterns for prompt injection.

        Args:
            patterns: List of pattern dictionaries from common-issues.json

        Returns:
            Formatted string for prompt injection
        """
        if not patterns:
            return ""

        section = "\n## ⚠️ CRITICAL PATTERNS - Auto-Learned from Previous Builds\n\n"
        section += "**IMPORTANT**: These patterns prevent known issues in your tech stack. Apply them proactively!\n\n"

        for i, pattern in enumerate(patterns, 1):
            severity = pattern.get("severity", "MEDIUM")
            severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")

            title = pattern.get("title", "Unknown Pattern")
            pattern_id = pattern.get("pattern_id", "unknown")

            section += f"### {severity_emoji} Pattern #{i}: {title}\n\n"
            section += f"**ID**: `{pattern_id}`  \n"
            section += f"**Severity**: {severity}  \n"
            section += f"**Impact**: {pattern.get('impact', 'Unknown')}  \n\n"

            # Root cause
            root_cause = pattern.get("root_cause", "")
            if root_cause:
                section += f"**Root Cause:**  \n{root_cause}\n\n"

            # Solution for Architect phase
            solution = pattern.get("solution", {})
            architect_solution = solution.get("architect", {})
            if architect_solution:
                section += "**Architect Solution:**\n"
                specifics = architect_solution.get("specifics", [])
                for spec in specifics:
                    section += f"- {spec}\n"
                section += "\n"

            # Solution for Builder phase
            builder_solution = solution.get("builder", {})
            if builder_solution:
                section += "**Builder Checklist:**\n"
                checklist = builder_solution.get("validation_checklist", [])
                for item in checklist:
                    section += f"- [ ] {item}\n"
                section += "\n"

            # Prevention actions
            prevention = pattern.get("prevention", {})
            actions = prevention.get("actions", [])
            if actions:
                section += "**Prevention Actions:**\n"
                for action in actions:
                    section += f"- {action}\n"
                section += "\n"

            section += "---\n\n"

        section += "**Apply these patterns IMMEDIATELY in your implementation to prevent these issues!**\n\n"

        return section

    def extract_tech_stack(self, text: str) -> List[str]:
        """Extract tech stack from text (spec, research, etc.).

        Uses keyword matching to identify technologies mentioned in the text.

        Args:
            text: Text to search for technologies

        Returns:
            List of detected technologies (lowercase)
        """
        # Common technologies to detect
        tech_keywords = [
            # Languages
            "typescript", "javascript", "python", "java", "go", "rust", "php",
            # Backend frameworks
            "express", "fastapi", "flask", "django", "spring", "gin",
            # Frontend frameworks
            "react", "vue", "angular", "next.js", "nextjs", "svelte",
            # Databases
            "postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis",
            # Real-time
            "socket.io", "socketio", "websocket", "sse",
            # Other
            "nodejs", "node", "docker", "kubernetes", "graphql", "rest"
        ]

        text_lower = text.lower()
        detected = []

        for tech in tech_keywords:
            if tech in text_lower:
                # Normalize some variations
                if tech in ("next.js", "nextjs"):
                    detected.append("nextjs")
                elif tech in ("postgres", "postgresql"):
                    detected.append("postgresql")
                elif tech in ("node", "nodejs"):
                    detected.append("nodejs")
                elif tech in ("socketio", "socket.io"):
                    detected.append("socket.io")
                else:
                    detected.append(tech)

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for tech in detected:
            if tech not in seen:
                seen.add(tech)
                result.append(tech)

        return result

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

        # Get code patterns from SQLite database
        enhanced_prompt, pattern_ids = self.enhance_prompt(
            base_prompt,
            search_query,
            language="python"
        )

        # Also inject common-issues patterns based on tech stack
        tech_stack = self.extract_tech_stack(research + " " + task)

        if tech_stack:
            common_issues = self.load_global_common_issues(tech_stack)

            if common_issues:
                common_issues_section = self.format_common_issues_section(common_issues)
                enhanced_prompt = enhanced_prompt + "\n" + common_issues_section

                # Log which patterns were injected
                print(f"  📚 Injected {len(common_issues)} common-issues patterns for tech stack: {', '.join(tech_stack)}")
                for pattern in common_issues:
                    severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(pattern.get("severity"), "⚪")
                    print(f"     {severity_emoji} {pattern.get('pattern_id')}: {pattern.get('title')}")

        return enhanced_prompt, pattern_ids

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

        # Get code patterns from SQLite database
        enhanced_prompt, pattern_ids = self.enhance_prompt(
            base_prompt,
            search_query,
            language="python"
        )

        # Also inject common-issues patterns based on tech stack
        tech_stack = self.extract_tech_stack(spec + " " + task)

        if tech_stack:
            common_issues = self.load_global_common_issues(tech_stack)

            if common_issues:
                common_issues_section = self.format_common_issues_section(common_issues)
                enhanced_prompt = enhanced_prompt + "\n" + common_issues_section

                # Log which patterns were injected
                print(f"  📚 Injected {len(common_issues)} common-issues patterns for tech stack: {', '.join(tech_stack)}")
                for pattern in common_issues:
                    severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(pattern.get("severity"), "⚪")
                    print(f"     {severity_emoji} {pattern.get('pattern_id')}: {pattern.get('title')}")

        return enhanced_prompt, pattern_ids

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
