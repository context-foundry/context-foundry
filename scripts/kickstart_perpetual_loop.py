#!/usr/bin/env python3
"""
Kickstart the Perpetual Self-Improvement Loop!

This creates the FIRST task, which will automatically generate
the NEXT task when it completes, creating an infinite loop!
"""
import sys
from tools.evolution.task_queue import TaskQueueManager, TaskType

def main():
    queue = TaskQueueManager()

    # Create the FIRST task to kickstart the perpetual loop
    task_id = queue.create_task(
        task_type=TaskType.SELF_IMPROVEMENT.value,
        params={
            'action': 'implement_full_self_improvement',
            'description': '''Kickstart Evolution System Perpetual Loop!

This is the FIRST task in the perpetual self-improvement loop.

Find opportunities to improve Context Foundry:
1. Check test coverage and add missing tests
2. Look for code duplication that could be refactored
3. Identify documentation gaps
4. Find performance bottlenecks

Create a PR with improvements.

IMPORTANT: After this completes, the system will automatically
queue the NEXT improvement task, creating a perpetual loop! 🔄'''
        },
        priority=10  # Highest priority to get started
    )

    print("🚀 PERPETUAL LOOP KICKSTARTED!")
    print(f"📋 Initial Task ID: {task_id}")
    print(f"⚡ Priority: 10 (MAX)")
    print()
    print("🔄 What happens next:")
    print("  1. Daemon picks up this task (60s)")
    print("  2. Task executes and completes")
    print("  3. System finds NEXT improvement")
    print("  4. Automatically creates NEW task in queue")
    print("  5. Daemon picks it up")
    print("  6. Loop repeats FOREVER! ♾️")
    print()
    print("📊 Watch it on dashboard: http://localhost:8765")
    print("📝 Monitor logs: tail -f ~/.context-foundry/evolution/logs/daemon.log")
    print()
    print("⚠️  To stop the loop, stop the daemon:")
    print("    kill $(cat ~/.context-foundry/evolution/daemon.pid)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
