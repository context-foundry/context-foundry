#!/usr/bin/env python3
"""
Failure Pattern Extractor
Automatically extract configuration patterns from build failures that were successfully fixed.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

class FailurePatternExtractor:
    """Extract patterns from build failures that were successfully resolved."""

    def __init__(self, ai_client=None, project_dir: Optional[Path] = None):
        """Initialize failure pattern extractor.

        Args:
            ai_client: AIClient instance for LLM-based pattern generation
            project_dir: Path to project directory (for git operations)
        """
        self.ai_client = ai_client
        self.project_dir = project_dir or Path.cwd()
        self.global_patterns_file = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"

    def extract_from_retry(
        self,
        error_details: Dict[str, Any],
        project_dir: Path,
        tech_stack: List[str],
        context_description: str = "Unknown"
    ) -> Optional[Dict[str, Any]]:
        """Extract pattern from a validation failure that was successfully fixed.

        Args:
            error_details: Error details from failed validation
            project_dir: Project directory path
            tech_stack: Detected tech stack
            context_description: Description of what failed

        Returns:
            Pattern dictionary or None if extraction failed
        """
        try:
            print("\n📋 Extracting pattern from successful fix...")

            # Capture git changes (what was fixed)
            git_diff = self._get_git_diff(project_dir)

            if not git_diff or len(git_diff) < 50:
                print("   ⚠️  No significant changes detected, skipping pattern extraction")
                return None

            # Generate pattern using LLM
            if self.ai_client:
                print("   🤖 Analyzing error and fix with LLM...")
                pattern = self._generate_pattern_with_llm(
                    error_details=error_details,
                    git_diff=git_diff,
                    tech_stack=tech_stack,
                    context_description=context_description
                )
            else:
                print("   ⚠️  No AI client available, using template-based extraction...")
                pattern = self._generate_pattern_template(
                    error_details=error_details,
                    git_diff=git_diff,
                    tech_stack=tech_stack,
                    context_description=context_description
                )

            if pattern:
                print(f"   ✅ Pattern generated: {pattern.get('pattern_id')}")
                return pattern
            else:
                print("   ❌ Failed to generate pattern")
                return None

        except Exception as e:
            print(f"   ⚠️  Pattern extraction error: {e}")
            return None

    def _get_git_diff(self, project_dir: Path) -> str:
        """Get git diff of uncommitted changes.

        Args:
            project_dir: Project directory

        Returns:
            Git diff string
        """
        try:
            # Get diff of staged and unstaged changes
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout
            else:
                # Try diff without HEAD (for new repos)
                result = subprocess.run(
                    ["git", "diff"],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.stdout if result.returncode == 0 else ""

        except Exception as e:
            print(f"   Warning: Could not get git diff: {e}")
            return ""

    def _generate_pattern_with_llm(
        self,
        error_details: Dict[str, Any],
        git_diff: str,
        tech_stack: List[str],
        context_description: str
    ) -> Optional[Dict[str, Any]]:
        """Generate pattern using LLM analysis.

        Args:
            error_details: Error information
            git_diff: Git diff of the fix
            tech_stack: Detected technologies
            context_description: What was being validated

        Returns:
            Pattern dictionary or None
        """
        # Build prompt for LLM
        prompt = f"""You are analyzing a build failure that was successfully fixed. Your task is to extract a reusable pattern that can prevent this issue in future builds.

CONTEXT: {context_description}

ERROR INFORMATION:
- Message: {error_details.get('message', 'Unknown')}
- Error Output: {error_details.get('stderr', '')[:500]}
- Exit Code: {error_details.get('exit_code', 'N/A')}

FIX APPLIED (git diff):
{git_diff[:2000]}

TECH STACK: {', '.join(tech_stack)}

Generate a pattern in this EXACT JSON structure:

{{
  "pattern_id": "descriptive-kebab-case-id",
  "title": "Clear Human-Readable Title",
  "severity": "HIGH|MEDIUM|LOW",
  "tech_stack": {json.dumps(tech_stack)},
  "issue": {{
    "description": "What went wrong",
    "error_message": "{error_details.get('message', '')[:100]}",
    "detected_in_phase": "Test|Builder|Architect"
  }},
  "root_cause": "Technical explanation of why this happened",
  "solution": {{
    "architect": {{
      "action": "What architect should specify",
      "specifics": ["Specific action 1", "Specific action 2"]
    }},
    "builder": {{
      "action": "What builder should implement",
      "validation_checklist": ["Check item 1", "Check item 2", "Check item 3"]
    }}
  }},
  "prevention": {{
    "auto_apply": true,
    "actions": ["Builder: Action 1", "Builder: Action 2"]
  }},
  "impact": "Description of impact if not fixed",
  "auto_apply": true
}}

