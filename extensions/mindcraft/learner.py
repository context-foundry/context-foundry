"""
Mindcraft Learner Module

Acts as the interface to the Knowledge Base.
Loads patterns and finds relevant wisdom for the current context.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

PATTERNS_DIR = Path(__file__).parent / "patterns"


class MindcraftLearner:
    """
    Knowledge Manager for Mindcraft.

    Responsibilities:
    1. Load patterns from disk (fast cache).
    2. Retrieve patterns matching specific tags/triggers.
    """

    def __init__(self):
        self.patterns: List[Dict[str, Any]] = []
        self._load_patterns()

    def _load_patterns(self):
        """Load all JSON patterns from the patterns directory."""
        self.patterns = []
        if not PATTERNS_DIR.exists():
            return

        for pattern_file in PATTERNS_DIR.glob("*.json"):
            try:
                with open(pattern_file, "r") as f:
                    data = json.load(f)

                    # Handle both single pattern and list of patterns
                    if "patterns" in data and isinstance(data["patterns"], list):
                        self.patterns.extend(data["patterns"])
                    else:
                        # Maybe it is a single pattern object?
                        if "id" in data:
                            self.patterns.append(data)

            except Exception as e:
                print(f"Error loading pattern file {pattern_file}: {e}")

        print(f"📚 Learner loaded {len(self.patterns)} patterns.")

    def find_relevant(self, context_tags: List[str]) -> List[Dict[str, Any]]:
        """
        Find patterns that match the given context tags.

        Args:
            context_tags: List of keywords (e.g. ["night", "water"])

        Returns:
            List of matching pattern objects, sorted by priority.
        """
        matches = []
        query_tags = set(t.lower() for t in context_tags)

        for p in self.patterns:
            # Check if any trigger matches our context
            triggers = set(t.lower() for t in p.get("trigger", []))

            # Intersection: Do we have any matching tags?
            if not query_tags.isdisjoint(triggers):
                matches.append(p)

        # Sort by priority (descending), default to 50
        matches.sort(key=lambda x: x.get("priority", 50), reverse=True)
        return matches

    def get_pattern_summary(self, context_tags: List[str]) -> str:
        """
        Get a concise string summary of relevant patterns for LLM context.
        """
        relevant = self.find_relevant(context_tags)
        if not relevant:
            return ""

        summary = "RELEVANT GUIDELINES (Follow these strictly):\n"
        for p in relevant:
            name = p.get("name", "Unknown Rule")
            rule = p.get("rule", "")
            solution = p.get("solution", "")
            summary += f"- [{name}]: {rule} -> {solution}\n"

        return summary
