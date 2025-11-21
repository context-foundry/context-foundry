from tools.mcp_utils.phase_execution import _normalize_build_tasks_schema


def test_normalize_build_tasks_handles_legacy_schema():
    plan = {
        "parallel_mode": True,
        "tasks": [
            {
                "id": "task-1",
                "description": "Legacy task without commands",
                "files": ["src/app.py"],
                "dependencies": [],
            }
        ],
    }

    normalized, ready, warnings = _normalize_build_tasks_schema(plan)

    assert normalized["tasks"][0]["task_id"] == "task-1"
    assert normalized["tasks"][0]["working_directory"] == "."
    assert normalized["tasks"][0]["build_commands"] == []
    assert (
        ready is False
    )  # Missing build_commands means we cannot run in parallel safely
    assert any("build_commands" in w for w in warnings)


def test_normalize_build_tasks_adds_provider_and_instruction():
    plan = {
        "parallel_mode": True,
        "tasks": [
            {
                "task_id": "task-1",
                "name": "Do work",
                "description": "Something important",
                "build_commands": [],
                # missing provider and agent_instruction
            }
        ],
    }

    normalized, ready, warnings = _normalize_build_tasks_schema(plan)

    task = normalized["tasks"][0]
    assert task["provider"] == "Claude"
    assert "Implement" in task["agent_instruction"]
    assert ready is False  # missing required fields triggers non-parallel readiness
    assert any("provider" in w for w in warnings)
    assert any("agent_instruction" in w for w in warnings)