Respond with ONLY the JSON, no other text."""

        try:
            # Call LLM via ai_client
            response = self.ai_client.chat(
                prompt=prompt,
                agent_name="pattern_extractor",
                response_format="json"
            )

            # Parse JSON response
            pattern = json.loads(response)

            # Add metadata
            pattern["first_seen"] = datetime.now().strftime("%Y-%m-%d")
            pattern["last_seen"] = datetime.now().strftime("%Y-%m-%d")
            pattern["frequency"] = 1
            pattern["project_types"] = self._infer_project_types(tech_stack)

            # Add prevention history entry
            pattern["prevention_history"] = [{
                "build": "extracted_from_retry",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "detected_by": "Automated pattern extraction",
                "root_cause_found": pattern.get("root_cause", ""),
                "fix_applied": "See git diff",
                "result": "Validation passed after fix"
            }]

            return pattern

        except Exception as e:
            print(f"   LLM pattern generation failed: {e}")
            return None

    def _generate_pattern_template(
        self,
        error_details: Dict[str, Any],
        git_diff: str,
        tech_stack: List[str],
        context_description: str
    ) -> Dict[str, Any]:
        """Generate pattern using template (fallback when no LLM available).

        Args:
            error_details: Error information
            git_diff: Git diff of the fix
            tech_stack: Detected technologies
            context_description: What was being validated

        Returns:
            Pattern dictionary
        """
        # Extract error type from message
        error_msg = error_details.get('message', 'Unknown error')
        error_type = self._classify_error_type(error_msg)

        # Generate pattern ID from error type + tech stack
        pattern_id = f"{error_type}-{'_'.join(tech_stack[:2])}"
        pattern_id = pattern_id.lower().replace(' ', '-').replace('_', '-')

        return {
            "pattern_id": pattern_id,
            "title": f"{error_type.title()} in {context_description}",
            "severity": "MEDIUM",  # Default to MEDIUM
            "tech_stack": tech_stack,
            "project_types": self._infer_project_types(tech_stack),
            "issue": {
                "description": error_msg,
                "error_message": error_msg,
                "detected_in_phase": "Test"
            },
            "root_cause": "Auto-extracted pattern - needs manual review",
            "solution": {
                "architect": {
                    "action": "Review architecture for this issue",
                    "specifics": ["See git diff for fix details"]
                },
                "builder": {
                    "action": "Apply fix from pattern",
                    "validation_checklist": ["Verify fix resolves the error"]
                }
            },
            "prevention": {
                "auto_apply": False,  # Require manual review for template patterns
                "actions": ["Builder: Review and apply fix from git diff"]
            },
            "impact": "Build failure - see error message",
            "fix_time_estimate": "Unknown",
            "auto_apply": False,  # Template patterns need review
            "first_seen": datetime.now().strftime("%Y-%m-%d"),
            "last_seen": datetime.now().strftime("%Y-%m-%d"),
            "frequency": 1,
            "prevention_history": [{
                "build": "extracted_from_retry",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "detected_by": "Automated pattern extraction (template)",
                "git_diff": git_diff[:500],
                "error": error_msg
            }],
            "notes": "⚠️ AUTO-GENERATED PATTERN - Requires manual review and refinement"
        }

    def _classify_error_type(self, error_message: str) -> str:
        """Classify error type from error message.

        Args:
            error_message: Error message string

        Returns:
            Error type classification
        """
        error_lower = error_message.lower()

        if "module not found" in error_lower or "cannot find module" in error_lower:
            return "module-resolution"
        elif "property" in error_lower and "does not exist" in error_lower:
            return "type-definition"
        elif "cors" in error_lower:
            return "cors-configuration"
        elif "rate limit" in error_lower or "too many requests" in error_lower:
            return "rate-limiting"
        elif "connection refused" in error_lower or "econnrefused" in error_lower:
            return "connection-error"
        elif "syntax error" in error_lower:
            return "syntax-error"
        elif "typescript" in error_lower or "ts(" in error_lower:
            return "typescript-error"
        else:
            return "build-error"

    def _infer_project_types(self, tech_stack: List[str]) -> List[str]:
        """Infer project types from tech stack.

        Args:
            tech_stack: List of technologies

        Returns:
            List of project type tags
        """
        types = []

        # Backend types
        if any(t in tech_stack for t in ["express", "fastapi", "flask", "django"]):
            types.append("nodejs-backend" if "express" in tech_stack else "python-backend")

        # Frontend types
        if any(t in tech_stack for t in ["react", "vue", "angular", "nextjs"]):
            types.append("frontend-app")

        # Fullstack
        if any(t in tech_stack for t in ["nextjs", "express", "fastapi"]):
            types.append("fullstack-app")

        # Language-specific
        if "typescript" in tech_stack:
            types.append("typescript-project")
        if "python" in tech_stack:
            types.append("python-project")

        return types if types else ["general"]

    def save_pattern(
        self,
        pattern: Dict[str, Any],
        autonomous: bool = False
    ) -> bool:
        """Save pattern to global common-issues.json.

        Args:
            pattern: Pattern dictionary
            autonomous: If True, save without prompting user

        Returns:
            True if saved, False otherwise
        """
        try:
            # In autonomous mode or if user approves
            if autonomous or self._prompt_user_review(pattern):
                print(f"   💾 Saving pattern to {self.global_patterns_file}")

                # Load existing patterns
                self.global_patterns_file.parent.mkdir(parents=True, exist_ok=True)

                if self.global_patterns_file.exists():
                    with open(self.global_patterns_file, 'r') as f:
                        data = json.load(f)
                else:
                    data = {
                        "patterns": [],
                        "version": "1.0",
                        "last_updated": datetime.now().isoformat(),
                        "total_builds": 0
                    }

                # Check for duplicate pattern_id
                existing_ids = [p.get("pattern_id") for p in data["patterns"]]
                if pattern["pattern_id"] in existing_ids:
                    print(f"   ⚠️  Pattern '{pattern['pattern_id']}' already exists, incrementing frequency...")
                    # Update existing pattern frequency
                    for p in data["patterns"]:
                        if p.get("pattern_id") == pattern["pattern_id"]:
                            p["frequency"] = p.get("frequency", 1) + 1
                            p["last_seen"] = datetime.now().strftime("%Y-%m-%d")
                            break
                else:
                    # Add new pattern
                    data["patterns"].append(pattern)
                    print(f"   ✅ New pattern added: {pattern['pattern_id']}")

                # Update metadata
                data["last_updated"] = datetime.now().isoformat()
                data["total_builds"] = data.get("total_builds", 0) + 1

                # Save
                with open(self.global_patterns_file, 'w') as f:
                    json.dump(data, f, indent=2)

                print(f"   ✅ Pattern saved! Total patterns: {len(data['patterns'])}")
                print(f"\n   🎯 Next {', '.join(pattern.get('tech_stack', ['similar']))} build will automatically apply this pattern!\n")

                return True
            else:
                print("   ⏭️  Pattern skipped by user")
                return False

        except Exception as e:
            print(f"   ❌ Failed to save pattern: {e}")
            return False

    def _prompt_user_review(self, pattern: Dict[str, Any]) -> bool:
        """Prompt user to review and approve pattern.

        Args:
            pattern: Pattern dictionary

        Returns:
            True if user approves, False otherwise
        """
        print("\n" + "="*70)
        print("📋 NEW PATTERN EXTRACTED FROM BUILD FAILURE")
        print("="*70)
        print(f"\nTitle: {pattern.get('title')}")
        print(f"ID: {pattern.get('pattern_id')}")
        print(f"Severity: {pattern.get('severity')}")
        print(f"Tech Stack: {', '.join(pattern.get('tech_stack', []))}")
        print(f"\nIssue: {pattern.get('issue', {}).get('description', 'N/A')}")
        print(f"\nRoot Cause:\n{pattern.get('root_cause', 'N/A')}")

        # Show builder checklist
        builder_solution = pattern.get('solution', {}).get('builder', {})
        checklist = builder_solution.get('validation_checklist', [])
        if checklist:
            print(f"\nBuilder Checklist:")
            for item in checklist:
                print(f"  - {item}")

        print("\n" + "="*70)

        # Prompt user
        while True:
            response = input("\nSave this pattern? [Y/n/e(dit)]: ").strip().lower()

            if response in ('', 'y', 'yes'):
                return True
            elif response in ('n', 'no'):
                return False
            elif response in ('e', 'edit'):
                print("⚠️  Pattern editing not yet implemented. Saving as-is...")
                return True
            else:
                print("Invalid response. Please enter Y, n, or e.")
