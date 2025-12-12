#!/usr/bin/env python3
"""
Overnight Task Scheduler
Schedule and manage overnight Context Foundry sessions
"""

import os
import smtplib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class TaskQueue:
    """Manage the overnight task queue."""

    def __init__(self, queue_file: Path = Path("overnight_tasks.txt")):
        self.queue_file = queue_file

    def load_tasks(self) -> List[Dict]:
        """Load tasks from queue file."""
        if not self.queue_file.exists():
            return []

        tasks = []
        with open(self.queue_file) as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse task: project_name|task_description|hours|priority
                parts = line.split("|")
                if len(parts) >= 2:
                    tasks.append(
                        {
                            "project": parts[0].strip(),
                            "description": parts[1].strip(),
                            "hours": int(parts[2].strip()) if len(parts) > 2 else 8,
                            "priority": int(parts[3].strip()) if len(parts) > 3 else 0,
                            "added": datetime.now().isoformat(),
                        }
                    )

        return sorted(tasks, key=lambda x: x["priority"], reverse=True)

    def remove_task(self, task: Dict):
        """Remove completed task from queue."""
        tasks = self.load_tasks()
        # Filter out the completed task
        remaining = [
            t
            for t in tasks
            if t["project"] != task["project"]
            or t["description"] != task["description"]
        ]

        # Rewrite queue file
        with open(self.queue_file, "w") as f:
            f.write("# Overnight Tasks Queue\n")
            f.write("# Format: project_name|task_description|hours|priority\n")
            f.write("# Priority: higher number = runs first\n\n")

            for t in remaining:
                f.write(
                    f"{t['project']}|{t['description']}|{t['hours']}|{t.get('priority', 0)}\n"
                )


class NotificationService:
    """Handle notifications for task completion/failure."""

    def __init__(self):
        self.email_config = self._load_email_config()
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

    def _load_email_config(self) -> Optional[Dict]:
        """Load email configuration from environment."""
        if all(
            [
                os.getenv("SMTP_HOST"),
                os.getenv("SMTP_PORT"),
                os.getenv("SMTP_USER"),
                os.getenv("SMTP_PASS"),
                os.getenv("NOTIFICATION_EMAIL"),
            ]
        ):
            return {
                "host": os.getenv("SMTP_HOST"),
                "port": int(os.getenv("SMTP_PORT", "587")),
                "user": os.getenv("SMTP_USER"),
                "password": os.getenv("SMTP_PASS"),
                "to": os.getenv("NOTIFICATION_EMAIL"),
            }
        return None

    def send_email(self, subject: str, body: str):
        """Send email notification."""
        if not self.email_config:
            print("⚠️  Email not configured, skipping email notification")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.email_config["user"]
            msg["To"] = self.email_config["to"]
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(
                self.email_config["host"], self.email_config["port"]
            ) as server:
                server.starttls()
                server.login(self.email_config["user"], self.email_config["password"])
                server.send_message(msg)

            print(f"✅ Email sent: {subject}")

        except Exception as e:
            print(f"❌ Email failed: {e}")

    def send_slack(self, message: str):
        """Send Slack notification."""
        if not self.slack_webhook:
            print("⚠️  Slack webhook not configured, skipping Slack notification")
            return

        try:
            import requests

            payload = {"text": message}
            response = requests.post(self.slack_webhook, json=payload)

            if response.status_code == 200:
                print("✅ Slack notification sent")
            else:
                print(f"❌ Slack failed: {response.status_code}")

        except Exception as e:
            print(f"❌ Slack failed: {e}")

    def send_desktop_notification(self, title: str, message: str):
        """Send desktop notification (fallback)."""
        try:
            # macOS
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False)
            print("✅ Desktop notification sent")

        except Exception as e:
            print(f"⚠️  Desktop notification not available: {e}")

    def notify_completion(self, task: Dict, result: Dict):
        """Send completion notification."""
        subject = f"✅ Context Foundry: {task['project']} Complete"
        body = f"""
Project: {task["project"]}
Task: {task["description"]}

Status: {"✅ Success" if result.get("success") else "❌ Failed"}
Duration: {result.get("duration", "Unknown")}
Iterations: {result.get("iterations", "Unknown")}

Check results:
  - Project: examples/{task["project"]}/
  - Logs: {result.get("log_file", "Unknown")}
"""

        # Try all notification methods
        self.send_email(subject, body)
        self.send_slack(
            f"Context Foundry: {task['project']} - {'✅ Complete' if result.get('success') else '❌ Failed'}"
        )
        self.send_desktop_notification("Context Foundry", f"{task['project']} complete")

    def notify_failure(self, task: Dict, error: str):
        """Send failure notification."""
        subject = f"❌ Context Foundry: {task['project']} Failed"
        body = f"""
Project: {task["project"]}
Task: {task["description"]}

Status: ❌ Failed
Error: {error}

Check logs for details.
"""

        self.send_email(subject, body)
        self.send_slack(f"❌ Context Foundry: {task['project']} failed - {error}")
        self.send_desktop_notification("Context Foundry", f"{task['project']} failed")


