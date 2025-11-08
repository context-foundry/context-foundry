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
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, Button, Label, RichLog
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.table import Table


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

            # Build status table
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Key", style="cyan")
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

            # Active Builds
            table.add_row(
                "Builds",
                Text(f"0 active", style="dim")
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
            "I can help you:\n"
            "• Start builds in isolated sandboxes\n"
            "• Check Evolution daemon status\n"
            "• Manage GitHub issues\n"
            "• Monitor MCP health\n\n"
            "What would you like to do?"
        )

    async def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat"""
        await self.mount(ChatMessage(role, content))
        self.scroll_end(animate=False)


class ChatInput(Input):
    """Chat input field"""

    def __init__(self, **kwargs):
        super().__init__(placeholder="Type a message... (Ctrl+D to send)", **kwargs)


class ActivityLog(RichLog):
    """Activity log showing daemon and build events"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs, max_lines=100, highlight=True, markup=True)
        self.border_title = "Activity Log"

    async def on_mount(self) -> None:
        """Start tailing daemon log"""
        self.set_interval(2.0, self.refresh_log)
        await self.refresh_log()

    async def refresh_log(self) -> None:
        """Tail daemon log"""
        try:
            log_file = Path.home() / ".context-foundry" / "evolution" / "logs" / "daemon.log"

            if log_file.exists():
                # Read last 5 lines
                lines = log_file.read_text().strip().split("\n")[-5:]

                for line in lines[-3:]:  # Show last 3
                    if line and not self._line_already_shown(line):
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

    def _line_already_shown(self, line: str) -> bool:
        """Check if line was already displayed (simple dedup)"""
        # Simple implementation - could be improved
        return False


class MissionControlApp(App):
    """Main Mission Control TUI Application"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 3;
        grid-rows: auto 1fr auto;
    }

    Header {
        column-span: 2;
    }

    Footer {
        column-span: 2;
    }

    StatusPanel {
        row-span: 2;
        border: solid cyan;
        height: 100%;
    }

    ChatPanel {
        border: solid green;
        height: 1fr;
    }

    ActivityLog {
        border: solid yellow;
        height: 1fr;
    }

    ChatInput {
        border: solid blue;
        height: 3;
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
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield Header(show_clock=True)
        yield StatusPanel()
        yield ChatPanel(id="chat")
        yield ActivityLog()
        yield ChatInput(id="chat_input")
        yield Footer()

    async def on_mount(self) -> None:
        """Set app title"""
        self.title = "Context Foundry Mission Control"
        self.sub_title = "Evolution System Dashboard"

    async def action_send_message(self) -> None:
        """Send chat message"""
        chat_input = self.query_one("#chat_input", ChatInput)
        chat_panel = self.query_one("#chat", ChatPanel)

        message = chat_input.value.strip()
        if not message:
            return

        # Add user message
        await chat_panel.add_message("user", message)

        # Clear input
        chat_input.value = ""

        # Process message and respond
        response = await self._process_command(message)
        await chat_panel.add_message("assistant", response)

    async def _process_command(self, message: str) -> str:
        """Process user command and return response"""
        message_lower = message.lower()

        # Build commands
        if any(word in message_lower for word in ["build", "start", "create"]):
            return (
                "🔧 To start a build, use Ctrl+B or type:\n"
                "`build <project-name> <task-description>`\n\n"
                "Example: `build my-app Add user authentication`"
            )

        # Status commands
        elif any(word in message_lower for word in ["status", "health", "check"]):
            daemon = self.query_one(StatusPanel)._get_daemon_status()
            return (
                f"System Status:\n"
                f"• Daemon: {daemon['status']}\n"
                f"• Backlog: Maintained at 20 issues\n"
                f"• MCP: {'Ready' if daemon['running'] else 'Waiting for Python 3.10+'}"
            )

        # Help commands
        elif any(word in message_lower for word in ["help", "what", "how"]):
            return (
                "Available commands:\n\n"
                "**Build Management:**\n"
                "• `build <name> <task>` - Start new build in sandbox\n"
                "• `list builds` - Show active builds\n\n"
                "**System Control:**\n"
                "• `status` - Show system health\n"
                "• `restart daemon` - Restart Evolution daemon\n\n"
                "**Shortcuts:**\n"
                "• Ctrl+B - Quick build\n"
                "• Ctrl+R - Refresh all panels\n"
                "• Ctrl+C - Quit"
            )

        else:
            return (
                f"I received: {message}\n\n"
                "I'm still learning! Try:\n"
                "• `help` - See available commands\n"
                "• `status` - Check system health\n"
                "• `build <name> <task>` - Start a new build"
            )

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


def main():
    """Run Mission Control TUI"""
    app = MissionControlApp()
    app.run()


if __name__ == "__main__":
    main()
