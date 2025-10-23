"""Token usage gauge widget"""

from textual.widgets import Static
from textual.reactive import reactive


class TokenGaugeWidget(Static):
    """Display token usage gauge"""

    tokens_used: reactive[int] = reactive(0, init=False)
    tokens_total: reactive[int] = reactive(200000, init=False)

    def watch_tokens_used(self, tokens: int):
        """Update gauge display"""
        self._update_display()

    def watch_tokens_total(self, total: int):
        """Update gauge when total changes"""
        self._update_display()

    def _update_display(self):
        """Render the token gauge"""
        total = self.tokens_total if self.tokens_total > 0 else 200000
        used = self.tokens_used

        # Calculate percentage
        percentage = (used / total * 100) if total > 0 else 0

        # Create progress bar
        bar_width = 40
        filled = int(bar_width * percentage / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Color based on usage
        if percentage < 50:
            color = "green"
        elif percentage < 80:
            color = "yellow"
        else:
            color = "red"

        # Format display
        display = f"[bold]Tokens:[/bold] {used:,} / {total:,} ({percentage:.1f}%)\n"
        display += f"[{color}]{bar}[/{color}]"

        self.update(display)
