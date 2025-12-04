# Architecture Transition: Code Changes

This document details the technical changes required in the `context-foundry` codebase to switch from the "Hybrid Manual" provider to the **AgentCore Provider**.

## 1. New Provider Class: `BedrockAgentProvider`

We need a new class in `llm_provider.py` that interacts with the *Agent Runtime* instead of the raw *Bedrock Runtime*.

### Old Way (`BedrockProvider`)
*   Uses `boto3.client("bedrock-runtime")`.
*   Calls `invoke_model()`.
*   Manually parses JSON for `tool_use` blocks.
*   Manually executes tools and loops back.

### New Way (`BedrockAgentProvider`)
*   Uses `boto3.client("bedrock-agent-runtime")`.
*   Calls `invoke_agent()`.
*   **No tool loop code!** The Agent Runtime handles the loop.
*   **Streaming is native:** The response from `invoke_agent` is an event stream containing chunks of text, citations, and trace information.

## 2. Code Snippet (Draft)

```python
class BedrockAgentProvider(LLMProvider):
    def __init__(self, agent_id: str, agent_alias_id: str, session_id: str):
        self.client = boto3.client("bedrock-agent-runtime")
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.session_id = session_id

    def generate(self, user_prompt: str, ...) -> str:
        response = self.client.invoke_agent(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            sessionId=self.session_id,
            inputText=user_prompt
        )

        completion = ""
        
        # The response is an Event Stream
        for event in response.get("completion"):
            if "chunk" in event:
                chunk = event["chunk"]
                text = chunk.get("bytes").decode("utf-8")
                completion += text
                # Call event_callback for dashboard visibility
                if event_callback:
                    event_callback({"type": "assistant", "text": text})
            
            elif "trace" in event:
                # Capture "thought process" for the dashboard!
                trace = event["trace"]
                # ... parse trace ...

        return completion
```

## 3. Handling "Return Control" (Local Hands)

If we use the **"Return Control"** invocation type (recommended for local development), the loop *does* come back to us, but in a structured way.

1.  `invoke_agent` returns a `returnControl` event containing the tool call.
2.  We execute the tool locally (using our existing `ToolExecutor`).
3.  We call `invoke_agent` *again*, passing the tool result in the `sessionState`.

This is safer than the raw API because AWS manages the conversation history and state validation.

## 4. Configuration Updates

We will need to update `provider_config.json` to support Agent IDs:

```json
"phases": {
  "Builder": {
    "provider": "bedrock-agent",
    "agent_id": "AG12345678",
    "alias_id": "TSTALIAS01"
  }
}
```

## 5. Migration Strategy

1.  **Implement `BedrockAgentProvider`** alongside the existing `BedrockProvider`.
2.  **Add "Return Control" logic** to handle local file writes.
3.  **Update `phase_execution.py`** to select the new provider when configured.
4.  **Test with one phase** (e.g., Scout) before migrating the complex Builder phase.
