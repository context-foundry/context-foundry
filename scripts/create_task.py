#!/usr/bin/env python3
"""Quick script to create an evolution task"""

import sys
from tools.evolution.task_queue import TaskQueueManager, TaskType


def main():
    # Initialize task queue
    queue = TaskQueueManager()

    # Create self-improvement task
    task_id = queue.create_task(
        task_type=TaskType.SELF_IMPROVEMENT.value,
        params={
            "mode": "scan_codebase",
            "target": "context-foundry",
            "focus": "Find TODOs, improve test coverage, optimize performance",
        },
        priority=8,
    )

    print(f"✅ Created self-improvement task: {task_id}")
    print("📋 Task type: SELF_IMPROVEMENT")
    print("⚡ Priority: 8")
    print("🎯 Target: Context Foundry codebase")
    print("\n🔍 The daemon will pick this up in the next poll cycle (60s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
