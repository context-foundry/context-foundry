# Agent Refactoring Audit Report

**Date:** 2025-11-30
**Objective:** Refactor Agent Logic for Hybrid "Cloud Brain, Local Hands" Architecture
**Status:** Complete

## 1. Executive Summary

This report documents the successful refactoring of the Context Foundry agent architecture. The primary goal was to decouple agent logic from local execution dependencies (specifically the `claude` CLI) to enable a hybrid architecture where agents can run either locally or in the cloud (e.g., AWS Bedrock), while tool execution remains local.

**Key Achievements:**
*   **Decoupled Agents:** All agents (`Scout`, `Architect`, `Builder`, `Generic`) are now standalone Python classes inheriting from a common `Agent` interface.
*   **Abstracted Execution:** Introduced `LLMProvider` abstraction, allowing seamless switching between `LocalClaudeProvider` (CLI) and `BedrockProvider` (Cloud API).
*   **Restored Visibility:** Implemented real-time event streaming in the local provider to ensure the dashboard continues to function with the new architecture.
*   **Communication Bridge:** Established a secure protocol and API endpoint for remote agents ("Cloud Brain") to execute tools on the local machine ("Local Hands").

## 2. Architectural Changes

### Previous Architecture (Implicit)
*   Agents were defined implicitly within `phase_execution.py`.
*   Execution was tightly coupled to `subprocess.run(["claude", ...])`.
*   No clear separation between the "Brain" (LLM logic) and "Hands" (Tool execution).

### New Architecture (Hybrid)
*   **Agent Interface:** A formal `Agent` class defines the contract (`run`, `get_system_prompt`).
*   **LLM Provider:** An `LLMProvider` interface handles the interaction with the AI model.
    *   `LocalClaudeProvider`: Wraps the local `claude` CLI (Subscription).
    *   `BedrockProvider`: Stub for AWS Bedrock API (Pay-per-use).
*   **Orchestration:** `phase_execution.py` instantiates the configured Agent + Provider and delegates execution.
*   **Bridge:** A `ToolExecutor` and Daemon API endpoint allow remote agents to drive local tools.

## 3. Component Details

### 3.1 Framework (`tools/evolution/framework`)
*   **`agent_base.py`**: Defines the abstract base class `Agent`.
*   **`llm_provider.py`**: Defines `LLMProvider` abstract class and `LocalClaudeProvider` implementation.
    *   **Streaming:** `LocalClaudeProvider` supports `event_callback` to stream JSON events from the `claude` CLI, preserving dashboard visibility.

### 3.2 Agents (`tools/evolution/agents`)
*   **`ScoutAgent`**: Refactored to inherit from `Agent`. Now returns findings programmatically and saves reports (`scout_report.json`, `scout-report.md`) for downstream consumption.
*   **`ArchitectAgent`**: New class encapsulating the architecture phase logic.
*   **`BuilderAgent`**: New class encapsulating the build phase logic.
*   **`GenericAgent`**: New class handling standard phases (Test, Deploy, Screenshot, Feedback, etc.) using prompt files.
    *   **Prompt Coverage:** Created missing `phase_screenshot.txt` and `phase_feedback.txt` to ensure all phases have dedicated system prompts.

### 3.3 Communication Bridge (`tools/evolution/communication`)
*   **`tool_executor.py`**: A secure sandbox for executing tools locally (`run_command`, `read_file`, `write_file`, `list_directory`).
*   **`cloud_client.py`**: `RemoteToolExecutor` client for remote agents to send commands to the local daemon.
*   **Daemon API**: Added `POST /tools/execute` endpoint to `context_foundry/daemon/http_api.py` to expose the `ToolExecutor`.

## 4. Orchestration & Dashboard

### 4.1 Phase Execution (`tools/mcp_utils/phase_execution.py`)
*   **Deprecation:** Removed direct `subprocess` calls to `claude`.
*   **Dynamic Instantiation:** `_run_phase_internal` now selects the `Agent` class based on the phase name and the `LLMProvider` based on configuration.
*   **Logging:** Wired up `ConversationLogger` to the `event_callback` of the `Agent.run()` method. This ensures that "Thinking..." states and tool usage are visible in the dashboard.

## 5. Verification & Testing

### 5.1 Agent Verification
*   **Script:** `tools/evolution/agents/verify_agents.py`
*   **Result:** Confirmed successful instantiation of all Agent classes with `LocalClaudeProvider`.

### 5.2 Bridge Verification
*   **Script:** `tools/evolution/communication/verify_bridge.py`
*   **Result:** Confirmed `ToolExecutor` correctly handles:
    *   Command execution (`echo`)
    *   File writing and reading
    *   Directory listing

## 6. Usage & Configuration

### Switching Providers
To switch an agent to use AWS Bedrock (once implemented), you would instantiate it with the `BedrockProvider`:

```python
from tools.evolution.framework.llm_provider import BedrockProvider
from tools.evolution.agents.architect_agent import ArchitectAgent

agent = ArchitectAgent(llm_provider=BedrockProvider())
```

### Enabling the Bridge
The `POST /tools/execute` endpoint is available on the daemon (default port 8421). To enable it, restart the daemon:

```bash
cfd stop
cfd start
```

## 7. Future Work

1.  **Bedrock Implementation:** Flesh out `BedrockProvider` with `boto3` logic to fully enable the cloud path.
2.  **Cloud Orchestrator:** Create the cloud-side component that uses `RemoteToolExecutor` to drive the local build.
3.  **Security Hardening:** Add authentication/authorization to the `POST /tools/execute` endpoint before exposing it beyond `localhost`.
