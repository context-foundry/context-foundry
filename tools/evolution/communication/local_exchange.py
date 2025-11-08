"""Local file-based agent exchange"""

import json
from pathlib import Path
from typing import Dict, List


class LocalExchange:
    """File-based message exchange for local agents"""
    
    def __init__(self):
        self.shared_dir = Path.home() / ".context-foundry" / "evolution" / "shared_tasks"
        self.shared_dir.mkdir(parents=True, exist_ok=True)
    
    def write_message(self, target_agent: str, message: Dict):
        """Write message to shared directory"""
        message_file = self.shared_dir / f"msg_{target_agent}_{message['timestamp']}.json"
        with open(message_file, 'w') as f:
            json.dump(message, f)
    
    def read_messages(self, agent_name: str) -> List[Dict]:
        """Read messages for agent"""
        messages = []
        for file in self.shared_dir.glob(f"msg_{agent_name}_*.json"):
            with open(file) as f:
                messages.append(json.load(f))
            file.unlink()  # Delete after reading
        return messages
