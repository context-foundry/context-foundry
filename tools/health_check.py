#!/usr/bin/env python3
"""
Context Foundry Health Check
Validates setup and dependencies on first launch.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


class HealthCheck:
    """Validates Context Foundry installation and setup."""

    def __init__(self):
        self.issues: List[Tuple[str, str, str]] = []  # (severity, check, message)
        self.warnings: List[Tuple[str, str]] = []  # (check, message)
        self.passed: List[str] = []

    def run(self) -> bool:
        """Run all health checks. Returns True if all critical checks pass."""
        console.print(Panel.fit(
            "[bold cyan]Context Foundry Health Check[/bold cyan]\n"
            "Validating installation and configuration...",
            border_style="cyan"
        ))
        console.print()

        # Run checks
        self.check_python_version()
        self.check_api_key()
        self.check_dependencies()
        self.check_directory_structure()
        self.check_git()
        self.check_optional_tools()

        # Display results
        self.display_results()

        # Return status
        critical_issues = [i for i in self.issues if i[0] == "critical"]
        return len(critical_issues) == 0

    def check_python_version(self):
        """Check Python version."""
        major, minor = sys.version_info[:2]
        if major >= 3 and minor >= 8:
            self.passed.append(f"Python version {major}.{minor}")
        else:
            self.issues.append((
                "critical",
                "Python Version",
                f"Python 3.8+ required, found {major}.{minor}"
            ))

    def check_api_key(self):
        """Check if ANTHROPIC_API_KEY is configured."""
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if api_key and api_key != "your_api_key_here":
            # Basic validation (should start with sk-)
            if api_key.startswith("sk-"):
                self.passed.append("API key configured")
            else:
                self.warnings.append((
                    "API Key Format",
                    "API key doesn't match expected format (should start with 'sk-')"
                ))
        else:
            self.issues.append((
                "critical",
                "API Key",
                "ANTHROPIC_API_KEY not set or invalid\n"
                "   → Get your key from: https://console.anthropic.com/\n"
                "   → Set with: export ANTHROPIC_API_KEY=your_key\n"
                "   → Or run: foundry config --init"
            ))

    def check_dependencies(self):
        """Check if required Python packages are installed."""
        required_packages = [
            "anthropic",
            "click",
            "rich",
            "tabulate",
            "dotenv",
            "sentence_transformers",
            "numpy",
            "yaml"
        ]

        missing = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                # Handle special cases
                if package == "dotenv":
                    try:
                        __import__("dotenv")
                    except ImportError:
                        missing.append("python-dotenv")
                elif package == "yaml":
                    try:
                        __import__("yaml")
                    except ImportError:
                        missing.append("pyyaml")
                else:
                    missing.append(package)

        if missing:
            self.issues.append((
                "critical",
                "Dependencies",
                f"Missing packages: {', '.join(missing)}\n"
                f"   → Install with: pip install -r requirements.txt"
            ))
        else:
            self.passed.append("All dependencies installed")

    def check_directory_structure(self):
        """Check if required directories exist."""
        base_dir = Path.cwd()
        required_dirs = [
            "ace",
            "foundry/patterns",
            "checkpoints",
            "blueprints/specs",
            "blueprints/plans",
            "blueprints/tasks",
            "workflows",
            "tools"
        ]

        missing_dirs = []
        for dir_path in required_dirs:
            full_path = base_dir / dir_path
            if not full_path.exists():
                missing_dirs.append(dir_path)

        if missing_dirs:
            self.warnings.append((
                "Directory Structure",
                f"Missing directories: {', '.join(missing_dirs)}\n"
                f"   → These will be created automatically when needed"
            ))
        else:
            self.passed.append("Directory structure complete")

    def check_git(self):
        """Check if git is available and repository initialized."""
        # Check git installed
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.passed.append("Git available")
            else:
                self.warnings.append((
                    "Git",
                    "Git not working properly\n"
                    "   → Install from: https://git-scm.com/"
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.warnings.append((
                "Git",
                "Git not found\n"
                "   → Install from: https://git-scm.com/\n"
                "   → Needed for checkpointing and PR creation"
            ))
            return

        # Check if in a git repository
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.passed.append("Git repository initialized")
            else:
                self.warnings.append((
                    "Git Repository",
                    "Not in a git repository\n"
                    "   → Initialize with: git init\n"
                    "   → Recommended for version control"
                ))
        except subprocess.TimeoutExpired:
            pass

    def check_optional_tools(self):
        """Check for optional tools that enhance functionality."""
        # Check for gh CLI (for PR creation)
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.passed.append("GitHub CLI available (gh)")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.warnings.append((
                "GitHub CLI (Optional)",
                "GitHub CLI not found\n"
                "   → Install from: https://cli.github.com/\n"
                "   → Enables automatic PR creation"
            ))

        # Check for SLACK_WEBHOOK
        if os.getenv("SLACK_WEBHOOK"):
            self.passed.append("Slack webhook configured")

    def display_results(self):
        """Display health check results."""
        # Passed checks
        if self.passed:
            console.print("[bold green]✓ Passed Checks:[/bold green]")
            for check in self.passed:
                console.print(f"  [green]✓[/green] {check}")
            console.print()

        # Warnings
        if self.warnings:
            console.print("[bold yellow]⚠ Warnings:[/bold yellow]")
            for check, message in self.warnings:
                console.print(f"  [yellow]⚠[/yellow] {check}")
                console.print(f"     {message}")
                console.print()

        # Critical issues
        if self.issues:
            critical = [i for i in self.issues if i[0] == "critical"]
            if critical:
                console.print("[bold red]❌ Critical Issues:[/bold red]")
                for _, check, message in critical:
                    console.print(f"  [red]❌[/red] {check}")
                    console.print(f"     {message}")
                    console.print()

        # Summary
        if not self.issues:
            console.print(Panel.fit(
                "[bold green]✅ All critical checks passed![/bold green]\n"
                "Context Foundry is ready to use.\n\n"
                "[cyan]Quick start:[/cyan]\n"
                "  foundry build my-app \"Your task description\"",
                title="Health Check Complete",
                border_style="green"
            ))
        else:
            critical_count = len([i for i in self.issues if i[0] == "critical"])
            console.print(Panel.fit(
                f"[bold red]{critical_count} critical issue(s) found[/bold red]\n"
                "Please resolve the issues above before using Context Foundry.",
                title="Health Check Failed",
                border_style="red"
            ))


def main():
    """Run health check and exit with appropriate code."""
    checker = HealthCheck()
    success = checker.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
