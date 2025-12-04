# AWS Bedrock AgentCore Migration: Overview

## 🎯 Objective
Transition **Context Foundry** from a "Hybrid Manual" architecture (where we manually manage tool loops and context) to a **"Cloud Native" AgentCore architecture**.

## 🏗️ Architecture Shift

### Current State ("Hybrid Manual")
*   **Brain:** AWS Bedrock API (Stateless).
*   **Memory:** Manual context stuffing (reading `architecture.md` into every prompt).
*   **Hands:** Local Claude CLI or custom `RemoteToolExecutor`.
*   **Orchestration:** Python `while` loops in `BedrockProvider` handling tool calls.

### Future State ("AgentCore")
*   **Brain:** **AWS Bedrock Agent Runtime** (Stateful, Serverless).
*   **Memory:** **AgentCore Memory** (Built-in session persistence).
*   **Hands:** **Action Groups** (API endpoints that Bedrock calls automatically).
*   **Orchestration:** Fully managed by AWS. We just send a prompt, and AgentCore handles the loop.

## 🚀 Benefits
1.  **8-Hour Runtime:** No more timeouts on complex "Builder" phases.
2.  **Session Isolation:** Each build runs in a secure, isolated microVM.
3.  **Simplified Code:** We delete hundreds of lines of manual tool parsing logic.
4.  **Observability:** Built-in CloudWatch traces for every thought and action.

## 📚 Migration Guide
This documentation series covers the transition:

1.  **[02_SETUP_CLI.md](./02_SETUP_CLI.md):** How to provision AgentCore using the AWS CLI (Automated/DevOps approach).
2.  **[03_SETUP_CONSOLE.md](./03_SETUP_CONSOLE.md):** How to provision AgentCore using the AWS Console (Visual/Learning approach).
3.  **[04_ARCHITECTURE_TRANSITION.md](./04_ARCHITECTURE_TRANSITION.md):** Technical details on code changes required in `BedrockProvider`.
