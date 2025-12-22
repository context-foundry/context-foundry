from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
import subprocess
import json
import os
import shutil
from pathlib import Path


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        working_directory: Optional[Path] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            system_prompt: The system instructions.
            user_prompt: The user's input.
            model: Optional model identifier.
            tools: Optional list of tools (MCP format).
            working_directory: Working directory for execution (relevant for local CLI).
            event_callback: Optional callback for streaming events (e.g. logging).

        Returns:
            The LLM's response as a string.
        """
        pass


class LocalClaudeProvider(LLMProvider):
    """Provider that uses the local 'claude' CLI."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        working_directory: Optional[Path] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        import sys
        import threading

        # Verify claude CLI exists and get full path (needed for Windows .CMD files)
        claude_path = shutil.which("claude")
        if not claude_path:
            raise FileNotFoundError("claude CLI not found in PATH")

        cmd = [
            claude_path,
            "--permission-mode",
            "bypassPermissions",
            "--strict-mcp-config",
            "--print",
            "--tools",
            "default",  # Enable all tools in print mode
            "--settings",
            '{"thinkingMode": "off"}',
            "--system-prompt",
            system_prompt,
        ]

        if model:
            cmd.insert(1, "--model")
            cmd.insert(2, model)

        # Enable stream-json if callback is provided
        if event_callback:
            cmd.extend(["--output-format", "stream-json", "--verbose"])

        cwd = working_directory if working_directory else Path.cwd()

        # Windows-specific: use creationflags to prevent console window
        creation_flags = 0
        if sys.platform == 'win32':
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

        try:
            if event_callback:
                # Streaming execution with Windows-compatible approach
                process = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env={**dict(os.environ), "PYTHONUNBUFFERED": "1"},
                    creationflags=creation_flags,
                )

                response_text = []
                stderr_lines = []

                # Use a thread to read stderr to prevent deadlock on Windows
                def read_stderr():
                    try:
                        for line in process.stderr:
                            stderr_lines.append(line)
                    except Exception:
                        pass

                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stderr_thread.start()

                # Write input and close stdin
                try:
                    process.stdin.write(user_prompt)
                    process.stdin.flush()
                    process.stdin.close()
                except BrokenPipeError:
                    pass  # Process may have exited early

                # Read stdout line by line
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        event_callback(data)

                        # Accumulate text content for final return
                        if data.get("type") == "assistant":
                            message = data.get("message", {})
                            content = message.get("content", [])
                            for block in content:
                                if block.get("type") == "text":
                                    response_text.append(block.get("text", ""))

                    except json.JSONDecodeError:
                        # Ignore non-JSON lines (verbose output etc)
                        pass

                process.wait()
                stderr_thread.join(timeout=1.0)

                if process.returncode != 0:
                    stderr = "".join(stderr_lines)
                    raise RuntimeError(
                        f"Claude CLI execution failed (code {process.returncode}): {stderr}"
                    )

                return "".join(response_text)

            else:
                # Blocking execution with --print and --tools
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    input=user_prompt,
                    capture_output=True,
                    text=True,
                    check=True,
                    env={**dict(os.environ), "PYTHONUNBUFFERED": "1"},
                    creationflags=creation_flags,
                )
                return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Claude CLI execution failed: {e.stderr}")


