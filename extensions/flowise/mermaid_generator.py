#!/usr/bin/env python3
"""
Flowise to Mermaid Diagram Generator

Converts Flowise JSON workflow files into beautiful Mermaid diagrams
for GitHub README visualization.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def sanitize_label(label: str) -> str:
    """Sanitize label for Mermaid syntax."""
    # Remove special characters that could break Mermaid syntax
    label = label.replace('"', "'")
    label = label.replace('\n', ' ')
    label = label.replace('\r', ' ')
    # Truncate if too long
    if len(label) > 50:
        label = label[:47] + "..."
    return label


def get_node_style(node_type: str, node_data: Dict) -> tuple:
    """Determine Mermaid node shape and color based on type."""
    node_name = node_data.get("name", "")
    node_color = node_data.get("color", "#4DD0E1")

    # Start nodes
    if "start" in node_name.lower() or node_type == "SeqStart":
        return "([{}])", "#7EE787"  # Stadium shape, green

    # Condition/Router nodes
    if "condition" in node_name.lower() or node_type == "ConditionAgent":
        return "{{&{}&#}}", "#ff8fab"  # Hexagon, pink

    # Agent nodes
    if "agent" in node_name.lower() or node_type == "Agent":
        return "[{}]", "#4DD0E1"  # Rectangle, teal

    # Default
    return "[{}]", "#E0E0E0"


def extract_node_info(node: Dict) -> Dict:
    """Extract key information from a Flowise node."""
    data = node.get("data", {})
    node_id = node.get("id", "unknown")
    label = data.get("label", "Unlabeled")
    node_type = data.get("type", "Unknown")
    description = data.get("description", "")

    # Get instructions/system message if available
    inputs = data.get("inputs", {})
    instructions = inputs.get("conditionAgentInstructions", "")
    if not instructions:
        instructions = inputs.get("agentInstructions", "")
    if not instructions:
        messages = inputs.get("agentMessages", [])
        if messages:
            for msg in messages:
                if msg.get("role") == "system":
                    instructions = msg.get("content", "")
                    break

    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "description": description,
        "instructions": instructions[:200] if instructions else "",  # Truncate
        "shape_color": get_node_style(node_type, data)
    }


def extract_edges(edges: List[Dict], nodes_info: Dict) -> List[tuple]:
    """Extract edge connections from Flowise edges."""
    connections = []

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        source_handle = edge.get("sourceHandle", "")

        # Extract scenario number from sourceHandle if it's a condition node
        label = ""
        if "output-" in source_handle:
            # Extract the scenario number (e.g., "conditionAgentAgentflow_1-output-0" -> "Scenario 0")
            parts = source_handle.split("-output-")
            if len(parts) > 1:
                scenario_num = parts[1]
                if scenario_num.isdigit():
                    # Get scenario label from source node if available
                    source_info = nodes_info.get(source, {})
                    label = f"S{scenario_num}"

        connections.append((source, target, label))

    return connections


def generate_mermaid(workflow_json: Dict, include_details: bool = False) -> str:
    """Generate Mermaid diagram from Flowise workflow JSON."""
    nodes = workflow_json.get("nodes", [])
    edges = workflow_json.get("edges", [])

    # Extract node information
    nodes_info = {}
    for node in nodes:
        info = extract_node_info(node)
        nodes_info[info["id"]] = info

    # Build Mermaid diagram
    mermaid_lines = [
        "```mermaid",
        "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#4DD0E1','primaryTextColor':'#000','primaryBorderColor':'#0097A7','lineColor':'#757575','secondaryColor':'#ff8fab','tertiaryColor':'#7EE787'}}}%%",
        "graph TD"
    ]

    # Add nodes with styled shapes
    for node_id, info in nodes_info.items():
        shape_template, color = info["shape_color"]
        safe_label = sanitize_label(info["label"])
        node_def = f"    {node_id}{shape_template.format(safe_label)}"
        mermaid_lines.append(node_def)

        # Add styling
        mermaid_lines.append(f"    style {node_id} fill:{color},stroke:#333,stroke-width:2px")

    # Add empty line for readability
    mermaid_lines.append("")

    # Extract and add edges
    connections = extract_edges(edges, nodes_info)
    for source, target, label in connections:
        if label:
            mermaid_lines.append(f"    {source} -->|{label}| {target}")
        else:
            mermaid_lines.append(f"    {source} --> {target}")

    mermaid_lines.append("```")

    # Add detailed legend if requested
    if include_details:
        mermaid_lines.extend([
            "",
            "### Node Details",
            ""
        ])

        for node_id, info in nodes_info.items():
            mermaid_lines.append(f"**{info['label']}** (`{node_id}`)")
            mermaid_lines.append(f"- Type: {info['type']}")
            if info['description']:
                mermaid_lines.append(f"- Description: {info['description']}")
            mermaid_lines.append("")

    return "\n".join(mermaid_lines)


def generate_interactive_section(workflow_json: Dict) -> str:
    """Generate an interactive/collapsible section with agent details."""
    nodes = workflow_json.get("nodes", [])

    sections = [
        "<details>",
        "<summary><b>🔍 View Agent Details (Click to Expand)</b></summary>",
        "",
        "| Agent | Type | Description |",
        "|-------|------|-------------|"
    ]

    for node in nodes:
        data = node.get("data", {})
        label = sanitize_label(data.get("label", "Unlabeled"))
        node_type = data.get("type", "Unknown")
        description = sanitize_label(data.get("description", "No description"))

        sections.append(f"| {label} | {node_type} | {description} |")

    sections.extend([
        "",
        "</details>",
        ""
    ])

    return "\n".join(sections)


def main():
    """Main entry point for CLI usage."""
    if len(sys.argv) < 2:
        print("Usage: python3 mermaid_generator.py <flowise-workflow.json> [output.md]")
        print("\nGenerates a Mermaid diagram from a Flowise workflow JSON file.")
        print("\nOptions:")
        print("  --include-details    Include detailed node descriptions")
        print("  --interactive        Include interactive/collapsible agent details")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    include_details = "--include-details" in sys.argv
    include_interactive = "--interactive" in sys.argv

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Load workflow JSON
    try:
        with open(input_path, 'r') as f:
            workflow_json = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}")
        sys.exit(1)

    # Generate Mermaid diagram
    mermaid_output = generate_mermaid(workflow_json, include_details=include_details)

    # Add interactive section if requested
    if include_interactive:
        interactive_section = generate_interactive_section(workflow_json)
        mermaid_output = mermaid_output + "\n\n" + interactive_section

    # Output to file or stdout
    if output_path:
        with open(output_path, 'w') as f:
            f.write(mermaid_output)
        print(f"✅ Mermaid diagram generated: {output_path}")
    else:
        print(mermaid_output)


if __name__ == "__main__":
    main()
