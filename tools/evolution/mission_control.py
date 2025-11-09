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
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path to import version
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from __version__ import __version__

from enum import Enum
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button, Label, RichLog, Tree, ListView, ListItem
from textual.widgets.tree import TreeNode
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax


class ViewMode(Enum):
    """View modes for single-focus interface"""
    CONVERSATION = "conversation"
    BUILDS = "builds"
    STATUS = "status"


class TabBar(Static):
    """Minimal tab bar showing current view"""

    current_view = reactive(ViewMode.CONVERSATION)

    def render(self) -> Text:
        """Render the tab bar text"""
        tabs: list[Text] = []

        # Conversation tab
        if self.current_view == ViewMode.CONVERSATION:
            tabs.append(Text("Conversation", style="bold #8B5CF6"))
        else:
            tabs.append(Text("Conversation", style="dim"))

        tabs.append(Text("    "))

        # Builds tab
        if self.current_view == ViewMode.BUILDS:
            tabs.append(Text("Builds", style="bold #3B82F6"))
        else:
            tabs.append(Text("Builds", style="dim"))

        tabs.append(Text("    "))

        # Status tab
        if self.current_view == ViewMode.STATUS:
            tabs.append(Text("Status", style="bold #A78BFA"))
        else:
            tabs.append(Text("Status", style="dim"))

        result = Text()
        for tab in tabs:
            result.append(tab)

        return result

    def watch_current_view(self, new_value: ViewMode) -> None:
        """Refresh display when current view changes"""
        self.refresh()

    def on_mount(self) -> None:
        """Ensure initial render on mount"""
        self.refresh()

    async def on_click(self, event) -> None:
        """Handle tab clicks"""
        # Get click position
        x = event.x

        # Simple position-based detection (each tab is ~12-15 chars wide)
        if x < 15:
            # Conversation tab
            await self.app.switch_to_view(ViewMode.CONVERSATION)
        elif x < 30:
            # Builds tab
            await self.app.switch_to_view(ViewMode.BUILDS)
        else:
            # Status tab
            await self.app.switch_to_view(ViewMode.STATUS)


