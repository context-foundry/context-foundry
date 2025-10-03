#!/usr/bin/env python3
"""
Real Context Foundry - Generate actual prompts for Claude
This creates the EXACT prompts to paste into Claude to get real results
"""

from datetime import datetime
from pathlib import Path
import json

class RealContextFoundry:
    """Generate real prompts for Context Foundry workflow."""

    def __init__(self, project_name: str, task: str):
        self.project_name = project_name
        self.task = task
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def generate_scout_prompt(self) -> str:
        """Generate the Scout phase prompt for Claude."""

        return f"""You are the Scout agent in Context Foundry - a spec-first development system.

# Your Role
Research specialist exploring how to build this project from scratch. You're starting with no existing codebase.

# Task
{self.task}

# Instructions
Create a comprehensive RESEARCH.md file that explores:
1. The best architecture for this project
2. Required libraries and dependencies
3. Project structure recommendations
4. Data models and storage approach
5. Implementation patterns to follow
6. Potential challenges and solutions

# Output Format
Generate EXACTLY this format:
\`\`\`markdown
# Research Report: {self.project_name}
Generated: {datetime.now().isoformat()}
Context Usage: 28%

## Architecture Overview
[Provide a clear description of the recommended architecture]

## Technology Stack
- Language: Python 3.9+
- CLI Framework: [recommend click or typer]
- Storage: JSON file
- Output: Rich library for colors
- Testing: pytest

## Project Structure
todo-app/
├── todo/
│   ├── __init__.py
│   ├── cli.py          # CLI commands
│   ├── models.py       # Data models
│   ├── storage.py      # JSON persistence
│   └── display.py      # Rich output formatting
├── tests/
│   ├── test_cli.py
│   ├── test_models.py
│   └── test_storage.py
├── todo_data.json
├── requirements.txt
└── README.md

## Data Models
[Define Task model with fields: id, title, description, completed, created_at, completed_at]

## Storage Approach
[Explain JSON file structure and CRUD operations]

## CLI Commands
- \`todo add <title>\` - Add a new task
- \`todo list\` - Show all tasks with colors
- \`todo complete <id>\` - Mark task as done
- \`todo remove <id>\` - Delete a task
- \`todo clear\` - Remove completed tasks

## Display Strategy
[How to use Rich library for tables, colors, progress indicators]

## Testing Strategy
[Unit tests for each component, integration tests for CLI]

## Implementation Challenges
1. [Challenge]: [Solution]
2. Concurrent access to JSON file: File locking or accept single-user limitation
3. ID generation: UUID or auto-increment

## Recommendations
- Start with simple in-memory model, add persistence
- Use Click for CLI with built-in help
- Rich.table for beautiful task display
- Pytest fixtures for test data
\`\`\`

Keep output under 5000 tokens. Be specific and actionable."""

    def generate_architect_prompt(self, research_content: str) -> str:
        """Generate the Architect phase prompt for Claude."""

        return f"""You are the Architect agent in Context Foundry - a spec-first development system.

# Your Role
Planning specialist that creates detailed specifications and implementation plans.

# Task
{self.task}

# Research Findings
{research_content}

# Instructions
Create THREE files with comprehensive planning:

FILE 1: SPEC.md
\`\`\`markdown
# Specification: {self.project_name}
Generated: {datetime.now().isoformat()}
Context Usage: 35%

## Goal
Create a beautiful, functional CLI todo application with persistent storage and rich terminal output.

## User Stories
- As a user, I want to add tasks quickly from the command line
- As a user, I want to see my tasks in a beautiful colored table
- As a user, I want to mark tasks complete and see visual feedback
- As a user, I want my tasks to persist between sessions
- As a user, I want to remove tasks I no longer need

## Success Criteria
- [ ] Can add tasks with: \`todo add "Buy groceries"\`
- [ ] Tasks persist in JSON file between runs
- [ ] List shows tasks in colored table with IDs
- [ ] Completed tasks show with strikethrough/dimmed
- [ ] Tests achieve 90%+ coverage
- [ ] Error handling for edge cases

## Technical Requirements
- Python 3.9+ compatible
- No external services required
- Single JSON file for storage
- Rich library for terminal output
- Click for CLI framework
- 100% type hints

## Out of Scope
- Multi-user support
- Task priorities/categories
- Due dates
- Subtasks
- Web interface
\`\`\`

FILE 2: PLAN.md
\`\`\`markdown
# Implementation Plan: {self.project_name}
Generated: {datetime.now().isoformat()}
Context Usage: 38%

## Technical Approach
Build a modular CLI application with clear separation of concerns: CLI interface, business logic, storage, and display.

## Architecture Decisions
| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|---------|-----------|
| CLI Framework | argparse, click, typer | Click | Good balance of simplicity and features |
| Storage | SQLite, JSON, CSV | JSON | Simple, human-readable, sufficient for requirements |
| ID Generation | UUID, auto-increment | UUID | Avoids ID conflicts, simple implementation |
| Display | print, rich, colorama | Rich | Beautiful output with minimal code |

## Implementation Phases
1. **Core Models**: Define Task dataclass with all fields
2. **Storage Layer**: JSON file read/write with error handling
3. **CLI Commands**: Implement add/list/complete/remove
4. **Display Formatting**: Rich tables and colors
5. **Testing**: Comprehensive test suite with fixtures

## Testing Strategy
- Unit tests for each module
- Integration tests for CLI commands
- Mock file I/O for storage tests
- Test error conditions and edge cases

## Risks & Mitigations
| Risk | Probability | Impact | Mitigation |
|------|------------|---------|------------|
| Concurrent file access | Low | Medium | Document single-user limitation |
| Large task lists | Low | Low | Implement pagination if >100 tasks |
| Data corruption | Low | High | Backup before write, validate JSON |
\`\`\`

FILE 3: TASKS.md
\`\`\`markdown
# Task Breakdown: {self.project_name}
Generated: {datetime.now().isoformat()}
Context Usage: 40%

## Task Execution Order

### Task 1: Project Setup and Models
- **Files**: Create project structure, todo/__init__.py, todo/models.py
- **Changes**: Define Task dataclass with id, title, description, completed, created_at, completed_at
- **Tests**: test_models.py - Test Task creation, string representation
- **Dependencies**: None
- **Estimated Context**: 20%

### Task 2: Storage Layer
- **Files**: todo/storage.py
- **Changes**: Implement TodoStorage class with load(), save(), get_all(), add(), update(), delete()
- **Tests**: test_storage.py - Test CRUD operations, file handling
- **Dependencies**: Task 1
- **Estimated Context**: 25%

### Task 3: CLI Foundation
- **Files**: todo/cli.py, setup.py
- **Changes**: Create Click group, add command, list command (basic output)
- **Tests**: test_cli.py - Test command routing
- **Dependencies**: Tasks 1, 2
- **Estimated Context**: 30%

### Task 4: Complete CLI Commands
- **Files**: todo/cli.py
- **Changes**: Implement complete and remove commands with error handling
- **Tests**: Extend test_cli.py with all commands
- **Dependencies**: Task 3
- **Estimated Context**: 35%

### Task 5: Rich Display
- **Files**: todo/display.py, update todo/cli.py
- **Changes**: Create TaskDisplay class with rich tables, colors, formatting
- **Tests**: test_display.py - Test formatting output
- **Dependencies**: Task 4
- **Estimated Context**: 40%

### Task 6: Polish and Documentation
- **Files**: README.md, requirements.txt, .gitignore
- **Changes**: Write user docs, add examples, requirements file
- **Tests**: Run full suite, ensure 90%+ coverage
- **Dependencies**: Task 5
- **Estimated Context**: 45%
\`\`\`

CRITICAL: This is the highest leverage point. Bad planning = bad code. Be thorough and specific."""

    def generate_builder_prompt(self, task_number: int) -> str:
        """Generate Builder phase prompt for a specific task."""

        tasks = [
            {
                "name": "Project Setup and Models",
                "description": "Create project structure and Task dataclass",
                "files": ["todo/__init__.py", "todo/models.py", "tests/test_models.py"],
            },
            {
                "name": "Storage Layer",
                "description": "Implement JSON storage with CRUD operations",
                "files": ["todo/storage.py", "tests/test_storage.py"],
            },
            {
                "name": "CLI Foundation",
                "description": "Create Click CLI with add and list commands",
                "files": ["todo/cli.py", "setup.py", "tests/test_cli.py"],
            },
            {
                "name": "Complete CLI Commands",
                "description": "Add complete and remove commands",
                "files": ["todo/cli.py", "tests/test_cli.py"],
            },
            {
                "name": "Rich Display",
                "description": "Beautiful output with Rich library",
                "files": ["todo/display.py", "todo/cli.py", "tests/test_display.py"],
            },
            {
                "name": "Polish and Documentation",
                "description": "README, requirements, and final testing",
                "files": ["README.md", "requirements.txt", ".gitignore"],
            }
        ]

        if task_number < 1 or task_number > len(tasks):
            return "Invalid task number"

        task = tasks[task_number - 1]

        return f"""You are the Builder agent in Context Foundry - implementing Task {task_number}.

# Current Task
Task {task_number}: {task['name']}
{task['description']}

# Instructions
1. FIRST write comprehensive tests (TDD approach)
2. THEN implement the functionality
3. Ensure all tests pass
4. Use proper type hints
5. Include docstrings

# Files to Create/Modify
{chr(10).join(f"- {f}" for f in task['files'])}

# Context Management
Current context usage: {20 + (task_number * 5)}%
Keep responses focused and concise.

Generate the complete, working code for this task. Include all file contents.

# Expected Output Format
File: {task['files'][0] if task['files'] else 'filename.py'}
\`\`\`python
# Complete implementation here
\`\`\`

File: {task['files'][-1] if task['files'] and 'test' in task['files'][-1] else 'tests/test_file.py'}
\`\`\`python
# Comprehensive tests here
\`\`\`

Remember: This is production code. Make it clean, tested, and documented."""

    def save_prompts(self):
        """Save all prompts to files for easy access."""

        prompts_dir = Path("prompts")
        prompts_dir.mkdir(exist_ok=True)

        # Save Scout prompt
        scout_prompt = self.generate_scout_prompt()
        (prompts_dir / "1_scout_prompt.md").write_text(scout_prompt)

        print("📝 PROMPT 1: SCOUT")
        print("-" * 60)
        print(scout_prompt)
        print("\n" + "=" * 60 + "\n")

        input("Copy the above prompt to Claude and save the response as RESEARCH.md\nPress Enter when done...")

        # Read research and generate Architect prompt
        if Path("RESEARCH.md").exists():
            research = Path("RESEARCH.md").read_text()
            architect_prompt = self.generate_architect_prompt(research)
            (prompts_dir / "2_architect_prompt.md").write_text(architect_prompt)

            print("📝 PROMPT 2: ARCHITECT")
            print("-" * 60)
            print(architect_prompt[:1000] + "\n...[truncated for display]...")
            print("\n" + "=" * 60 + "\n")

            print("🚨 CRITICAL: Review the plan carefully before proceeding!")
            input("Copy the prompt to Claude and save responses as SPEC.md, PLAN.md, TASKS.md\nPress Enter when done...")

            # Generate builder prompts for each task
            for i in range(1, 7):
                builder_prompt = self.generate_builder_prompt(i)
                (prompts_dir / f"3_builder_task_{i}_prompt.md").write_text(builder_prompt)

                print(f"\n📝 PROMPT 3.{i}: BUILDER - Task {i}")
                print("-" * 60)
                print(builder_prompt[:500] + "\n...[truncated]...")

                input(f"Copy to Claude and implement Task {i}. Press Enter for next task...")

        print("\n✅ All prompts generated and saved in prompts/ directory!")
        print("You can now use these with Claude to build your todo app.")


def main():
    """Run the Real Context Foundry."""
    print("🏭 REAL CONTEXT FOUNDRY - Generate Actual Content")
    print("=" * 60)

    # Define the task
    task = """Create a CLI todo app with:
- Add/remove/list tasks
- Mark tasks complete
- Save to JSON file
- Colorful output with rich library
- Full test coverage"""

    foundry = RealContextFoundry("todo-app", task)
    foundry.save_prompts()

    print("\n🎯 Next Steps:")
    print("1. Copy each prompt to Claude")
    print("2. Save Claude's responses to the specified files")
    print("3. After Task 6, you'll have a complete, working todo app!")
    print("\nThe prompts are also saved in prompts/ for reference.")


if __name__ == "__main__":
    main()
