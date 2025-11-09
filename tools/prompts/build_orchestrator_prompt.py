#!/usr/bin/env python3
"""
Orchestrator Prompt Builder

Builds the complete orchestrator_prompt.txt from modular components:
- Header (git workflow, phase tracking, BAML, tool usage, etc.)
- Phase-specific instructions (loaded from separate files)
- Footer (final output format, critical rules, error handling)

This allows easier maintenance of individual phases while preserving
the single-file format expected by the runtime system.
"""

from pathlib import Path
from typing import Optional
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from extensions.flowise import extensions_loader

    FLOWISE_AVAILABLE = True
except ImportError:
    FLOWISE_AVAILABLE = False


def build_orchestrator_prompt(
    include_flowise: bool = True, output_path: Optional[str] = None
) -> str:
    """
    Build complete orchestrator prompt from modular components.

    Args:
        include_flowise: Include Flowise-specific enhancements (default: True)
        output_path: Path to write output file (default: tools/orchestrator_prompt.txt)

    Returns:
        Complete orchestrator prompt content

    Process:
        1. Load header (common sections)
        2. Load all phase files in sequence
        3. Add Flowise enhancements if applicable
        4. Load footer (final output, rules)
        5. Combine and return
    """
    prompts_dir = Path(__file__).parent
    tools_dir = prompts_dir.parent

    # ═══════════════════════════════════════════════════════════
    # 1. Load Header (Common Sections)
    # ═══════════════════════════════════════════════════════════

    header_path = prompts_dir / "orchestrator_header.txt"
    if header_path.exists():
        with open(header_path, "r", encoding="utf-8") as f:
            header = f.read()
    else:
        # Fallback: extract from current orchestrator_prompt.txt
        current_prompt = tools_dir / "orchestrator_prompt.txt"
        if current_prompt.exists():
            with open(current_prompt, "r", encoding="utf-8") as f:
                lines = f.readlines()
                header = "".join(lines[:343])
        else:
            raise FileNotFoundError("Cannot find header section")

    # ═══════════════════════════════════════════════════════════
    # 2. Load Phase Files
    # ═══════════════════════════════════════════════════════════

    phase_files = [
        "phase_0_codebase_analysis.md",
        "phase_1_scout.md",
        "phase_2_architect.md",
        "phase_2_5_parallel_build.md",
        "phase_3_5_integration_precheck.md",
        "phase_4_test.md",
        "phase_4_5_screenshot.md",
        "phase_5_documentation.md",
        "phase_6_deployment.md",
        "phase_7_feedback.md",
        "phase_7_5_github.md",
    ]

    phases_content = []

    for phase_file in phase_files:
        phase_path = prompts_dir / phase_file
        if not phase_path.exists():
            print(f"⚠️  Warning: Phase file not found: {phase_file}")
            continue

        with open(phase_path, "r", encoding="utf-8") as f:
            phase_content = f.read()

        phases_content.append(phase_content)

        # Add Flowise enhancements if available
        if include_flowise and FLOWISE_AVAILABLE:
            # Extract phase name from filename (e.g., phase_1_scout.md -> scout)
            phase_name = phase_file.replace(".md", "").split("_", 2)[-1]

            flowise_enhancement = extensions_loader.get_extension_prompt(
                "flowise", phase_name
            )
            if flowise_enhancement:
                phases_content.append("\n")
                phases_content.append("═" * 63)
                phases_content.append("\n")
                phases_content.append(
                    f"FLOWISE EXTENSION - {phase_name.upper()} ENHANCEMENTS\n"
                )
                phases_content.append("═" * 63)
                phases_content.append("\n\n")
                phases_content.append(flowise_enhancement)
                phases_content.append("\n")

        # Add spacing between phases
        phases_content.append("\n")

    # ═══════════════════════════════════════════════════════════
    # 3. Load Footer (Final Output, Rules, Error Handling)
    # ═══════════════════════════════════════════════════════════

    footer_path = prompts_dir / "orchestrator_footer.txt"
    if footer_path.exists():
        with open(footer_path, "r", encoding="utf-8") as f:
            footer = f.read()
    else:
        # Fallback: extract from current orchestrator_prompt.txt
        current_prompt = tools_dir / "orchestrator_prompt.txt"
        if current_prompt.exists():
            with open(current_prompt, "r", encoding="utf-8") as f:
                lines = f.readlines()
                footer = "".join(lines[3100:])  # Lines 3101+
        else:
            raise FileNotFoundError("Cannot find footer section")

    # ═══════════════════════════════════════════════════════════
    # 4. Combine All Sections
    # ═══════════════════════════════════════════════════════════

    complete_prompt = header + "".join(phases_content) + footer

    # ═══════════════════════════════════════════════════════════
    # 5. Write Output
    # ═══════════════════════════════════════════════════════════

    if output_path:
        output_file = Path(output_path)
    else:
        output_file = tools_dir / "orchestrator_prompt.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(complete_prompt)

    print(f"✅ Built orchestrator prompt: {output_file}")
    print(f"   Total length: {len(complete_prompt)} chars")
    print(f"   Estimated tokens: {len(complete_prompt) // 4}")
    print(
        f"   Flowise enhancements: {'Included' if include_flowise and FLOWISE_AVAILABLE else 'Not included'}"
    )

    return complete_prompt


def main():
    """Command-line interface for building orchestrator prompt."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build orchestrator_prompt.txt from modular components"
    )
    parser.add_argument(
        "--no-flowise",
        action="store_true",
        help="Exclude Flowise-specific enhancements",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: tools/orchestrator_prompt.txt)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show stats without writing file"
    )

    args = parser.parse_args()

    include_flowise = not args.no_flowise

    if args.dry_run:
        print("🔍 Dry run mode - will not write file\n")
        output_path = None
        # Build but don't write
        prompt = build_orchestrator_prompt(
            include_flowise=include_flowise, output_path="/tmp/dry_run_orchestrator.txt"
        )
        print("\n✅ Dry run complete - no files modified")
    else:
        prompt = build_orchestrator_prompt(
            include_flowise=include_flowise, output_path=args.output
        )


if __name__ == "__main__":
    main()
