"""
Flowise Flow Detector

Analyzes JSON files to detect Flowise flows and classify them by type and complexity.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def detect_flowise_flow(file_path: Path) -> Dict[str, Any]:
    """
    Detect if a JSON file is a Flowise flow.

    Args:
        file_path: Path to JSON file to analyze

    Returns:
        Dictionary with detection results:
        {
            "is_flowise": bool,
            "flow_type": "multi-agent" | "rag" | "workflow" | "chatbot" | "unknown",
            "complexity": "simple" | "moderate" | "complex",
            "node_count": int,
            "agent_count": int,
            "has_memory": bool,
            "has_tools": bool,
            "expertise_level": "beginner" | "advanced" | "expert"
        }

    Example:
        >>> result = detect_flowise_flow(Path("flow.json"))
        >>> if result["is_flowise"]:
        ...     print(f"Detected {result['flow_type']} flow")
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return _create_negative_result()

    # Check for Flowise structure
    if not isinstance(data, dict):
        return _create_negative_result()

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Must have nodes and edges to be a Flowise flow
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return _create_negative_result()

    # Empty flows are not valid
    if len(nodes) == 0:
        return _create_negative_result()

    # Additional Flowise indicators (optional but strengthen confidence)
    has_chatflowid = "chatflowid" in data or "chatFlowId" in data
    has_deployed = "deployed" in data

    # Analyze nodes
    node_types = _extract_node_types(nodes)
    agent_count = _count_agents(node_types)
    has_memory = _has_memory_nodes(node_types)
    has_tools = _has_tool_nodes(node_types)

    # Classify flow type
    flow_type = classify_flow_type(nodes, node_types, edges)

    # Calculate complexity
    complexity = calculate_complexity(len(nodes), len(edges), agent_count)

    # Determine expertise level
    expertise_level = _determine_expertise_level(
        len(nodes), agent_count, has_memory, has_tools, complexity
    )

    return {
        "is_flowise": True,
        "flow_type": flow_type,
        "complexity": complexity,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "agent_count": agent_count,
        "has_memory": has_memory,
        "has_tools": has_tools,
        "expertise_level": expertise_level,
        "has_chatflowid": has_chatflowid,
        "has_deployed": has_deployed,
    }


def scan_directory(directory: Path) -> List[Path]:
    """
    Find all JSON files in directory (non-recursive).

    Args:
        directory: Directory to scan

    Returns:
        List of JSON file paths

    Example:
        >>> json_files = scan_directory(Path("./templates"))
        >>> print(f"Found {len(json_files)} JSON files")
    """
    if not directory.exists() or not directory.is_dir():
        return []

    return sorted(directory.glob("*.json"))


def classify_flow_type(
    nodes: List[dict], node_types: List[str], edges: List[dict]
) -> str:
    """
    Classify flow based on node patterns.

    Args:
        nodes: List of node dictionaries
        node_types: List of node type strings
        edges: List of edge dictionaries

    Returns:
        Flow type: "multi-agent", "rag", "workflow", "chatbot", or "unknown"

    Example:
        >>> flow_type = classify_flow_type(nodes, node_types, edges)
        >>> print(f"This is a {flow_type} flow")
    """
    # Count specific node types
    agent_count = sum(1 for nt in node_types if "agent" in nt.lower())
    llm_count = sum(
        1 for nt in node_types if "llm" in nt.lower() and "agent" not in nt.lower()
    )
    retriever_count = sum(
        1 for nt in node_types if "retriev" in nt.lower() or "vector" in nt.lower()
    )
    memory_count = sum(1 for nt in node_types if "memory" in nt.lower())
    conversation_count = sum(1 for nt in node_types if "conversation" in nt.lower())

    # Multi-agent: Multiple agent executors
    if agent_count >= 2:
        return "multi-agent"

    # RAG: Has retriever/vector store + LLM
    if retriever_count > 0 and (llm_count > 0 or agent_count > 0):
        return "rag"

    # Chatbot: Conversation chain with memory
    if conversation_count > 0 or (
        memory_count > 0 and (llm_count > 0 or agent_count > 0)
    ):
        return "chatbot"

    # Workflow: Multiple LLM chains (sequential processing)
    if llm_count >= 2:
        return "workflow"

    # Single agent or single LLM
    if agent_count == 1 or llm_count == 1:
        return "chatbot"

    return "unknown"


def calculate_complexity(node_count: int, edge_count: int, agent_count: int) -> str:
    """
    Determine flow complexity.

    Args:
        node_count: Number of nodes
        edge_count: Number of edges
        agent_count: Number of agent nodes

    Returns:
        Complexity level: "simple", "moderate", or "complex"

    Example:
        >>> complexity = calculate_complexity(15, 20, 3)
        >>> print(f"Complexity: {complexity}")
    """
    # Complex: Many nodes or multiple agents
    if node_count > 15 or agent_count > 3:
        return "complex"

    # Simple: Few nodes and at most one agent
    if node_count < 5 and agent_count <= 1:
        return "simple"

    # Moderate: Everything in between
    return "moderate"


def _create_negative_result() -> Dict[str, Any]:
    """Create a result indicating the file is not a Flowise flow."""
    return {
        "is_flowise": False,
        "flow_type": "unknown",
        "complexity": "unknown",
        "node_count": 0,
        "edge_count": 0,
        "agent_count": 0,
        "has_memory": False,
        "has_tools": False,
        "expertise_level": "unknown",
        "has_chatflowid": False,
        "has_deployed": False,
    }


def _extract_node_types(nodes: List[dict]) -> List[str]:
    """Extract node types from nodes list."""
    node_types = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        # Try different possible locations for type information
        node_type = (
            node.get("type")
            or node.get("data", {}).get("type")
            or node.get("data", {}).get("name")
            or ""
        )
        if node_type:
            node_types.append(str(node_type))

    return node_types


def _count_agents(node_types: List[str]) -> int:
    """Count agent executor nodes."""
    return sum(1 for nt in node_types if "agent" in nt.lower())


def _has_memory_nodes(node_types: List[str]) -> bool:
    """Check if flow has memory nodes."""
    return any("memory" in nt.lower() for nt in node_types)


def _has_tool_nodes(node_types: List[str]) -> bool:
    """Check if flow has tool nodes."""
    return any("tool" in nt.lower() for nt in node_types)


def _determine_expertise_level(
    node_count: int,
    agent_count: int,
    has_memory: bool,
    has_tools: bool,
    complexity: str,
) -> str:
    """Determine the expertise level required for this flow."""
    # Expert: Complex multi-agent with memory and tools
    if complexity == "complex" and agent_count >= 2 and has_memory and has_tools:
        return "expert"

    # Advanced: Multi-agent or complex with some features
    if agent_count >= 2 or (complexity == "complex") or (has_memory and has_tools):
        return "advanced"

    # Beginner: Simple flows
    return "beginner"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python detector.py <path_to_json_file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    result = detect_flowise_flow(file_path)

    print("\nFlowise Flow Detection Results:")
    print(f"{'=' * 50}")
    print(f"Is Flowise Flow: {result['is_flowise']}")
    if result["is_flowise"]:
        print(f"Flow Type: {result['flow_type']}")
        print(f"Complexity: {result['complexity']}")
        print(f"Nodes: {result['node_count']}")
        print(f"Edges: {result['edge_count']}")
        print(f"Agents: {result['agent_count']}")
        print(f"Has Memory: {result['has_memory']}")
        print(f"Has Tools: {result['has_tools']}")
        print(f"Expertise Level: {result['expertise_level']}")