class StatusBar(Static):
    """Simple bottom status bar"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_mount(self) -> None:
        """Start status updates"""
        self.set_interval(2.0, self.refresh_status)
        await self.refresh_status()

    async def refresh_status(self) -> None:
        """Update status bar"""
        try:
            app = self.app

            # Get model name
            model_display = {
                "sonnet": "Sonnet 4.5",
                "opus": "Opus 4",
                "haiku": "Haiku 3.5"
            }.get(app.model if hasattr(app, 'model') else "sonnet", "Sonnet 4.5")

            # Count active builds
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            active_builds = 0
            if delegations_dir.exists():
                for task_file in delegations_dir.glob("task-*.json"):
                    try:
                        metadata = json.loads(task_file.read_text())
                        if metadata.get("status") == "running":
                            active_builds += 1
                    except:
                        continue

            # Get MCP status
            mcp_status = self._get_mcp_status()
            status_text = "Ready" if mcp_status["available"] else "MCP Offline"

            # Get current view mode
            view_mode = "Conversation"
            if hasattr(app, 'current_view'):
                view_mode = app.current_view.value.capitalize()

            # Simple status line
            builds_text = f"{active_builds} build{'s' if active_builds != 1 else ''}" if active_builds > 0 else "No builds"
            status_line = f"Context Foundry v{__version__} | {status_text} | {builds_text} active | {model_display} | Press ? for help"

            self.update(Text(status_line, style="dim"))

        except Exception as e:
            self.update(Text(f"Status error", style="dim red"))

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


class FileTreePanel(Static):
    """Live file tree showing build directory contents"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_dir = None

    async def on_mount(self) -> None:
        """Start file tree updates"""
        self.set_interval(1.5, self.refresh_tree)
        await self.refresh_tree()

    async def refresh_tree(self) -> None:
        """Refresh file tree from selected build directory"""
        try:
            # Get the selected build from the delegations panel
            build_dir = None

            # Try to get the currently selected delegation
            app = self.app
            if hasattr(app, 'query_one'):
                try:
                    delegations_panel = app.query_one("#delegations", DelegationsListPanel)
                    selected = delegations_panel.get_selected_delegation()

                    if selected:
                        working_dir = selected.get("working_directory", "")
                        if working_dir and Path(working_dir).exists():
                            build_dir = Path(working_dir)
                except:
                    pass

            # Fallback: If no selection, find first running delegation
            if not build_dir:
                delegations_dir = Path.home() / ".context-foundry" / "delegations"
                if delegations_dir.exists():
                    try:
                        for task_file in delegations_dir.glob("task-*.json"):
                            try:
                                metadata = json.loads(task_file.read_text())
                                if metadata.get("status") == "running":
                                    working_dir = metadata.get("working_directory", "")
                                    if working_dir and Path(working_dir).exists():
                                        build_dir = Path(working_dir)
                                        break
                            except:
                                continue
                    except Exception:
                        pass

            if build_dir and build_dir.exists():
                self.current_dir = build_dir

                # Count files
                file_count = 0
                changed_count = 0
                try:
                    for item in build_dir.rglob("*"):
                        if item.is_file() and not item.name.startswith('.'):
                            file_count += 1
                            # Simple heuristic: files modified in last hour are "changed"
                            if (datetime.now().timestamp() - item.stat().st_mtime) < 3600:
                                changed_count += 1
                except:
                    pass

                # Compact summary with colored header
                result = Text()

                # Colored header
                result.append("Build Directory:\n\n", style="bold #A78BFA")

                # Folder name (no emoji)
                result.append(build_dir.name, style="bold #8B5CF6")
                result.append("\n")

                # File counts with colors
                result.append("   ", style="")
                result.append(str(file_count), style="#3B82F6")
                result.append(" files", style="dim")

                if changed_count > 0:
                    result.append(", ", style="dim")
                    result.append(str(changed_count), style="green")
                    result.append(" changed", style="dim")

                result.append("\n")

                # Path in dim color
                result.append("   ", style="")
                result.append(str(build_dir), style="dim")
                result.append("\n\n")

                # Ready status in green
                result.append("   ", style="")
                result.append("Ready to build", style="green")

                self.update(result)
            else:
                # No active build with colored header
                result = Text()
                result.append("Build Directory:\n\n", style="bold #A78BFA")
                result.append("No active build\n\nStart a build to see it here", style="dim italic")
                self.update(result)

        except Exception as e:
            self.update(Text(f"Error loading build directory", style="dim red"))


