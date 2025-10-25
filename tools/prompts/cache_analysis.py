#!/usr/bin/env python3
"""
Cache Analysis Tool
Analyze orchestrator prompt structure and recommend cache segmentation
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


def analyze_prompt_structure(
    prompt_path: str = "tools/orchestrator_prompt.txt"
) -> Dict[str, Any]:
    """
    Analyze orchestrator prompt for optimal cache segmentation.

    Args:
        prompt_path: Path to orchestrator prompt file

    Returns:
        Analysis results dict with recommendations
    """
    prompt_file = Path(prompt_path)

    if not prompt_file.exists():
        return {
            "error": f"Prompt file not found: {prompt_path}",
            "total_lines": 0,
            "total_tokens": 0
        }

    # Read prompt
    with open(prompt_file, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    total_lines = len(lines)
    total_chars = len(content)
    total_tokens = _estimate_tokens(content)

    # Find cache boundary marker
    cache_boundary = "<<CACHE_BOUNDARY_MARKER>>"
    boundary_line = None

    for i, line in enumerate(lines):
        if cache_boundary in line:
            boundary_line = i
            break

    # If no boundary marker, find natural boundary
    if boundary_line is None:
        # Look for "BEGIN AUTONOMOUS EXECUTION NOW" or similar
        for i, line in enumerate(lines):
            if "BEGIN EXECUTION NOW" in line or "BEGIN AUTONOMOUS EXECUTION NOW" in line or "START NOW" in line:
                boundary_line = i - 5  # A few lines before
                break

    # Default boundary if still not found
    if boundary_line is None:
        # Use 98% of file as static, 2% as dynamic
        boundary_line = int(total_lines * 0.98)

    # Split sections
    static_lines = lines[:boundary_line]
    dynamic_lines = lines[boundary_line:]

    static_content = '\n'.join(static_lines)
    dynamic_content = '\n'.join(dynamic_lines)

    static_chars = len(static_content)
    static_tokens = _estimate_tokens(static_content)

    dynamic_chars = len(dynamic_content)
    dynamic_tokens = _estimate_tokens(dynamic_content)

    # Check if static section meets minimum
    min_tokens = 1024
    static_cacheable = static_tokens >= min_tokens

    # Calculate expected savings
    # Assumption: 90% of requests hit cache after first request
    first_request_cost = total_tokens * 3.00 / 1_000_000  # $3/MTok input
    cache_write_cost = static_tokens * 3.75 / 1_000_000  # $3.75/MTok cache write

    subsequent_request_cost = (
        (dynamic_tokens * 3.00 / 1_000_000) +  # Regular input
        (static_tokens * 0.30 / 1_000_000)      # Cache read (90% discount)
    )

    # 50 builds scenario: 1 cache write + 49 cache reads
    cost_without_caching = 50 * (total_tokens * 3.00 / 1_000_000)
    cost_with_caching = cache_write_cost + (49 * subsequent_request_cost)
    savings = cost_without_caching - cost_with_caching
    savings_pct = (savings / cost_without_caching) * 100 if cost_without_caching > 0 else 0

    # Generate recommendations
    recommendations = []

    if static_cacheable:
        recommendations.append(f"✅ Static section meets minimum token requirement ({static_tokens:,} > {min_tokens})")
    else:
        recommendations.append(f"❌ Static section too small ({static_tokens:,} < {min_tokens}) - caching will not work")

    if boundary_line:
        recommendations.append(f"✅ Cache boundary at line {boundary_line}")
    else:
        recommendations.append(f"⚠️  No cache boundary marker found - using heuristic")

    if savings_pct > 80:
        recommendations.append(f"✅ Expected savings: {savings_pct:.1f}% (50 builds: ${cost_without_caching:.2f} → ${cost_with_caching:.2f})")
    else:
        recommendations.append(f"⚠️  Expected savings: {savings_pct:.1f}% (lower than typical 80-90%)")

    if dynamic_tokens < 100:
        recommendations.append(f"⚠️  Dynamic section very small ({dynamic_tokens} tokens) - consider expanding")

    # Identify section types
    section_analysis = _analyze_sections(static_content, dynamic_content)

    return {
        "total_lines": total_lines,
        "total_chars": total_chars,
        "total_tokens": total_tokens,
        "recommended_boundary": boundary_line,
        "has_boundary_marker": cache_boundary in content,
        "static_section": {
            "lines": len(static_lines),
            "chars": static_chars,
            "tokens": static_tokens,
            "cacheable": static_cacheable,
            "content_types": section_analysis["static_types"]
        },
        "dynamic_section": {
            "lines": len(dynamic_lines),
            "chars": dynamic_chars,
            "tokens": dynamic_tokens,
            "cacheable": False,
            "content_types": section_analysis["dynamic_types"]
        },
        "cost_analysis": {
            "first_request": round(first_request_cost, 6),
            "subsequent_request": round(subsequent_request_cost, 6),
            "cost_without_caching_50_builds": round(cost_without_caching, 4),
            "cost_with_caching_50_builds": round(cost_with_caching, 4),
            "savings_50_builds": round(savings, 4),
            "savings_percentage": round(savings_pct, 2)
        },
        "recommendations": recommendations
    }


def _estimate_tokens(text: str) -> int:
    """
    Estimate token count.

    Args:
        text: Text to estimate

    Returns:
        Estimated tokens (4 chars per token heuristic)
    """
    return len(text) // 4


def _analyze_sections(static_content: str, dynamic_content: str) -> Dict[str, Any]:
    """
    Analyze what types of content are in each section.

    Args:
        static_content: Static section text
        dynamic_content: Dynamic section text

    Returns:
        Dict with content type lists
    """
    static_types = []
    dynamic_types = []

    # Analyze static section
    if "PHASE" in static_content:
        static_types.append("Phase instructions")
    if "GIT WORKFLOW" in static_content:
        static_types.append("Git workflow reference")
    if "ENHANCEMENT MODE" in static_content:
        static_types.append("Enhancement mode guide")
    if "CRITICAL RULES" in static_content:
        static_types.append("Critical rules")
    if "ERROR HANDLING" in static_content:
        static_types.append("Error handling")
    if "FINAL OUTPUT" in static_content:
        static_types.append("Output format")

    # Analyze dynamic section
    if "CONFIGURATION" in dynamic_content:
        dynamic_types.append("Task configuration")
    if "task\":" in dynamic_content:
        dynamic_types.append("Task description")
    if "working_directory" in dynamic_content:
        dynamic_types.append("Working directory")
    if "mode\":" in dynamic_content:
        dynamic_types.append("Mode flags")

    return {
        "static_types": static_types if static_types else ["Unknown static content"],
        "dynamic_types": dynamic_types if dynamic_types else ["Unknown dynamic content"]
    }


def print_analysis_report(analysis: Dict[str, Any]):
    """
    Print formatted analysis report to console.

    Args:
        analysis: Analysis results from analyze_prompt_structure()
    """
    print("\n" + "="*70)
    print("📊 ORCHESTRATOR PROMPT CACHE ANALYSIS")
    print("="*70)

    if "error" in analysis:
        print(f"\n❌ Error: {analysis['error']}")
        return

    print(f"\n📄 Overall Statistics:")
    print(f"   Total lines: {analysis['total_lines']:,}")
    print(f"   Total characters: {analysis['total_chars']:,}")
    print(f"   Total tokens: ~{analysis['total_tokens']:,}")
    print(f"   Has boundary marker: {'✅ Yes' if analysis['has_boundary_marker'] else '❌ No'}")

    print(f"\n📦 Static Section (Cacheable):")
    static = analysis['static_section']
    print(f"   Lines: {static['lines']:,}")
    print(f"   Tokens: ~{static['tokens']:,}")
    print(f"   Cacheable: {'✅ Yes' if static['cacheable'] else '❌ No'}")
    print(f"   Content types:")
    for content_type in static['content_types']:
        print(f"      - {content_type}")

    print(f"\n🔄 Dynamic Section:")
    dynamic = analysis['dynamic_section']
    print(f"   Lines: {dynamic['lines']:,}")
    print(f"   Tokens: ~{dynamic['tokens']:,}")
    print(f"   Content types:")
    for content_type in dynamic['content_types']:
        print(f"      - {content_type}")

    print(f"\n💰 Cost Analysis (50 builds):")
    cost = analysis['cost_analysis']
    print(f"   Without caching: ${cost['cost_without_caching_50_builds']:.4f}")
    print(f"   With caching:    ${cost['cost_with_caching_50_builds']:.4f}")
    print(f"   Savings:         ${cost['savings_50_builds']:.4f} ({cost['savings_percentage']:.1f}%)")

    print(f"\n💡 Recommendations:")
    for rec in analysis['recommendations']:
        print(f"   {rec}")

    print("\n" + "="*70)
    print()


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze orchestrator prompt for cache optimization"
    )
    parser.add_argument(
        '--prompt',
        default='tools/orchestrator_prompt.txt',
        help='Path to orchestrator prompt file'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output JSON instead of formatted report'
    )

    args = parser.parse_args()

    # Run analysis
    analysis = analyze_prompt_structure(args.prompt)

    # Output results
    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        print_analysis_report(analysis)


if __name__ == "__main__":
    main()
