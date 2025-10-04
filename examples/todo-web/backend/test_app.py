"""
Integration tests for Flask API endpoints.
"""
import json
import os
import tempfile
import unittest
from app import app, storage


class TestTodoAPI(unittest.TestCase):
    """Test cases for REST API endpoints."""
    
    def setUp(self):
        """Set up test client and temporary storage."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Clear storage before each test
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.close()
        self.temp_file_name = temp_file.name
        
        # Replace storage with test storage
        from storage import TodoStorage
        global storage
        storage = TodoStorage(filepath=self.temp_file_name)
        
        # Update app's storage reference
        import app as app_module
        app_module.storage = storage
    
    def tearDown(self):
        """Clean up temporary file."""
        if os.path.exists(self.temp_file_name):
            os.unlink(self.temp_file_name)
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "ok")
    
    def test_get_todos_empty(self):
        """Test getting todos when none exist."""
        response = self.client.get('/api/todos')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["todos"], [])
    
    def test_create_todo_success(self):
        """Test creating a valid todo."""
        response = self.client.post('/api/todos',
                                    data=json.dumps({"title": "Test Todo", "description": "Test Desc"}),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        
        self.assertIn("todo", data)
        self.assertEqual(data["todo"]["title"], "Test Todo")
        self.assertEqual(data["todo"]["description"], "Test Desc")
        self.assertFalse(data["todo"]["completed"])
    
    def test_create_todo_missing_title(self):
        """Test creating todo without title returns 400."""
        response = self.client.post('/api/todos',
                                    data=json.dumps({"description": "No title"}),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertEqual(data["code"], "INVALID_TITLE")
    
    def test_create_todo_empty_body(self):
        """Test creating todo with empty body returns 400."""
        response = self.client.post('/api/todos',
                                    data='',
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data["code"], "MISSING_BODY")
    
    def test_get_todos_with_items(self):
        """Test getting todos after adding some."""
        self.client.post('/api/todos',
                        data=json.dumps({"title": "Todo 1"}),
                        content_type='application/json')
        self.client.post('/api/todos',
                        data=json.dumps({"title": "Todo 2"}),
                        content_type='application/json')
        
        response = self.client.get('/api/todos')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertEqual(len(data["todos"]), 2)
    
    def test_complete_todo_success(self):
        """Test marking a todo as completed."""
        # Create todo
        create_response = self.client.post('/api/todos',
                                          data=json.dumps({"title": "Todo to complete"}),
                                          content_type='application/json')
        todo_id = json.loads(create_response.data)["todo"]["id"]
        
        # Complete it
        response = self.client.put(f'/api/todos/{todo_id}/complete')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data["todo"]["completed"])
        self.assertIsNotNone(data["todo"]["completed_at"])
    
    def test_complete_todo_not_found(self):
        """Test completing non-existent todo returns 404."""
        response = self.client.put('/api/todos/non-existent-id/complete')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data["code"], "NOT_FOUND")
    
    def test_delete_todo_success(self):
        """Test deleting a todo."""
        # Create todo
        create_response = self.client.post('/api/todos',
                                          data=json.dumps({"title": "Todo to delete"}),
                                          content_type='application/json')
        todo_id = json.loads(create_response.data)["todo"]["id"]
        
        # Delete it
        response = self.client.delete(f'/api/todos/{todo_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        
        # Verify it's gone
        get_response = self.client.get('/api/todos')
        todos = json.loads(get_response.data)["todos"]
        self.assertEqual(len(todos), 0)
    
    def test_delete_todo_not_found(self):
        """Test deleting non-existent todo returns 404."""
        response = self.client.delete('/api/todos/non-existent-id')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data["code"], "NOT_FOUND")
    
    def test_invalid_endpoint(self):
        """Test accessing invalid endpoint returns 404."""
        response = self.client.get('/api/invalid')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()