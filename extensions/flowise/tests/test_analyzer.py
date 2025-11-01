"""
Tests for Flowise Template Analyzer
"""

import json
import unittest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import analyzer


class TestFlowiseAnalyzer(unittest.TestCase):
    """Test cases for Flowise template analyzer."""

    def setUp(self):
        """Set up test fixtures path."""
        self.fixtures_dir = Path(__file__).parent / 'fixtures'

    def test_analyze_template_valid(self):
        """Test analysis of valid template."""
        template_file = self.fixtures_dir / 'supervisor_multi_agent.json'
        result = analyzer.analyze_template(template_file)

        self.assertTrue(result['success'])
        self.assertEqual(result['node_count'], 5)
        self.assertEqual(result['edge_count'], 4)
        self.assertIn('node_patterns', result)
        self.assertIn('connection_patterns', result)

    def test_analyze_template_invalid_file(self):
        """Test analysis of nonexistent file."""
        template_file = self.fixtures_dir / 'nonexistent.json'
        result = analyzer.analyze_template(template_file)

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_analyze_directory(self):
        """Test analysis of directory with multiple templates."""
        result = analyzer.analyze_directory(self.fixtures_dir)

        self.assertTrue(result['success'])
        self.assertGreater(result['total_files'], 0)
        self.assertGreater(result['analyzed_successfully'], 0)
        self.assertIn('node_type_frequency', result)
        self.assertIn('connection_frequency', result)

    def test_analyze_nonexistent_directory(self):
        """Test analysis of nonexistent directory."""
        result = analyzer.analyze_directory(Path('/nonexistent/path'))

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_extract_node_patterns(self):
        """Test node pattern extraction."""
        with open(self.fixtures_dir / 'supervisor_multi_agent.json') as f:
            data = json.load(f)

        patterns = analyzer.extract_node_patterns(data['nodes'])

        self.assertGreater(len(patterns), 0)
        self.assertTrue(all('type' in p for p in patterns))
        self.assertTrue(all('count' in p for p in patterns))

        # Should find AgentExecutor (4 times) and BufferMemory (1 time)
        agent_patterns = [p for p in patterns if 'Agent' in p['type']]
        self.assertGreater(len(agent_patterns), 0)

    def test_extract_node_patterns_empty(self):
        """Test pattern extraction with empty nodes list."""
        patterns = analyzer.extract_node_patterns([])
        self.assertEqual(len(patterns), 0)

    def test_extract_connection_patterns(self):
        """Test connection pattern extraction."""
        with open(self.fixtures_dir / 'supervisor_multi_agent.json') as f:
            data = json.load(f)

        connections = analyzer.extract_connection_patterns(data['edges'], data['nodes'])

        self.assertGreater(len(connections), 0)
        self.assertTrue(all('pattern' in c for c in connections))
        self.assertTrue(all('source' in c for c in connections))
        self.assertTrue(all('target' in c for c in connections))

    def test_extract_connection_patterns_empty(self):
        """Test connection extraction with empty edges."""
        connections = analyzer.extract_connection_patterns([], [])
        self.assertEqual(len(connections), 0)

    def test_export_patterns(self):
        """Test pattern export to JSON file."""
        test_patterns = {
            "test": "data",
            "patterns": [{"id": "test1"}]
        }

        output_file = self.fixtures_dir / 'test_export.json'
        try:
            analyzer.export_patterns(test_patterns, output_file)

            self.assertTrue(output_file.exists())

            # Verify content
            with open(output_file) as f:
                loaded = json.load(f)
                self.assertEqual(loaded['test'], 'data')

        finally:
            if output_file.exists():
                output_file.unlink()

    def test_classification_supervisor_pattern(self):
        """Test classification of supervisor-to-worker connections."""
        pattern = analyzer._classify_connection('SupervisorAgent', 'WorkerAgent')
        self.assertEqual(pattern, 'supervisor-to-worker')

    def test_classification_rag_pattern(self):
        """Test classification of RAG retrieval pattern."""
        pattern = analyzer._classify_connection('VectorStoreRetriever', 'LLMChain')
        self.assertEqual(pattern, 'retrieval-to-llm')

    def test_classification_agent_tool_pattern(self):
        """Test classification of agent-to-tool connections."""
        pattern = analyzer._classify_connection('AgentExecutor', 'CustomTool')
        self.assertEqual(pattern, 'agent-to-tool')

    def test_quality_markers_detection(self):
        """Test identification of quality markers in flows."""
        nodes = [
            {
                'type': 'AgentExecutor',
                'data': {
                    'errorHandling': 'retry',
                    'maxRetries': 3
                }
            }
        ]
        edges = [{'source': '1', 'target': '2'}]

        markers = analyzer._identify_quality_markers(nodes, edges)

        self.assertIn('has_error_handling', markers)
        self.assertIn('has_retry_logic', markers)
        self.assertIn('node_to_edge_ratio', markers)

    def test_common_patterns_extraction(self):
        """Test extraction of common patterns across multiple analyses."""
        analyses = [
            {
                'node_count': 5,
                'edge_count': 4,
                'quality_markers': {'has_error_handling': True, 'has_retry_logic': False}
            },
            {
                'node_count': 8,
                'edge_count': 7,
                'quality_markers': {'has_error_handling': True, 'has_retry_logic': True}
            }
        ]

        common = analyzer._extract_common_patterns(analyses)

        self.assertIn('average_nodes', common)
        self.assertIn('average_edges', common)
        self.assertEqual(common['average_nodes'], 6.5)
        self.assertEqual(common['files_with_error_handling'], 2)


class TestAnalyzerCLI(unittest.TestCase):
    """Test CLI functionality (without actual execution)."""

    def test_main_function_exists(self):
        """Test that main() function is defined."""
        self.assertTrue(callable(analyzer.main))


if __name__ == '__main__':
    unittest.main()