class BedrockProvider(LLMProvider):
    """Provider that uses AWS Bedrock."""

    def __init__(
        self,
        region_name: str = "us-east-1",
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
        default_model: Optional[str] = None,
    ):
        self.region_name = region_name
        self._client = None
        self.tool_executor = tool_executor
        self.default_model = default_model
        self.default_model = default_model

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=self.region_name)
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        working_directory: Optional[Path] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        # Model priority: explicit param > instance default > hardcoded fallback
        # Default to configured default_model, then to Opus 4.5
        model_id = (
            model or self.default_model or "anthropic.claude-opus-4-5-20251101-v1:0"
        )

        # Use default tools if not provided but executor is present
        if tools is None and self.tool_executor:
            from .tools_schema import TOOLS_SCHEMA

            tools = TOOLS_SCHEMA

        messages = [
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
        ]

        # Tool Loop
        while True:
            # Construct Bedrock payload
            # https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": messages,
            }

            # For Claude 3 on Bedrock, tools are passed in the body, but the key is 'tools' not 'toolConfig'
            # Wait, the error said "extraneous key [toolConfig] is not permitted"
            # Let's check the latest docs.
            # Actually, for Bedrock Runtime InvokeModel, the body structure depends on the model.
            # For Anthropic Claude 3, it follows the Messages API.
            # The key should be 'tools' directly in the body, and 'tool_choice' (optional).

            if tools:
                body["tools"] = tools
                body["tool_choice"] = {"type": "auto"}

            try:
                # We use blocking call for tool loop simplicity for now,
                # but we can stream the *final* response or intermediate thoughts.
                # For now, let's stream if it's the final response or if we want to show thoughts.
                # To keep it simple for this iteration: Blocking for tool calls, Streaming for final.

                # Actually, to support dashboard visibility, we should stream everything.
                # But streaming tool calls is complex. Let's start with blocking for the loop.

                response = self.client.invoke_model(
                    modelId=model_id, body=json.dumps(body)
                )

                response_body = json.loads(response.get("body").read())
                stop_reason = response_body.get("stop_reason")
                content = response_body.get("content", [])

                # Append assistant response to messages
                messages.append({"role": "assistant", "content": content})

                # Process content for text and tool use
                full_text = ""
                tool_requests = []

                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        full_text += text
                        if event_callback:
                            event_callback(
                                {
                                    "type": "assistant",
                                    "message": {
                                        "content": [{"type": "text", "text": text}]
                                    },
                                }
                            )
                    elif block.get("type") == "tool_use":
                        tool_requests.append(block)

                if stop_reason == "tool_use":
                    if not self.tool_executor:
                        raise RuntimeError(
                            "Model requested tool use but no tool_executor provided"
                        )

                    tool_results = []
                    for request in tool_requests:
                        tool_use_id = request.get("id")
                        tool_name = request.get("name")
                        tool_input = request.get("input")

                        if event_callback:
                            event_callback(
                                {
                                    "type": "tool_use",
                                    "tool": tool_name,
                                    "input": tool_input,
                                }
                            )

                        try:
                            # Execute tool
                            result = self.tool_executor(tool_name, tool_input)

                            tool_results.append(
                                {
                                    "toolUseId": tool_use_id,
                                    "content": [{"json": result}],
                                }
                            )

                            if event_callback:
                                event_callback(
                                    {
                                        "type": "tool_result",
                                        "tool": tool_name,
                                        "output": result,
                                    }
                                )

                        except Exception as e:
                            tool_results.append(
                                {
                                    "toolUseId": tool_use_id,
                                    "content": [{"text": f"Error: {str(e)}"}],
                                    "status": "error",
                                }
                            )

                    # Append tool results to messages
                    # Bedrock expects toolResult content to be a list of blocks
                    # Each block must have 'json' or 'text'

                    tool_result_content = []
                    for res in tool_results:
                        # Map internal tool result format to Anthropic Messages API format
                        tool_result_content.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": res["toolUseId"],
                                "content": res[
                                    "content"
                                ],  # This is [{"json": ...}] or [{"text": ...}]
                                "is_error": res.get("status") == "error",
                            }
                        )

                    messages.append({"role": "user", "content": tool_result_content})
                    # Loop continues to get next response
                    continue

                else:
                    # Final response
                    return full_text

            except Exception as e:
                raise RuntimeError(f"Bedrock execution failed: {e}")


