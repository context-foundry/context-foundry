"""
Storage layer for todo application using JSON file persistence.
Implements thread-safe file operations with atomic writes.
"""
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class TodoStorage:
    """Thread-safe JSON file storage for todos."""
    
    def __init__(self, filepath: str = "data/todos.json"):
        """
        Initialize storage manager.
        
        Args:
            filepath: Path to JSON storage file
        """
        self.filepath = filepath
        self.lock = threading.Lock()
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Create storage file with initial structure if it doesn't exist."""
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        if not os.path.exists(self.filepath):
            initial_data = {
                "todos": [],
                "metadata": {
                    "version": "1.0",
                    "last_modified": datetime.utcnow().isoformat() + "Z"
                }
            }
            with open(self.filepath, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def _read_data(self) -> Dict:
        """
        Read entire data structure from file.
        
        Returns:
            Dictionary containing todos and metadata
            
        Raises:
            json.JSONDecodeError: If file is corrupted
        """
        with open(self.filepath, 'r') as f:
            return json.load(f)
    
    def _write_data(self, data: Dict) -> None:
        """
        Atomically write data structure to file.
        
        Args:
            data: Dictionary containing todos and metadata
        """
        data["metadata"]["last_modified"] = datetime.utcnow().isoformat() + "Z"
        temp_path = f"{self.filepath}.tmp"
        
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        os.replace(temp_path, self.filepath)
    
    def get_all_todos(self) -> List[Dict]:
        """
        Retrieve all todos.
        
        Returns:
            List of todo dictionaries
        """
        with self.lock:
            data = self._read_data()
            return data["todos"]
    
    def add_todo(self, title: str, description: str = "") -> Dict:
        """
        Add a new todo.
        
        Args:
            title: Todo title (required)
            description: Optional description
            
        Returns:
            Created todo dictionary with generated ID and timestamps
            
        Raises:
            ValueError: If title is empty
        """
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")
        
        with self.lock:
            data = self._read_data()
            
            new_todo = {
                "id": str(uuid4()),
                "title": title.strip(),
                "description": description.strip(),
                "completed": False,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "completed_at": None
            }
            
            data["todos"].append(new_todo)
            self._write_data(data)
            
            return new_todo
    
    def complete_todo(self, todo_id: str) -> Optional[Dict]:
        """
        Mark a todo as completed.
        
        Args:
            todo_id: UUID of todo to complete
            
        Returns:
            Updated todo dictionary, or None if not found
        """
        with self.lock:
            data = self._read_data()
            
            for todo in data["todos"]:
                if todo["id"] == todo_id:
                    todo["completed"] = True
                    todo["completed_at"] = datetime.utcnow().isoformat() + "Z"
                    self._write_data(data)
                    return todo
            
            return None
    
    def delete_todo(self, todo_id: str) -> bool:
        """
        Delete a todo by ID.
        
        Args:
            todo_id: UUID of todo to delete
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            data = self._read_data()
            initial_length = len(data["todos"])
            
            data["todos"] = [t for t in data["todos"] if t["id"] != todo_id]
            
            if len(data["todos"]) < initial_length:
                self._write_data(data)
                return True
            
            return False
    
    def get_todo_by_id(self, todo_id: str) -> Optional[Dict]:
        """
        Retrieve a specific todo by ID.
        
        Args:
            todo_id: UUID of todo to retrieve
            
        Returns:
            Todo dictionary or None if not found
        """
        with self.lock:
            data = self._read_data()
            for todo in data["todos"]:
                if todo["id"] == todo_id:
                    return todo
            return None