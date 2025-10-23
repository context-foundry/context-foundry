#!/usr/bin/env python3
"""
Incremental Pattern Updater - Extracts and merges patterns in real-time during builds.

This enables the system to learn from mistakes immediately and apply fixes
in the same build, rather than waiting until the end.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class IncrementalPatternUpdater:
    """
    Extracts patterns from phase results and merges them immediately.

    Expected impact: 10-15% speedup by preventing repeated mistakes within same build.
    """

    def __init__(self, pattern_db_path: Optional[Path] = None):
        """
        Initialize incremental pattern updater.

        Args:
            pattern_db_path: Path to pattern database (default: ~/.context-foundry/patterns/)
        """
        if pattern_db_path is None:
            pattern_db_path = Path.home() / ".context-foundry" / "patterns" / "common-issues.json"

        self.pattern_db_path = pattern_db_path
        self.pattern_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing patterns
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[str, Any]:
        """Load existing pattern database."""
        if self.pattern_db_path.exists():
            try:
                with open(self.pattern_db_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"   ⚠️  Failed to load patterns: {e}")
                return {"patterns": {}, "total_builds": 0, "last_updated": None}
        else:
            return {"patterns": {}, "total_builds": 0, "last_updated": None}

    def _save_patterns(self):
        """Save pattern database to disk."""
        try:
            self.patterns["last_updated"] = datetime.now().isoformat()
            with open(self.pattern_db_path, 'w') as f:
                json.dump(self.patterns, f, indent=2)
        except Exception as e:
            print(f"   ⚠️  Failed to save patterns: {e}")

    def extract_patterns_from_scout(self, scout_result: Any) -> List[Dict[str, Any]]:
        """
        Extract insights and patterns from Scout research results.

        Args:
            scout_result: PhaseResult from Scout phase

        Returns:
            List of extracted patterns
        """
        new_patterns = []

        if not scout_result or not hasattr(scout_result, 'subagent_results'):
            return new_patterns

        for result in scout_result.subagent_results:
            if not result.success or not result.findings:
                continue

            findings = result.findings.lower()

            # Pattern: CORS / ES6 module issues
            if 'cors' in findings and ('es6' in findings or 'module' in findings):
                new_patterns.append({
                    "pattern_id": "cors-es6-modules",
                    "issue": "Browser blocks ES6 module imports from file://",
                    "solution": {
                        "scout": "Flag CORS risk in scout-report.md",
                        "architect": "Include http-server in architecture",
                        "builder": "Add http-server to devDependencies"
                    },
                    "severity": "HIGH",
                    "detected_phase": "scout",
                    "confidence": 0.8
                })

            # Pattern: Rate limiting in development
            if 'rate' in findings and 'limit' in findings and 'dev' in findings:
                new_patterns.append({
                    "pattern_id": "rate-limiting-dev-mode",
                    "issue": "API rate limiting affects development workflow",
                    "solution": {
                        "scout": "Research rate limiting requirements",
                        "architect": "Design rate limiting with dev mode bypass",
                        "builder": "Implement conditional rate limiting"
                    },
                    "severity": "MEDIUM",
                    "detected_phase": "scout",
                    "confidence": 0.7
                })

        return new_patterns

    def extract_patterns_from_test_failure(self, test_result: Dict[str, Any], error_details: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract patterns from test failures.

        Args:
            test_result: Test execution result
            error_details: Optional error details/stack trace

        Returns:
            List of extracted patterns
        """
        new_patterns = []

        if not test_result or test_result.get('success'):
            return new_patterns

        error_text = (error_details or "").lower()
        output_text = test_result.get('output', '').lower()
        combined_text = error_text + " " + output_text

        # Pattern: Input buffer timing issues
        if ('input' in combined_text or 'key' in combined_text) and ('timing' in combined_text or 'buffer' in combined_text):
            new_patterns.append({
                "pattern_id": "input-buffer-timing",
                "issue": "Single-frame input detection incompatible with test timing",
                "solution": {
                    "architect": "Design 150ms input buffer with timestamp expiration",
                    "builder": "Implement buffered input handling",
                    "test": "Add input timing assertions"
                },
                "severity": "HIGH",
                "detected_phase": "test",
                "confidence": 0.9
            })

        # Pattern: Async timing issues
        if 'timeout' in combined_text and ('async' in combined_text or 'promise' in combined_text):
            new_patterns.append({
                "pattern_id": "async-timeout",
                "issue": "Async operations timing out in tests",
                "solution": {
                    "architect": "Design with proper promise handling",
                    "builder": "Add timeout configurations",
                    "test": "Increase timeout or fix async logic"
                },
                "severity": "MEDIUM",
                "detected_phase": "test",
                "confidence": 0.8
            })

        # Pattern: Database connection issues
        if 'database' in combined_text and ('connection' in combined_text or 'connect' in combined_text):
            new_patterns.append({
                "pattern_id": "database-connection-test",
                "issue": "Database connection failures in test environment",
                "solution": {
                    "architect": "Design test database setup/teardown",
                    "builder": "Implement database fixtures",
                    "test": "Add connection retry logic"
                },
                "severity": "HIGH",
                "detected_phase": "test",
                "confidence": 0.85
            })

        return new_patterns

    def merge_patterns(self, new_patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge new patterns into global database immediately.

        Args:
            new_patterns: List of newly discovered patterns

        Returns:
            Dict with merge statistics
        """
        if not new_patterns:
            return {"new_patterns": 0, "updated_patterns": 0}

        new_count = 0
        updated_count = 0

        for pattern in new_patterns:
            pattern_id = pattern.get('pattern_id')
            if not pattern_id:
                continue

            # Check if pattern already exists
            if pattern_id in self.patterns.get('patterns', {}):
                # Update existing pattern (increase frequency)
                existing = self.patterns['patterns'][pattern_id]
                existing['frequency'] = existing.get('frequency', 1) + 1
                existing['last_seen'] = datetime.now().isoformat()

                # Update confidence if new confidence is higher
                if pattern.get('confidence', 0) > existing.get('confidence', 0):
                    existing['confidence'] = pattern['confidence']

                updated_count += 1
            else:
                # Add new pattern
                pattern['frequency'] = 1
                pattern['first_seen'] = datetime.now().isoformat()
                pattern['last_seen'] = datetime.now().isoformat()

                if 'patterns' not in self.patterns:
                    self.patterns['patterns'] = {}

                self.patterns['patterns'][pattern_id] = pattern
                new_count += 1

        # Save to disk
        self._save_patterns()

        stats = {
            "new_patterns": new_count,
            "updated_patterns": updated_count,
            "total_patterns": len(self.patterns.get('patterns', {}))
        }

        if new_count > 0 or updated_count > 0:
            print(f"   📚 Pattern database updated: +{new_count} new, ~{updated_count} updated (total: {stats['total_patterns']})")

        return stats

    def get_relevant_patterns(self, phase: str, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get patterns relevant to current phase.

        Args:
            phase: Current phase ('scout', 'architect', 'builder', 'test')
            context: Optional context string to filter patterns

        Returns:
            List of relevant patterns sorted by severity and frequency
        """
        relevant = []

        for pattern_id, pattern in self.patterns.get('patterns', {}).items():
            # Check if pattern has solution for this phase
            if phase in pattern.get('solution', {}):
                # Filter by context if provided
                if context:
                    context_lower = context.lower()
                    if any(keyword in context_lower for keyword in pattern.get('keywords', [])):
                        relevant.append(pattern)
                    elif context_lower in str(pattern).lower():
                        relevant.append(pattern)
                else:
                    relevant.append(pattern)

        # Sort by severity and frequency
        severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        relevant.sort(
            key=lambda p: (
                severity_order.get(p.get('severity', 'LOW'), 0),
                p.get('frequency', 0),
                p.get('confidence', 0)
            ),
            reverse=True
        )

        return relevant

    def format_patterns_for_prompt(self, phase: str, context: Optional[str] = None) -> str:
        """
        Format relevant patterns for inclusion in LLM prompt.

        Args:
            phase: Current phase
            context: Optional context

        Returns:
            Formatted string for prompt inclusion
        """
        patterns = self.get_relevant_patterns(phase, context)

        if not patterns:
            return ""

        lines = ["\n## 📚 Lessons from Previous Builds"]
        lines.append(f"\nApplying {len(patterns)} patterns from global knowledge base:\n")

        for i, pattern in enumerate(patterns[:10], 1):  # Limit to top 10
            severity_icon = {
                'CRITICAL': '🔴',
                'HIGH': '🟠',
                'MEDIUM': '🟡',
                'LOW': '🟢'
            }.get(pattern.get('severity', 'LOW'), '⚪')

            lines.append(f"{i}. {severity_icon} **{pattern.get('pattern_id')}** (seen {pattern.get('frequency', 1)}x)")
            lines.append(f"   Issue: {pattern.get('issue', 'Unknown')}")
            lines.append(f"   Solution: {pattern.get('solution', {}).get(phase, 'See full pattern')}")
            lines.append("")

        return "\n".join(lines)
