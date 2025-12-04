"""Communication Layer for CFES"""

from .tool_executor import ToolExecutor
from .cloud_client import RemoteToolExecutor

__all__ = [
    "rest_api", 
    "web_dashboard", 
    "websocket_stream", 
    "local_exchange",
    "ToolExecutor",
    "RemoteToolExecutor"
]
