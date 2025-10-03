#!/usr/bin/env python3
"""
Session Analyzer
Post-run analysis and continuous improvement metrics.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from foundry.patterns.pattern_manager import PatternLibrary


class SessionAnalyzer:
    """Analyze completed sessions for metrics and improvements."""

    def __init__(self, pattern_library: Optional[PatternLibrary] = None):
        """Initialize session analyzer.

        Args:
            pattern_library: Optional PatternLibrary instance
        """
        self.library = pattern_library

    def analyze(self, session_id: str, checkpoints_dir: Path = None) -> Dict:
        """Analyze completed session.

        Args:
            session_id: Session identifier
            checkpoints_dir: Path to checkpoints directory

        Returns:
            Metrics dictionary
        """
        if checkpoints_dir is None:
            checkpoints_dir = Path.home() / "context-foundry" / "checkpoints" / "ralph"

        session_dir = checkpoints_dir / session_id

        if not session_dir.exists():
            print(f"❌ Session not found: {session_dir}")
            return {}

        print(f"📊 Analyzing session: {session_id}")

        metrics = {
            'session_id': session_id,
            'completion': self._calculate_completion_rate(session_dir),
            'context': self._analyze_context_efficiency(session_dir),
            'time': self._analyze_time_metrics(session_dir),
            'tokens': self._analyze_token_usage(session_dir),
            'cost': self._calculate_cost(session_dir),
            'patterns': self._analyze_pattern_usage(session_id) if self.library else {}
        }

        # Generate report
        report_path = self._generate_report(session_id, metrics, session_dir)
        metrics['report_path'] = str(report_path)

        # Update pattern ratings if library available
        if self.library:
            self._update_pattern_ratings(session_id, metrics)

        return metrics

    def _calculate_completion_rate(self, session_dir: Path) -> Dict:
        """Calculate task completion rate.

        Args:
            session_dir: Path to session directory

        Returns:
            Completion metrics
        """
        progress_file = session_dir / "progress.json"

        if not progress_file.exists():
            return {'rate': 0.0, 'completed': 0, 'total': 0}

        with open(progress_file) as f:
            progress = json.load(f)

        completed = len(progress.get('completed', []))
        remaining = len(progress.get('remaining', []))
        total = completed + remaining

        return {
            'rate': (completed / total * 100) if total > 0 else 0.0,
            'completed': completed,
            'total': total,
            'remaining': remaining
        }

    def _analyze_context_efficiency(self, session_dir: Path) -> Dict:
        """Analyze context usage efficiency.

        Args:
            session_dir: Path to session directory

        Returns:
            Context metrics
        """
        # Read state.json for context data
        state_file = session_dir / "state.json"

        if not state_file.exists():
            return {'average': 0.0, 'max': 0.0, 'compactions': 0}

        with open(state_file) as f:
            state = json.load(f)

        # Parse iterations for context percentages
        iterations_dir = session_dir / "iterations"
        context_values = []
        compactions = 0

        if iterations_dir.exists():
            for iter_file in sorted(iterations_dir.glob("iteration_*.json")):
                try:
                    with open(iter_file) as f:
                        iter_data = json.load(f)
                        context_pct = iter_data.get('context_percent', 0)
                        context_values.append(context_pct)

                        if iter_data.get('compacted', False):
                            compactions += 1
                except Exception:
                    continue

        if not context_values:
            context_values = [state.get('context_percent', 0)]

        return {
            'average': sum(context_values) / len(context_values) if context_values else 0.0,
            'max': max(context_values) if context_values else 0.0,
            'min': min(context_values) if context_values else 0.0,
            'compactions': compactions
        }

    def _analyze_time_metrics(self, session_dir: Path) -> Dict:
        """Analyze time metrics.

        Args:
            session_dir: Path to session directory

        Returns:
            Time metrics
        """
        state_file = session_dir / "state.json"

        if not state_file.exists():
            return {'total_minutes': 0.0, 'avg_per_task': 0.0}

        with open(state_file) as f:
            state = json.load(f)

        start_time = state.get('start_time')
        end_time = state.get('end_time')

        if not start_time:
            return {'total_minutes': 0.0, 'avg_per_task': 0.0}

        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time) if end_time else datetime.now()

        total_seconds = (end_dt - start_dt).total_seconds()
        total_minutes = total_seconds / 60

        # Calculate avg per task
        progress_file = session_dir / "progress.json"
        tasks_completed = 0
        if progress_file.exists():
            with open(progress_file) as f:
                progress = json.load(f)
                tasks_completed = len(progress.get('completed', []))

        avg_per_task = total_minutes / tasks_completed if tasks_completed > 0 else 0.0

        return {
            'total_minutes': total_minutes,
            'total_hours': total_minutes / 60,
            'avg_per_task': avg_per_task,
            'tasks_completed': tasks_completed
        }

    def _analyze_token_usage(self, session_dir: Path) -> Dict:
        """Analyze token usage.

        Args:
            session_dir: Path to session directory

        Returns:
            Token metrics
        """
        state_file = session_dir / "state.json"

        if not state_file.exists():
            return {'total': 0, 'per_task': 0}

        with open(state_file) as f:
            state = json.load(f)

        total_tokens = state.get('total_tokens', 0)

        # Get task count
        progress_file = session_dir / "progress.json"
        tasks_completed = 0
        if progress_file.exists():
            with open(progress_file) as f:
                progress = json.load(f)
                tasks_completed = len(progress.get('completed', []))

        return {
            'total': total_tokens,
            'per_task': total_tokens // tasks_completed if tasks_completed > 0 else 0,
            'input': state.get('input_tokens', 0),
            'output': state.get('output_tokens', 0)
        }

    def _calculate_cost(self, session_dir: Path) -> float:
        """Calculate estimated API cost.

        Args:
            session_dir: Path to session directory

        Returns:
            Cost in USD
        """
        tokens = self._analyze_token_usage(session_dir)

        # Claude Sonnet 4 pricing (approximate)
        input_cost_per_1k = 0.003
        output_cost_per_1k = 0.015

        input_tokens = tokens.get('input', 0)
        output_tokens = tokens.get('output', 0)

        cost = (input_tokens / 1000 * input_cost_per_1k) + \
               (output_tokens / 1000 * output_cost_per_1k)

        return cost

    def _analyze_pattern_usage(self, session_id: str) -> Dict:
        """Analyze pattern usage and effectiveness.

        Args:
            session_id: Session identifier

        Returns:
            Pattern usage metrics
        """
        if not self.library:
            return {}

        # Query pattern usage for this session
        usage = self.library.db.execute(
            """SELECT p.id, p.description, pu.rating, p.usage_count, p.success_count
               FROM pattern_usage pu
               JOIN patterns p ON pu.pattern_id = p.id
               WHERE pu.session_id = ?""",
            (session_id,)
        ).fetchall()

        if not usage:
            return {'patterns_used': 0, 'top': []}

        patterns_used = len(usage)
        avg_rating = sum(u[2] for u in usage) / len(usage)

        # Get top patterns
        top = []
        for p_id, desc, rating, usage_count, success_count in usage[:5]:
            success_rate = (success_count / usage_count * 100) if usage_count > 0 else 0
            top.append({
                'id': p_id,
                'name': desc,
                'rating': rating,
                'success_rate': success_rate
            })

        return {
            'patterns_used': patterns_used,
            'avg_rating': avg_rating,
            'top': top
        }

    def _update_pattern_ratings(self, session_id: str, metrics: Dict):
        """Update pattern ratings based on session success.

        Args:
            session_id: Session identifier
            metrics: Session metrics
        """
        if not self.library:
            return

        completion_rate = metrics['completion']['rate']

        # Determine rating based on completion
        if completion_rate >= 90:
            rating = 5
        elif completion_rate >= 70:
            rating = 4
        elif completion_rate >= 50:
            rating = 3
        elif completion_rate >= 30:
            rating = 2
        else:
            rating = 1

        # Update all patterns used in this session
        patterns = self.library.db.execute(
            "SELECT DISTINCT pattern_id FROM pattern_usage WHERE session_id = ?",
            (session_id,)
        ).fetchall()

        for (pattern_id,) in patterns:
            self.library.rate_pattern(pattern_id, rating, session_id)

    def _generate_report(self, session_id: str, metrics: Dict, session_dir: Path) -> Path:
        """Generate Markdown report.

        Args:
            session_id: Session identifier
            metrics: Metrics dictionary
            session_dir: Session directory path

        Returns:
            Path to generated report
        """
        report = f"""# Session Analysis: {session_id}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Completion Rate**: {metrics['completion']['rate']:.1f}%
