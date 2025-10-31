#!/usr/bin/env python3
"""
Context Budget Check - CLI Tool for Agents

This tool allows agents to check context budget status during builds.
Designed to be called directly from orchestrator_prompt.txt.

Usage:
    python3 tools/check_context_budget.py --phase scout --check-before
    python3 tools/check_context_budget.py --phase builder --tokens 45000
    python3 tools/check_context_budget.py --report
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.context_budget import (
    ContextBudgetMonitor,
    TokenCounter,
    ContextBudgetReporter,
    ContextZone
)


def get_build_context(working_dir: str = '.') -> Dict:
    """
    Extract build identifying information from session files.

    Returns dictionary with build context or empty dict if no session data.
    """
    context = {}
    context_dir = Path(working_dir) / '.context-foundry'

    # Try to load session-summary.json
    session_path = context_dir / 'session-summary.json'
    if session_path.exists():
        try:
            with open(session_path, 'r') as f:
                session = json.load(f)
                context['session_id'] = session.get('session_id', 'unknown')
                context['task'] = session.get('task', 'N/A')
                context['mode'] = session.get('mode', 'N/A')
                context['started_at'] = session.get('started_at', session.get('created_at', 'N/A'))
                context['completed_at'] = session.get('completed_at')
                context['status'] = session.get('status', 'unknown')
                context['github_url'] = session.get('github_url')
                context['pr_number'] = session.get('pr_number')
                context['duration_minutes'] = session.get('duration_minutes')
        except Exception as e:
            print(f"Warning: Failed to read session-summary.json: {e}", file=sys.stderr)

    # Try to load current-phase.json for live status
    phase_path = context_dir / 'current-phase.json'
    if phase_path.exists():
        try:
            with open(phase_path, 'r') as f:
                phase = json.load(f)
                # Update with current phase info if not completed
                if context.get('status') != 'completed':
                    context['current_phase'] = phase.get('current_phase', 'unknown')
                    context['phase_number'] = phase.get('phase_number', 'N/A')
                    context['status'] = phase.get('status', 'unknown')
                    context['progress_detail'] = phase.get('progress_detail')
        except Exception as e:
            print(f"Warning: Failed to read current-phase.json: {e}", file=sys.stderr)

    # Add working directory
    context['working_directory'] = str(Path(working_dir).resolve())

    return context


def print_build_context_header(context: Dict, width: int = 78):
    """
    Print formatted header with build identification.

    Args:
        context: Build context dictionary from get_build_context()
        width: Header width in characters
    """
    if not context:
        print("\nNo active build context found.")
        print("This may be a standalone context budget check.\n")
        return

    # Header
    print("╔" + "═" * (width - 2) + "╗")
    print("║" + "CONTEXT BUDGET - BUILD INFORMATION".center(width - 2) + "║")
    print("╚" + "═" * (width - 2) + "╝")
    print()

    # Session ID
    session_id = context.get('session_id', 'unknown')
    print(f"  Session ID:   {session_id}")

    # Task (truncate if too long)
    task = context.get('task', 'N/A')
    if len(task) > 60:
        task = task[:57] + "..."
    print(f"  Task:         {task}")

    # Mode
    mode = context.get('mode', 'N/A')
    print(f"  Mode:         {mode}")

    # Working directory (show relative to home if possible)
    working_dir = context.get('working_directory', 'N/A')
    home = str(Path.home())
    if working_dir.startswith(home):
        working_dir = '~' + working_dir[len(home):]
    print(f"  Directory:    {working_dir}")

    # Timestamp
    started = context.get('started_at', 'N/A')
    if started != 'N/A' and isinstance(started, str):
        # Try to format timestamp nicely
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
            started = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            pass  # Use raw value
    print(f"  Started:      {started}")

    # Status and phase
    status = context.get('status', 'unknown')
    current_phase = context.get('current_phase')
    phase_number = context.get('phase_number')

    if status == 'completed':
        duration = context.get('duration_minutes')
        if duration:
            print(f"  Status:       Completed ({duration:.1f} minutes)")
        else:
            print(f"  Status:       Completed")
    elif current_phase:
        phase_info = f"Phase {phase_number} ({current_phase})" if phase_number else current_phase
        print(f"  Status:       {status.title()} - {phase_info}")

        # Progress detail if available
        progress = context.get('progress_detail')
        if progress:
            if len(progress) > 50:
                progress = progress[:47] + "..."
            print(f"                {progress}")
    else:
        print(f"  Status:       {status.title()}")

    # GitHub info
    pr_number = context.get('pr_number')
    github_url = context.get('github_url')
    if pr_number and github_url:
        print(f"  GitHub:       PR #{pr_number}")
        print(f"                {github_url}")
    elif github_url:
        print(f"  GitHub:       {github_url}")

    print()


def load_session_summary(working_dir: str = '.') -> Optional[Dict]:
    """Load existing session summary"""
    summary_path = Path(working_dir) / '.context-foundry' / 'session-summary.json'
    if summary_path.exists():
        try:
            with open(summary_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load session summary: {e}", file=sys.stderr)
    return None


def save_session_summary(data: Dict, working_dir: str = '.'):
    """Save updated session summary"""
    summary_path = Path(working_dir) / '.context-foundry' / 'session-summary.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(summary_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error: Failed to save session summary: {e}", file=sys.stderr)
        sys.exit(1)


def estimate_phase_tokens(phase: str, working_dir: str = '.') -> int:
    """Estimate tokens that will be used in upcoming phase"""
    counter = TokenCounter()
    context_dir = Path(working_dir) / '.context-foundry'

    # Estimate based on existing artifacts
    total = 0

    if phase in ['scout', 'architect', 'builder', 'test']:
        # Count existing context files
        if (context_dir / 'scout-report.md').exists():
            total += counter.count_file_tokens(context_dir / 'scout-report.md')
        if (context_dir / 'architecture.md').exists():
            total += counter.count_file_tokens(context_dir / 'architecture.md')

    # Add phase-specific estimates
    estimates = {
        'scout': 14000,        # Typical scout report size
        'architect': 14000,    # Architecture design
        'builder': 40000,      # Code generation
        'test': 40000,         # Test execution + results
        'documentation': 10000,
        'deploy': 6000,
        'feedback': 10000,
    }

    return max(total, estimates.get(phase, 10000))


def check_before_phase(phase: str, working_dir: str = '.') -> int:
    """
    Check budget BEFORE starting a phase (proactive warning).

    Returns exit code: 0 = safe, 1 = warning, 2 = critical
    """
    monitor = ContextBudgetMonitor()

    # Get and display build context
    build_context = get_build_context(working_dir)
    print_build_context_header(build_context)

    # Estimate tokens for upcoming phase
    estimated_tokens = estimate_phase_tokens(phase, working_dir)

    # Check against budget
    analysis = monitor.check_phase(phase, estimated_tokens)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  Context Budget Pre-Check: {phase.upper():15}        ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print()
    print(f"Estimated tokens: {estimated_tokens:,}")
    print(f"Budget allocated: {analysis.budget_allocated:,}")
    print(f"Context usage:    {analysis.percentage:.1f}% of 200K window")
    print(f"Performance zone: {analysis.zone.value.upper()}")
    print()

    # Show warnings
    if analysis.warnings:
        print("⚠️  WARNINGS:")
        for warning in analysis.warnings:
            print(f"  • {warning}")
        print()

    # Show recommendations
    if analysis.recommendations:
        print("💡 RECOMMENDATIONS:")
        for rec in analysis.recommendations:
            print(f"  • {rec}")
        print()

    # Determine exit code
    if analysis.zone == ContextZone.CRITICAL:
        print("🚨 CRITICAL: Consider using sub-agent to avoid context overflow")
        return 2
    elif analysis.zone == ContextZone.DUMB:
        print("⚠️  WARNING: Approaching dumb zone - model performance may degrade")
        return 1
    else:
        print("✅ SAFE: Operating in smart zone for optimal performance")
        return 0


def record_phase_actual(phase: str, tokens: int, working_dir: str = '.') -> int:
    """
    Record actual token usage after phase completes.
    Updates session-summary.json.

    Returns exit code: 0 = success
    """
    monitor = ContextBudgetMonitor()

    # Get and display build context
    build_context = get_build_context(working_dir)
    print_build_context_header(build_context)

    # Analyze phase
    analysis = monitor.check_phase(phase, tokens)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  Context Budget Report: {phase.upper():18}        ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print()
    print(f"Actual tokens used: {tokens:,}")
    print(f"Budget allocated:   {analysis.budget_allocated:,}")
    print(f"Context usage:      {analysis.percentage:.1f}%")
    print(f"Performance zone:   {analysis.zone.value.upper()}")

    if analysis.budget_exceeded_by > 0:
        print(f"Budget exceeded by: {analysis.budget_exceeded_by:,} tokens")
    else:
        print(f"Budget remaining:   {analysis.budget_remaining:,} tokens")

    print()

    # Show warnings/recommendations
    if analysis.warnings:
        print("⚠️  WARNINGS:")
        for warning in analysis.warnings:
            print(f"  • {warning}")
        print()

    if analysis.recommendations:
        print("💡 RECOMMENDATIONS:")
        for rec in analysis.recommendations:
            print(f"  • {rec}")
        print()

    # Update session summary
    session = load_session_summary(working_dir) or {}

    if 'context_metrics' not in session:
        session['context_metrics'] = monitor.export_to_session_summary()
    else:
        # Merge with existing
        session['context_metrics']['by_phase'][f'phase_{phase}'] = analysis.to_dict()
        session['context_metrics']['overall'] = monitor.get_overall_stats()

    save_session_summary(session, working_dir)

    return 0


def generate_report(working_dir: str = '.') -> int:
    """Generate full context budget report"""
    session = load_session_summary(working_dir)

    if not session or 'context_metrics' not in session:
        print("No context metrics available yet.")
        print("Run phases with --tokens flag to collect data.")
        return 1

    # Get and display build context
    build_context = get_build_context(working_dir)
    print_build_context_header(build_context)

    reporter = ContextBudgetReporter()
    report = reporter.generate_context_report(session['context_metrics'])

    print(report)
    print()

    # Visualization
    viz = reporter.visualize_context_usage(session['context_metrics'])
    print(viz)
    print()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Context Budget Monitoring for Context Foundry',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check budget before starting phase
  python3 tools/check_context_budget.py --phase scout --check-before

  # Record actual usage after phase
  python3 tools/check_context_budget.py --phase scout --tokens 12000

  # Generate full report
  python3 tools/check_context_budget.py --report
        """
    )

    parser.add_argument('--phase', help='Phase name (scout, architect, builder, test, etc.)')
    parser.add_argument('--tokens', type=int, help='Actual token count (for recording)')
    parser.add_argument('--check-before', action='store_true',
                       help='Check budget BEFORE phase starts (proactive)')
    parser.add_argument('--report', action='store_true', help='Generate full report')
    parser.add_argument('--working-dir', default='.', help='Working directory')

    args = parser.parse_args()

    # Validate arguments
    if args.report:
        return generate_report(args.working_dir)

    if not args.phase:
        parser.error('--phase required (unless using --report)')

    if args.check_before:
        return check_before_phase(args.phase, args.working_dir)
    elif args.tokens is not None:
        return record_phase_actual(args.phase, args.tokens, args.working_dir)
    else:
        parser.error('Either --check-before or --tokens required')


if __name__ == '__main__':
    sys.exit(main())