class OvernightScheduler:
    """Schedule and run overnight sessions."""

    def __init__(self, queue_file: Path = Path("overnight_tasks.txt")):
        self.queue = TaskQueue(queue_file)
        self.notifier = NotificationService()

    def run_task(self, task: Dict, max_retries: int = 3) -> Dict:
        """Run a single overnight task with retry logic."""
        print(f"\n{'=' * 60}")
        print("🌙 Starting overnight session")
        print(f"📋 Project: {task['project']}")
        print(f"📝 Task: {task['description']}")
        print(f"⏰ Duration: {task['hours']} hours")
        print(f"{'=' * 60}\n")

        for attempt in range(1, max_retries + 1):
            print(f"🔄 Attempt {attempt}/{max_retries}")

            try:
                # Run overnight_session.sh
                cmd = [
                    "./tools/overnight_session.sh",
                    task["project"],
                    task["description"],
                    str(task["hours"]),
                ]

                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=task["hours"] * 3600 + 300,
                )

                # Success
                return {
                    "success": True,
                    "attempts": attempt,
                    "output": result.stdout,
                    "log_file": "logs/overnight_*.log",
                }

            except subprocess.CalledProcessError as e:
                print(f"❌ Attempt {attempt} failed: {e}")

                if attempt == max_retries:
                    return {
                        "success": False,
                        "attempts": attempt,
                        "error": str(e),
                        "output": e.stderr,
                    }

                print("⏸️  Waiting 60s before retry...")
                import time

                time.sleep(60)

            except subprocess.TimeoutExpired:
                print("⏰ Timeout reached")
                return {
                    "success": False,
                    "attempts": attempt,
                    "error": "Timeout exceeded",
                }

        return {
            "success": False,
            "attempts": max_retries,
            "error": "Max retries exceeded",
        }

    def process_queue(self):
        """Process all tasks in the queue."""
        tasks = self.queue.load_tasks()

        if not tasks:
            print("📭 No tasks in queue")
            return

        print(f"📊 {len(tasks)} tasks in queue\n")

        for i, task in enumerate(tasks, 1):
            print(f"\n{'=' * 60}")
            print(f"Task {i}/{len(tasks)}")
            print(f"{'=' * 60}")

            result = self.run_task(task)

            if result["success"]:
                print("\n✅ Task completed successfully")
                self.notifier.notify_completion(task, result)
                self.queue.remove_task(task)
            else:
                print(f"\n❌ Task failed: {result.get('error')}")
                self.notifier.notify_failure(task, result.get("error", "Unknown error"))
                # Don't remove from queue - will retry next run

        print(f"\n{'=' * 60}")
        print("🌅 All queued tasks processed")
        print(f"{'=' * 60}")

    def add_task(
        self, project: str, description: str, hours: int = 8, priority: int = 0
    ):
        """Add a task to the queue."""
        with open(self.queue.queue_file, "a") as f:
            f.write(f"{project}|{description}|{hours}|{priority}\n")

        print(f"✅ Task added to queue: {project}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Overnight Task Scheduler")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Process queue
    subparsers.add_parser("process", help="Process task queue")

    # Add task
    add_parser = subparsers.add_parser("add", help="Add task to queue")
    add_parser.add_argument("project", help="Project name")
    add_parser.add_argument("description", help="Task description")
    add_parser.add_argument("--hours", type=int, default=8, help="Duration in hours")
    add_parser.add_argument(
        "--priority", type=int, default=0, help="Priority (higher = first)"
    )

    # List queue
    subparsers.add_parser("list", help="List queued tasks")

    args = parser.parse_args()

    scheduler = OvernightScheduler()

    if args.command == "process":
        scheduler.process_queue()

    elif args.command == "add":
        scheduler.add_task(args.project, args.description, args.hours, args.priority)

    elif args.command == "list":
        tasks = scheduler.queue.load_tasks()
        if not tasks:
            print("📭 No tasks in queue")
        else:
            print(f"📊 {len(tasks)} tasks in queue:\n")
            for i, task in enumerate(tasks, 1):
                print(f"{i}. {task['project']}")
                print(f"   Description: {task['description']}")
                print(f"   Duration: {task['hours']} hours")
                print(f"   Priority: {task.get('priority', 0)}")
                print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