class BedrockAgentProvider(LLMProvider):
    """
    Provider that uses AWS Bedrock Agent Runtime.

    This provider delegates the orchestration loop to the AWS Cloud ("Cloud Brain").
    It handles:
    1. Invoking the Agent
    2. Streaming the response (chunks)
    3. Handling "Return Control" events (executing local tools and sending results back)
    """

    def __init__(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: Optional[str] = None,
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
        region: str = "us-east-1",
    ):
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        # Use provided session_id or generate a new one (persistent across generate calls if reused)
        import uuid

        self.session_id = session_id or str(uuid.uuid4())
        self.tool_executor = tool_executor
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "bedrock-agent-runtime", region_name=self.region
            )
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        working_directory: Optional[Path] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """
        Invoke the Bedrock Agent.

        Note: 'system_prompt', 'model', and 'tools' are largely ignored here because
        they are configured in the Agent itself on AWS. We pass 'user_prompt' as the input.
        """
        return self._invoke_loop(input_text=user_prompt, event_callback=event_callback)

    def _invoke_loop(
        self,
        input_text: Optional[str] = None,
        session_state: Optional[Dict] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """
        Internal loop to handle Agent invocation and Return Control.
        """
        import json

        # Prepare arguments for invoke_agent
        kwargs = {
            "agentId": self.agent_id,
            "agentAliasId": self.agent_alias_id,
            "sessionId": self.session_id,
            "enableTrace": True,  # Enable trace to see agent's thought process
        }

        if input_text:
            kwargs["inputText"] = input_text

        if session_state:
            kwargs["sessionState"] = session_state

        try:
            response = self.client.invoke_agent(**kwargs)

            completion_text = ""

            # Iterate over the event stream
            for event in response.get("completion"):
                # 1. Handle Text Chunk
                if "chunk" in event:
                    chunk = event["chunk"]
                    text = chunk.get("bytes").decode("utf-8")
                    completion_text += text

                    if event_callback:
                        event_callback(
                            {
                                "type": "assistant",
                                "message": {
                                    "content": [{"type": "text", "text": text}]
                                },
                            }
                        )

                # 2. Handle Trace (Agent's "Thoughts")
                elif "trace" in event:
                    trace = event["trace"]
                    # We can parse this to show "Pre-processing", "Orchestration", etc.
                    # For now, just log that we got a trace
                    if event_callback and "orchestrationTrace" in trace:
                        orch_trace = trace["orchestrationTrace"]
                        if "rationale" in orch_trace:
                            text = orch_trace["rationale"].get("text", "")
                            event_callback(
                                {
                                    "type": "assistant",
                                    "message": {
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": f"\\n[Thinking]: {text}\\n",
                                            }
                                        ]
                                    },
                                }
                            )

                # 3. Handle Return Control (Tool Execution)
                elif "returnControl" in event:
                    return_control = event["returnControl"]
                    invocation_id = return_control.get("invocationId")
                    invocation_inputs = return_control.get("invocationInputs", [])

                    if not self.tool_executor:
                        raise RuntimeError(
                            "Agent requested tool execution (Return Control) but no tool_executor provided."
                        )

                    tool_results = []

                    for tool_call in invocation_inputs:
                        function_inv = tool_call.get("functionInvocationInput", {})
                        action_group = function_inv.get("actionGroup")
                        function_name = function_inv.get("function")
                        parameters = function_inv.get("parameters", [])

                        # Convert parameters list to dict
                        # AWS sends: [{'name': 'path', 'type': 'string', 'value': '...'}]
                        args = {}
                        for param in parameters:
                            args[param["name"]] = param["value"]

                        # Notify dashboard
                        if event_callback:
                            event_callback(
                                {
                                    "type": "tool_use",
                                    "tool": function_name,
                                    "input": args,
                                }
                            )

                        # Execute Tool
                        try:
                            result = self.tool_executor(function_name, args)

                            if event_callback:
                                event_callback(
                                    {
                                        "type": "tool_result",
                                        "tool": function_name,
                                        "output": result,
                                    }
                                )

                        except Exception as e:
                            result = f"Error: {str(e)}"

                        # Prepare result for Bedrock
                        # Needs to match: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvocationInputMember.html
                        tool_results.append(
                            {
                                "functionResult": {
                                    "actionGroup": action_group,
                                    "function": function_name,
                                    "responseBody": {
                                        "TEXT": {"body": json.dumps(result)}
                                    },
                                }
                            }
                        )

                    # RECURSIVE CALL: Send results back to Agent
                    # We pass the results in 'sessionState' and NO inputText
                    next_session_state = {
                        "invocationId": invocation_id,
                        "returnControlInvocationResults": tool_results,
                    }

                    # Recursively call loop to continue execution
                    # We append the result of the recursive call to our current completion
                    return completion_text + self._invoke_loop(
                        input_text=None,
                        session_state=next_session_state,
                        event_callback=event_callback,
                    )

            return completion_text

        except Exception as e:
            raise RuntimeError(f"Bedrock Agent execution failed: {e}")
