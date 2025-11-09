"""
Flowise Template Analyzer

Analyzes Flowise templates to extract patterns, best practices, and architectural insights.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def analyze_template(template_path: Path) -> Dict[str, Any]:
    """
    Analyze a single Flowise template and extract patterns.

    Args:
        template_path: Path to Flowise JSON template

    Returns:
        Dictionary with extracted patterns and analysis

    Example:
        >>> analysis = analyze_template(Path("supervisor.json"))
        >>> print(f"Found {len(analysis['node_patterns'])} node patterns")
    """
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
        return {"error": str(e), "file": str(template_path), "success": False}

    if not isinstance(data, dict):
        return {"error": "Invalid JSON structure", "success": False}

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    return {
        "success": True,
        "file": str(template_path),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_patterns": extract_node_patterns(nodes),
        "connection_patterns": extract_connection_patterns(edges, nodes),
        "configuration_patterns": _extract_configurations(nodes),
        "quality_markers": _identify_quality_markers(nodes, edges),
    }


def analyze_directory(directory: Path) -> Dict[str, Any]:
    """
    Analyze all templates in a directory.

    Args:
        directory: Directory containing Flowise templates

    Returns:
        Aggregated analysis of all templates

    Example:
        >>> results = analyze_directory(Path("./templates"))
        >>> print(f"Analyzed {results['total_files']} files")
    """
    if not directory.exists() or not directory.is_dir():
        return {"error": f"Directory not found: {directory}", "success": False}

    json_files = sorted(directory.glob("*.json"))

    if not json_files:
        return {
            "error": "No JSON files found in directory",
            "success": False,
            "total_files": 0,
        }

    all_analyses = []
    node_type_counter = Counter()
    connection_counter = Counter()

    for json_file in json_files:
        analysis = analyze_template(json_file)
        if analysis.get("success"):
            all_analyses.append(analysis)

            # Aggregate node types
            for pattern in analysis.get("node_patterns", []):
                node_type_counter[pattern["type"]] += pattern["count"]

            # Aggregate connection patterns
            for conn in analysis.get("connection_patterns", []):
                connection_counter[conn["pattern"]] += 1

    return {
        "success": True,
        "total_files": len(json_files),
        "analyzed_successfully": len(all_analyses),
        "node_type_frequency": dict(node_type_counter.most_common()),
        "connection_frequency": dict(connection_counter.most_common()),
        "individual_analyses": all_analyses,
        "common_patterns": _extract_common_patterns(all_analyses),
    }


def extract_node_patterns(nodes: List[dict]) -> List[dict]:
    """
    Extract common node configurations.

    Args:
        nodes: List of node dictionaries

    Returns:
        List of node pattern dictionaries

    Example:
        >>> patterns = extract_node_patterns(nodes)
        >>> for pattern in patterns:
        ...     print(f"{pattern['type']}: {pattern['count']} occurrences")
    """
    if not nodes:
        return []

    node_type_counter = Counter()
    node_configs = {}

    for node in nodes:
        if not isinstance(node, dict):
            continue

        # Extract node type
        node_type = (
            node.get("type")
            or node.get("data", {}).get("type")
            or node.get("data", {}).get("name")
            or "unknown"
        )

        node_type_counter[node_type] += 1

        # Store configuration example
        if node_type not in node_configs:
            node_configs[node_type] = {
                "type": node_type,
                "example_config": node.get("data", {}),
                "example_id": node.get("id", ""),
            }

    patterns = []
    for node_type, count in node_type_counter.most_common():
        patterns.append(
            {
                "type": node_type,
                "count": count,
                "example_config": node_configs[node_type]["example_config"],
            }
        )

    return patterns


def extract_connection_patterns(edges: List[dict], nodes: List[dict]) -> List[dict]:
    """
    Identify connection patterns (supervisor→worker, sequential, parallel).

    Args:
        edges: List of edge dictionaries
        nodes: List of node dictionaries for context

    Returns:
        List of connection pattern dictionaries

    Example:
        >>> connections = extract_connection_patterns(edges, nodes)
        >>> for conn in connections:
        ...     print(f"{conn['pattern']}: {conn['source']} -> {conn['target']}")
    """
    if not edges:
        return []

    # Create node lookup by id
    node_lookup = {}
    for node in nodes:
        if isinstance(node, dict) and "id" in node:
            node_type = (
                node.get("type")
                or node.get("data", {}).get("type")
                or node.get("data", {}).get("name")
                or "unknown"
            )
            node_lookup[node["id"]] = node_type

    patterns = []
    connection_type_counter = Counter()

    for edge in edges:
        if not isinstance(edge, dict):
            continue

        source = edge.get("source", "")
        target = edge.get("target", "")

        if not source or not target:
            continue

        source_type = node_lookup.get(source, "unknown")
        target_type = node_lookup.get(target, "unknown")

        # Classify connection pattern
        pattern = _classify_connection(source_type, target_type)
        connection_type_counter[pattern] += 1

        patterns.append(
            {
                "pattern": pattern,
                "source": source,
                "target": target,
                "source_type": source_type,
                "target_type": target_type,
            }
        )

    return patterns


def export_patterns(patterns: Dict, output_path: Path) -> None:
    """
    Export patterns to JSON file.

    Args:
        patterns: Dictionary of patterns to export
        output_path: Path to output JSON file

    Example:
        >>> export_patterns(patterns, Path("patterns/expertise.json"))
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)


