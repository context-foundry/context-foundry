#!/usr/bin/env python3
"""
Context Foundry CLI Entry Point

Usage:
    cf              # Launch Context Foundry TUI (browser)
    cf desktop      # Launch Context Foundry Desktop app
    cf setup        # Configure Claude Code MCP integration
    cf --version    # Show version
    cf --help       # Show help
"""

import sys
import argparse
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from __version__ import __version__


def main():
    """Main CLI entry point"""
    # Check Python version at runtime
    if sys.version_info < (3, 10):
        print(
            f"""
Error: Python 3.10 or higher required

Your current Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
Context Foundry requires: Python 3.10+

Why? Context Foundry uses Python 3.10+ exclusive features:
  - Structural pattern matching (match statements)
  - Advanced type hints (TypeAlias, ParamSpec, etc.)

Solutions:
  1. Upgrade Python: brew install python@3.11 (macOS)
  2. Use pyenv: pyenv install 3.11 && pyenv local 3.11
  3. Use a virtual environment with Python 3.10+:
     python3.11 -m venv venv
     source venv/bin/activate
     cf

For more help: https://github.com/context-foundry/context-foundry/blob/main/INSTALL.md
""",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="cf",
        description="Context Foundry - The AI That Builds Itself",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cf              Launch Context Foundry (browser)
  cf desktop      Launch Context Foundry Desktop app
  cf setup        Configure Claude Code MCP integration
  cf --version    Show version information
  cf --help       Show this help message

For more information, visit: https://github.com/context-foundry/context-foundry
        """,
    )

    parser.add_argument(
        "--version", action="version", version=f"Context Foundry {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Setup command
    subparsers.add_parser("setup", help="Configure Claude Code MCP integration")

    # Watch command - watch agent conversations in real-time
    watch_parser = subparsers.add_parser(
        "watch", help="Watch agent conversation in real-time"
    )
    watch_parser.add_argument(
        "job_id", nargs="?", help="Job ID (optional - uses most recent if omitted)"
    )
    watch_parser.add_argument(
        "--follow", "-f", action="store_true", help="Follow conversation in real-time"
    )
    watch_parser.add_argument(
        "--lines", "-n", type=int, default=50, help="Number of lines to show"
    )
    watch_parser.add_argument(
        "--dir", "-d", help="Project directory to watch (instead of job_id)"
    )

    # Conversations command - list conversation logs
    conv_parser = subparsers.add_parser(
        "conversations", help="List all conversation logs"
    )
    conv_parser.add_argument(
        "job_id", nargs="?", help="Job ID (optional - lists all if omitted)"
    )
    conv_parser.add_argument("--dir", "-d", help="Project directory to search")

    # Jobs command - list recent jobs (alias for cfd list)
    jobs_parser = subparsers.add_parser("jobs", help="List recent daemon jobs")
    jobs_parser.add_argument(
        "--status", help="Filter by status (running, succeeded, failed)"
    )
    jobs_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum jobs to show"
    )

    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Manage background daemon")
    daemon_parser.add_argument(
        "action",
        choices=["start", "stop", "restart", "status", "logs"],
        help="Daemon action",
    )
    daemon_parser.add_argument(
        "--foreground", "-f", action="store_true", help="Run in foreground"
    )
    daemon_parser.add_argument("--config", "-c", help="Path to config file")
    daemon_parser.add_argument(
        "--timeout", "-t", type=int, default=10, help="Timeout for stop/restart"
    )
    daemon_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed status"
    )

    # Desktop command - launch Tauri desktop app
    desktop_parser = subparsers.add_parser(
        "desktop", help="Launch Context Foundry desktop app"
    )
    desktop_parser.add_argument(
        "action",
        nargs="?",
        choices=["start", "stop"],
        default="start",
        help="Action (default: start)",
    )

    args = parser.parse_args()

    if args.command == "setup":
        setup_claude_code()
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "conversations":
        cmd_conversations(args)
    elif args.command == "jobs":
        cmd_jobs(args)
    elif args.command == "daemon":
        cmd_daemon(args)
    elif args.command == "desktop":
        cmd_desktop(args)
    else:
        # Default action: Launch Context Foundry TUI
        launch_context_foundry()


def cmd_daemon(args):
    """Manage daemon process"""
    try:
        from context_foundry.daemon.cli import cmd_daemon as daemon_main

        daemon_main(args)
    except ImportError as e:
        print(f"Error importing daemon CLI: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_desktop(args):
    """Launch Context Foundry desktop app"""
    import subprocess
    import os

    # Find the desktop app directory
    cli_dir = Path(__file__).parent
    desktop_dir = cli_dir.parent / "apps" / "context-foundry-desktop"

    if not desktop_dir.exists():
        print(f"Error: Desktop app not found at {desktop_dir}", file=sys.stderr)
        print("\nTo install the desktop app:")
        print(f"  cd {desktop_dir.parent}")
        print("  git clone ... context-foundry-desktop")
        sys.exit(1)

    if args.action == "stop":
        print("Stopping Context Foundry Desktop...")
        # Kill any running vite and tauri processes
        try:
            subprocess.run(
                ["pkill", "-f", "vite.*5174"],
                capture_output=True,
            )
            subprocess.run(
                ["pkill", "-f", "tauri dev"],
                capture_output=True,
            )
            print("Stopped.")
        except Exception as e:
            print(f"Error stopping: {e}")
        return

    # Start the desktop app
    print("🚀 Starting Context Foundry Desktop...")
    print("   Dashboard: http://localhost:5174")
    print("   Press Ctrl+C to stop\n")

    try:
        # Change to desktop directory and run npm start
        os.chdir(desktop_dir)
        process = subprocess.Popen(
            ["npm", "run", "start"],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        # Wait for process or interrupt
        process.wait()

    except KeyboardInterrupt:
        print("\n\n👋 Stopping Context Foundry Desktop...")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("Stopped.")
    except FileNotFoundError:
        print("Error: npm not found. Please install Node.js.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error launching desktop app: {e}", file=sys.stderr)
        sys.exit(1)


def get_setup_banner():
    """Get colored ASCII art banner for setup screen"""
    import random

    try:
        from context_foundry.daemon.art import get_lava_lamp_art

        # Use random frame for color variety each time
        frame = random.randint(0, 359)
        return get_lava_lamp_art(frame)
    except ImportError:
        # Fallback to plain text if daemon module not available
        return r"""
   ______            __            __
  / ____/___  ____  / /____  _  __/ /_
 / /   / __ \/ __ \/ __/ _ \| |/_/ __/
/ /___/ /_/ / / / / /_/  __/>  </ /_
\____/\____/_/ /_/\__/\___/_/|_|\__/
    ______                      __
   / ____/___  __  ______  ____/ /______  __
  / /_  / __ \/ / / / __ \/ __  / ___/ / / /
 / __/ / /_/ / /_/ / / / / /_/ / /  / /_/ /
/_/    \____/\__,_/_/ /_/\__,_/_/   \__, /
                                   /____/
"""


def setup_claude_code():
    """Configure Claude Code MCP integration automatically"""
    print(get_setup_banner())
    print("\nSetting up Context Foundry for Claude Code...\n")

    # Find the MCP server path
    mcp_server_path = Path(__file__).parent / "mcp_server.py"
    if not mcp_server_path.exists():
        print(f"Error: MCP server not found at {mcp_server_path}", file=sys.stderr)
        sys.exit(1)

    mcp_server_path = mcp_server_path.resolve()

    # Claude Code settings file
    claude_settings_path = Path.home() / ".claude" / "mcp_settings.json"

    # Load existing settings or create new
    if claude_settings_path.exists():
        try:
            with open(claude_settings_path) as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(
                f"Warning: Invalid JSON in {claude_settings_path}, creating backup..."
            )
            backup_path = claude_settings_path.with_suffix(".json.backup")
            claude_settings_path.rename(backup_path)
            settings = {}
    else:
        settings = {}

    # Ensure mcpServers key exists
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    # Add or update context-foundry config
    settings["mcpServers"]["context-foundry"] = {
        "command": "python",
        "args": [str(mcp_server_path)],
    }

    # Create directory if needed
    claude_settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Write settings
    with open(claude_settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    print("Claude Code configured successfully!\n")
    print(f"   Settings file: {claude_settings_path}")
    print(f"   MCP server:    {mcp_server_path}\n")
    print("You can now use Context Foundry in Claude Code!")
    print('   Just ask: "Use CF to build a todo app"\n')


def launch_context_foundry():
    """Launch the Context Foundry Dashboard"""
    import webbrowser
    import subprocess

    dashboard_url = "http://localhost:8420"

    try:
        # Check if daemon is running
        import requests

        try:
            requests.get(f"{dashboard_url}/health", timeout=1)
            print(f"Dashboard already running at {dashboard_url}")
        except Exception:
            # Start daemon in background
            print("Starting Context Foundry daemon...")
            subprocess.Popen(
                ["cfd", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            import time

            time.sleep(2)

        # Open dashboard in browser
        print(f"Opening dashboard at {dashboard_url}")
        webbrowser.open(dashboard_url)

    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)

    except Exception as e:
        print(
            f"""
Error launching Context Foundry

{str(e)}

Try starting manually:
    cfd start
    Then visit: {dashboard_url}

Please report this issue at:
https://github.com/context-foundry/context-foundry/issues
""",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_watch(args):
    """Watch agent conversation in real-time"""
    import subprocess

    # Determine where to look for conversations
    if args.dir:
        working_dir = Path(args.dir)
    elif args.job_id:
        # Look up job from daemon store
        working_dir = get_working_dir_for_job(args.job_id)
        if not working_dir:
            print(f"Job not found: {args.job_id}", file=sys.stderr)
            print("\nTip: Use 'cf jobs' to list recent jobs", file=sys.stderr)
            sys.exit(1)
    else:
        # Find most recent conversation in current dir or homelab
        working_dir = find_most_recent_conversation_dir()
        if not working_dir:
            print("No recent conversations found.", file=sys.stderr)
            print("\nTip: Specify a job ID or directory:", file=sys.stderr)
            print("  cf watch <job_id>", file=sys.stderr)
            print("  cf watch --dir /path/to/project", file=sys.stderr)
            sys.exit(1)

    conversations_dir = working_dir / ".context-foundry" / "conversations"

    if not conversations_dir.exists():
        print(f"No conversation logs found at {conversations_dir}")
        print("\nConversation logging requires streaming mode.")
        sys.exit(1)

    # Find the most recent conversation log
    log_files = list(conversations_dir.glob("conversation-*.log"))
    if not log_files:
        print(f"No conversation logs found in {conversations_dir}")
        sys.exit(1)

    # Sort by modification time, get most recent
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)

    print(f"📺 Watching: {latest_log.name}")
    print(f"📂 Project: {working_dir.name}")
    print("-" * 60)

    if args.follow:
        # Use tail -f for real-time following
        try:
            tail_cmd = ["tail", "-n", str(args.lines), "-f", str(latest_log)]
            process = subprocess.Popen(tail_cmd)
            process.wait()
        except KeyboardInterrupt:
            print("\n\nStopped watching conversation")
            if process.poll() is None:
                process.terminate()
    else:
        # Just show last N lines
        with open(latest_log) as f:
            lines = f.readlines()
            for line in lines[-args.lines :]:
                print(line, end="")


def cmd_conversations(args):
    """List all conversation logs"""
    from datetime import datetime

    # Determine where to look
    if args.dir:
        search_dirs = [Path(args.dir)]
    elif args.job_id:
        working_dir = get_working_dir_for_job(args.job_id)
        if not working_dir:
            print(f"Job not found: {args.job_id}", file=sys.stderr)
            sys.exit(1)
        search_dirs = [working_dir]
    else:
        # Search common locations
        search_dirs = find_all_project_dirs()

    conversations = []
    for project_dir in search_dirs:
        conv_dir = project_dir / ".context-foundry" / "conversations"
        if not conv_dir.exists():
            continue

        for log_file in conv_dir.glob("conversation-*.log"):
            stat = log_file.stat()
            task_id = log_file.stem.replace("conversation-", "")
            jsonl_file = conv_dir / f"conversation-{task_id}.jsonl"

            # Count events in JSONL
            event_count = 0
            if jsonl_file.exists():
                with open(jsonl_file) as f:
                    event_count = sum(1 for _ in f)

            conversations.append(
                {
                    "project": project_dir.name,
                    "task_id": task_id,
                    "log_file": log_file,
                    "modified": stat.st_mtime,
                    "size_kb": stat.st_size / 1024,
                    "event_count": event_count,
                }
            )

    if not conversations:
        print("No conversation logs found.")
        print("\nTip: Start a build with streaming to create logs:")
        print("  Use delegate_to_claude_code_streaming() via MCP")
        return

    # Sort by modification time
    conversations.sort(key=lambda x: x["modified"], reverse=True)

    print("📂 Recent Conversations\n")
    for conv in conversations[:20]:  # Show last 20
        modified = datetime.fromtimestamp(conv["modified"]).strftime("%Y-%m-%d %H:%M")
        print(f"  {conv['project']}/{conv['task_id'][:8]}...")
        print(
            f"    📊 {conv['event_count']} events | {conv['size_kb']:.1f} KB | {modified}"
        )
        print()

    print("To watch a conversation:")
    print(f"  cf watch --dir {conversations[0]['log_file'].parent.parent.parent}")


def cmd_jobs(args):
    """List recent daemon jobs"""
    try:
        from context_foundry.daemon.config import Config
        from context_foundry.daemon.store import Store
        from context_foundry.daemon.models import JobStatus
    except ImportError:
        print(
            "Daemon module not available. Is Context Foundry installed?",
            file=sys.stderr,
        )
        sys.exit(1)

    config = Config.load()
    store = Store(config.db_path)

    # Get jobs
    status_filter = None
    if args.status:
        try:
            status_filter = JobStatus(args.status.upper())
        except ValueError:
            print(f"Unknown status: {args.status}", file=sys.stderr)
            print("Valid values: running, succeeded, failed, cancelled, pending")
            sys.exit(1)

    jobs = store.get_jobs(status=status_filter, limit=args.limit)

    if not jobs:
        print("No jobs found.")
        return

    print("📋 Recent Jobs\n")
    for job in jobs:
        status_emoji = {
            "RUNNING": "🔄",
            "SUCCEEDED": "✅",
            "FAILED": "❌",
            "CANCELLED": "⏹️",
            "PENDING": "⏳",
        }.get(job.status.value, "❓")

        working_dir = job.params.get(
            "working_directory", job.params.get("project_path", "")
        )
        project_name = Path(working_dir).name if working_dir else "unknown"

        print(f"  {status_emoji} {job.id[:8]}... | {project_name}")
        if job.created_at:
            created = job.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"     Created: {created} | Status: {job.status.value}")
        print()

    print("To watch a job's conversation:")
    print(f"  cf watch {jobs[0].id[:8]}")


def get_working_dir_for_job(job_id: str) -> Path:
    """Look up working directory for a job from daemon store"""
    try:
        from context_foundry.daemon.config import Config
        from context_foundry.daemon.store import Store

        config = Config.load()
        store = Store(config.db_path)

        # Try full ID first
        job = store.get_job(job_id)

        # If not found, try prefix match
        if not job:
            jobs = store.get_jobs(limit=100)
            for j in jobs:
                if j.id.startswith(job_id):
                    job = j
                    break

        if job:
            working_dir = job.params.get(
                "working_directory", job.params.get("project_path")
            )
            if working_dir:
                return Path(working_dir)

    except Exception:
        pass

    return None


def find_most_recent_conversation_dir() -> Path:
    """Find the most recently modified conversation directory"""
    search_dirs = find_all_project_dirs()

    most_recent = None
    most_recent_time = 0

    for project_dir in search_dirs:
        conv_dir = project_dir / ".context-foundry" / "conversations"
        if not conv_dir.exists():
            continue

        for log_file in conv_dir.glob("conversation-*.log"):
            mtime = log_file.stat().st_mtime
            if mtime > most_recent_time:
                most_recent_time = mtime
                most_recent = project_dir

    return most_recent


def find_all_project_dirs() -> list:
    """Find all project directories that might have conversation logs"""
    dirs = []

    # Current directory
    dirs.append(Path.cwd())

    # Check homelab if it exists
    homelab = Path.home() / "homelab"
    if homelab.exists():
        # Add immediate subdirectories
        for subdir in homelab.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("."):
                dirs.append(subdir)

    return dirs


if __name__ == "__main__":
    main()
