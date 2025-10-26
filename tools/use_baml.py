#!/usr/bin/env python3
"""
BAML Integration Wrapper for Context Foundry Orchestrator

This script provides a simple CLI interface for the orchestrator to use BAML
type-safe LLM outputs. It gracefully falls back to JSON mode if BAML is unavailable
or if API keys are not configured.

Usage:
    python3 tools/use_baml.py update-phase Scout researching "Analyzing requirements" --session-id my-project
    python3 tools/use_baml.py scout-report "Build a web app" "New project, no codebase"
    python3 tools/use_baml.py architecture "{scout_json}" '["risk1", "risk2"]'

Environment Variables Required:
    OPENAI_API_KEY - For GPT models (Context Foundry uses GPT-4o-mini for BAML)
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.baml_integration import (
    is_baml_available,
    update_phase_with_baml,
    generate_scout_report_baml,
    generate_architecture_baml,
    validate_build_result_baml,
    get_baml_error,
    clear_baml_cache
)


def main():
    parser = argparse.ArgumentParser(
        description="BAML Integration CLI for Context Foundry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Status command
    subparsers.add_parser('status', help='Check BAML integration status')

    # Update phase command
    phase_parser = subparsers.add_parser('update-phase', help='Update phase tracking with BAML')
    phase_parser.add_argument('phase', help='Phase name (Scout, Architect, Builder, etc.)')
    phase_parser.add_argument('status', help='Phase status (researching, designing, etc.)')
    phase_parser.add_argument('detail', help='Progress detail message')
    phase_parser.add_argument('--session-id', default='context-foundry', help='Session ID')
    phase_parser.add_argument('--iteration', type=int, default=0, help='Test iteration number')

    # Scout report command
    scout_parser = subparsers.add_parser('scout-report', help='Generate Scout report with BAML')
    scout_parser.add_argument('task', help='Task description')
    scout_parser.add_argument('codebase', help='Codebase analysis content')
    scout_parser.add_argument('--patterns', default='', help='Past patterns to consider')

    # Architecture command
    arch_parser = subparsers.add_parser('architecture', help='Generate architecture with BAML')
    arch_parser.add_argument('scout_json', help='Scout report JSON string')
    arch_parser.add_argument('risks', help='JSON array of flagged risks')

    # Validate build result command
    build_parser = subparsers.add_parser('validate-build', help='Validate build result with BAML')
    build_parser.add_argument('result_json', help='Build result JSON string')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Status command
    if args.command == 'status':
        if is_baml_available():
            print("✅ BAML is available and ready to use")
            print("\nAPI Keys configured:")
            import os
            print(f"  OPENAI_API_KEY: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
            return 0
        else:
            print(f"❌ BAML is not available: {get_baml_error()}")
            return 1

    # Update phase command
    elif args.command == 'update-phase':
        # Clear cache to pick up any new environment variables
        clear_baml_cache()

        # Normalize status to capitalized form for BAML compatibility
        # BAML enums require capitalized values (Researching not researching)
        status_map = {
            'analyzing': 'Analyzing',
            'researching': 'Researching',
            'designing': 'Designing',
            'building': 'Building',
            'testing': 'Testing',
            'self-healing': 'SelfHealing',
            'capturing': 'Capturing',
            'documenting': 'Documenting',
            'deploying': 'Deploying',
            'completed': 'Completed',
            'failed': 'Failed'
        }

        # Normalize the status input
        normalized_status = status_map.get(args.status.lower(), args.status)

        result = update_phase_with_baml(
            phase=args.phase,
            status=normalized_status,
            detail=args.detail,
            session_id=args.session_id,
            iteration=args.iteration
        )
        print(json.dumps(result, indent=2))
        return 0

    # Scout report command
    elif args.command == 'scout-report':
        result = generate_scout_report_baml(
            task_description=args.task,
            codebase_analysis=args.codebase,
            past_patterns=args.patterns
        )
        if result:
            print(json.dumps(result, indent=2))
            return 0
        else:
            print("BAML Scout report generation not available (falling back to orchestrator's method)")
            return 1

    # Architecture command
    elif args.command == 'architecture':
        risks = json.loads(args.risks)
        result = generate_architecture_baml(
            scout_report_json=args.scout_json,
            flagged_risks=risks
        )
        if result:
            print(json.dumps(result, indent=2))
            return 0
        else:
            print("BAML Architecture generation not available (falling back to orchestrator's method)")
            return 1

    # Validate build result command
    elif args.command == 'validate-build':
        result = validate_build_result_baml(
            result_json=args.result_json
        )
        if result:
            print(json.dumps(result, indent=2))
            return 0
        else:
            print("BAML build validation not available (falling back to orchestrator's method)")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