class DelegationsListPanel(Static, can_focus=True):
    """List of all delegations with status"""

    selected_index = reactive(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.delegations = []

    async def on_mount(self) -> None:
        """Start delegation list updates"""
        self.set_interval(2.0, self.refresh_delegations)
        await self.refresh_delegations()

    async def refresh_delegations(self) -> None:
        """Refresh delegation list"""
        try:
            # Read from shared delegations directory
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            if not delegations_dir.exists():
                self.delegations = []
                self._render_list()
                return

            delegations = []
            for task_file in sorted(delegations_dir.glob("task-*.json"), reverse=True):
                try:
                    metadata = json.loads(task_file.read_text())

                    # Get start time
                    start_time_str = metadata.get("start_time", "")
                    start_display = "unknown"
                    if start_time_str:
                        try:
                            start_time = datetime.fromisoformat(start_time_str)
                            start_display = start_time.strftime("%H:%M:%S")
                        except:
                            pass

                    # Extract GitHub repo name from task or working directory
                    github_repo = metadata.get("github_repo_name", "")
                    if not github_repo:
                        # Try to infer from working directory
                        working_dir = metadata.get("working_directory", "")
                        github_repo = Path(working_dir).name if working_dir else ""

                    # Only show running or pending builds (filter out completed/cancelled/failed)
                    status = metadata.get("status", "unknown")
                    if status not in ["running", "pending"]:
                        continue

                    delegations.append({
                        "task_id": metadata.get("task_id", "unknown"),
                        "status": status,
                        "task": metadata.get("task", "")[:40],
                        "working_directory": metadata.get("working_directory", ""),
                        "start_time": start_display,
                        "github_repo": github_repo
                    })
                except:
                    continue

            self.delegations = delegations
            self._render_list()

        except Exception as e:
            self.delegations = []
            self._render_list()

    def _render_list(self) -> None:
        """Render the delegation list with colored styling"""
        if not self.delegations:
            self.update(Text("No active builds\n\nStart a build to see it here", style="dim italic"))
            return

        # Build colored list with Rich Text
        result = Text()

        # Colored header
        result.append("Active Builds (", style="bold #3B82F6")
        result.append(str(len(self.delegations)), style="bold #3B82F6")
        result.append("):\n", style="bold #3B82F6")

        # Instructions at the TOP (not bottom)
        result.append("Use ↑↓ arrow keys to navigate  •  x to cancel  •  d for details\n", style="dim italic")
        result.append("(Keyboard only - clicking not supported)\n\n", style="dim italic")

        for i, delegation in enumerate(self.delegations):
            # Status styling
            status = delegation["status"]
            if status == "running":
                status_text = "Running"
                status_style = "green"
            elif status == "completed":
                status_text = "Done"
                status_style = "blue"
            elif status == "cancelled":
                status_text = "Cancelled"
                status_style = "yellow"
            else:
                status_text = "Failed"
                status_style = "red"

            # Extract project name
            working_dir = delegation.get("working_directory", "")
            project = Path(working_dir).name if working_dir else "build"

            # Build line with colors
            is_selected = i == self.selected_index
            selector = "▶ " if is_selected else "  "
            github_repo = delegation.get("github_repo", "")[:30]
            start_time = delegation.get("start_time", "")

            # Selector and project name with list number
            list_num = f"[{i+1}] "
            result.append(list_num, style="dim")
            result.append(selector, style="bold #8B5CF6" if is_selected else "")
            result.append(project, style="bold #8B5CF6")

            if is_selected:
                result.append("  ← SELECTED", style="bold #8B5CF6")
            result.append("\n")

            # Status line with colors
            result.append("   Status: ", style="dim")
            result.append(status_text, style=status_style)
            result.append("  Started: ", style="dim")
            result.append(start_time, style="#3B82F6")
            result.append("\n")

            # GitHub repo if present
            if github_repo:
                result.append("   Repo: ", style="dim")
                result.append(github_repo, style="#A78BFA")
                result.append("\n")

        self.update(result)

    def get_selected_delegation(self) -> Optional[dict]:
        """Get the currently selected delegation"""
        if 0 <= self.selected_index < len(self.delegations):
            return self.delegations[self.selected_index]
        return None

    def move_selection_up(self) -> None:
        """Move selection up"""
        if self.selected_index > 0:
            self.selected_index -= 1
            self._render_list()

    def move_selection_down(self) -> None:
        """Move selection down"""
        if self.selected_index < len(self.delegations) - 1:
            self.selected_index += 1
            self._render_list()


class ChatMessage(Static):
    """Individual chat message"""

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content

    def compose(self) -> ComposeResult:
        """Render chat message with markup support"""
        from rich.text import Text

        if self.role == "user":
            # User messages with light blue styling
            text = Text()
            text.append("You: ", style="bold #3B82F6")
            text.append(self.content)
            yield Static(text, classes="user-message")
        else:
            # Assistant messages with markup support
            from rich.markup import render
            text = render(self.content)
            yield Static(text, classes="assistant-message")


class ChatPanel(VerticalScroll):
    """Context Chat interface panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_mount(self) -> None:
        """Show welcome message with colored header"""
        # Use markup for colored header
        await self.add_message(
            "assistant",
            "[bold #8B5CF6]Home • Conversation[/bold #8B5CF6]\n\nReady to help. What are you building?"
        )

    async def on_click(self) -> None:
        """Focus input when chat panel is clicked"""
        try:
            chat_input = self.app.query_one("#chat_input", ChatInput)
            chat_input.focus()
        except:
            pass

    async def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat"""
        await self.mount(ChatMessage(role, content))
        self.scroll_end(animate=False)


class ChatInput(Input, can_focus=True):
    """Chat input field"""

    def __init__(self, **kwargs):
        super().__init__(placeholder="Type a message... (Enter to send, Tab to switch views)", **kwargs)

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


class DetailsModal(ModalScreen):
    """Modal screen showing detailed build results"""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def __init__(self, task_id: str, **kwargs):
        super().__init__(**kwargs)
        self.task_id = task_id
        self.result_text = "Loading..."

    def compose(self) -> ComposeResult:
        with Container(id="details_modal"):
            yield Static(f"Build Details: {self.task_id[:8]}...", id="modal_title")
            yield ScrollableContainer(
                Static(self.result_text, id="details_content"),
                id="details_scroll"
            )
            yield Button("Close (ESC)", id="btn_close_details", variant="primary")

    async def on_mount(self) -> None:
        """Load delegation result when modal opens"""
        await self.load_result()

    async def load_result(self) -> None:
        """Load detailed results via MCP wrapper"""
        try:
            wrapper_path = Path(__file__).parent / "mcp_wrapper.py"
            python_cmd = "/opt/homebrew/bin/python3.13"

            if not Path(python_cmd).exists():
                self.result_text = "❌ Python 3.13 not found"
                return

            process = await asyncio.create_subprocess_exec(
                python_cmd, str(wrapper_path),
                "get_result",
                "--task-id", self.task_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=5.0
            )

            if process.returncode == 0 and stdout:
                result = json.loads(stdout.decode())

                # Format the result nicely
                formatted = []
                formatted.append(f"[bold cyan]Task ID:[/bold cyan] {self.task_id}")
                formatted.append(f"[bold cyan]Status:[/bold cyan] {result.get('status', 'unknown')}")
                formatted.append(f"[bold cyan]Duration:[/bold cyan] {result.get('duration', 'unknown')}")
                formatted.append("")

                if result.get("stdout"):
                    formatted.append("[bold green]Output:[/bold green]")
                    formatted.append(result.get("stdout", "")[:2000])  # Limit to 2000 chars

                if result.get("stderr"):
                    formatted.append("")
                    formatted.append("[bold red]Errors:[/bold red]")
                    formatted.append(result.get("stderr", "")[:1000])

                self.result_text = "\n".join(formatted)
            else:
                error = stderr.decode() if stderr else "Unknown error"
                self.result_text = f"❌ Failed to load results:\n{error}"

            # Update the content widget
            content_widget = self.query_one("#details_content", Static)
            content_widget.update(self.result_text)

        except asyncio.TimeoutError:
            self.result_text = "⏱️ Timeout loading results"
            content_widget = self.query_one("#details_content", Static)
            content_widget.update(self.result_text)
        except Exception as e:
            self.result_text = f"❌ Error: {str(e)}"
            content_widget = self.query_one("#details_content", Static)
            content_widget.update(self.result_text)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press"""
        if event.button.id == "btn_close_details":
            self.dismiss()

    def action_dismiss(self) -> None:
        """Dismiss the modal"""
        self.dismiss()


class PatternsModal(ModalScreen):
    """Modal screen showing global patterns and learnings"""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.patterns_text = "Loading patterns..."

    def compose(self) -> ComposeResult:
        with Container(id="patterns_modal"):
            yield Static("🎓 Global Learnings & Patterns", id="modal_title")
            yield ScrollableContainer(
                Static(self.patterns_text, id="patterns_content"),
                id="patterns_scroll"
            )
            yield Button("Close (ESC)", id="btn_close_patterns", variant="primary")

    async def on_mount(self) -> None:
        """Load patterns when modal opens"""
        await self.load_patterns()

    async def load_patterns(self) -> None:
        """Load global patterns via MCP wrapper"""
        try:
            wrapper_path = Path(__file__).parent / "mcp_wrapper.py"
            python_cmd = "/opt/homebrew/bin/python3.13"

            if not Path(python_cmd).exists():
                self.patterns_text = "❌ Python 3.13 not found"
                return

            process = await asyncio.create_subprocess_exec(
                python_cmd, str(wrapper_path),
                "patterns",
                "--type", "common-issues",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=5.0
            )

            if process.returncode == 0 and stdout:
                result = json.loads(stdout.decode())

                # Format patterns nicely
                formatted = []
                formatted.append("[bold cyan]Common Issues & Solutions:[/bold cyan]\n")

                patterns = result.get("patterns", [])
                if patterns:
                    for i, pattern in enumerate(patterns[:10], 1):  # Show top 10
                        formatted.append(f"[bold yellow]{i}. {pattern.get('issue', 'Unknown')}[/bold yellow]")
                        formatted.append(f"   Frequency: {pattern.get('frequency', 0)} times")
                        formatted.append(f"   Solution: {pattern.get('solution', 'N/A')[:100]}")
                        formatted.append("")
                else:
                    formatted.append("[dim]No patterns learned yet. Build more projects to accumulate learnings![/dim]")

                self.patterns_text = "\n".join(formatted)
            else:
                error = stderr.decode() if stderr else "Unknown error"
                self.patterns_text = f"❌ Failed to load patterns:\n{error}"

            # Update the content widget
            content_widget = self.query_one("#patterns_content", Static)
            content_widget.update(self.patterns_text)

        except asyncio.TimeoutError:
            self.patterns_text = "⏱️ Timeout loading patterns"
            content_widget = self.query_one("#patterns_content", Static)
            content_widget.update(self.patterns_text)
        except Exception as e:
            self.patterns_text = f"❌ Error: {str(e)}"
            content_widget = self.query_one("#patterns_content", Static)
            content_widget.update(self.patterns_text)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press"""
        if event.button.id == "btn_close_patterns":
            self.dismiss()

    def action_dismiss(self) -> None:
        """Dismiss the modal"""
        self.dismiss()


class ConfirmCancelModal(ModalScreen):
    """Confirmation dialog for canceling a build"""

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
        ("n", "dismiss", "No"),
    ]

    def __init__(self, task_id: str, project_name: str, **kwargs):
        super().__init__(**kwargs)
        self.task_id = task_id
        self.project_name = project_name
        self.confirmed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_modal"):
            yield Static("⚠️  Confirm Cancel Build", id="confirm_title")
            yield Static(
                f"\nAre you sure you want to cancel this build?\n\n"
                f"[bold cyan]Project:[/bold cyan] {self.project_name}\n"
                f"[bold cyan]Task ID:[/bold cyan] {self.task_id[:8]}...\n\n"
                f"[yellow]This action cannot be undone.[/yellow]",
                id="confirm_message"
            )
            with Horizontal(id="confirm_buttons"):
                yield Button("OK, Cancel Build", id="btn_confirm_yes", variant="error")
                yield Button("Nevermind", id="btn_confirm_no", variant="primary")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press"""
        if event.button.id == "btn_confirm_yes":
            self.confirmed = True
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss(self) -> None:
        """Dismiss without confirming"""
        self.dismiss(False)


class MissionControlApp(App):
    """Main Mission Control TUI Application"""

    # Model selection (default to sonnet)
    model = reactive("sonnet")

    # Current view mode
    current_view = reactive(ViewMode.CONVERSATION)

    # Track active builds
    active_builds = []

    # Enable mouse support for text selection
    # Users can select text with mouse and copy with their terminal's copy command
    # (usually Cmd+C on Mac, Ctrl+Shift+C on Linux/Windows)

    CSS = """
    Screen {
        layout: vertical;
        padding: 0;
    }

    Header {
        display: none;
    }

    Footer {
        dock: bottom;
        background: #16213e;
        color: #e0e0e0;
    }

    Footer > .footer--key {
        background: #8B5CF6;
        color: #ffffff;
    }

    Footer > .footer--description {
        color: #A78BFA;
    }

    TabBar {
        dock: top;
        height: 1;
        min-height: 1;
        background: $surface;
        padding: 0 2;
        border-bottom: tall $panel;
    }

    StatusBar {
        dock: bottom;
        height: 1;
        background: #1a1a2e;
        color: #A78BFA;
        padding: 0 1;
    }

    ChatPanel {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
        background: $background;
        display: block;
    }

    ChatPanel.hidden {
        display: none;
    }

    DelegationsListPanel {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
        background: $background;
        display: none;
    }

    DelegationsListPanel.visible {
        display: block;
    }

    FileTreePanel {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
        background: $background;
        display: none;
    }

    FileTreePanel.visible {
        display: block;
    }

    ChatInput {
        height: 3;
        min-height: 3;
        max-height: 3;
        padding: 0 1;
        background: #1a1a2e;
        color: #e0e0e0;
        border: solid #8B5CF6;
    }

    /* Modal styles */
    #details_modal, #patterns_modal {
        align: center middle;
        background: $surface;
        border: thick $primary;
        width: 80%;
        height: 80%;
        padding: 1;
    }

    #confirm_modal {
        align: center middle;
        background: $surface;
        border: thick $error;
        width: 60;
        height: auto;
        max-height: 20;
        padding: 1;
    }

    #confirm_title {
        text-align: center;
        text-style: bold;
        background: $error;
        color: $text;
        padding: 1;
        width: 100%;
    }

    #confirm_message {
        text-align: center;
        padding: 2;
        margin: 1 0;
        width: 100%;
    }

    #confirm_buttons {
        align: center middle;
        width: 100%;
        height: auto;
        padding: 1;
        margin-top: 1;
    }

    #confirm_buttons Button {
        min-width: 20;
        margin: 0 2;
    }

    #modal_title {
        text-align: center;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 1;
        margin-bottom: 1;
    }

    #details_scroll, #patterns_scroll {
        height: 100%;
        border: solid $accent;
    }

    .user-message {
        padding: 1 2;
        margin: 0 0 1 0;
        color: $text;
        background: #1e3a5f 15%;
    }

    .assistant-message {
        padding: 1 2;
        margin: 0 0 2 0;
        color: $text;
        background: #4a1f6f 10%;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+d", "send_message", "Send", show=False),
        Binding("ctrl+m", "cycle_model", "Model", show=True),
        Binding("tab", "toggle_view", "View", show=True, priority=True),
        Binding("up", "select_up", "Up", show=False),
        Binding("down", "select_down", "Down", show=False),
        Binding("d", "show_details", "Details", show=False),
        Binding("x", "cancel_build", "Cancel", show=False),
        Binding("question_mark", "show_help", "Help", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield TabBar(id="tab_bar")
        yield ChatPanel(id="chat")
        yield FileTreePanel(id="file_tree")
        yield DelegationsListPanel(id="delegations")
        yield ChatInput(id="chat_input")
        yield StatusBar(id="status_bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize app"""
        self.title = ""  # No title, we have status bar
        self.sub_title = ""

        # Set initial view
        await self._update_view()

        # Focus chat input
        try:
            chat_input = self.query_one("#chat_input", ChatInput)
            chat_input.focus()
        except:
            pass

    async def _update_view(self) -> None:
        """Update visibility based on current view"""
        try:
            chat = self.query_one("#chat", ChatPanel)
            delegations = self.query_one("#delegations", DelegationsListPanel)
            file_tree = self.query_one("#file_tree", FileTreePanel)
            tab_bar = self.query_one("#tab_bar", TabBar)

            # Sync tab bar
            tab_bar.current_view = self.current_view

            # Show current view
            if self.current_view == ViewMode.CONVERSATION:
                chat.remove_class("hidden")
                delegations.remove_class("visible")
                file_tree.remove_class("visible")
                delegations.display = False
                file_tree.display = False
                chat.display = True
            elif self.current_view == ViewMode.BUILDS:
                chat.add_class("hidden")
                delegations.add_class("visible")
                file_tree.remove_class("visible")
                chat.display = False
                delegations.display = True
                file_tree.display = False
            elif self.current_view == ViewMode.STATUS:
                chat.add_class("hidden")
                delegations.remove_class("visible")
                file_tree.add_class("visible")
                chat.display = False
                delegations.display = False
                file_tree.display = True

        except Exception:
            pass

    async def switch_to_view(self, view_mode: ViewMode) -> None:
        """Switch to a specific view"""
        self.current_view = view_mode
        await self._update_view()

        # Auto-focus input when on conversation view
        if self.current_view == ViewMode.CONVERSATION:
            try:
                chat_input = self.query_one("#chat_input", ChatInput)
                chat_input.focus()
            except:
                pass

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
        message_lower = message.lower().strip()

        # Status commands - check first before greeting filter
        if any(word in message_lower for word in ["status", "health", "check", "delegation"]):
            # Check if they want details for a specific build
            delegations_panel = self.query_one("#delegations", DelegationsListPanel)
            selected = delegations_panel.get_selected_delegation()

            if selected and "selected" in message_lower:
                project = selected.get("github_repo", "build")
                status = selected.get("status", "unknown")
                start_time = selected.get("start_time", "unknown")

                return (
                    f"{project}\n"
                    f"Status: {status}\n"
                    f"Started: {start_time}\n\n"
                    f"Press d for full details"
                )
            else:
                return await self._get_mcp_status()

        # Help commands - check before greeting filter
        if any(word in message_lower for word in ["help", "what", "how", "?"]):
            return (
                "Commands:\n"
                "  Describe what you want to build in plain English\n"
                "  status - Check system status\n"
                "  help or ? - Show this message\n\n"
                "Navigation:\n"
                "  Click tabs at top to switch views\n"
                "  Tab key - Cycle through views\n\n"
                "Keyboard:\n"
                "  d - View build details\n"
                "  ↑↓ - Navigate builds\n"
                "  x - Cancel build\n"
                "  Ctrl+M - Change model\n"
                "  Ctrl+C - Quit"
            )

        # Build commands - delegate to autonomous build
        # Keywords: build, create, make, develop, implement, write, design, upgrade, fix, update
        build_keywords = ["build", "create", "make", "develop", "implement", "write", "design", "upgrade", "fix", "update", "add", "modify"]
        if any(word in message_lower for word in build_keywords):
            return await self._start_autonomous_build(message)

        # Check for query/info commands that should NOT trigger builds
        query_keywords = ["get", "show", "list", "view", "display", "details", "result", "info"]
        if any(word in message_lower.split() for word in query_keywords):
            return "Use Tab to switch views, or type 'help' for commands"

        # Greetings and casual messages - don't start a build!
        greeting_keywords = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "sup", "yo"]
        if message_lower in greeting_keywords:
            return "Hello! What would you like to build?"

        # Very short messages (1-2 words) that aren't commands - ask for clarification
        if len(message_lower.split()) <= 2:
            return "Not sure what you mean. Try 'build a [description]' or type 'help'"

        # Unclear intent - ask for clarification
        return "Not sure what you mean. Try 'build a [description]' or type 'help'"

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
                        f"Starting build: {project_name}\n\n"
                        f"Task: {task_description}\n"
                        f"Model: {self.model.capitalize()}\n"
                        f"Location: {working_dir}\n\n"
                        f"Running in background. Press Tab to view builds."
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
        """Save build info to shared delegations directory"""
        try:
            delegations_dir = Path.home() / ".context-foundry" / "delegations"
            delegations_dir.mkdir(parents=True, exist_ok=True)

            task_id = build_info.get("task_id")
            task_file = delegations_dir / f"task-{task_id}.json"

            # Write delegation metadata
            task_file.write_text(json.dumps(build_info, indent=2))

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

    async def action_refresh(self) -> None:
        """Refresh status bar"""
        try:
            status_bar = self.query_one("#status_bar", StatusBar)
            await status_bar.refresh_status()
        except:
            pass

    async def action_toggle_view(self) -> None:
        """Toggle between views"""
        if self.current_view == ViewMode.CONVERSATION:
            self.current_view = ViewMode.BUILDS
        elif self.current_view == ViewMode.BUILDS:
            self.current_view = ViewMode.STATUS
        else:
            self.current_view = ViewMode.CONVERSATION

        await self._update_view()

        # Always refocus input when on conversation view
        if self.current_view == ViewMode.CONVERSATION:
            try:
                chat_input = self.query_one("#chat_input", ChatInput)
                chat_input.focus()
            except:
                pass

    async def action_show_help(self) -> None:
        """Show help message"""
        chat_panel = self.query_one("#chat", ChatPanel)
        await chat_panel.add_message(
            "assistant",
            "Commands:\n"
            "  Describe what you want to build in plain English\n"
            "  status - Check system status\n"
            "  help or ? - Show this message\n\n"
            "Navigation:\n"
            "  Click tabs at top to switch views\n"
            "  Tab key - Cycle through views\n\n"
            "Keyboard:\n"
            "  d - View build details\n"
            "  ↑↓ - Navigate builds\n"
            "  x - Cancel build\n"
            "  Ctrl+M - Change model\n"
            "  Ctrl+C - Quit"
        )

    async def action_cycle_model(self) -> None:
        """Cycle through available models"""
        models = ["sonnet", "opus", "haiku"]
        current_index = models.index(self.model)
        next_index = (current_index + 1) % len(models)
        self.model = models[next_index]

        # Show notification
        chat_panel = self.query_one("#chat", ChatPanel)
        model_names = {
            "sonnet": "Sonnet 4.5",
            "opus": "Opus 4",
            "haiku": "Haiku 3.5"
        }
        await chat_panel.add_message(
            "assistant",
            f"Model: {model_names[self.model]}"
        )

    async def action_select_up(self) -> None:
        """Move delegation selection up"""
        try:
            delegations_panel = self.query_one("#delegations", DelegationsListPanel)
            delegations_panel.move_selection_up()
        except:
            pass

    async def action_select_down(self) -> None:
        """Move delegation selection down"""
        try:
            delegations_panel = self.query_one("#delegations", DelegationsListPanel)
            delegations_panel.move_selection_down()
        except:
            pass

    async def action_show_details(self) -> None:
        """Show detailed results for selected delegation"""
        try:
            delegations_panel = self.query_one("#delegations", DelegationsListPanel)
            selected = delegations_panel.get_selected_delegation()

            if selected:
                task_id = selected.get("task_id")
                if task_id:
                    # Push the details modal screen
                    await self.push_screen(DetailsModal(task_id))
        except Exception as e:
            pass

    async def action_cancel_build(self) -> None:
        """Cancel selected delegation with confirmation"""
        try:
            delegations_panel = self.query_one("#delegations", DelegationsListPanel)
            selected = delegations_panel.get_selected_delegation()

            if not selected:
                return

            task_id = selected.get("task_id")
            if not task_id:
                return

            # Get project name
            working_dir = selected.get("working_directory", "")
            project_name = Path(working_dir).name if working_dir else "build"

            # Show confirmation modal
            confirmed = await self.push_screen_wait(
                ConfirmCancelModal(task_id, project_name)
            )

            # Only proceed if user confirmed
            if not confirmed:
                return

            # Call cancel via MCP wrapper
            wrapper_path = Path(__file__).parent / "mcp_wrapper.py"
            python_cmd = "/opt/homebrew/bin/python3.13"

            if Path(python_cmd).exists():
                process = await asyncio.create_subprocess_exec(
                    python_cmd, str(wrapper_path),
                    "cancel",
                    "--task-id", task_id,
                    "--reason", "User cancelled via Mission Control",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=5.0
                )

                if process.returncode == 0:
                    # Show success message
                    chat_panel = self.query_one("#chat", ChatPanel)
                    await chat_panel.add_message(
                        "assistant",
                        f"✅ Cancelled build: {project_name} ({task_id[:8]}...)"
                    )

                    # Force immediate refresh of delegations list
                    await delegations_panel.refresh_delegations()
                else:
                    # Parse error message from stderr if possible
                    error_msg = stderr.decode() if stderr else 'Unknown error'
                    try:
                        # Try to parse JSON error for better message
                        error_json = json.loads(error_msg)
                        error_detail = error_json.get("error", error_msg)
                        error_detail += "\n" + error_json.get("message", "")
                    except:
                        error_detail = error_msg

                    chat_panel = self.query_one("#chat", ChatPanel)
                    await chat_panel.add_message(
                        "assistant",
                        f"Failed to cancel build: {error_detail}"
                    )
        except Exception as e:
            # Show actual errors instead of swallowing them
            try:
                chat_panel = self.query_one("#chat", ChatPanel)
                await chat_panel.add_message(
                    "assistant",
                    f"Error cancelling build: {str(e)}"
                )
            except:
                # If even showing the error fails, at least log it
                import traceback
                traceback.print_exc()

    async def action_show_learnings(self) -> None:
        """Show global patterns and learnings"""
        try:
            # Push the patterns modal screen
            await self.push_screen(PatternsModal())
        except Exception as e:
            pass


def main():
    """Run Mission Control TUI"""
    app = MissionControlApp()
    app.run()


if __name__ == "__main__":
    main()
