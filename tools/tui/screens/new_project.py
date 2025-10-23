"""New Project screen - launch autonomous builds"""

import os
from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Input, Button, Label
from textual.binding import Binding

from ..data.provider import TUIDataProvider


class NewProjectScreen(Screen):
    """Screen for launching new Context Foundry builds"""

    CSS = """
    NewProjectScreen {
        align: center middle;
    }

    #form-container {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #form-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        margin-bottom: 1;
        color: $text;
    }

    .field-input {
        margin-bottom: 1;
    }

    #button-container {
        layout: horizontal;
        align: center middle;
        margin-top: 2;
        height: auto;
    }

    Button {
        margin: 0 2;
    }

    #status-message {
        text-align: center;
        margin-top: 1;
        height: 3;
    }

    .success {
        color: $success;
    }

    .error {
        color: $error;
    }

    .info {
        color: $accent;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]

    def __init__(self, provider: TUIDataProvider):
        super().__init__()
        self.provider = provider
        self.task_id = None

    def compose(self) -> ComposeResult:
        """Compose the new project form"""
        yield Header()

        with Container(id="form-container"):
            yield Static("🚀 Launch New Project", id="form-title")

            yield Label("Task Description:", classes="field-label")
            yield Input(
                placeholder="e.g., Build a tic-tac-toe game with React",
                id="task-input",
                classes="field-input"
            )

            yield Label("Working Directory:", classes="field-label")
            yield Input(
                placeholder=str(Path.home() / "homelab"),
                value=str(Path.home() / "homelab"),
                id="directory-input",
                classes="field-input"
            )

            yield Label("Project Name (optional):", classes="field-label")
            yield Input(
                placeholder="e.g., my-game",
                id="project-name-input",
                classes="field-input"
            )

            yield Label("GitHub Repo Name (optional):", classes="field-label")
            yield Input(
                placeholder="e.g., my-game (leave empty to skip deploy)",
                id="repo-input",
                classes="field-input"
            )

            with Horizontal(id="button-container"):
                yield Button("Launch Build", variant="success", id="launch-button")
                yield Button("Cancel", variant="default", id="cancel-button")

            yield Static("", id="status-message")

        yield Footer()

    def on_mount(self):
        """Focus task input when screen mounts"""
        self.query_one("#task-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses"""
        if event.button.id == "launch-button":
            self.run_worker(self.launch_build())
        elif event.button.id == "cancel-button":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted):
        """Handle Enter key in any input field"""
        # If Enter is pressed in any input, launch build
        if event.input.id in ["task-input", "directory-input", "project-name-input", "repo-input"]:
            self.run_worker(self.launch_build())

    async def launch_build(self):
        """Launch autonomous build with form data"""
        try:
            # Get form values
            task = self.query_one("#task-input", Input).value.strip()
            directory = self.query_one("#directory-input", Input).value.strip()
            project_name = self.query_one("#project-name-input", Input).value.strip()
            repo_name = self.query_one("#repo-input", Input).value.strip()

            # Validate
            if not task:
                self.show_message("❌ Task description is required", "error")
                return

            if not directory:
                self.show_message("❌ Working directory is required", "error")
                return

            # Build working directory path
            working_dir = Path(directory).expanduser()

            # If project name provided, append it to directory
            if project_name:
                working_dir = working_dir / project_name

            # Show launching message early
            self.show_message("🚀 Creating directory...", "info")

            # Create directory if it doesn't exist
            try:
                working_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.show_message(f"❌ Cannot create directory: {e}", "error")
                return

            # Show launching message
            self.show_message("🚀 Launching build...", "info")

            # Launch build via provider
            try:
                result = await self.provider.launch_build(
                    task=task,
                    working_directory=str(working_dir),
                    github_repo_name=repo_name if repo_name else None
                )

                if "error" in result:
                    self.show_message(f"❌ Failed: {result['error']}", "error")
                elif "task_id" in result:
                    task_id = result["task_id"]
                    self.show_message(
                        f"✅ Build started!\nTask ID: {task_id}\nDirectory: {working_dir}",
                        "success"
                    )

                    # Wait 2 seconds then close screen
                    self.set_timer(2.0, self.action_cancel)
                else:
                    self.show_message(f"❌ Unknown result: {result}", "error")

            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                self.show_message(f"❌ Error launching: {e}\n{error_detail[:200]}", "error")

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.show_message(f"❌ Unexpected error: {e}\n{error_detail[:200]}", "error")

    def show_message(self, message: str, status_type: str = "info"):
        """Show status message"""
        status_widget = self.query_one("#status-message", Static)
        status_widget.update(message)
        status_widget.remove_class("success", "error", "info")
        status_widget.add_class(status_type)

    def action_cancel(self):
        """Cancel and return to dashboard"""
        self.app.pop_screen()
