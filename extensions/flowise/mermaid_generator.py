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


def get_node_emoji(node_type: str) -> str:
    """Get emoji icon for node type."""
    emoji_map = {
        "Start": "🚀",
        "Agent": "🤖",
        "Condition": "🔀",
        "ConditionAgent": "🎯",
        "LLM": "💬",
        "Tool": "🔧",
        "ExecuteFlow": "▶️",
        "CustomFunction": "⚙️",
        "HTTP": "🌐",
        "HumanInput": "👤",
        "DirectReply": "💭",
        "Loop": "🔄",
        "Iteration": "🔁",
        "StickyNote": "📝"
    }
    return emoji_map.get(node_type, "⬜")


def get_node_style(node_type: str, node_data: Dict) -> tuple:
    """
    Determine Mermaid node shape and color based on Flowise node type.
    Returns: (shape_template, color, emoji)
    """
    node_name = node_data.get("name", "")
    # Use authentic Flowise colors from node data
    node_color = node_data.get("color", "#E0E0E0")

    # Complete node type mapping with authentic Flowise shapes and colors
    node_styles = {
        # Start node - Stadium shape, green
        "Start": ("([{}])", "#7EE787"),

        # Agent nodes - Rectangle, teal
        "Agent": ("[{}]", "#4DD0E1"),

        # Condition nodes - Diamond, orange / Hexagon, pink
        "Condition": ("{{&{}&#}}", "#FFB938"),
        "ConditionAgent": ("{{&{}&#}}", "#ff8fab"),

        # LLM nodes - Rounded rectangle, blue
        "LLM": ("(({}))", "#64B5F6"),

        # Tool nodes - Trapezoid, brown
        "Tool": ("[/{}/]", "#d4a373"),

        # ExecuteFlow - Rectangle, olive
        "ExecuteFlow": ("[{}]", "#a3b18a"),

        # CustomFunction - Rectangle, purple
        "CustomFunction": ("[{}]", "#E4B7FF"),

        # HTTP - Rectangle, red
        "HTTP": ("[{}]", "#FF7F7F"),

        # HumanInput - Hexagon, indigo
        "HumanInput": ("{{&{}&#}}", "#6E6EFD"),

        # DirectReply - Rectangle, mint
        "DirectReply": ("[{}]", "#4DDBBB"),

        # Loop - Asymmetric shape, coral
        "Loop": ("([{}])", "#FFA07A"),

        # Iteration - Rectangle, lavender (will use subgraph)
        "Iteration": ("[{}]", "#9C89B8"),

        # StickyNote - Rectangle, yellow
        "StickyNote": ("[{}]", "#fee440")
    }

    # Try exact type match first
    if node_type in node_styles:
        shape, default_color = node_styles[node_type]
        # Prefer color from node data if available, otherwise use default
        color = node_color if node_color != "#E0E0E0" else default_color
        return shape, color, get_node_emoji(node_type)

    # Fallback: check by name pattern
    name_lower = node_name.lower()
    if "start" in name_lower:
        return node_styles["Start"][0], node_styles["Start"][1], get_node_emoji("Start")
    elif "condition" in name_lower:
        if "agent" in name_lower:
            return node_styles["ConditionAgent"][0], node_styles["ConditionAgent"][1], get_node_emoji("ConditionAgent")
        return node_styles["Condition"][0], node_styles["Condition"][1], get_node_emoji("Condition")
    elif "agent" in name_lower:
        return node_styles["Agent"][0], node_styles["Agent"][1], get_node_emoji("Agent")
    elif "llm" in name_lower:
        return node_styles["LLM"][0], node_styles["LLM"][1], get_node_emoji("LLM")
    elif "tool" in name_lower:
        return node_styles["Tool"][0], node_styles["Tool"][1], get_node_emoji("Tool")

    # Default: rectangle with node's own color or gray
    return "[{}]", node_color, "⬜"


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

    # Get node styling with emoji
    shape, color, emoji = get_node_style(node_type, data)

    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "description": description,
        "instructions": instructions[:200] if instructions else "",  # Truncate
        "shape": shape,
        "color": color,
        "emoji": emoji
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


