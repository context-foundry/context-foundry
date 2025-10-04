"""
Flask REST API server for todo application.
Provides endpoints for CRUD operations on todos.
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from storage import TodoStorage
import os


app = Flask(__name__)
CORS(app)

# Initialize storage
storage_path = os.environ.get("TODO_STORAGE_PATH", "data/todos.json")
storage = TodoStorage(filepath=storage_path)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route('/api/todos', methods=['GET'])
def get_todos():
    """
    Retrieve all todos.
    
    Returns:
        JSON response with todos array
    """
    try:
        todos = storage.get_all_todos()
        return jsonify({"todos": todos}), 200
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve todos",
            "code": "READ_ERROR",
            "details": str(e)
        }), 500


@app.route('/api/todos', methods=['POST'])
def create_todo():
    """
    Create a new todo.
    
    Expected JSON body:
        {
            "title": "string (required)",
            "description": "string (optional)"
        }
    
    Returns:
        JSON response with created todo
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "error": "Request body is required",
                "code": "MISSING_BODY"
            }), 400
        
        title = data.get("title", "").strip()
        if not title:
            return jsonify({
                "error": "Title is required and cannot be empty",
                "code": "INVALID_TITLE"
            }), 400
        
        description = data.get("description", "")
        
        todo = storage.add_todo(title=title, description=description)
        return jsonify({"todo": todo}), 201
        
    except ValueError as e:
        return jsonify({
            "error": str(e),
            "code": "VALIDATION_ERROR"
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Failed to create todo",
            "code": "CREATE_ERROR",
            "details": str(e)
        }), 500


@app.route('/api/todos/<todo_id>/complete', methods=['PUT'])
def complete_todo(todo_id: str):
    """
    Mark a todo as completed.
    
    Args:
        todo_id: UUID of todo to complete
    
    Returns:
        JSON response with updated todo
    """
    try:
        todo = storage.complete_todo(todo_id)
        
        if todo is None:
            return jsonify({
                "error": "Todo not found",
                "code": "NOT_FOUND"
            }), 404
        
        return jsonify({"todo": todo}), 200
        
    except Exception as e:
        return jsonify({
            "error": "Failed to complete todo",
            "code": "UPDATE_ERROR",
            "details": str(e)
        }), 500


@app.route('/api/todos/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id: str):
    """
    Delete a todo.
    
    Args:
        todo_id: UUID of todo to delete
    
    Returns:
        JSON response indicating success
    """
    try:
        deleted = storage.delete_todo(todo_id)
        
        if not deleted:
            return jsonify({
                "error": "Todo not found",
                "code": "NOT_FOUND"
            }), 404
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        return jsonify({
            "error": "Failed to delete todo",
            "code": "DELETE_ERROR",
            "details": str(e)
        }), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({
        "error": "Endpoint not found",
        "code": "ENDPOINT_NOT_FOUND"
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    return jsonify({
        "error": "Internal server error",
        "code": "INTERNAL_ERROR"
    }), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)