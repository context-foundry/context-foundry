#!/usr/bin/env python3
"""
Flowise Workflow Validator - Comprehensive Pattern-Based Validation

Validates Flowise JSON workflows against all documented failure patterns
in FAILURE_PATTERNS.md to prevent known issues before deployment.

Usage:
    python3 validate_workflow.py <workflow.json>

Exit Codes:
    0 - All validations passed
    1 - Critical failures found (blocks deployment)
    2 - Warnings found (manual review recommended)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

class FlowiseValidator:
    """Validates Flowise workflows against failure patterns"""

    def __init__(self, workflow_file: Path):
        self.workflow_file = workflow_file
        self.errors = []
        self.warnings = []

        with open(workflow_file) as f:
            self.workflow = json.load(f)

        self.nodes = self.workflow.get('nodes', [])
        self.edges = self.workflow.get('edges', [])

    def validate_all(self) -> int:
        """Run all validations, return exit code"""
        print(f"🔍 Validating Flowise workflow: {self.workflow_file.name}")
        print(f"   Nodes: {len(self.nodes)}, Edges: {len(self.edges)}\n")

        # Run all validation checks
        self.validate_pattern_01_meta_description()
        self.validate_pattern_04_disconnected_nodes()
        self.validate_pattern_05_phantom_tools()
        self.validate_pattern_06_tool_structure()
        self.validate_pattern_08_missing_inputparams()
        self.validate_pattern_10_hil_gate_inputparams()  # NEW!
        self.validate_structure_authority()

        # Report results
        self.print_results()

        if self.errors:
            return 1  # Critical failures
        elif self.warnings:
            return 2  # Warnings only
        else:
            return 0  # All pass

    def validate_pattern_10_hil_gate_inputparams(self):
        """Pattern #10: HIL Gate Invalid inputParams Configuration"""
        hil_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'humanInputAgentflow']

        if not hil_nodes:
            return  # No HIL gates, skip

        print(f"[Pattern #10] HIL Gate inputParams Validation ({len(hil_nodes)} gate(s))")

        for hil_node in hil_nodes:
            node_id = hil_node.get('id', 'unknown')
            node_label = hil_node.get('data', {}).get('label', 'Unknown')
            input_params = hil_node.get('data', {}).get('inputParams', [])
            inputs = hil_node.get('data', {}).get('inputs', {})

            # Check 1: inputParams should have exactly 3 elements
            if len(input_params) != 3:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) has {len(input_params)} inputParams (expected 3)"
                )

            # Check 2: No humanInputOutputAnchors in inputParams
            has_invalid_param = any(
                p.get('name') == 'humanInputOutputAnchors'
                for p in input_params
            )
            if has_invalid_param:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) has invalid 'humanInputOutputAnchors' inputParam\n"
                    f"     This causes blank screen in Flowise UI - MUST be removed"
                )

            # Check 3: No humanInputOutputAnchors in inputs object
            if 'humanInputOutputAnchors' in inputs:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) has 'humanInputOutputAnchors' in inputs object\n"
                    f"     MUST be removed - outputAnchors are hardcoded, not configurable"
                )

            # Check 4: outputAnchors should have exactly 2 routes (proceed/reject)
            output_anchors = hil_node.get('data', {}).get('outputAnchors', [])
            if len(output_anchors) != 2:
                self.warnings.append(
                    f"  ⚠️  HIL node '{node_label}' ({node_id}) has {len(output_anchors)} outputAnchors (expected 2: proceed/reject)"
                )

            # Check 5: Validate required inputParams exist
            required_params = {'humanInputDescriptionType', 'humanInputDescription', 'humanInputEnableFeedback'}
            actual_params = {p.get('name') for p in input_params}
            missing = required_params - actual_params
            if missing:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) missing required inputParams: {missing}"
                )

            # Check 6: Validate type and version
            node_type = hil_node.get('data', {}).get('type')
            if node_type != 'HumanInput':
                self.warnings.append(
                    f"  ⚠️  HIL node '{node_label}' ({node_id}) has type='{node_type}' (expected 'HumanInput')"
                )

            version = hil_node.get('data', {}).get('version')
            if version != 1.0:
                self.warnings.append(
                    f"  ⚠️  HIL node '{node_label}' ({node_id}) has version={version} (expected 1.0)"
                )

        if not self.errors and not self.warnings:
            print("  ✅ All HIL gates configured correctly\n")
        else:
            print()

    def validate_pattern_01_meta_description(self):
        """Pattern #1: Meta-Description Instead of Complete Flow"""
        print("[Pattern #1] Complete Flow Validation")

        # Check for customNode types (meta-description indicator)
        custom_nodes = [n for n in self.nodes if n.get('type') == 'customNode']
        if custom_nodes:
            self.errors.append(
                f"  ❌ Found {len(custom_nodes)} customNode types (indicates meta-description, not complete flow)"
            )

        # Check file size is substantial
        file_size = self.workflow_file.stat().st_size
        if file_size < 10000:  # Less than 10KB is suspicious for multi-agent flow
            self.warnings.append(
                f"  ⚠️  Workflow file only {file_size} bytes (expected >10KB for complete flows)"
            )

        # Check for agent nodes
        agent_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'agentAgentflow']
        if not agent_nodes and len(self.nodes) > 2:
            self.warnings.append(
                f"  ⚠️  No agent nodes found, but {len(self.nodes)} nodes exist"
            )

        if not self.errors and not self.warnings:
            print("  ✅ Complete flow structure detected\n")
        else:
            print()

    def validate_pattern_04_disconnected_nodes(self):
        """Pattern #4: Disconnected Agent Nodes"""
        print("[Pattern #4] Node Connectivity Validation")

        condition_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'conditionAgentAgentflow']

        for condition_node in condition_nodes:
            node_id = condition_node.get('id')
            scenarios = condition_node.get('data', {}).get('inputs', {}).get('conditionAgentScenarios', [])

            if isinstance(scenarios, str):
                scenarios = []

            scenario_count = len(scenarios)

            # Count outgoing edges from this condition node
            outgoing_edges = [e for e in self.edges if e.get('source') == node_id]
            edge_count = len(outgoing_edges)

            if scenario_count != edge_count:
                self.errors.append(
                    f"  ❌ Condition node '{node_id}' has {scenario_count} scenarios but {edge_count} edges\n"
                    f"     MUST match: each scenario needs corresponding edge"
                )

        if not self.errors:
            print("  ✅ All condition nodes properly connected\n")
        else:
            print()

    def validate_pattern_05_phantom_tools(self):
        """Pattern #5: Phantom Tool and Knowledge References"""
        print("[Pattern #5] Phantom Tool Detection")

        # Known valid Flowise tools
        valid_tools = {'currentDateTime', 'searXNG', 'calculator', 'webBrowser'}

        agent_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'agentAgentflow']

        for agent in agent_nodes:
            agent_label = agent.get('data', {}).get('label', 'Unknown')
            tools = agent.get('data', {}).get('inputs', {}).get('agentTools', [])

            if isinstance(tools, str):
                continue  # Empty string, no tools

            for tool in tools:
                tool_name = tool.get('agentSelectedTool', '')
                if tool_name and tool_name not in valid_tools:
                    self.warnings.append(
                        f"  ⚠️  Agent '{agent_label}' references unknown tool '{tool_name}'\n"
                        f"     Valid tools: {valid_tools}\n"
                        f"     Consider using empty string if tool not needed"
                    )

        if not self.warnings:
            print("  ✅ No phantom tool references detected\n")
        else:
            print()

    def validate_pattern_06_tool_structure(self):
        """Pattern #6: Incorrect Tool JSON Structure"""
        print("[Pattern #6] Tool Structure Validation")

        agent_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'agentAgentflow']

        for agent in agent_nodes:
            agent_label = agent.get('data', {}).get('label', 'Unknown')
            tools = agent.get('data', {}).get('inputs', {}).get('agentTools', [])

            if isinstance(tools, str):
                continue

            for tool in tools:
                # Check for agentSelectedToolConfig
                if 'agentSelectedToolConfig' not in tool:
                    self.errors.append(
                        f"  ❌ Agent '{agent_label}' tool '{tool.get('agentSelectedTool')}' missing 'agentSelectedToolConfig'\n"
                        f"     MUST include nested config object"
                    )

                # Check for correct field name (not requiresHumanInput)
                if 'requiresHumanInput' in tool:
                    self.errors.append(
                        f"  ❌ Agent '{agent_label}' uses 'requiresHumanInput' (should be 'agentSelectedToolRequiresHumanInput')"
                    )

        if not self.errors:
            print("  ✅ All tools have correct structure\n")
        else:
            print()

    def validate_pattern_08_missing_inputparams(self):
        """Pattern #8: Agent Nodes Missing inputParams"""
        print("[Pattern #8] InputParams Validation")

        agent_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'agentAgentflow']

        for agent in agent_nodes:
            agent_label = agent.get('data', {}).get('label', 'Unknown')
            input_params = agent.get('data', {}).get('inputParams', [])

            if not input_params or len(input_params) == 0:
                self.errors.append(
                    f"  ❌ Agent '{agent_label}' has no inputParams array\n"
                    f"     MUST include complete inputParams definition"
                )

        if not self.errors:
            print("  ✅ All agents have inputParams arrays\n")
        else:
            print()

    def validate_structure_authority(self):
        """FLOWISE-STRUCTURE-AUTHORITY.md validation"""
        print("[STRUCTURE] FLOWISE-STRUCTURE-AUTHORITY Compliance")

        # Check outputAnchor ID format (no extra suffixes)
        for node in self.nodes:
            output_anchors = node.get('data', {}).get('outputAnchors', [])
            for anchor in output_anchors:
                anchor_id = anchor.get('id', '')
                node_name = node.get('data', {}).get('name', '')

                # Check for forbidden suffixes
                if '-StartFlow' in anchor_id or '-Agent|AgentExecutor' in anchor_id:
                    self.errors.append(
                        f"  ❌ Node '{node.get('id')}' has invalid outputAnchor ID: {anchor_id}\n"
                        f"     MUST NOT include '-StartFlow' or '-Agent|AgentExecutor' suffix"
                    )

        # Check agentMessages is empty string (not array)
        agent_nodes = [n for n in self.nodes if n.get('data', {}).get('name') == 'agentAgentflow']
        for agent in agent_nodes:
            agent_label = agent.get('data', {}).get('label', 'Unknown')
            agent_messages = agent.get('data', {}).get('inputs', {}).get('agentMessages')

            if isinstance(agent_messages, list):
                self.errors.append(
                    f"  ❌ Agent '{agent_label}' has agentMessages as array (should be empty string \"\")"
                )

        if not self.errors:
            print("  ✅ Structure authority compliance verified\n")
        else:
            print()

    def print_results(self):
        """Print validation summary"""
        print("=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        if self.errors:
            print(f"\n❌ CRITICAL FAILURES ({len(self.errors)}):\n")
            for error in self.errors:
                print(error)
            print("\n🔧 BUILD BLOCKED - Fix critical failures before deployment")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):\n")
            for warning in self.warnings:
                print(warning)
            print("\n💡 Manual review recommended")

        if not self.errors and not self.warnings:
            print("\n✅ ALL VALIDATIONS PASSED")
            print("   Workflow is ready for Flowise import")

        print("\n" + "=" * 70)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 validate_workflow.py <workflow.json>")
        sys.exit(1)

    workflow_file = Path(sys.argv[1])

    if not workflow_file.exists():
        print(f"Error: File not found: {workflow_file}")
        sys.exit(1)

    validator = FlowiseValidator(workflow_file)
    exit_code = validator.validate_all()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