- **Tasks Completed**: {metrics['completion']['completed']}/{metrics['completion']['total']}
- **Total Time**: {metrics['time']['total_hours']:.1f} hours
- **Total Cost**: ${metrics['cost']:.2f}

## Performance Metrics

### Context Usage
- **Average**: {metrics['context']['average']:.1f}%
- **Maximum**: {metrics['context']['max']:.1f}%
- **Minimum**: {metrics['context']['min']:.1f}%
- **Compactions**: {metrics['context']['compactions']}

### Time
- **Total Duration**: {metrics['time']['total_minutes']:.1f} minutes ({metrics['time']['total_hours']:.1f} hours)
- **Avg per Task**: {metrics['time']['avg_per_task']:.1f} minutes
- **Tasks Completed**: {metrics['time']['tasks_completed']}

### Tokens
- **Total Tokens**: {metrics['tokens']['total']:,}
- **Input Tokens**: {metrics['tokens']['input']:,}
- **Output Tokens**: {metrics['tokens']['output']:,}
- **Tokens per Task**: {metrics['tokens']['per_task']:,}

### Cost
- **Total Cost**: ${metrics['cost']:.2f}
- **Cost per Task**: ${metrics['cost'] / metrics['completion']['completed'] if metrics['completion']['completed'] > 0 else 0:.2f}

