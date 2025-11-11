#!/usr/bin/env python3
"""
Backlog Generator - Creates GitHub issues from Scout findings

Integrates with Scout's AI-powered analysis to create well-formatted GitHub issues
following Context Foundry's issue template standards.
"""

import subprocess
import sys
from pathlib import Path
from typing import List
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.evolution.agents.scout_agent import ScoutAgent, Finding


class BacklogGenerator:
    """Generates GitHub issues from Scout findings using Context Foundry template"""

    def __init__(self, project_root: Path, target_backlog_size: int = 5):
        self.project_root = project_root
        self.target_backlog_size = target_backlog_size
        self.template_path = (
            project_root / "tools/evolution/templates/github_issue_template.md"
        )
        self.valid_labels = None  # Cache for valid labels

        # Load template
        if self.template_path.exists():
            self.template = self.template_path.read_text()
        else:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def get_valid_labels(self) -> List[str]:
        """Get list of valid GitHub labels (cached)"""
        if self.valid_labels is not None:
            return self.valid_labels

        try:
            result = subprocess.run(
                ["gh", "label", "list", "--json", "name"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                labels_data = json.loads(result.stdout)
                self.valid_labels = [label["name"] for label in labels_data]
                return self.valid_labels
            else:
                print(f"  ⚠️  Failed to get label list: {result.stderr}")
                return []
        except Exception as e:
            print(f"  ⚠️  Error getting labels: {e}")
            return []

    def get_current_issue_count(self) -> int:
        """Get count of current open issues"""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--state", "open", "--json", "number"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                issues = json.loads(result.stdout)
                return len(issues)
            else:
                print(f"  ⚠️  Failed to get issue count: {result.stderr}")
                return 0
        except Exception as e:
            print(f"  ⚠️  Error getting issue count: {e}")
            return 0

    def get_existing_issue_titles(self) -> list:
        """Get titles of all open issues to prevent duplicates"""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--state", "open", "--json", "title"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                issues = json.loads(result.stdout)
                return [issue["title"] for issue in issues]
            else:
                print(f"  ⚠️  Failed to get issue titles: {result.stderr}")
                return []
        except Exception as e:
            print(f"  ⚠️  Error getting issue titles: {e}")
            return []

    def format_issue_body(self, finding: Finding) -> str:
        """Format finding into GitHub issue using Context Foundry template"""

        # Determine emoji based on finding type
        emoji_map = {
            "security": "🔒",
            "bug": "🐛",
            "performance": "⚡",
            "enhancement": "✨",
            "debt": "🏗️",
        }
        emoji = emoji_map.get(finding.finding_type, "📋")

        # Determine effort label
        effort_map = {
            "small": "Small (< 1 day)",
            "medium": "Medium (1-3 days)",
            "large": "Large (3+ days)",
        }
        effort = effort_map.get(finding.effort, "Medium (1-3 days)")

        # Format categories
        categories = ", ".join(finding.category) if finding.category else "general"

        # Add file metadata if present
        file_metadata = ""
        if finding.file_path:
            file_metadata = f"- **File:** `{finding.file_path}`"
            if finding.line_number:
                file_metadata += f" (line {finding.line_number})"

        # Add AI analysis section if available
        ai_analysis = ""
        if finding.research and "expert_perspectives" in finding.research:
            perspectives = finding.research["expert_perspectives"]
            reasoning = finding.research.get("reasoning", "")
            ai_score = finding.research.get("ai_score", 0)

            ai_analysis = "\n### AI Analysis\n"
            ai_analysis += f"**Priority Score:** {ai_score}/10\n\n"

            if reasoning:
                ai_analysis += f"**Why this matters:** {reasoning}\n\n"

            if perspectives:
                ai_analysis += "**Expert Perspectives:**\n"
                for expert, assessment in perspectives.items():
                    if assessment and assessment != "":
                        ai_analysis += f"- **{expert.title()}:** {assessment}\n"

        # Fill template
        body = self.template.format(
            emoji=emoji,
            title=finding.title,
            finding_type=finding.finding_type.title(),
            priority=finding.priority,
            categories=categories,
            effort=effort,
            file_metadata=file_metadata,
            description=finding.description,
            ai_analysis=ai_analysis,
        )

        return body

    def create_github_issue(self, finding: Finding) -> bool:
        """Create a GitHub issue for the finding"""

        title = finding.title
        body = self.format_issue_body(finding)

        # Determine labels from finding and AI analysis
        labels = []

        # Add type label
        if finding.finding_type:
            labels.append(finding.finding_type)

        # Add priority label (lowercase)
        if finding.priority:
            labels.append(finding.priority.lower())

        # Add category labels
        if finding.category:
            labels.extend(finding.category)

        # Add AI-recommended labels if available
        if finding.research and "github_labels" in finding.research:
            ai_labels = finding.research["github_labels"]
            for label in ai_labels:
                if label not in labels:
                    labels.append(label)

        # Filter to only valid labels
        valid_labels = self.get_valid_labels()
        filtered_labels = [label for label in labels if label in valid_labels]

        if len(filtered_labels) < len(labels):
            invalid = [label for label in labels if label not in valid_labels]
            print(f"  ⚠️  Skipping invalid labels: {', '.join(invalid)}")

        print(f"📝 Creating issue: {title[:70]}")

        try:
            # Create issue using gh CLI
            cmd = ["gh", "issue", "create", "--title", title, "--body", body]

            # Add labels if we have them
            if filtered_labels:
                for label in filtered_labels:
                    cmd.extend(["--label", label])

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.project_root
            )

            if result.returncode == 0:
                issue_url = result.stdout.strip()
                print(f"  ✅ Created: {issue_url}")
                return True
            else:
                print(f"  ❌ Failed to create issue: {result.stderr.strip()}")
                return False

        except Exception as e:
            print(f"  ❌ Error creating issue: {e}")
            return False

    def maintain_backlog(self):
        """Maintain backlog at target size by running Scout and creating issues"""

        print("📊 Backlog Manager starting...")
        print()

        # Check current backlog size
        current_count = self.get_current_issue_count()
        print(f"Current open issues: {current_count}/{self.target_backlog_size}")

        if current_count >= self.target_backlog_size:
            print(f"✅ Backlog is healthy ({current_count}/{self.target_backlog_size})")
            return

        needed = self.target_backlog_size - current_count
        print(f"🔍 Need {needed} more issues. Running Scout...")
        print()

        # Run Scout with AI analysis
        scout = ScoutAgent(self.project_root)
        findings = scout.scan()

        if not findings:
            print("  ⚠️  Scout found no issues")
            return

        # Filter out findings that already have open issues (deduplication)
        existing_titles = self.get_existing_issue_titles()
        new_findings = [f for f in findings if f.title not in existing_titles]

        print(f"  📊 Found {len(findings)} total findings")
        print(f"  📊 {len(new_findings)} new (after deduplication)")

        if not new_findings:
            print("  ⚠️  All findings already have open issues")
            return

        # Create issues for top new findings (up to needed amount)
        created = 0
        for finding in new_findings[:needed]:
            if self.create_github_issue(finding):
                created += 1

        print()
        print(f"✅ Created {created} new issues")
        print()
        print(
            f"✅ Backlog updated: {current_count + created}/{self.target_backlog_size} issues"
        )


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Maintain GitHub issue backlog")
    parser.add_argument("action", choices=["maintain"], help="Action to perform")
    parser.add_argument(
        "--target-size", type=int, default=5, help="Target backlog size"
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent

    generator = BacklogGenerator(project_root, target_backlog_size=args.target_size)

    if args.action == "maintain":
        generator.maintain_backlog()


if __name__ == "__main__":
    main()
