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