def _extract_configurations(nodes: List[dict]) -> Dict[str, Any]:
    """Extract common configuration patterns from nodes."""
    config_keys = Counter()

    for node in nodes:
        if not isinstance(node, dict):
            continue

        data = node.get("data", {})
        if isinstance(data, dict):
            for key in data.keys():
                config_keys[key] += 1

    return {
        "common_config_keys": dict(config_keys.most_common(10)),
        "total_unique_keys": len(config_keys),
    }


def _identify_quality_markers(nodes: List[dict], edges: List[dict]) -> Dict[str, Any]:
    """Identify markers of high-quality flows."""
    has_error_handling = False
    has_retry_logic = False
    has_proper_memory = False

    for node in nodes:
        if not isinstance(node, dict):
            continue

        data = node.get("data", {})
        if isinstance(data, dict):
            # Check for error handling configurations
            if any(key in str(data).lower() for key in ["error", "fallback", "catch"]):
                has_error_handling = True

            # Check for retry logic
            if any(
                key in str(data).lower() for key in ["retry", "attempt", "max_retries"]
            ):
                has_retry_logic = True

            # Check for memory management
            if "memory" in str(data).lower():
                has_proper_memory = True

    return {
        "has_error_handling": has_error_handling,
        "has_retry_logic": has_retry_logic,
        "has_proper_memory": has_proper_memory,
        "node_to_edge_ratio": len(nodes) / max(len(edges), 1),
    }


def _classify_connection(source_type: str, target_type: str) -> str:
    """Classify the type of connection between nodes."""
    source_lower = source_type.lower()
    target_lower = target_type.lower()

    # Supervisor to worker
    if "supervisor" in source_lower or "router" in source_lower:
        return "supervisor-to-worker"

    # Agent to tool
    if "agent" in source_lower and "tool" in target_lower:
        return "agent-to-tool"

    # Retriever to LLM (RAG pattern)
    if (
        "retriev" in source_lower or "vector" in source_lower
    ) and "llm" in target_lower:
        return "retrieval-to-llm"

    # Memory to conversation
    if "memory" in source_lower and "conversation" in target_lower:
        return "memory-to-conversation"

    # Sequential LLM chain
    if "llm" in source_lower and "llm" in target_lower:
        return "sequential-llm"

    return "generic-connection"


def _extract_common_patterns(analyses: List[dict]) -> Dict[str, Any]:
    """Extract patterns common across multiple analyses."""
    if not analyses:
        return {}

    total_nodes = sum(a.get("node_count", 0) for a in analyses)
    total_edges = sum(a.get("edge_count", 0) for a in analyses)

    return {
        "average_nodes": total_nodes / len(analyses) if analyses else 0,
        "average_edges": total_edges / len(analyses) if analyses else 0,
        "files_with_error_handling": sum(
            1
            for a in analyses
            if a.get("quality_markers", {}).get("has_error_handling", False)
        ),
        "files_with_retry_logic": sum(
            1
            for a in analyses
            if a.get("quality_markers", {}).get("has_retry_logic", False)
        ),
    }


def main() -> None:
    """CLI entry point with argparse."""
    parser = argparse.ArgumentParser(
        description="Analyze Flowise templates to extract patterns and best practices"
    )

    parser.add_argument(
        "--analyze", type=str, help="Analyze a single Flowise template JSON file"
    )

    parser.add_argument(
        "--analyze-all", type=str, help="Analyze all templates in a directory"
    )

    parser.add_argument(
        "--export-patterns", type=str, help="Export patterns to JSON file"
    )

    args = parser.parse_args()

    if args.analyze:
        template_path = Path(args.analyze)
        result = analyze_template(template_path)

        if result.get("success"):
            print(f"\n✅ Analysis successful: {template_path}")
            print(f"Nodes: {result['node_count']}")
            print(f"Edges: {result['edge_count']}")
            print("\nNode Patterns:")
            for pattern in result["node_patterns"]:
                print(f"  - {pattern['type']}: {pattern['count']} occurrences")
            print("\nConnection Patterns:")
            for conn in result["connection_patterns"]:
                print(
                    f"  - {conn['pattern']}: {conn['source_type']} → {conn['target_type']}"
                )
        else:
            print(f"\n❌ Analysis failed: {result.get('error')}")

    elif args.analyze_all:
        directory = Path(args.analyze_all)
        result = analyze_directory(directory)

        if result.get("success"):
            print(
                f"\n✅ Analyzed {result['analyzed_successfully']}/{result['total_files']} files"
            )
            print("\nMost Common Node Types:")
            for node_type, count in list(result["node_type_frequency"].items())[:5]:
                print(f"  - {node_type}: {count} occurrences")
            print("\nMost Common Connection Patterns:")
            for pattern, count in list(result["connection_frequency"].items())[:5]:
                print(f"  - {pattern}: {count} occurrences")

            if args.export_patterns:
                export_path = Path(args.export_patterns)
                export_patterns(result, export_path)
                print(f"\n✅ Patterns exported to {export_path}")
        else:
            print(f"\n❌ Analysis failed: {result.get('error')}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
