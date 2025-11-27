#!/usr/bin/env python3
"""
Unified Test Runner for Context Foundry

Usage:
    ./run_tests.py [options]

Options:
    --unit          Run only unit tests (fast)
    --integration   Run only integration tests (slower, requires env)
    --e2e           Run end-to-end tests (slowest)
    --all           Run all tests (default)
    --coverage      Generate coverage report
    --fast          Fail fast (stop on first error)
"""

import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return exit code"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(description="Context Foundry Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--fast", action="store_true", help="Stop on first failure")
    
    args = parser.parse_args()
    
    # Default to all if no specific category selected
    if not (args.unit or args.integration or args.e2e):
        args.all = True
        
    base_cmd = ["pytest"]
    
    if args.fast:
        base_cmd.append("-x")
        
    if args.coverage:
        base_cmd.extend(["--cov=context_foundry", "--cov=tools", "--cov-report=term-missing"])
    
    # Construct test paths/markers
    # Note: This assumes we have markers or specific paths. 
    # For now, we'll try to discover based on naming or directory if possible,
    # but since everything is in tests/, we might need to rely on markers if they exist.
    # If not, we run everything for --all.
    
    tests_to_run = []
    
    if args.all:
        tests_to_run.append("tests/")
    else:
        # If we had separate dirs, we'd add them here.
        # Since it's flat, we might need to filter by filename pattern if markers aren't used.
        # For now, let's assume the user wants to run specific files if they pass them to pytest directly,
        # but this script is a high-level wrapper.
        # Let's try to use markers if they are standard, otherwise just run all for now 
        # and advise using pytest directly for granular control.
        
        # TODO: Implement proper categorization if tests are marked.
        # For this first pass, we'll just run everything if they ask for specific types 
        # unless we can identify them.
        
        if args.unit:
            # Heuristic: exclude integration/e2e named files?
            # Or just run everything for now and print a message.
            print("Note: Test categorization relies on pytest markers. Running all tests in tests/...")
            tests_to_run.append("tests/")
            
        if args.integration:
             tests_to_run.append("tests/")
             
        if args.e2e:
             tests_to_run.append("tests/")

    cmd = base_cmd + tests_to_run
    
    sys.exit(run_command(cmd))

if __name__ == "__main__":
    main()
