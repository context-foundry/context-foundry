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


class FlowiseValidator:
    """Validates Flowise workflows against failure patterns"""

    def __init__(self, workflow_file: Path):
        self.workflow_file = workflow_file
        self.errors = []
        self.warnings = []

        with open(workflow_file) as f:
            self.workflow = json.load(f)

        self.nodes = self.workflow.get("nodes", [])
        self.edges = self.workflow.get("edges", [])

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
        self.validate_pattern_10_hil_gate_inputparams()
        self.validate_pattern_14_node_type_mismatch()  # CRITICAL
        self.validate_pattern_15_missing_agent_state_updates()  # NEW! CRITICAL
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
        hil_nodes = [
            n
            for n in self.nodes
            if n.get("data", {}).get("name") == "humanInputAgentflow"
        ]

        if not hil_nodes:
            return  # No HIL gates, skip

        print(
            f"[Pattern #10] HIL Gate inputParams Validation ({len(hil_nodes)} gate(s))"
        )

        for hil_node in hil_nodes:
            node_id = hil_node.get("id", "unknown")
            node_label = hil_node.get("data", {}).get("label", "Unknown")
            input_params = hil_node.get("data", {}).get("inputParams", [])
            inputs = hil_node.get("data", {}).get("inputs", {})

            # Check 1: inputParams should have exactly 5 elements (updated per Pattern #11)
            if len(input_params) != 5:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) has {len(input_params)} inputParams (expected 5)"
                )

            # Check 2: No humanInputOutputAnchors in inputParams
            has_invalid_param = any(
                p.get("name") == "humanInputOutputAnchors" for p in input_params
            )
            if has_invalid_param:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) has invalid 'humanInputOutputAnchors' inputParam\n"
                    f"     This causes blank screen in Flowise UI - MUST be removed"
                )

            # Check 3: No humanInputOutputAnchors in inputs object
            if "humanInputOutputAnchors" in inputs:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) has 'humanInputOutputAnchors' in inputs object\n"
                    f"     MUST be removed - outputAnchors are hardcoded, not configurable"
                )

            # Check 4: outputAnchors should have exactly 2 routes (proceed/reject)
            output_anchors = hil_node.get("data", {}).get("outputAnchors", [])
            if len(output_anchors) != 2:
                self.warnings.append(
                    f"  ⚠️  HIL node '{node_label}' ({node_id}) has {len(output_anchors)} outputAnchors (expected 2: proceed/reject)"
                )

            # Check 5: Validate required inputParams exist (all 5 per Pattern #11)
            required_params = {
                "humanInputDescriptionType",
                "humanInputDescription",
                "humanInputModel",
                "humanInputModelPrompt",
                "humanInputEnableFeedback",
            }
            actual_params = {p.get("name") for p in input_params}
            missing = required_params - actual_params
            if missing:
                self.errors.append(
                    f"  ❌ HIL node '{node_label}' ({node_id}) missing required inputParams: {missing}"
                )

            # Check 6: Validate type and version
            node_type = hil_node.get("data", {}).get("type")
            if node_type != "HumanInput":
                self.warnings.append(
                    f"  ⚠️  HIL node '{node_label}' ({node_id}) has type='{node_type}' (expected 'HumanInput')"
                )

            version = hil_node.get("data", {}).get("version")
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
        custom_nodes = [n for n in self.nodes if n.get("type") == "customNode"]
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
        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("name") == "agentAgentflow"
        ]
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

        condition_nodes = [
            n
            for n in self.nodes
            if n.get("data", {}).get("name") == "conditionAgentAgentflow"
        ]

        for condition_node in condition_nodes:
            node_id = condition_node.get("id")
            scenarios = (
                condition_node.get("data", {})
                .get("inputs", {})
                .get("conditionAgentScenarios", [])
            )

            if isinstance(scenarios, str):
                scenarios = []

            scenario_count = len(scenarios)

            # Count outgoing edges from this condition node
            outgoing_edges = [e for e in self.edges if e.get("source") == node_id]
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
        valid_tools = {"currentDateTime", "searXNG", "calculator", "webBrowser"}

        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("name") == "agentAgentflow"
        ]

        for agent in agent_nodes:
            agent_label = agent.get("data", {}).get("label", "Unknown")
            tools = agent.get("data", {}).get("inputs", {}).get("agentTools", [])

            if isinstance(tools, str):
                continue  # Empty string, no tools

            for tool in tools:
                tool_name = tool.get("agentSelectedTool", "")
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

        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("name") == "agentAgentflow"
        ]

        for agent in agent_nodes:
            agent_label = agent.get("data", {}).get("label", "Unknown")
            tools = agent.get("data", {}).get("inputs", {}).get("agentTools", [])

            if isinstance(tools, str):
                continue

            for tool in tools:
                # Check for agentSelectedToolConfig
                if "agentSelectedToolConfig" not in tool:
                    self.errors.append(
                        f"  ❌ Agent '{agent_label}' tool '{tool.get('agentSelectedTool')}' missing 'agentSelectedToolConfig'\n"
                        f"     MUST include nested config object"
                    )

                # Check for correct field name (not requiresHumanInput)
                if "requiresHumanInput" in tool:
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

        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("name") == "agentAgentflow"
        ]

        for agent in agent_nodes:
            agent_label = agent.get("data", {}).get("label", "Unknown")
            input_params = agent.get("data", {}).get("inputParams", [])

            if not input_params or len(input_params) == 0:
                self.errors.append(
                    f"  ❌ Agent '{agent_label}' has no inputParams array\n"
                    f"     MUST include complete inputParams definition"
                )

        if not self.errors:
            print("  ✅ All agents have inputParams arrays\n")
        else:
            print()

    def validate_pattern_14_node_type_mismatch(self):
        """Pattern #14: Node Type Mismatch (CRITICAL)"""
        print("[Pattern #14] Node Type Mismatch Validation (CRITICAL)")

        # Check 1: Start node type validation
        start_nodes = [n for n in self.nodes if n.get("id", "").startswith("start_")]
        for start_node in start_nodes:
            node_id = start_node.get("id", "unknown")
            node_name = start_node.get("data", {}).get("name", "")
            node_type = start_node.get("data", {}).get("type", "")

            # Check for correct node name
            if node_name != "startAgentflow":
                self.errors.append(
                    f"  ❌ Start node '{node_id}' has wrong name: '{node_name}' (expected 'startAgentflow')\n"
                    f"     This causes sync problems in Flowise UI - MUST be 'startAgentflow'"
                )

            # Check for correct node type (CRITICAL)
            if node_type != "Start":
                self.errors.append(
                    f"  ❌ Start node '{node_id}' has WRONG TYPE: '{node_type}' (expected 'Start')\n"
                    f"     Common mistake: using 'StartFlow' instead of 'Start'\n"
                    f"     This causes sync problems and missing icons in Flowise UI"
                )

            # Check for hideInput
            hide_input = start_node.get("data", {}).get("hideInput")
            if hide_input != True:
                self.errors.append(
                    f"  ❌ Start node '{node_id}' missing 'hideInput: true'"
                )

        # Check 2: ConditionAgent vs Condition node type validation
        condition_nodes = [
            n for n in self.nodes if "condition" in n.get("id", "").lower()
        ]
        for node in condition_nodes:
            node_id = node.get("id", "unknown")
            node_name = node.get("data", {}).get("name", "")
            node_type = node.get("data", {}).get("type", "")

            # AI-driven routing should use ConditionAgent
            if node_name == "conditionAgentAgentflow":
                if node_type != "ConditionAgent":
                    self.errors.append(
                        f"  ❌ Condition node '{node_id}' has WRONG TYPE: '{node_type}' (expected 'ConditionAgent')\n"
                        f"     Common mistake: using 'ConditionNode' or 'Condition' for AI routing\n"
                        f"     AI-driven routing MUST use type 'ConditionAgent'"
                    )

            # Deterministic logic should use Condition
            elif node_name == "conditionAgentflow":
                if node_type != "Condition":
                    self.errors.append(
                        f"  ❌ Condition node '{node_id}' has WRONG TYPE: '{node_type}' (expected 'Condition')\n"
                        f"     Deterministic if/else logic MUST use type 'Condition'"
                    )

            # Unknown condition node name
            elif node_type in ["ConditionNode", "conditionNode"]:
                self.errors.append(
                    f"  ❌ Node '{node_id}' uses invalid type '{node_type}'\n"
                    f"     Use 'ConditionAgent' for AI routing or 'Condition' for deterministic logic\n"
                    f"     'ConditionNode' is NOT a valid Flowise type"
                )

        # Check 3: DirectReply node validation
        reply_nodes = [
            n
            for n in self.nodes
            if "reply" in n.get("id", "").lower()
            or n.get("data", {}).get("name") == "directReplyAgentflow"
        ]
        for node in reply_nodes:
            node_id = node.get("id", "unknown")
            node_label = node.get("data", {}).get("label", "Unknown")
            node_name = node.get("data", {}).get("name", "")
            node_type = node.get("data", {}).get("type", "")

            # Check for correct node name
            if node_name and node_name != "directReplyAgentflow":
                self.warnings.append(
                    f"  ⚠️  DirectReply node '{node_id}' has unexpected name: '{node_name}' (expected 'directReplyAgentflow')"
                )

            # Check for correct node type (CRITICAL)
            if node_type != "DirectReply":
                self.errors.append(
                    f"  ❌ DirectReply node '{node_label}' ({node_id}) has WRONG TYPE: '{node_type}' (expected 'DirectReply')\n"
                    f"     Common mistake: using 'directReply' (lowercase) or 'Reply'\n"
                    f"     This causes missing icons in Flowise UI"
                )

            # Check for hideOutput
            hide_output = node.get("data", {}).get("hideOutput")
            if hide_output != True:
                self.errors.append(
                    f"  ❌ DirectReply node '{node_label}' ({node_id}) missing 'hideOutput: true'\n"
                    f"     Terminal nodes MUST have hideOutput set to true"
                )

            # Check for directReplyMessage in inputParams
            input_params = node.get("data", {}).get("inputParams", [])
            has_message_param = any(
                p.get("name") == "directReplyMessage" for p in input_params
            )
            if not has_message_param:
                self.errors.append(
                    f"  ❌ DirectReply node '{node_label}' ({node_id}) missing 'directReplyMessage' in inputParams\n"
                    f"     DirectReply nodes MUST have directReplyMessage parameter"
                )

            # Check for directReplyMessage in inputs
            inputs = node.get("data", {}).get("inputs", {})
            if "directReplyMessage" not in inputs:
                self.errors.append(
                    f"  ❌ DirectReply node '{node_label}' ({node_id}) missing 'directReplyMessage' in inputs\n"
                    f"     MUST include message content"
                )

        # Check 4: Agent node type validation
        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("name") == "agentAgentflow"
        ]
        for node in agent_nodes:
            node_id = node.get("id", "unknown")
            node_label = node.get("data", {}).get("label", "Unknown")
            node_type = node.get("data", {}).get("type", "")

            if node_type != "Agent":
                self.errors.append(
                    f"  ❌ Agent node '{node_label}' ({node_id}) has WRONG TYPE: '{node_type}' (expected 'Agent')\n"
                    f"     Common mistake: using 'agent' (lowercase) or 'AgentNode'\n"
                    f"     This causes missing icons and execution failures"
                )

        # Check 5: Iteration node type validation
        iteration_nodes = [
            n
            for n in self.nodes
            if "iteration" in n.get("id", "").lower()
            or n.get("data", {}).get("name") == "iterationAgentflow"
        ]
        for node in iteration_nodes:
            node_id = node.get("id", "unknown")
            node_type = node.get("data", {}).get("type", "")

            if node_type and node_type != "Iteration":
                self.errors.append(
                    f"  ❌ Iteration node '{node_id}' has WRONG TYPE: '{node_type}' (expected 'Iteration')\n"
                    f"     Common mistake: using 'IterationNode' or 'Loop'\n"
                    f"     This causes missing icons and loop failures"
                )

        # Check 6: StickyNote type validation
        sticky_nodes = [
            n
            for n in self.nodes
            if n.get("type") == "stickyNote"
            or n.get("data", {}).get("type") == "stickyNote"
        ]
        for node in sticky_nodes:
            node_id = node.get("id", "unknown")
            # Type is at top level for sticky notes, not in data.type
            node_type = node.get("type", "")

            if node_type != "stickyNote":
                self.warnings.append(
                    f"  ⚠️  Sticky note '{node_id}' has wrong type: '{node_type}' (expected 'stickyNote' lowercase)\n"
                    f"     Common mistake: using 'StickyNote' (capital S)"
                )

        if not self.errors and not self.warnings:
            print("  ✅ All node types are correct (Pattern #14 passed)\n")
        else:
            print()

    def validate_pattern_15_missing_agent_state_updates(self):
        """Pattern #15: Missing Agent State Updates (CRITICAL)"""
        print("[Pattern #15] Agent State Updates Validation (CRITICAL)")

        # Only validate if there are multiple agents (chaining pattern)
        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("type") == "Agent"
        ]

        if len(agent_nodes) < 2:
            print("  ℹ️  Single agent or no agents - state updates not required\n")
            return

        # Validate each agent node
        for node in agent_nodes:
            node_id = node.get("id", "unknown")
            node_label = node.get("data", {}).get("label", "Unknown")

            # Check 1: agentStateUpdates exists in inputParams
            input_params = node.get("data", {}).get("inputParams", [])
            has_state_updates_param = any(
                p.get("name") == "agentStateUpdates" for p in input_params
            )

            if not has_state_updates_param:
                self.errors.append(
                    f"  ❌ Agent '{node_label}' (id: {node_id}) missing 'agentStateUpdates' in inputParams\n"
                    f"     Without this, workflow will stop after this agent\n"
                    f'     Add inputParam: {{"name": "agentStateUpdates", "type": "array", ...}}'
                )
                continue  # Skip inputs check if inputParams is missing

            # Check 2: agentStateUpdates configuration in inputs
            inputs = node.get("data", {}).get("inputs", {})
            state_updates = inputs.get("agentStateUpdates", [])

            if not state_updates or len(state_updates) == 0:
                self.errors.append(
                    f"  ❌ Agent '{node_label}' (id: {node_id}) has no agentStateUpdates configuration\n"
                    f"     Agent cannot update Flow State - workflow will not progress\n"
                    f'     Add inputs.agentStateUpdates: [{{"key": "variable_name", "value": "{{ artifact_id }}"}}]'
                )

            # Check 3: System message uses artifact output pattern
            system_message = inputs.get("agentSystemMessage", "")
            has_artifact = "antArtifact identifier=" in system_message

            if not has_artifact:
                self.warnings.append(
                    f"  ⚠️  Agent '{node_label}' (id: {node_id}) prompt doesn't use artifact output\n"
                    f"     Recommended: Use <antArtifact identifier='variable_name'>...</antArtifact>\n"
                    f"     This ensures reliable Flow State updates"
                )

        if not self.errors and not self.warnings:
            print(
                "  ✅ All agents have proper state management configured (Pattern #15 passed)\n"
            )
        else:
            print()

    def validate_structure_authority(self):
        """FLOWISE-STRUCTURE-AUTHORITY.md validation"""
        print("[STRUCTURE] FLOWISE-STRUCTURE-AUTHORITY Compliance")

        # Check outputAnchor ID format (no extra suffixes)
        for node in self.nodes:
            output_anchors = node.get("data", {}).get("outputAnchors", [])
            for anchor in output_anchors:
                anchor_id = anchor.get("id", "")
                node_name = node.get("data", {}).get("name", "")

                # Check for forbidden suffixes
                if "-StartFlow" in anchor_id or "-Agent|AgentExecutor" in anchor_id:
                    self.errors.append(
                        f"  ❌ Node '{node.get('id')}' has invalid outputAnchor ID: {anchor_id}\n"
                        f"     MUST NOT include '-StartFlow' or '-Agent|AgentExecutor' suffix"
                    )

        # Check agentMessages is empty string (not array)
        agent_nodes = [
            n for n in self.nodes if n.get("data", {}).get("name") == "agentAgentflow"
        ]
        for agent in agent_nodes:
            agent_label = agent.get("data", {}).get("label", "Unknown")
            agent_messages = (
                agent.get("data", {}).get("inputs", {}).get("agentMessages")
            )

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


if __name__ == "__main__":
    main()