"""

        # Add pattern usage if available
        if metrics['patterns']:
            report += f"""## Pattern Usage

- **Patterns Used**: {metrics['patterns'].get('patterns_used', 0)}
- **Avg Rating**: {metrics['patterns'].get('avg_rating', 0):.1f}/5

### Top Patterns
"""
            for pattern in metrics['patterns'].get('top', []):
                report += f"- Pattern #{pattern['id']}: {pattern['name']} ({pattern['success_rate']:.0f}% success, rating: {pattern['rating']}/5)\n"

        # Add recommendations
        report += f"""
## Recommendations

"""
        if metrics['context']['average'] > 40:
            report += "- ⚠️ **High Context Usage**: Average context usage is above 40%. Consider more aggressive compaction.\n"

        if metrics['context']['compactions'] > 5:
            report += "- ⚠️ **Frequent Compactions**: Consider chunking tasks into smaller units.\n"

        if metrics['completion']['rate'] < 70:
            report += "- ⚠️ **Low Completion Rate**: Review task complexity and time allocation.\n"

        if metrics['time']['avg_per_task'] > 30:
            report += "- ⚠️ **Long Task Duration**: Tasks taking >30min on average. Consider breaking down further.\n"

        # Save report
        report_file = session_dir / f"{session_id}_analysis.md"
        report_file.write_text(report)

        return report_file


def main():
    """CLI for session analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze session metrics")
    parser.add_argument("session_id", help="Session identifier")
    parser.add_argument("--checkpoints", default=None, help="Checkpoints directory")
    parser.add_argument("--patterns-db", default=None, help="Pattern library database")
    parser.add_argument("--recent", type=int, default=0, help="Analyze N recent sessions")
    parser.add_argument("--compare", nargs=2, metavar=('SESSION1', 'SESSION2'), help="Compare two sessions")

    args = parser.parse_args()

    # Initialize pattern library if specified
    lib = None
    if args.patterns_db:
        lib = PatternLibrary(db_path=args.patterns_db)

    analyzer = SessionAnalyzer(pattern_library=lib)

    # Handle recent sessions
    if args.recent > 0:
        checkpoints_dir = Path(args.checkpoints) if args.checkpoints else \
                         Path.home() / "context-foundry" / "checkpoints" / "ralph"

        sessions = sorted(checkpoints_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        sessions = [s for s in sessions if s.is_dir()][:args.recent]

        print(f"📊 Analyzing {len(sessions)} recent sessions...\n")

        for session_dir in sessions:
            metrics = analyzer.analyze(session_dir.name, checkpoints_dir)
            print(f"✅ {session_dir.name}: {metrics['completion']['rate']:.0f}% complete, ${metrics['cost']:.2f}")

        if lib:
            lib.close()
        return 0

    # Handle comparison
    if args.compare:
        checkpoints_dir = Path(args.checkpoints) if args.checkpoints else \
                         Path.home() / "context-foundry" / "checkpoints" / "ralph"

        session1, session2 = args.compare
        metrics1 = analyzer.analyze(session1, checkpoints_dir)
        metrics2 = analyzer.analyze(session2, checkpoints_dir)

        print(f"\n📊 Comparison: {session1} vs {session2}\n")
        print(f"Completion:  {metrics1['completion']['rate']:.1f}% vs {metrics2['completion']['rate']:.1f}%")
        print(f"Time:        {metrics1['time']['total_hours']:.1f}h vs {metrics2['time']['total_hours']:.1f}h")
        print(f"Cost:        ${metrics1['cost']:.2f} vs ${metrics2['cost']:.2f}")
        print(f"Context Avg: {metrics1['context']['average']:.1f}% vs {metrics2['context']['average']:.1f}%")

        if lib:
            lib.close()
        return 0

    # Single session analysis
    checkpoints_dir = Path(args.checkpoints) if args.checkpoints else None
    metrics = analyzer.analyze(args.session_id, checkpoints_dir)

    if metrics:
        print(f"\n✅ Analysis complete!")
        print(f"📄 Report: {metrics['report_path']}")

    if lib:
        lib.close()

    return 0


if __name__ == "__main__":
    exit(main())
