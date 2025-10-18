#!/usr/bin/env python3
"""
Observability for multi-agent workflows.

Track:
- Agent decision patterns
- Token usage per phase
- Success/failure rates
- Performance metrics

Based on Anthropic: "Adding full production tracing let us
diagnose why agents failed and fix issues systematically."
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class WorkflowObserver:
    """
    Tracks metrics and patterns across agent workflows.
    """

    def __init__(self, session_dir: Path):
        """Initialize workflow observer.

        Args:
            session_dir: Directory for this session
        """
        self.session_dir = Path(session_dir)
        self.metrics_file = self.session_dir / 'metrics.jsonl'
        self.events = []
        self.phase_start_times = {}

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event with timestamp.

        Args:
            event_type: Type of event
            data: Event data
        """

        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data
        }

        self.events.append(event)

        # Append to JSONL file
        with open(self.metrics_file, 'a') as f:
            f.write(json.dumps(event) + '\n')

    def log_phase_start(self, phase: str, details: Optional[Dict] = None):
        """Log phase start.

        Args:
            phase: Phase name
            details: Optional phase details
        """
        self.phase_start_times[phase] = datetime.now()

        self.log_event('phase_start', {
            'phase': phase,
            **(details or {})
        })

        print(f"\n📊 Phase {phase} started")

    def log_phase_complete(self, phase: str, metrics: Dict[str, Any]):
        """Log phase completion with metrics.

        Args:
            phase: Phase name
            metrics: Phase metrics
        """

        # Calculate duration
        if phase in self.phase_start_times:
            start_time = self.phase_start_times[phase]
            duration = (datetime.now() - start_time).total_seconds()
            metrics['duration_seconds'] = duration

        self.log_event('phase_complete', {
            'phase': phase,
            **metrics
        })

        print(f"📊 Phase {phase} completed")
        if 'duration_seconds' in metrics:
            print(f"   Duration: {metrics['duration_seconds']:.1f}s")
        if 'token_usage' in metrics:
            print(f"   Tokens: {metrics['token_usage']:,}")

    def log_validation_result(self, validation_type: str, result: Dict[str, Any]):
        """Log validation attempt.

        Args:
            validation_type: Type of validation
            result: Validation result
        """
        self.log_event('validation', {
            'type': validation_type,
            'passed': result.get('passed', False),
            'error': result.get('error'),
            'attempt': result.get('attempt', 1)
        })

    def log_subagent_result(self, subagent_id: str, result: Dict[str, Any]):
        """Log individual subagent result.

        Args:
            subagent_id: Subagent ID
            result: Subagent result
        """
        self.log_event('subagent_complete', {
            'subagent_id': subagent_id,
            'success': result.get('success', False),
            'token_usage': result.get('token_usage', 0),
            'files_written': len(result.get('files_written', []))
        })

    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary of workflow metrics.

        Returns:
            Summary dictionary
        """

        summary = {
            'total_events': len(self.events),
            'phases': {},
            'validations': {
                'total': 0,
                'passed': 0,
                'failed': 0
            },
            'token_usage': {
                'total': 0
            },
            'subagents': {
                'total': 0,
                'successful': 0,
                'failed': 0
            }
        }

        for event in self.events:
            event_type = event['type']
            data = event['data']

            if event_type == 'phase_complete':
                phase = data['phase']
                summary['phases'][phase] = {
                    'duration': data.get('duration_seconds', 0),
                    'tokens': data.get('token_usage', 0),
                    'success': data.get('success', True)
                }

                tokens = data.get('token_usage', 0)
                summary['token_usage']['total'] += tokens
                summary['token_usage'][phase] = tokens

            elif event_type == 'validation':
                summary['validations']['total'] += 1
                if data.get('passed'):
                    summary['validations']['passed'] += 1
                else:
                    summary['validations']['failed'] += 1

            elif event_type == 'subagent_complete':
                summary['subagents']['total'] += 1
                if data.get('success'):
                    summary['subagents']['successful'] += 1
                else:
                    summary['subagents']['failed'] += 1

        return summary

    def print_summary(self):
        """Print formatted summary."""

        summary = self.generate_summary()

        print("\n" + "="*60)
        print("📊 WORKFLOW SUMMARY")
        print("="*60)

        # Phases
        print("\n🔄 Phases:")
        for phase, metrics in summary['phases'].items():
            duration = metrics.get('duration', 0)
            tokens = metrics.get('tokens', 0)
            success = "✅" if metrics.get('success', True) else "❌"
            print(f"   {success} {phase}: {duration:.1f}s, {tokens:,} tokens")

        # Token usage
        print(f"\n💰 Total tokens: {summary['token_usage']['total']:,}")

        # Subagents
        if summary['subagents']['total'] > 0:
            success_rate = (summary['subagents']['successful'] / summary['subagents']['total']) * 100
            print(f"\n🤖 Subagents: {summary['subagents']['successful']}/{summary['subagents']['total']} succeeded ({success_rate:.1f}%)")

        # Validations
        if summary['validations']['total'] > 0:
            print(f"\n✅ Validations: {summary['validations']['passed']}/{summary['validations']['total']} passed")

        print("\n" + "="*60)

    def export_metrics(self, output_file: Optional[Path] = None) -> Path:
        """Export metrics to JSON file.

        Args:
            output_file: Optional output file path

        Returns:
            Path to exported file
        """

        if output_file is None:
            output_file = self.session_dir / 'metrics_summary.json'

        summary = self.generate_summary()

        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"📊 Metrics exported to {output_file}")

        return output_file
