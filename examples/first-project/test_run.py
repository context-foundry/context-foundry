#!/usr/bin/env python3
"""
First test of Context Foundry
Let's build something real to validate the workflow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from workflows.orchestrate import ContextFoundryOrchestrator

def test_simple_api():
    """Test building a simple API with Context Foundry."""

    task = """
    Create a simple FastAPI application with the following features:

    1. Health check endpoint (GET /)
    2. User model with id, name, email
    3. CRUD endpoints for users:
       - GET /users (list all)
       - GET /users/{id} (get one)
       - POST /users (create)
       - PUT /users/{id} (update)
       - DELETE /users/{id} (delete)
    4. In-memory storage (dictionary)
    5. Comprehensive tests for all endpoints
    6. README with setup instructions

    Follow Context Foundry workflow:
    - Scout: Research FastAPI patterns
    - Architect: Create spec and plan
    - Builder: Implement with tests
    """

    print("=" * 60)
    print("CONTEXT FOUNDRY: First Test Run")
    print("=" * 60)
    print()

    orchestrator = ContextFoundryOrchestrator(
        project_name="simple-api",
        task_description=task
    )

    result = orchestrator.run()

    if result['status'] == 'success':
        print("\n" + "🎉" * 20)
        print("SUCCESS! Context Foundry workflow completed.")
        print("Check the generated files in:")
        print(f"  - Blueprints: blueprints/")
        print(f"  - Project: examples/simple-api/")
        print(f"  - Progress: checkpoints/sessions/")
        print("🎉" * 20)
    else:
        print(f"\n❌ Test failed: {result}")

    return result

if __name__ == "__main__":
    test_simple_api()
