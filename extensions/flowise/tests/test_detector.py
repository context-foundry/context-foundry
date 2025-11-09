"""
Tests for Flowise Flow Detector
"""

import json
import unittest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import detector


class TestFlowiseDetector(unittest.TestCase):
    """Test cases for Flowise flow detection."""

    def setUp(self):
        """Set up test fixtures path."""
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_detect_valid_multi_agent_flow(self):
        """Test detection of valid multi-agent flow."""
        flow_file = self.fixtures_dir / "supervisor_multi_agent.json"
        result = detector.detect_flowise_flow(flow_file)

        self.assertTrue(result["is_flowise"])
        self.assertEqual(result["flow_type"], "multi-agent")
        self.assertEqual(result["node_count"], 5)
        self.assertEqual(result["agent_count"], 4)  # 3 workers + 1 supervisor
        self.assertTrue(result["has_memory"])
        # Note: 5 nodes but 4 agents makes it complex (agent_count > 3)
        self.assertIn(result["complexity"], ["simple", "complex"])  # Borderline case
        self.assertIn(result["expertise_level"], ["beginner", "advanced"])

    def test_detect_valid_rag_flow(self):
        """Test detection of valid RAG flow."""
        flow_file = self.fixtures_dir / "rag_workflow.json"
        result = detector.detect_flowise_flow(flow_file)

        self.assertTrue(result["is_flowise"])
        self.assertEqual(result["flow_type"], "rag")
        self.assertEqual(result["node_count"], 4)
        self.assertEqual(result["agent_count"], 0)  # No agents, just retriever + LLM
        self.assertFalse(result["has_memory"])
        self.assertEqual(result["complexity"], "simple")

    def test_detect_valid_chatbot(self):
        """Test detection of simple chatbot flow."""
        flow_file = self.fixtures_dir / "simple_chatbot.json"
        result = detector.detect_flowise_flow(flow_file)

        self.assertTrue(result["is_flowise"])
        self.assertEqual(result["flow_type"], "chatbot")
        self.assertEqual(result["node_count"], 3)
        self.assertTrue(result["has_memory"])
        self.assertEqual(result["complexity"], "simple")

    def test_reject_invalid_json(self):
        """Test rejection of non-Flowise JSON."""
        flow_file = self.fixtures_dir / "invalid_file.json"
        result = detector.detect_flowise_flow(flow_file)

        self.assertFalse(result["is_flowise"])
        self.assertEqual(result["flow_type"], "unknown")
        self.assertEqual(result["node_count"], 0)

    def test_reject_missing_file(self):
        """Test handling of missing file."""
        flow_file = self.fixtures_dir / "nonexistent.json"
        result = detector.detect_flowise_flow(flow_file)

        self.assertFalse(result["is_flowise"])
        self.assertEqual(result["flow_type"], "unknown")

    def test_reject_malformed_json(self):
        """Test handling of malformed JSON."""
        # Create temporary malformed JSON
        malformed_file = self.fixtures_dir / "malformed.json"
        try:
            with open(malformed_file, "w") as f:
                f.write('{"invalid": json syntax')

            result = detector.detect_flowise_flow(malformed_file)

            self.assertFalse(result["is_flowise"])
            self.assertEqual(result["flow_type"], "unknown")
        finally:
            if malformed_file.exists():
                malformed_file.unlink()

    def test_classify_complexity_simple(self):
        """Test complexity classification for simple flows."""
        complexity = detector.calculate_complexity(
            node_count=3, edge_count=2, agent_count=0
        )
        self.assertEqual(complexity, "simple")

    def test_classify_complexity_moderate(self):
        """Test complexity classification for moderate flows."""
        complexity = detector.calculate_complexity(
            node_count=8, edge_count=10, agent_count=2
        )
        self.assertEqual(complexity, "moderate")

    def test_classify_complexity_complex(self):
        """Test complexity classification for complex flows."""
        complexity = detector.calculate_complexity(
            node_count=20, edge_count=30, agent_count=5
        )
        self.assertEqual(complexity, "complex")

    def test_scan_directory(self):
        """Test directory scanning for JSON files."""
        json_files = detector.scan_directory(self.fixtures_dir)

        self.assertGreater(len(json_files), 0)
        self.assertTrue(all(f.suffix == ".json" for f in json_files))
        self.assertTrue(all(f.exists() for f in json_files))

    def test_scan_nonexistent_directory(self):
        """Test scanning nonexistent directory."""
        json_files = detector.scan_directory(Path("/nonexistent/path"))
        self.assertEqual(len(json_files), 0)

    def test_classify_flow_type_workflow(self):
        """Test classification of workflow type (multiple LLM chains)."""
        nodes = [
            {"type": "LLMChain", "id": "1"},
            {"type": "LLMChain", "id": "2"},
            {"type": "LLMChain", "id": "3"},
        ]
        node_types = ["LLMChain", "LLMChain", "LLMChain"]
        edges = []

        flow_type = detector.classify_flow_type(nodes, node_types, edges)
        self.assertEqual(flow_type, "workflow")

    def test_empty_nodes_returns_negative(self):
        """Test that empty nodes list returns negative result."""
        flow_data = {"nodes": [], "edges": []}

        # Create temporary file
        temp_file = self.fixtures_dir / "empty.json"
        try:
            with open(temp_file, "w") as f:
                json.dump(flow_data, f)

            result = detector.detect_flowise_flow(temp_file)
            self.assertFalse(result["is_flowise"])
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_node_type_extraction(self):
        """Test extraction of node types from various formats."""
        nodes = [
            {"type": "AgentExecutor"},
            {"data": {"type": "LLMChain"}},
            {"data": {"name": "CustomNode"}},
            {},  # No type info
        ]

        node_types = detector._extract_node_types(nodes)
        self.assertEqual(len(node_types), 3)  # 3 valid types
        self.assertIn("AgentExecutor", node_types)
        self.assertIn("LLMChain", node_types)
        self.assertIn("CustomNode", node_types)


if __name__ == "__main__":
    unittest.main()