def extract_flow_metadata(workflow_json: Dict) -> Dict:
    """Extract flow metadata for badges and statistics."""
    nodes = workflow_json.get("nodes", [])
    edges = workflow_json.get("edges", [])

    # Count node types
    agent_count = sum(1 for n in nodes if n.get("data", {}).get("type") == "Agent")
    condition_count = sum(1 for n in nodes if "Condition" in n.get("data", {}).get("type", ""))
    tool_count = sum(1 for n in nodes if n.get("data", {}).get("type") == "Tool")
    llm_count = sum(1 for n in nodes if n.get("data", {}).get("type") == "LLM")

    # Determine complexity
    total_nodes = len(nodes)
    total_edges = len(edges)
    if total_nodes <= 3:
        complexity = "Simple"
    elif total_nodes <= 8:
        complexity = "Moderate"
    else:
        complexity = "Complex"

    # Check for memory and tools
    has_memory = any("memory" in str(n.get("data", {}).get("inputs", {})).lower() for n in nodes)
    has_tools = tool_count > 0 or any("tools" in str(n.get("data", {}).get("inputs", {})).lower() for n in nodes)

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "agent_count": agent_count,
        "condition_count": condition_count,
        "tool_count": tool_count,
        "llm_count": llm_count,
        "complexity": complexity,
        "has_memory": has_memory,
        "has_tools": has_tools
    }


def detect_layout_direction(nodes: List[Dict], edges: List[Dict]) -> str:
    """
    Intelligently detect optimal graph direction based on flow structure.
    Returns: 'TD' (top-down) or 'LR' (left-right)
    """
    node_count = len(nodes)
    edge_count = len(edges)

    # Simple linear flows: top-down
    if node_count <= 5:
        return "TD"

    # Check for branching complexity
    sources = set(e.get("source") for e in edges)
    targets = set(e.get("target") for e in edges)

    # Count nodes with multiple outputs (branching)
    branch_count = 0
    for source in sources:
        outputs = sum(1 for e in edges if e.get("source") == source)
        if outputs > 1:
            branch_count += 1

    # Complex branching: left-right for better readability
    if branch_count >= 2 or node_count > 10:
        return "LR"

    # Default: top-down
    return "TD"


def generate_badges(metadata: Dict) -> str:
    """Generate GitHub-style badges for flow metadata."""
    badges = []

    # Node count badge
    badges.append(f"![Nodes](https://img.shields.io/badge/Nodes-{metadata['total_nodes']}-blue)")

    # Agent count badge
    if metadata['agent_count'] > 0:
        badges.append(f"![Agents](https://img.shields.io/badge/Agents-{metadata['agent_count']}-green)")

    # Complexity badge
    complexity_colors = {
        "Simple": "brightgreen",
        "Moderate": "yellow",
        "Complex": "orange"
    }
    color = complexity_colors.get(metadata['complexity'], "gray")
    badges.append(f"![Complexity](https://img.shields.io/badge/Complexity-{metadata['complexity']}-{color})")

    # Memory badge
    if metadata['has_memory']:
        badges.append("![Memory](https://img.shields.io/badge/Memory-Enabled-purple)")

    # Tools badge
    if metadata['has_tools']:
        badges.append(f"![Tools](https://img.shields.io/badge/Tools-{metadata['tool_count']}-red)")

    return " ".join(badges)


def generate_legend() -> str:
    """Generate a visual legend explaining node types."""
    legend = [
        "### 🎨 Node Type Legend",
        "",
        "| Icon | Type | Description |",
        "|------|------|-------------|",
        "| 🚀 | Start | Entry point of the workflow |",
        "| 🤖 | Agent | AI agent with reasoning capabilities |",
        "| 💬 | LLM | Large Language Model node |",
        "| 🔀 | Condition | Branching logic |",
        "| 🎯 | ConditionAgent | AI-powered conditional routing |",
        "| 🔧 | Tool | External tool integration |",
        "| ▶️ | ExecuteFlow | Execute another workflow |",
        "| ⚙️ | CustomFunction | Custom JavaScript function |",
        "| 🌐 | HTTP | HTTP request node |",
        "| 👤 | HumanInput | Request human input/approval |",
        "| 💭 | DirectReply | Direct message response |",
        "| 🔄 | Loop | Loop back to previous node |",
        "| 🔁 | Iteration | Iterate over array |",
        "| 📝 | StickyNote | Documentation note |",
        ""
    ]
    return "\n".join(legend)


