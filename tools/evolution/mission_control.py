"""
Mission Control - Context Foundry Evolution TUI

Beautiful terminal UI for managing Evolution System:
- AI Chat Interface (familiar Claude-style)
- Live Dashboard (backlog, daemon, MCP status)
- Build Controls (start/stop builds in sandboxes)
- Real-time Log Streaming
"""

import asyncio
import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, Button, Label, RichLog, Tree
from textual.widgets.tree import TreeNode
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree as RichTree


class StatusPanel(Static):
    """Live status panel showing backlog, daemon, MCP health"""

    status_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "System Status"

    async def on_mount(self) -> None:
        """Start status updates when mounted"""
        self.set_interval(2.0, self.refresh_status)
        await self.refresh_status()

    async def refresh_status(self) -> None:
        """Refresh status from daemon and MCP"""
        try:
            # Get daemon status
            daemon_status = self._get_daemon_status()

            # Get GitHub issue count
            issue_count = self._get_issue_count()

            # Get MCP status
            mcp_status = self._get_mcp_status()

            # Get active builds and delegation info
            build_info = await self._get_build_status()
            delegation_info = await self._get_delegation_info()

            # Build status table
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Key", style="cyan bold")
            table.add_column("Value", style="white")

            # Daemon
            daemon_icon = "✓" if daemon_status["running"] else "✗"
            daemon_color = "green" if daemon_status["running"] else "red"
            table.add_row(
                "Daemon",
                Text(f"{daemon_icon} {daemon_status['status']}", style=daemon_color)
            )

            # Backlog
            backlog_icon = "✓" if issue_count >= 18 else "⚠"
            backlog_color = "green" if issue_count >= 18 else "yellow"
            table.add_row(
                "Backlog",
                Text(f"{backlog_icon} {issue_count}/20 issues", style=backlog_color)
            )

            # MCP
            mcp_icon = "✓" if mcp_status["available"] else "✗"
            mcp_color = "green" if mcp_status["available"] else "yellow"
            table.add_row(
                "MCP",
                Text(f"{mcp_icon} {mcp_status['status']}", style=mcp_color)
            )

            # Model (from app)
            app = self.app
            if hasattr(app, 'model'):
                model_display = {
                    "sonnet": "Sonnet 4.5",
                    "opus": "Opus 4",
                    "haiku": "Haiku 3.5"
                }.get(app.model, app.model)
                table.add_row(
                    "Model",
                    Text(f"🤖 {model_display}", style="magenta")
                )

            # Separator
            table.add_row("", "")

            # Claude Instances
            instances_icon = "⚡" if delegation_info["running"] > 0 else "💤"
            instances_color = "green bold" if delegation_info["running"] > 0 else "dim"
            table.add_row(
                "Claude Instances",
                Text(f"{instances_icon} {delegation_info['running']} running", style=instances_color)
            )

            table.add_row(
                "Total Delegations",
                Text(f"📊 {delegation_info['total']} ({delegation_info['completed']} done)", style="white")
            )

            # Active Builds
            build_count = build_info["active"]
            build_icon = "🚀" if build_count > 0 else "💤"
            build_color = "green bold" if build_count > 0 else "dim"
            build_text = f"{build_count} active"
            if build_info["latest"]:
                build_text += f" ({build_info['latest']})"
            table.add_row(
                "Active Builds",
                Text(f"{build_icon} {build_text}", style=build_color)
            )

            self.update(Panel(table, border_style="cyan", title="[bold]System Status[/bold]"))

        except Exception as e:
            self.update(f"Error: {e}")

    def _get_daemon_status(self) -> dict:
        """Check if daemon is running"""
        try:
            result = subprocess.run(
                ["python3", "-m", "tools.evolution.daemon", "status"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            running = "running" in result.stdout.lower()

            if running:
                # Extract PID
                for line in result.stdout.split("\n"):
                    if "PID:" in line:
                        pid = line.split("PID:")[1].strip().rstrip(")")
                        return {"running": True, "status": f"Running (PID {pid})"}
                return {"running": True, "status": "Running"}
            else:
                return {"running": False, "status": "Offline"}

        except Exception:
            return {"running": False, "status": "Unknown"}

    def _get_issue_count(self) -> int:
        """Get current GitHub issue count"""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--state", "open", "--json", "number"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                issues = json.loads(result.stdout)
                return len(issues)

        except Exception:
            pass

        return 0

    def _get_mcp_status(self) -> dict:
        """Check MCP server availability via Claude Code"""
        try:
            # MCP is available through Claude Code's built-in MCP server
            # We don't need fastmcp package - Claude Code provides the connection

            # Check if tools/mcp_server.py exists (our MCP tool definitions)
            mcp_server_path = Path(__file__).parent.parent / "mcp_server.py"

            if mcp_server_path.exists():
                # MCP tools are defined and available via Claude Code
                return {
                    "available": True,
                    "status": "Ready (Claude Code MCP)"
                }
            else:
                return {
                    "available": False,
                    "status": "MCP tools not found"
                }

        except Exception as e:
            return {"available": False, "status": f"Error: {e}"}

    async def _get_build_status(self) -> dict:
        """Get active build count and latest build info from tracked builds"""
        try:
            # Load builds from persistent storage
            running_builds = self._load_tracked_builds()

            if running_builds:
                # Get most recent running build
                latest = running_builds[-1]  # Last one is most recent
                project_name = latest.get("project", "build")

                return {
                    "active": len(running_builds),
                    "latest": project_name
                }

            return {"active": 0, "latest": None}

        except Exception as e:
            return {"active": 0, "latest": None}

    async def _get_delegation_info(self) -> dict:
        """Get delegation/Claude instance information from tracked builds"""
        try:
            # Load all builds from persistent storage
            builds_file = Path.home() / ".context-foundry" / "tui-tracked-builds.json"
            if not builds_file.exists():
                return {"running": 0, "completed": 0, "total": 0}

            all_builds = json.loads(builds_file.read_text())

            running = sum(1 for b in all_builds if b.get("status") == "running")
            completed = sum(1 for b in all_builds if b.get("status") == "completed")

            return {
                "running": running,
                "completed": completed,
                "total": len(all_builds)
            }

        except Exception:
            return {"running": 0, "completed": 0, "total": 0}


class FileTreePanel(Static):
    """Live file tree showing build directory contents"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Build Directory"
        self.current_dir = None

    async def on_mount(self) -> None:
        """Start file tree updates"""
        self.set_interval(1.5, self.refresh_tree)
        await self.refresh_tree()

    async def refresh_tree(self) -> None:
        """Refresh file tree from active build directory"""
        try:
            # Load tracked builds from disk
            build_dir = None

            builds_file = Path.home() / ".context-foundry" / "tui-tracked-builds.json"
            if builds_file.exists():
                try:
                    builds = json.loads(builds_file.read_text())

                    # Find first running build
                    for build in builds:
                        if build.get("status") == "running":
                            working_dir = build.get("working_directory", "")
                            if working_dir and Path(working_dir).exists():
                                build_dir = Path(working_dir)
                                break

                except Exception:
                    pass

            if build_dir and build_dir.exists():
                self.current_dir = build_dir
                tree_text = self._build_tree(build_dir)

                self.update(Panel(
                    tree_text,
                    border_style="magenta",
                    title=f"[bold]📁 {build_dir.name}[/bold]",
                    subtitle=f"[dim]{str(build_dir)}[/dim]"
                ))
            else:
                # No active build
                self.update(Panel(
                    Text("No active build\n\nStart a build to see files appear here in real-time!", style="dim italic"),
                    border_style="dim magenta",
                    title="[bold]Build Directory[/bold]"
                ))

        except Exception as e:
            self.update(Panel(
                Text(f"Error: {e}", style="red"),
                border_style="red",
                title="[bold]Build Directory[/bold]"
            ))

    def _build_tree(self, directory: Path, max_depth: int = 4) -> RichTree:
        """Build a rich tree structure from directory"""
        try:
            # Create root tree
            tree = RichTree(
                f"[bold cyan]📁 {directory.name}/[/bold cyan]",
                guide_style="dim"
            )

            # Add directory contents
            self._add_directory_to_tree(tree, directory, current_depth=0, max_depth=max_depth)

            return tree

        except Exception as e:
            return Text(f"Error building tree: {e}", style="red")

    def _add_directory_to_tree(self, tree: RichTree, directory: Path, current_depth: int, max_depth: int) -> None:
        """Recursively add directory contents to tree"""
        if current_depth >= max_depth:
            tree.add(Text("... (max depth reached)", style="dim"))
            return

        try:
            # Get all items, sorted (dirs first, then files)
            items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

            # Limit number of items to prevent huge trees
            if len(items) > 50:
                items = items[:50]
                show_truncated = True
            else:
                show_truncated = False

            for item in items:
                # Skip hidden files and common ignore patterns
                if item.name.startswith('.') or item.name in ['node_modules', '__pycache__', 'venv', '.git']:
                    continue

                if item.is_dir():
                    # Add directory
                    branch = tree.add(f"[cyan]📁 {item.name}/[/cyan]")
                    self._add_directory_to_tree(branch, item, current_depth + 1, max_depth)
                else:
                    # Add file with icon based on extension
                    icon = self._get_file_icon(item.suffix)
                    size = self._format_size(item.stat().st_size)
                    tree.add(f"{icon} {item.name} [dim]({size})[/dim]")

            if show_truncated:
                tree.add(Text("... (truncated)", style="dim"))

        except PermissionError:
            tree.add(Text("Permission denied", style="red"))
        except Exception as e:
            tree.add(Text(f"Error: {e}", style="red"))

    def _get_file_icon(self, suffix: str) -> str:
        """Get icon for file type"""
        icons = {
            '.py': '🐍',
            '.js': '📜',
            '.ts': '📘',
            '.tsx': '⚛️',
            '.jsx': '⚛️',
            '.html': '🌐',
            '.css': '🎨',
            '.json': '📋',
            '.md': '📝',
            '.txt': '📄',
            '.yml': '⚙️',
            '.yaml': '⚙️',
            '.toml': '⚙️',
            '.sh': '🔧',
            '.dockerfile': '🐳',
            '.gitignore': '🚫',
            '.env': '🔐',
        }
        return icons.get(suffix.lower(), '📄')

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"


class ChatMessage(Static):
    """Individual chat message bubble"""

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content

    def compose(self) -> ComposeResult:
        """Render chat message"""
        if self.role == "user":
            yield Static(
                f"[bold cyan]You:[/bold cyan] {self.content}",
                classes="user-message"
            )
        else:
            yield Static(
                f"[bold green]Assistant:[/bold green] {self.content}",
                classes="assistant-message"
            )


class ChatPanel(VerticalScroll):
    """AI Chat interface panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "AI Assistant"

    async def on_mount(self) -> None:
        """Show welcome message"""
        await self.add_message(
            "assistant",
            "Welcome to Context Foundry Mission Control! 🚀\n\n"
            "**Just type what you want to build in natural language!**\n\n"
            "Examples:\n"
            "• 'build a gorilla tag fun math game web based'\n"
            "• 'create a todo app with React'\n"
            "• 'make a weather dashboard'\n\n"
            "**Controls:**\n"
            "• Enter or Ctrl+D to send\n"
            "• Ctrl+M to cycle models (currently: Sonnet 4.5)\n"
            "• Shift+Click to select and copy text\n"
            "• Type 'help' for more options\n\n"
            "I'll delegate your request to Claude and track the build!"
        )

    async def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat"""
        await self.mount(ChatMessage(role, content))
        self.scroll_end(animate=False)


class ChatInput(Input):
    """Chat input field"""

    def __init__(self, **kwargs):
        super().__init__(placeholder="Type a message... (Enter or Ctrl+D to send)", **kwargs)

    async def on_key(self, event) -> None:
        """Handle Enter key to submit message"""
        if event.key == "enter":
            # Trigger the send_message action
            await self.app.action_send_message()
            event.prevent_default()
            event.stop()


class ActivityLog(RichLog):
    """Activity log showing daemon and build events"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs, max_lines=100, highlight=True, markup=True)
        self.border_title = "Activity Log"
        self.last_build_lines = {}  # Track last lines shown per build

    async def on_mount(self) -> None:
        """Start tailing build logs"""
        self.set_interval(2.0, self.refresh_log)
        await self.refresh_log()

    async def refresh_log(self) -> None:
        """Tail build logs and daemon log"""
        try:
            # First, check for active builds and show their progress
            app = self.app
            if hasattr(app, 'active_builds') and app.active_builds:
                for build in app.active_builds:
                    task_id = build.get("task_id")
                    project = build.get("project", "unknown")

                    if task_id:
                        await self._show_build_progress(task_id, project)

            # Also show daemon log as fallback
            log_file = Path.home() / ".context-foundry" / "evolution" / "logs" / "daemon.log"

            if log_file.exists() and (not hasattr(app, 'active_builds') or not app.active_builds):
                # Only show daemon log if no active builds
                lines = log_file.read_text().strip().split("\n")[-3:]

                for line in lines:
                    if line:
                        # Parse and colorize log line
                        if "INFO" in line:
                            self.write(Text(line, style="dim white"))
                        elif "WARNING" in line:
                            self.write(Text(line, style="yellow"))
                        elif "ERROR" in line:
                            self.write(Text(line, style="red"))
                        else:
                            self.write(Text(line, style="dim"))

        except Exception as e:
            self.write(Text(f"Error reading log: {e}", style="red"))

    async def _show_build_progress(self, task_id: str, project: str) -> None:
        """Show progress for a specific build"""
        try:
            # Read delegation output file
            output_file = Path.home() / ".context-foundry" / "delegations" / f"task-{task_id}.log"

            if output_file.exists():
                # Read last few lines
                all_lines = output_file.read_text().strip().split("\n")

                # Track which line we last showed for this build
                last_line_count = self.last_build_lines.get(task_id, 0)
                new_lines = all_lines[last_line_count:]

                # Show up to 3 new lines
                for line in new_lines[-3:]:
                    if line.strip():
                        # Colorize based on content
                        if "✓" in line or "success" in line.lower():
                            self.write(Text(f"[{project}] {line}", style="green"))
                        elif "error" in line.lower() or "failed" in line.lower():
                            self.write(Text(f"[{project}] {line}", style="red"))
                        elif "warning" in line.lower():
                            self.write(Text(f"[{project}] {line}", style="yellow"))
                        else:
                            self.write(Text(f"[{project}] {line}", style="cyan"))

                # Update last line count
                self.last_build_lines[task_id] = len(all_lines)

        except Exception:
            pass


class MissionControlApp(App):
    """Main Mission Control TUI Application"""

    # Model selection (default to sonnet)
    model = reactive("sonnet")

    # Track active builds
    active_builds = []

    # Enable mouse support for text selection
    # Users can select text with mouse and copy with their terminal's copy command
    # (usually Cmd+C on Mac, Ctrl+Shift+C on Linux/Windows)

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 4;
        grid-rows: auto 1fr 1fr auto;
        grid-gutter: 0;
        padding: 0;
    }

    Header {
        dock: top;
    }

    Footer {
        dock: bottom;
    }

    StatusPanel {
        border: solid cyan;
        max-height: 100%;
        overflow-y: auto;
        height: auto;
    }

    FileTreePanel {
        border: solid magenta;
        max-height: 100%;
        overflow-y: auto;
    }

    ChatPanel {
        row-span: 2;
        border: solid green;
        max-height: 100%;
        overflow-y: auto;
    }

    ActivityLog {
        column-span: 2;
        border: solid yellow;
        max-height: 100%;
        overflow-y: auto;
    }

    ChatInput {
        column-span: 2;
        border: solid blue;
        height: 3;
        min-height: 3;
        max-height: 3;
    }

    .user-message {
        background: $boost;
        padding: 1;
        margin: 1;
    }

    .assistant-message {
        background: $panel;
        padding: 1;
        margin: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+d", "send_message", "Send", show=True),
        Binding("ctrl+b", "start_build", "Build", show=True),
        Binding("ctrl+r", "refresh", "Refresh", show=True),
        Binding("ctrl+m", "cycle_model", "Model", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header(show_clock=True)
        yield StatusPanel()
        yield ChatPanel(id="chat")
        yield FileTreePanel()
        yield ActivityLog()
        yield ChatInput(id="chat_input")
        yield Footer()

    async def on_mount(self) -> None:
        """Set app title and focus input"""
        self.title = "Context Foundry Mission Control"
        self.update_subtitle()

        # Focus the input box so user can start typing immediately
        try:
            chat_input = self.query_one("#chat_input", ChatInput)
            chat_input.focus()
        except:
            pass

    def update_subtitle(self) -> None:
        """Update subtitle with current model"""
        model_display = {
            "sonnet": "Sonnet 4.5",
            "opus": "Opus 4",
            "haiku": "Haiku 3.5"
        }.get(self.model, self.model)
        self.sub_title = f"Evolution System Dashboard | Model: {model_display}"

    async def action_send_message(self) -> None:
        """Send chat message"""
        chat_input = None
        chat_panel = None

        try:
            chat_input = self.query_one("#chat_input", ChatInput)
            chat_panel = self.query_one("#chat", ChatPanel)

            message = chat_input.value.strip()
            if not message:
                # Still refocus even if empty
                self.call_later(lambda: chat_input.focus())
                return

            # Add user message
            await chat_panel.add_message("user", message)

            # Clear input
            chat_input.value = ""

            # Process message and respond
            response = await self._process_command(message)
            await chat_panel.add_message("assistant", response)

        except Exception as e:
            # Don't let errors break the UI
            if chat_panel:
                try:
                    await chat_panel.add_message("assistant", f"❌ Error: {str(e)}")
                except:
                    pass

        finally:
            # ALWAYS refocus the input with a slight delay to ensure UI is stable
            def refocus():
                try:
                    input_widget = self.query_one("#chat_input", ChatInput)
                    input_widget.focus()
                except Exception as e:
                    # Log error but don't crash
                    pass

            # Use call_later to ensure refocus happens after UI updates
            self.call_later(refocus)

    async def _get_mcp_status(self) -> str:
        """Get MCP status via wrapper"""
        try:
            # Use the MCP wrapper script
            wrapper_path = Path(__file__).parent / "mcp_wrapper.py"

            # Require python3.13 (has MCP deps installed)
            python_cmd = "/opt/homebrew/bin/python3.13"
            if not Path(python_cmd).exists():
                return (
                    "❌ Python 3.13 not found\n\n"
                    "MCP features require Python 3.13+ with FastMCP installed.\n\n"
                    "Install: brew install python@3.13\n"
                    "Then: /opt/homebrew/bin/python3.13 -m pip install -r requirements-mcp.txt"
                )

            # Call status command
            process = await asyncio.create_subprocess_exec(
                python_cmd, str(wrapper_path),
                "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                # Try to parse error JSON
                try:
                    import json
                    error_data = json.loads(stderr.decode())
                    return (
                        f"❌ {error_data.get('error', 'MCP Error')}\n\n"
                        f"{error_data.get('message', '')}\n\n"
                        f"{error_data.get('help', '')}"
                    )
                except:
                    return f"❌ MCP status error:\n{stderr.decode()}"

        except Exception as e:
            return f"❌ Error getting MCP status:\n{str(e)}"

    async def _process_command(self, message: str) -> str:
        """Process user command and return response"""
        message_lower = message.lower()

        # Build commands - delegate to autonomous build
        if any(word in message_lower for word in ["build", "create", "make", "develop"]):
            return await self._start_autonomous_build(message)

        # Status commands - call MCP status via wrapper
        elif any(word in message_lower for word in ["status", "health", "check"]):
            return await self._get_mcp_status()

        # Help commands
        elif any(word in message_lower for word in ["help", "what", "how"]):
            return (
                "Available commands:\n\n"
                "**Build Management:**\n"
                "• Just describe what you want to build!\n"
                "  Example: 'build a gorilla tag fun math game'\n"
                "• Natural language - AI will understand\n\n"
                "**System Control:**\n"
                "• `status` - Show system health\n"
                "• `restart daemon` - Restart Evolution daemon\n\n"
                "**Keyboard Shortcuts:**\n"
                "• Enter/Ctrl+D - Send message\n"
                "• Ctrl+M - Cycle model (Sonnet/Opus/Haiku)\n"
                "• Ctrl+R - Refresh panels\n"
                "• Ctrl+C - Quit\n\n"
                "**Copy Text:**\n"
                "• Hold Shift + Click and drag to select text\n"
                "• Then use your terminal's copy (Cmd+C / Ctrl+Shift+C)"
            )

        else:
            # Default: treat as build request
            return await self._start_autonomous_build(message)

    async def _start_autonomous_build(self, task_description: str) -> str:
        """Start an autonomous build via MCP wrapper"""
        try:
            # Import needed modules first
            import re
            import tempfile

            # Extract project name from task if possible
            words = task_description.split()
            if "build" in task_description.lower():
                # Try to extract name after "build"/"build a"
                build_idx = next((i for i, w in enumerate(words) if w.lower() == "build"), 0)
                # Skip articles
                name_start = build_idx + 1
                if name_start < len(words) and words[name_start].lower() in ["a", "an", "the"]:
                    name_start += 1
                # Take next 1-3 words as project name
                name_words = words[name_start:min(name_start + 3, len(words))]
                project_name = "-".join(name_words).lower().replace(",", "")
            else:
                # Use first few words
                project_name = "-".join(words[:3]).lower().replace(",", "")

            # Clean project name
            project_name = re.sub(r'[^a-z0-9-]', '', project_name)[:30]
            if not project_name:
                project_name = "mission-control-build"

            # Create working directory in homelab (same level as context-foundry)
            working_dir = Path.home() / "homelab" / project_name

            # Use the MCP wrapper script
            wrapper_path = Path(__file__).parent / "mcp_wrapper.py"

            # Require python3.13 (has MCP deps installed)
            python_cmd = "/opt/homebrew/bin/python3.13"
            if not Path(python_cmd).exists():
                return (
                    "❌ Python 3.13 not found\n\n"
                    "MCP features require Python 3.13+ with FastMCP installed.\n\n"
                    "Install: brew install python@3.13\n"
                    "Then: /opt/homebrew/bin/python3.13 -m pip install -r requirements-mcp.txt"
                )

            # Start the build and wait for task ID (fast - just returns delegation info)
            # The actual build runs in background via delegation system
            process = await asyncio.create_subprocess_exec(
                python_cmd, str(wrapper_path),
                "autonomous_build",
                "--task", task_description,
                "--working-directory", str(working_dir),
                "--github-repo-name", project_name,
                "--model", self.model,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for response (should be quick - just returns task ID)
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=10.0  # 10 second timeout for initial response
                )

                # Check for errors first
                stderr_text = stderr.decode() if stderr else ""
                stdout_text = stdout.decode() if stdout else ""

                if process.returncode != 0:
                    # Non-zero return code = error
                    return (
                        f"❌ Failed to start build:\n\n"
                        f"{stderr_text[:500]}\n\n"
                        f"Return code: {process.returncode}"
                    )

                if not stdout_text.strip():
                    # Empty stdout = something went wrong
                    return (
                        f"❌ No response from MCP wrapper:\n\n"
                        f"Stdout: (empty)\n"
                        f"Stderr: {stderr_text[:300]}\n\n"
                        f"Debug: Check that FastMCP is installed in Python 3.13"
                    )

                # Try to parse JSON response
                try:
                    result = json.loads(stdout_text)
                    task_id = result.get("task_id", "unknown")

                    # Track this build persistently
                    build_info = {
                        "task_id": task_id,
                        "project": project_name,
                        "working_directory": str(working_dir),
                        "started": datetime.now().isoformat(),
                        "status": "running"
                    }

                    # Save to disk for persistence
                    self._save_tracked_build(build_info)

                    # Also track in memory
                    self.active_builds.append(build_info)

                    return (
                        f"🚀 Build started successfully!\n\n"
                        f"**Project:** {project_name}\n"
                        f"**Task:** {task_description}\n"
                        f"**Model:** Claude {self.model.capitalize()}\n"
                        f"**Location:** {working_dir}\n"
                        f"**Task ID:** {task_id[:8]}...\n\n"
                        f"✅ Build is running in the background.\n"
                        f"✅ It will continue even if you close this TUI.\n\n"
                        f"Watch System Status panel for live progress!\n\n"
                        f"💡 Tip: The build will auto-deploy to GitHub when complete!"
                    )
                except json.JSONDecodeError as je:
                    return (
                        f"❌ Invalid JSON response:\n\n"
                        f"Stdout: {stdout_text[:300]}\n"
                        f"Stderr: {stderr_text[:300]}\n\n"
                        f"JSON Error: {str(je)}"
                    )

            except asyncio.TimeoutError:
                return (
                    f"⚠️ Build start timeout\n\n"
                    f"The build may still be starting in the background.\n"
                    f"Check the delegation system with:\n"
                    f"`claude-code 'list delegations'`"
                )

        except Exception as e:
            return (
                f"❌ Error starting build:\n{str(e)}\n\n"
                f"Make sure MCP server is available.\n"
                f"Error details: {type(e).__name__}"
            )

    def _save_tracked_build(self, build_info: dict) -> None:
        """Save build info to persistent storage"""
        try:
            builds_file = Path.home() / ".context-foundry" / "tui-tracked-builds.json"
            builds_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing builds
            builds = []
            if builds_file.exists():
                try:
                    builds = json.loads(builds_file.read_text())
                except:
                    builds = []

            # Add new build
            builds.append(build_info)

            # Save back
            builds_file.write_text(json.dumps(builds, indent=2))

        except Exception as e:
            pass  # Don't crash if saving fails

    def _load_tracked_builds(self) -> list:
        """Load tracked builds from disk"""
        try:
            builds_file = Path.home() / ".context-foundry" / "tui-tracked-builds.json"
            if builds_file.exists():
                builds = json.loads(builds_file.read_text())
                # Filter out completed builds older than 1 hour
                cutoff = datetime.now().timestamp() - 3600
                active_builds = []
                for build in builds:
                    if build.get("status") == "running":
                        started = datetime.fromisoformat(build["started"]).timestamp()
                        if started > cutoff:
                            active_builds.append(build)
                return active_builds
            return []
        except:
            return []

    async def action_start_build(self) -> None:
        """Quick build action"""
        chat_panel = self.query_one("#chat", ChatPanel)
        await chat_panel.add_message(
            "assistant",
            "🚀 Quick Build\n\n"
            "Please provide:\n"
            "1. Project name\n"
            "2. Task description\n\n"
            "Format: `build <name> <task>`"
        )

    async def action_refresh(self) -> None:
        """Refresh all panels"""
        status_panel = self.query_one(StatusPanel)
        await status_panel.refresh_status()

    async def action_cycle_model(self) -> None:
        """Cycle through available models"""
        models = ["sonnet", "opus", "haiku"]
        current_index = models.index(self.model)
        next_index = (current_index + 1) % len(models)
        self.model = models[next_index]
        self.update_subtitle()

        # Show notification
        chat_panel = self.query_one("#chat", ChatPanel)
        model_names = {
            "sonnet": "Claude Sonnet 4.5",
            "opus": "Claude Opus 4",
            "haiku": "Claude Haiku 3.5"
        }
        await chat_panel.add_message(
            "assistant",
            f"🔄 Model switched to: {model_names[self.model]}"
        )


def main():
    """Run Mission Control TUI"""
    app = MissionControlApp()
    app.run()


if __name__ == "__main__":
    main()
