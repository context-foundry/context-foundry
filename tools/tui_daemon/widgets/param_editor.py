"""
Parameter Editor Widget - Build parameter confirmation dialog

Shows parsed parameters and allows user to edit before submission.
"""

from typing import Callable
from textual.widgets import Static, Input, Button
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen

from ..conversation_parser import ConversationParams


class ParamEditor(ModalScreen):
    """
    Modal dialog for editing build parameters before submission.

    Shows all parsed parameters with editable fields:
    - Task description
    - Working directory
    - GitHub repo (optional)
    - Timeout
    - Mode
    - Max iterations
    """

    def __init__(
        self,
        params: ConversationParams,
        on_confirm: Callable[[ConversationParams], None],
        **kwargs,
    ):
        """
        Initialize the parameter editor.

        Args:
            params: Parsed ConversationParams to edit
            on_confirm: Callback when user confirms (receives edited params)
        """
        super().__init__(**kwargs)
        self.params = params
        self.on_confirm = on_confirm

    def compose(self):
        """Compose the dialog layout"""
        with Vertical(id="param-editor-dialog"):
            yield Static("Confirm Build Parameters", classes="title")

            # Task (read-only)
            yield Static(f"Task: {self.params.task}")

            # Working directory (editable)
            yield Static("Working Directory:")
            yield Input(value=self.params.working_directory, id="working-dir-input")

            # GitHub repo (editable)
            yield Static("GitHub Repo (optional):")
            yield Input(
                value=self.params.github_repo or "",
                id="github-repo-input",
                placeholder="user/repo",
            )

            # Timeout
            yield Static(f"Timeout: {self.params.timeout}s")

            # Mode
            yield Static(f"Mode: {self.params.mode}")

            # Max iterations
            yield Static(f"Max Iterations: {self.params.max_iterations}")

            # Confidence
            confidence_pct = self.params.confidence * 100
            yield Static(f"Parser Confidence: {confidence_pct:.0f}%")

            # Buttons
            with Horizontal(classes="button-row"):
                yield Button("Confirm", variant="primary", id="confirm-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "confirm-btn":
            # Get edited values
            working_dir = self.query_one("#working-dir-input", Input).value
            github_repo = self.query_one("#github-repo-input", Input).value

            # Update params
            self.params.working_directory = working_dir
            self.params.github_repo = github_repo if github_repo else None

            # Call confirmation callback
            self.on_confirm(self.params)

            # Dismiss modal
            self.dismiss()

        elif event.button.id == "cancel-btn":
            # Dismiss without callback
            self.dismiss()