def generate_mermaid(workflow_json: Dict, include_details: bool = False) -> str:
    """Generate Mermaid diagram from Flowise workflow JSON."""
    nodes = workflow_json.get("nodes", [])
    edges = workflow_json.get("edges", [])

    # Extract node information
    nodes_info = {}
    for node in nodes:
        info = extract_node_info(node)
        nodes_info[info["id"]] = info

    # Determine optimal layout direction
    direction = detect_layout_direction(nodes, edges)

    # Build Mermaid diagram
    mermaid_lines = [
        "```mermaid",
        "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#4DD0E1','primaryTextColor':'#000','primaryBorderColor':'#0097A7','lineColor':'#757575','secondaryColor':'#ff8fab','tertiaryColor':'#7EE787'}}}%%",
        f"graph {direction}"
    ]

    # Add nodes with styled shapes and emojis
    for node_id, info in nodes_info.items():
        shape_template = info["shape"]
        color = info["color"]
        emoji = info["emoji"]
        safe_label = sanitize_label(info["label"])
        # Include emoji in label
        label_with_emoji = f"{emoji} {safe_label}"
        node_def = f"    {node_id}{shape_template.format(label_with_emoji)}"
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


def generate_interactive_section(workflow_json: Dict, include_badges: bool = True, include_legend: bool = True) -> str:
    """Generate an interactive/collapsible section with agent details."""
    nodes = workflow_json.get("nodes", [])
    metadata = extract_flow_metadata(workflow_json)

    sections = []

    # 1. Add badges if requested
    if include_badges:
        badges = generate_badges(metadata)
        sections.extend([badges, "", "---", ""])

    # 2. Flow metadata
    sections.extend([
        f"**Total Nodes**: {metadata['total_nodes']} | ",
        f"**Agents**: {metadata['agent_count']} | ",
        f"**Complexity**: {metadata['complexity']}",
        "",
    ])

    # 3. Collapsible agent details
    sections.extend([
        "<details>",
        "<summary><b>🔍 View Agent Details (Click to Expand)</b></summary>",
        "",
        "| Agent | Type | Description |",
        "|-------|------|-------------|"
    ])

    for node in nodes:
        data = node.get("data", {})
        label = sanitize_label(data.get("label", "Unlabeled"))
        node_type = data.get("type", "Unknown")
        emoji = get_node_emoji(node_type)
        description = sanitize_label(data.get("description", "No description"))

        # Include emoji in agent column
        sections.append(f"| {emoji} {label} | {node_type} | {description} |")

    sections.extend([
        "",
        "</details>",
        ""
    ])

    # 4. Add legend if requested
    if include_legend:
        sections.extend(["", generate_legend()])

    return "\n".join(sections)


def main():
    """Main entry point for CLI usage."""
    if len(sys.argv) < 2:
        print("Usage: python3 mermaid_generator.py <flowise-workflow.json> [output.md]")
        print("\nGenerates a Mermaid diagram from a Flowise workflow JSON file.")
        print("\nOptions:")
        print("  --include-details    Include detailed node descriptions")
        print("  --interactive        Include interactive/collapsible agent details (default)")
        print("  --badges             Include flow metadata badges")
        print("  --legend             Include node type legend")
        print("  --no-interactive     Disable interactive features")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None

    include_details = "--include-details" in sys.argv
    no_interactive = "--no-interactive" in sys.argv

    # Default: interactive mode ON if no flags specified (backward compatible)
    # Explicit flags override
    if no_interactive:
        include_interactive = False
        include_badges = False
        include_legend = False
    else:
        include_interactive = "--interactive" in sys.argv or (len([arg for arg in sys.argv if arg.startswith('--')]) == 0)
        include_badges = "--badges" in sys.argv or include_interactive
        include_legend = "--legend" in sys.argv or include_interactive

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
        interactive_section = generate_interactive_section(
            workflow_json,
            include_badges=include_badges,
            include_legend=include_legend
        )
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
