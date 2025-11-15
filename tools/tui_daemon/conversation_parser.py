"""
Conversation Parser - Natural Language to Build Parameters

Extracts build parameters from natural language input using
regex patterns and keyword matching. Provides confidence scoring
for parsed results.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConversationParams:
    """Parsed build parameters from natural language"""

    task: str
    working_directory: str
    github_repo: Optional[str] = None
    timeout: int = 3600
    mode: str = "smart"
    max_iterations: int = 5
    confidence: float = 0.0


class ConversationParser:
    """
    Parse natural language input into structured build parameters.

    Supports extraction of:
    - Actions: build, create, make, develop, implement
    - Project types: react, vue, angular, python, node, fastapi, flask, game
    - Directories: "in ~/path" or "at /path"
    - GitHub repos: "github.com/user/repo" or "repo: user/repo"
    - Timeouts: "timeout 30m"
    - Modes: "quick mode", "thorough mode", "custom mode"
    - Iterations: "iterations 3"
    """

    # Action keywords
    ACTIONS = ["build", "create", "make", "develop", "implement", "code"]

    # Project type keywords
    PROJECT_TYPES = [
        "react",
        "vue",
        "angular",
        "svelte",
        "python",
        "node",
        "nodejs",
        "typescript",
        "fastapi",
        "flask",
        "django",
        "express",
        "game",
        "cli",
        "app",
        "api",
        "backend",
        "frontend",
    ]

    # Mode keywords
    MODES = {
        "quick": ["quick", "fast", "rapid"],
        "smart": ["smart", "balanced", "normal"],
        "thorough": ["thorough", "detailed", "comprehensive"],
        "custom": ["custom", "manual"],
    }

    def __init__(self):
        """Initialize the conversation parser"""
        pass

    def parse(self, user_input: str) -> ConversationParams:
        """
        Parse natural language input into build parameters.

        Args:
            user_input: Natural language task description

        Returns:
            ConversationParams with extracted parameters and confidence score
        """
        user_input = user_input.strip()

        # Extract components
        task = self._extract_task(user_input)
        working_dir = self._extract_directory(user_input)
        github_repo = self._extract_github_repo(user_input)
        timeout = self._extract_timeout(user_input)
        mode = self._extract_mode(user_input)
        iterations = self._extract_iterations(user_input)

        # Calculate confidence
        confidence = self._calculate_confidence(
            user_input, task, working_dir, github_repo
        )

        # Infer working directory if not specified
        if not working_dir:
            working_dir = self._infer_directory(task)

        return ConversationParams(
            task=task,
            working_directory=working_dir,
            github_repo=github_repo,
            timeout=timeout,
            mode=mode,
            max_iterations=iterations,
            confidence=confidence,
        )

    def _extract_task(self, text: str) -> str:
        """Extract the core task description"""
        # Remove directory paths, timeouts, and other metadata
        task = text

        # Remove "in ~/path" patterns
        task = re.sub(r"\s+(?:in|at)\s+[~/\w\-/.]+", "", task)

        # Remove "timeout Xm" patterns
        task = re.sub(r"\s+timeout\s+\d+[smh]", "", task)

        # Remove "iterations X" patterns
        task = re.sub(r"\s+iterations?\s+\d+", "", task)

        # Remove "repo: user/repo" patterns
        task = re.sub(r"\s+repo:\s*\S+", "", task)

        # Remove mode specifications
        task = re.sub(r"\s+(?:quick|smart|thorough|custom)\s+mode", "", task)

        return task.strip()

    def _extract_directory(self, text: str) -> Optional[str]:
        """
        Extract working directory from text.

        Patterns:
        - "in ~/path/to/dir"
        - "at /absolute/path"
        """
        # Pattern: "in ~/path" or "at /path"
        match = re.search(r"(?:in|at)\s+([~/\w\-/.]+)", text)
        if match:
            return match.group(1)

        return None

    def _extract_github_repo(self, text: str) -> Optional[str]:
        """
        Extract GitHub repository.

        Patterns:
        - "github.com/user/repo"
        - "repo: user/repo"
        """
        # Pattern: github.com/user/repo
        match = re.search(r"github\.com/([a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_]+)", text)
        if match:
            return match.group(1)

        # Pattern: repo: user/repo
        match = re.search(r"repo:\s*([a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_]+)", text)
        if match:
            return match.group(1)

        return None

    def _extract_timeout(self, text: str) -> int:
        """
        Extract timeout in seconds.

        Patterns:
        - "timeout 30m" → 1800
        - "timeout 2h" → 7200
        - "timeout 120s" → 120
        """
        match = re.search(r"timeout\s+(\d+)([smh])", text)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            if unit == "s":
                return value
            elif unit == "m":
                return value * 60
            elif unit == "h":
                return value * 3600

        return 3600  # Default 1 hour

    def _extract_mode(self, text: str) -> str:
        """
        Extract build mode.

        Patterns:
        - "quick mode"
        - "thorough mode"
        """
        text_lower = text.lower()

        for mode, keywords in self.MODES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return mode

        return "smart"  # Default mode

    def _extract_iterations(self, text: str) -> int:
        """
        Extract max iterations.

        Patterns:
        - "iterations 3"
        - "iteration 5"
        """
        match = re.search(r"iterations?\s+(\d+)", text)
        if match:
            return int(match.group(1))

        return 5  # Default iterations

    def _infer_directory(self, task: str) -> str:
        """
        Infer working directory from task description.

        Uses project name extraction to suggest ~/homelab/{project-name}
        """
        # Try to extract a project name
        task_lower = task.lower()

        # Look for "a {name} app/project"
        match = re.search(
            r"a\s+(\w+(?:\s+\w+)?)\s+(?:app|project|game|cli)", task_lower
        )
        if match:
            project_name = match.group(1).replace(" ", "-")
            return f"~/homelab/{project_name}"

        # Look for project types
        for ptype in self.PROJECT_TYPES:
            if ptype in task_lower:
                return f"~/homelab/{ptype}-project"

        # Fallback
        return "~/homelab/new-project"

    def _calculate_confidence(
        self,
        text: str,
        task: str,
        working_dir: Optional[str],
        github_repo: Optional[str],
    ) -> float:
        """
        Calculate confidence score for parsed parameters.

        Factors:
        - Has action keyword: +0.2
        - Has project type: +0.2
        - Has explicit directory: +0.3
        - Has GitHub repo: +0.2
        - Task is clear (>10 chars): +0.1
        """
        confidence = 0.0
        text_lower = text.lower()

        # Has action keyword
        if any(action in text_lower for action in self.ACTIONS):
            confidence += 0.2

        # Has project type
        if any(ptype in text_lower for ptype in self.PROJECT_TYPES):
            confidence += 0.2

        # Has explicit directory
        if working_dir and ("in " in text or "at " in text):
            confidence += 0.3

        # Has GitHub repo
        if github_repo:
            confidence += 0.2

        # Task is clear
        if len(task) > 10:
            confidence += 0.1

        return min(confidence, 1.0)
