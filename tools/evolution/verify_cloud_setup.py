"""
Verify Cloud Setup (Mocked).
"""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.evolution.communication.cloud_client import RemoteToolExecutor
from tools.evolution.framework.llm_provider import BedrockProvider

def verify_remote_executor_auth():
    print("🔍 Verifying RemoteToolExecutor Auth...")
    executor = RemoteToolExecutor(api_key="secret-key", working_directory="/tmp")
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"status": "success"}
        mock_post.return_value.raise_for_status.return_value = None
        
        executor.execute("test_tool", {})
        
        # Check headers
        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs.get("headers", {})
        
        if headers.get("Authorization") == "Bearer secret-key":
            print(" ✅ Auth header present")
        else:
            print(f" ❌ Auth header missing or invalid: {headers}")

def verify_bedrock_loop():
    print("🔍 Verifying BedrockProvider Tool Loop...")
    
    # Mock executor
    mock_executor = MagicMock()
    mock_executor.return_value = "Tool Output"
    
    provider = BedrockProvider(tool_executor=mock_executor)
    
    # Mock boto3 client
    mock_client = MagicMock()
    provider._client = mock_client
    
    # Sequence of responses:
    # 1. Tool Use Request
    # 2. Final Response
    
    response1 = {
        "stop_reason": "tool_use",
        "content": [
            {"type": "text", "text": "Thinking..."},
            {"type": "tool_use", "id": "call_1", "name": "test_tool", "input": {"arg": "val"}}
        ]
    }
    
    response2 = {
        "stop_reason": "end_turn",
        "content": [
            {"type": "text", "text": "Final Answer"}
        ]
    }
    
    # Configure mock to return these responses
    mock_client.invoke_model.side_effect = [
        {"body": MagicMock(read=lambda: json.dumps(response1).encode())},
        {"body": MagicMock(read=lambda: json.dumps(response2).encode())}
    ]
    
    # Run generate
    result = provider.generate("system", "user")
    
    # Verify loop
    if mock_executor.call_count == 1:
        print(" ✅ Tool executor called")
    else:
        print(f" ❌ Tool executor not called (count: {mock_executor.call_count})")
        
    if result == "Final Answer":
        print(" ✅ Final response correct")
    else:
        print(f" ❌ Final response incorrect: {result}")

if __name__ == "__main__":
    verify_remote_executor_auth()
    verify_bedrock_loop()
