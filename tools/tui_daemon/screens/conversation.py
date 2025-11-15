"""
Conversation Screen - Natural language build submission

Chat-style interface for submitting builds using natural language.
Includes parser, parameter confirmation, and recent builds sidebar.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Button, RichLog
from textual.containers import Vertical, Horizontal
from rich.text import Text

from ..manager import TUIManager
from ..conversation_parser import ConversationParser, ConversationParams
from ..widgets.param_editor import ParamEditor


class ConversationScreen(Screen):
    """
    Chat-style screen for natural language build submission.

    Features:
    - Chat history display
    - Input field with send button
    - Recent builds sidebar (templates)
    - Parameter confirmation before submission
    """

    BINDINGS = [
        ("escape", "back_to_dashboard", "Back to Dashboard"),
        ("ctrl+n", "new_conversation", "Clear History"),
    ]

    def __init__(self, manager: TUIManager, **kwargs):
        """
        Initialize the conversation screen.

        Args:
            manager: TUIManager instance
        """
        super().__init__(**kwargs)
        self.manager = manager
        self.parser = ConversationParser()
        self._chat_history: RichLog = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout"""
        yield Static("🤖 Conversational Build Launcher", classes="header")

        with Horizontal():
            # Main chat area
            with Vertical(id="chat-area"):
                # Chat history
                self._chat_history = RichLog(highlight=True, markup=True, wrap=True)
                yield self._chat_history

                # Input area
                with Horizontal(id="input-area"):
                    yield Input(
                        placeholder="Describe your build (e.g., 'build a todo app with react in ~/projects/todo')",
                        id="chat-input",
                    )
                    yield Button("Send", variant="primary", id="send-btn")

            # Sidebar with examples
            with Vertical(id="sidebar"):
                yield Static("📋 Examples", classes="sidebar-title")
                yield Static("• build a todo app with react")
                yield Static("• create a fastapi backend in ~/api")
                yield Static("• make a game in ~/homelab/snake")
                yield Static("")
                yield Static("Tips:")
                yield Static("• Specify directory with 'in ~/path'")
                yield Static("• Set timeout with 'timeout 30m'")
                yield Static("• Add iterations with 'iterations 3'")

    def on_mount(self) -> None:
        """Handle screen mount"""
        # Welcome message
        self._add_system_message(
            "Welcome! Describe the build you want to create in natural language."
        )
        self._add_system_message(
            "I'll parse your request and confirm the parameters before starting."
        )

        # Focus input
        self.query_one("#chat-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "send-btn":
            self._handle_send()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)"""
        if event.input.id == "chat-input":
            self._handle_send()

    def _handle_send(self) -> None:
        """Handle sending a message"""
        chat_input = self.query_one("#chat-input", Input)
        user_message = chat_input.value.strip()

        if not user_message:
            return

        # Display user message
        self._add_user_message(user_message)

        # Clear input
        chat_input.value = ""

        # Parse the message
        params = self.parser.parse(user_message)

        # Show confirmation dialog
        self._show_param_editor(params)

    def _show_param_editor(self, params: ConversationParams) -> None:
        """
        Show parameter editor dialog.

        Args:
            params: Parsed parameters to edit
        """

        def on_confirm(edited_params: ConversationParams):
            """Callback when user confirms parameters"""
            self._submit_build(edited_params)

        # Push modal screen
        self.app.push_screen(ParamEditor(params, on_confirm))

    def _submit_build(self, params: ConversationParams) -> None:
        """
        Submit the build with confirmed parameters.

        Args:
            params: Confirmed build parameters
        """
        # Convert to job params dict
        job_params = {
            "task": params.task,
            "working_directory": params.working_directory,
            "mode": params.mode,
            "max_iterations": params.max_iterations,
            "timeout": params.timeout,
        }

        if params.github_repo:
            job_params["github_repo"] = params.github_repo

        # Submit via manager
        job = self.manager.submit_build(job_params)

        if job:
            self._add_system_message(f"✅ Build submitted! Job ID: {job.job_id[:8]}")
            self._add_system_message("Navigate to Dashboard to monitor progress (Esc)")
        else:
            self._add_system_message(
                "❌ Failed to submit build. Is the daemon running?"
            )

    def _add_user_message(self, message: str) -> None:
        """Add user message to chat history"""
        text = Text()
        text.append("You: ", style="bold cyan")
        text.append(message)
        self._chat_history.write(text)

    def _add_system_message(self, message: str) -> None:
        """Add system message to chat history"""
        text = Text()
        text.append("System: ", style="bold green")
        text.append(message)
        self._chat_history.write(text)

    def action_back_to_dashboard(self) -> None:
        """Navigate back to dashboard"""
        self.app.pop_screen()

    def action_new_conversation(self) -> None:
        """Clear chat history"""
        self._chat_history.clear()
        self._add_system_message("Chat history cleared. Start a new conversation!")
