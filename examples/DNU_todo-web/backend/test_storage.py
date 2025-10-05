"""
Unit tests for storage layer.
"""
import json
import os
import tempfile
import unittest
from storage import TodoStorage


class TestTodoStorage(unittest.TestCase):
    """Test cases for TodoStorage class."""
    
    def setUp(self):
        """Create temporary storage file for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.storage = TodoStorage(filepath=self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary file."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_init_creates_file(self):
        """Test that initialization creates file with proper structure."""
        self.assertTrue(os.path.exists(self.temp_file.name))
        
        with open(self.temp_file.name, 'r') as f:
            data = json.load(f)
        
        self.assertIn("todos", data)
        self.assertIn("metadata", data)
        self.assertEqual(data["todos"], [])
    
    def test_add_todo_success(self):
        """Test adding a valid todo."""
        todo = self.storage.add_todo(title="Test Todo", description="Test Description")
        
        self.assertIsNotNone(todo["id"])
        self.assertEqual(todo["title"], "Test Todo")
        self.assertEqual(todo["description"], "Test Description")
        self.assertFalse(todo["completed"])
        self.assertIsNotNone(todo["created_at"])
        self.assertIsNone(todo["completed_at"])
    
    def test_add_todo_empty_title(self):
        """Test that empty title raises ValueError."""
        with self.assertRaises(ValueError):
            self.storage.add_todo(title="")
        
        with self.assertRaises(ValueError):
            self.storage.add_todo(title="   ")
    
    def test_add_todo_strips_whitespace(self):
        """Test that title and description are stripped."""
        todo = self.storage.add_todo(title="  Test  ", description="  Desc  ")
        
        self.assertEqual(todo["title"], "Test")
        self.assertEqual(todo["description"], "Desc")
    
    def test_get_all_todos(self):
        """Test retrieving all todos."""
        self.storage.add_todo(title="Todo 1")
        self.storage.add_todo(title="Todo 2")
        self.storage.add_todo(title="Todo 3")
        
        todos = self.storage.get_all_todos()
        self.assertEqual(len(todos), 3)
        self.assertEqual(todos[0]["title"], "Todo 1")
        self.assertEqual(todos[2]["title"], "Todo 3")
    
    def test_complete_todo_success(self):
        """Test marking a todo as completed."""
        todo = self.storage.add_todo(title="Test Todo")
        todo_id = todo["id"]
        
        completed_todo = self.storage.complete_todo(todo_id)
        
        self.assertIsNotNone(completed_todo)
        self.assertTrue(completed_todo["completed"])
        self.assertIsNotNone(completed_todo["completed_at"])
    
    def test_complete_todo_not_found(self):
        """Test completing non-existent todo returns None."""
        result = self.storage.complete_todo("non-existent-id")
        self.assertIsNone(result)
    
    def test_delete_todo_success(self):
        """Test deleting a todo."""
        todo = self.storage.add_todo(title="Test Todo")
        todo_id = todo["id"]
        
        deleted = self.storage.delete_todo(todo_id)
        self.assertTrue(deleted)
        
        todos = self.storage.get_all_todos()
        self.assertEqual(len(todos), 0)
    
    def test_delete_todo_not_found(self):
        """Test deleting non-existent todo returns False."""
        deleted = self.storage.delete_todo("non-existent-id")
        self.assertFalse(deleted)
    
    def test_get_todo_by_id_success(self):
        """Test retrieving specific todo by ID."""
        todo = self.storage.add_todo(title="Test Todo")
        todo_id = todo["id"]
        
        retrieved = self.storage.get_todo_by_id(todo_id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["id"], todo_id)
        self.assertEqual(retrieved["title"], "Test Todo")
    
    def test_get_todo_by_id_not_found(self):
        """Test retrieving non-existent todo returns None."""
        result = self.storage.get_todo_by_id("non-existent-id")
        self.assertIsNone(result)
    
    def test_persistence(self):
        """Test that data persists across storage instances."""
        self.storage.add_todo(title="Persistent Todo")
        
        # Create new storage instance with same file
        new_storage = TodoStorage(filepath=self.temp_file.name)
        todos = new_storage.get_all_todos()
        
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["title"], "Persistent Todo")
    
    def test_atomic_writes(self):
        """Test that writes are atomic (temp file method)."""
        self.storage.add_todo(title="Test")
        
        # Verify no .tmp file exists after write
        temp_path = f"{self.temp_file.name}.tmp"
        self.assertFalse(os.path.exists(temp_path))


if __name__ == '__main__':
    unittest.main()