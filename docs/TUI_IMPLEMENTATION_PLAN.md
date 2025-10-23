# Context Foundry TUI Monitor - Implementation Plan

## Executive Summary

Create a standalone Terminal User Interface (TUI) using Textual that provides real-time monitoring of Context Foundry builds without requiring Claude Code to be running. The TUI will integrate with the existing MCP server and metrics database to display build status, agent activity, token usage, and comprehensive statistics.

## Goals

1. **Standalone Operation**: Run independently without starting Claude Code
2. **Real-Time Updates**: Display live build progress with 1-2 second refresh
3. **Comprehensive Metrics**: Show all available data (phases, agents, tokens, costs, patterns)
4. **Modern UI/UX**: Keyboard navigation, responsive layout, vim-like keybindings
5. **Integration**: Seamlessly integrate with existing Context Foundry infrastructure
6. **No Breaking Changes**: Add new functionality without modifying existing code

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Textual TUI Application                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Dashboard   │  │    Build     │  │   Metrics    │         │
│  │   Screen     │  │   Details    │  │   Screen     │         │
│  │              │  │   Screen     │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         │                  │                  │                 │
│         └──────────────────┴──────────────────┘                 │
│                            │                                     │
│                   ┌────────▼────────┐                           │
│                   │  Screen Manager │                           │
│                   │  (Navigation)   │                           │
│                   └────────┬────────┘                           │
└────────────────────────────┼──────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                        │
┌────────▼──────────┐                  ┌─────────▼────────┐
│  Data Provider    │                  │  Update Manager  │
│                   │                  │                  │
│ • get_builds()    │◄─────────────────┤ • poll_updates() │
│ • get_metrics()   │                  │ • watch_files()  │
│ • get_phases()    │                  │ • notify()       │
└────────┬──────────┘                  └──────────────────┘
         │
         ├──────────────────┬─────────────────────┐
         │                  │                     │
┌────────▼─────────┐  ┌─────▼──────┐  ┌─────────▼────────┐
│  MCP Interface   │  │  Metrics   │  │   File Watcher   │
│                  │  │  Database  │  │                  │
│ • list_tasks()   │  │            │  │ • current-phase  │
│ • get_status()   │  │ • tasks    │  │ • build-log.md   │
│ • autonomous()   │  │ • metrics  │  │ • feedback/*.json│
└──────────────────┘  └────────────┘  └──────────────────┘
```

## File Structure

```
context-foundry/
├── tools/
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py                    # Main TUI application
│   │   ├── screens/
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py          # Main dashboard screen
│   │   │   ├── build_detail.py       # Single build detail view
│   │   │   ├── metrics.py            # Metrics and analytics screen
│   │   │   ├── agents.py             # Agent activity screen
│   │   │   └── help.py               # Help/keybindings screen
│   │   ├── widgets/
│   │   │   ├── __init__.py
│   │   │   ├── build_table.py        # Table of active builds
│   │   │   ├── phase_progress.py     # Phase progress bar
│   │   │   ├── token_gauge.py        # Token usage gauge
│   │   │   ├── agent_activity.py     # Agent status widget
│   │   │   ├── metrics_chart.py      # Simple ASCII charts
│   │   │   └── log_viewer.py         # Scrollable log viewer
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py           # Data provider layer
│   │   │   ├── models.py             # Data models/types
│   │   │   └── cache.py              # Local cache for performance
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── formatters.py         # Format numbers, dates, etc.
│   │   │   └── colors.py             # Color scheme definitions
│   │   └── config.py                 # TUI configuration
│   ├── tui_monitor.py                # CLI entry point
│   └── mcp_server.py                 # (existing)
├── docs/
│   └── TUI_IMPLEMENTATION_PLAN.md    # This file
└── requirements-tui.txt              # TUI dependencies
```

## Component Specifications

### 1. Main Application (`tools/tui/app.py`)

**Purpose**: Core Textual app with screen management and global state.

**Key Responsibilities**:
- Initialize Textual app
- Manage screen navigation
- Handle global keybindings
- Coordinate data updates
- Manage refresh timers

**Code Template**:

```python
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer
from .screens.dashboard import DashboardScreen
from .screens.build_detail import BuildDetailScreen
from .screens.metrics import MetricsScreen
from .screens.help import HelpScreen
from .data.provider import TUIDataProvider
from .config import TUIConfig

class ContextFoundryTUI(App):
    """Context Foundry TUI Monitor Application."""

    CSS_PATH = "app.css"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("d", "show_dashboard", "Dashboard", show=True),
        Binding("m", "show_metrics", "Metrics", show=True),
        Binding("h", "show_help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("/", "search", "Search", show=False),
    ]

    def __init__(self, config: TUIConfig = None):
        super().__init__()
        self.config = config or TUIConfig.load()
        self.data_provider = TUIDataProvider(self.config)
        self.title = "Context Foundry Monitor"
        self.sub_title = f"v{self.config.version}"

    def on_mount(self) -> None:
        """Initialize app when mounted."""
        # Start background data refresh
        self.set_interval(
            self.config.refresh_interval,
            self.refresh_data
        )

        # Show dashboard initially
        self.push_screen(DashboardScreen(self.data_provider))

    async def refresh_data(self) -> None:
        """Background task to refresh data."""
        await self.data_provider.refresh()

        # Notify current screen to update
        if self.screen:
            self.screen.post_message(self.DataRefreshed())

    def action_show_dashboard(self) -> None:
        """Switch to dashboard screen."""
        self.switch_screen(DashboardScreen(self.data_provider))

    def action_show_metrics(self) -> None:
        """Switch to metrics screen."""
        self.switch_screen(MetricsScreen(self.data_provider))

    def action_show_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    async def action_refresh(self) -> None:
        """Manually refresh data."""
        await self.refresh_data()
        self.notify("Data refreshed", severity="information")

    class DataRefreshed(Message):
        """Message sent when data is refreshed."""
        pass
```

### 2. Dashboard Screen (`tools/tui/screens/dashboard.py`)

**Purpose**: Main screen showing overview of all builds.

**Layout**:
```
┌────────────────────────────────────────────────────────────────┐
│ Context Foundry Monitor                              [23:45:12]│
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Active Builds (3)                                             │
│  ┌────────────────────────────────────────────────────────────┐
│  │ ID       │ Project      │ Phase      │ Progress │ Status  ││
│  ├──────────┼──────────────┼────────────┼──────────┼─────────┤│
│  │ abc-123  │ weather-app  │ Builder    │ 45%      │ Running ││
│  │ def-456  │ chat-bot     │ Test (2/3) │ 78%      │ Healing ││
│  │ ghi-789  │ api-server   │ Deploy     │ 95%      │ Running ││
│  └────────────────────────────────────────────────────────────┘
│                                                                │
│  System Stats                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐│
│  │ Total Builds: 24 │  │ Success Rate: 89%│  │ Avg Time: 12m││
│  └──────────────────┘  └──────────────────┘  └──────────────┘│
│                                                                │
│  Recent Activity                                               │
│  • 23:44:58 - weather-app: Builder phase started              │
│  • 23:42:15 - chat-bot: Test iteration 2 completed            │
│  • 23:40:03 - api-server: Deploying to GitHub                 │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ [d] Dashboard  [m] Metrics  [h] Help  [r] Refresh  [q] Quit   │
└────────────────────────────────────────────────────────────────┘
```

**Code Template**:

```python
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, DataTable, Label
from textual.reactive import reactive
from ..widgets.build_table import BuildTable
from ..widgets.metrics_chart import SystemStatsWidget
from ..data.provider import TUIDataProvider

class DashboardScreen(Screen):
    """Main dashboard showing all active builds."""

    BINDINGS = [
        ("enter", "view_build", "View Details"),
        ("n", "new_build", "New Build"),
    ]

    active_builds = reactive([])
    system_stats = reactive({})
    recent_activity = reactive([])

    def __init__(self, data_provider: TUIDataProvider):
        super().__init__()
        self.data_provider = data_provider

    def compose(self) -> ComposeResult:
        """Compose dashboard layout."""
        yield Container(
            Vertical(
                Static("Active Builds", classes="section-title"),
                BuildTable(id="builds-table"),
                id="builds-section"
            ),
            Vertical(
                Static("System Stats", classes="section-title"),
                SystemStatsWidget(id="stats-widget"),
                id="stats-section"
            ),
            Vertical(
                Static("Recent Activity", classes="section-title"),
                Static(id="activity-log", classes="log-viewer"),
                id="activity-section"
            ),
            id="dashboard-container"
        )

    async def on_mount(self) -> None:
        """Load initial data when screen mounts."""
        await self.refresh_all()

    async def refresh_all(self) -> None:
        """Refresh all dashboard data."""
        self.active_builds = await self.data_provider.get_active_builds()
        self.system_stats = await self.data_provider.get_system_stats()
        self.recent_activity = await self.data_provider.get_recent_activity(limit=10)

        # Update widgets
        self.query_one("#builds-table", BuildTable).update_data(self.active_builds)
        self.query_one("#stats-widget", SystemStatsWidget).update_stats(self.system_stats)
        self.query_one("#activity-log", Static).update(
            "\n".join(self.format_activity(a) for a in self.recent_activity)
        )

    def format_activity(self, activity: dict) -> str:
        """Format activity log entry."""
        timestamp = activity.get("timestamp", "")
        project = activity.get("project", "unknown")
        message = activity.get("message", "")
        return f"• {timestamp} - {project}: {message}"

    async def action_view_build(self) -> None:
        """View selected build details."""
        table = self.query_one("#builds-table", BuildTable)
        selected_task_id = table.get_selected_task_id()

        if selected_task_id:
            from .build_detail import BuildDetailScreen
            self.app.push_screen(
                BuildDetailScreen(self.data_provider, selected_task_id)
            )

    async def action_new_build(self) -> None:
        """Start a new build (future feature)."""
        self.app.notify("New build feature coming soon!", severity="information")
```

### 3. Build Detail Screen (`tools/tui/screens/build_detail.py`)

**Purpose**: Detailed view of a single build with real-time updates.

**Layout**:
```
┌────────────────────────────────────────────────────────────────┐
│ Build: weather-app (abc-123)                         [23:45:12]│
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Status: Running  │  Phase: Builder (3/7)  │  Iteration: 1/3  │
│  Elapsed: 8m 32s  │  Est. Remaining: 4m 15s                    │
│                                                                │
│  Phase Progress                                                │
│  ┌────────────────────────────────────────────────────────────┐
│  │ Scout     ████████████████████████ 100% ✓                 ││
│  │ Architect ████████████████████████ 100% ✓                 ││
│  │ Builder   ████████████░░░░░░░░░░░  45% →                  ││
│  │ Test      ░░░░░░░░░░░░░░░░░░░░░░░░   0%                   ││
│  │ Deploy    ░░░░░░░░░░░░░░░░░░░░░░░░   0%                   ││
│  └────────────────────────────────────────────────────────────┘
│                                                                │
│  Current Agent: Builder                                        │
│  Working on: Task 5/12 - Create weather API integration       │
│                                                                │
│  Token Usage                    Model Info                     │
│  ┌────────────────────┐        ┌────────────────────┐        │
│  │ 45,234 / 200,000   │        │ claude-sonnet-4    │        │
│  │ 22.6% ███░░░░░░░░  │        │ Anthropic          │        │
│  │ Est. Cost: $0.82   │        │ Context: 200K      │        │
│  └────────────────────┘        └────────────────────┘        │
│                                                                │
│  Recent Logs (live)                                            │
│  ┌────────────────────────────────────────────────────────────┐
│  │ [23:45:10] Builder: Creating src/services/weatherApi.js   ││
│  │ [23:45:08] Builder: Implementing error handling           ││
│  │ [23:45:05] Builder: Adding API key configuration          ││
│  │ [23:45:02] Builder: Task 5 started                        ││
│  └────────────────────────────────────────────────────────────┘
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ [←] Back  [l] Logs  [a] Agents  [p] Patterns  [q] Quit        │
└────────────────────────────────────────────────────────────────┘
```

**Code Template**:

```python
from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.widgets import Static, ProgressBar, Label
from textual.reactive import reactive
from ..widgets.phase_progress import PhaseProgressWidget
from ..widgets.token_gauge import TokenGaugeWidget
from ..widgets.log_viewer import LogViewerWidget
from ..data.provider import TUIDataProvider
from ..data.models import BuildStatus

class BuildDetailScreen(Screen):
    """Detailed view of a single build."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("l", "view_logs", "View Logs"),
        ("a", "view_agents", "View Agents"),
        ("p", "view_patterns", "View Patterns"),
    ]

    build_status = reactive(None)

    def __init__(self, data_provider: TUIDataProvider, task_id: str):
        super().__init__()
        self.data_provider = data_provider
        self.task_id = task_id

    def compose(self) -> ComposeResult:
        """Compose build detail layout."""
        yield Container(
            # Header info
            Horizontal(
                Static(id="status-indicator"),
                Static(id="phase-info"),
                Static(id="iteration-info"),
                classes="info-bar"
            ),
            Horizontal(
                Static(id="elapsed-time"),
                Static(id="estimated-remaining"),
                classes="time-bar"
            ),

            # Phase progress
            Vertical(
                Static("Phase Progress", classes="section-title"),
                PhaseProgressWidget(id="phase-progress"),
            ),

            # Current agent
            Vertical(
                Static("Current Agent", classes="section-title"),
                Static(id="agent-status"),
                Static(id="current-task"),
            ),

            # Metrics grid
            Grid(
                # Token usage
                Vertical(
                    Static("Token Usage", classes="subsection-title"),
                    TokenGaugeWidget(id="token-gauge"),
                ),
                # Model info
                Vertical(
                    Static("Model Info", classes="subsection-title"),
                    Static(id="model-info"),
                ),
                classes="metrics-grid"
            ),

            # Live logs
            Vertical(
                Static("Recent Logs (live)", classes="section-title"),
                LogViewerWidget(id="log-viewer"),
            ),

            id="build-detail-container"
        )

    async def on_mount(self) -> None:
        """Load build data when screen mounts."""
        # Set up auto-refresh
        self.set_interval(2.0, self.refresh_build)
        await self.refresh_build()

    async def refresh_build(self) -> None:
        """Refresh build status and update all widgets."""
        status = await self.data_provider.get_build_status(self.task_id)
        self.build_status = status

        if not status:
            self.notify(f"Build {self.task_id} not found", severity="error")
            self.app.pop_screen()
            return

        # Update all widgets with new data
        self._update_header(status)
        self._update_phase_progress(status)
        self._update_agent_info(status)
        self._update_metrics(status)
        self._update_logs(status)

    def _update_header(self, status: BuildStatus) -> None:
        """Update header information."""
        self.query_one("#status-indicator", Static).update(
            f"Status: {self._format_status(status.status)}"
        )
        self.query_one("#phase-info", Static).update(
            f"Phase: {status.current_phase} ({status.phase_number})"
        )
        self.query_one("#iteration-info", Static).update(
            f"Iteration: {status.test_iteration}/{status.max_iterations}"
        )
        self.query_one("#elapsed-time", Static).update(
            f"Elapsed: {self._format_duration(status.elapsed_seconds)}"
        )
        self.query_one("#estimated-remaining", Static).update(
            f"Est. Remaining: {self._format_duration(status.estimated_remaining)}"
        )

    def _update_phase_progress(self, status: BuildStatus) -> None:
        """Update phase progress widget."""
        widget = self.query_one("#phase-progress", PhaseProgressWidget)
        widget.update_phases(status.phases_completed, status.current_phase)

    def _update_agent_info(self, status: BuildStatus) -> None:
        """Update current agent information."""
        agent_name = status.current_phase  # Phase name = agent type
        self.query_one("#agent-status", Static).update(
            f"Working on: {agent_name}"
        )
        self.query_one("#current-task", Static).update(
            f"Task: {status.progress_detail}"
        )

    def _update_metrics(self, status: BuildStatus) -> None:
        """Update metrics widgets."""
        # Token gauge
        token_widget = self.query_one("#token-gauge", TokenGaugeWidget)
        token_widget.update_usage(
            status.tokens_used,
            status.token_budget,
            status.estimated_cost
        )

        # Model info
        model_info = f"[b]{status.model_name}[/b]\n"
        model_info += f"Provider: {status.provider}\n"
        model_info += f"Context: {status.context_window:,} tokens"
        self.query_one("#model-info", Static).update(model_info)

    def _update_logs(self, status: BuildStatus) -> None:
        """Update log viewer with recent logs."""
        log_widget = self.query_one("#log-viewer", LogViewerWidget)
        log_widget.add_logs(status.recent_logs)

    def _format_status(self, status: str) -> str:
        """Format status with color."""
        status_colors = {
            "running": "[green]Running[/green]",
            "completed": "[bold green]Completed[/bold green]",
            "failed": "[red]Failed[/red]",
            "healing": "[yellow]Healing[/yellow]",
        }
        return status_colors.get(status.lower(), status)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"

    def action_back(self) -> None:
        """Go back to dashboard."""
        self.app.pop_screen()

    def action_view_logs(self) -> None:
        """Open full log viewer (future)."""
        self.notify("Full log viewer coming soon!", severity="information")

    def action_view_agents(self) -> None:
        """View agent performance details (future)."""
        self.notify("Agent details coming soon!", severity="information")

    def action_view_patterns(self) -> None:
        """View patterns being applied (future)."""
        self.notify("Pattern viewer coming soon!", severity="information")
```

### 4. Data Provider (`tools/tui/data/provider.py`)

**Purpose**: Abstraction layer for data access, combining MCP, database, and file sources.

**Code Template**:

```python
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from .models import BuildStatus, SystemStats, AgentMetrics
from .cache import DataCache
from ..config import TUIConfig

# Import existing Context Foundry components
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from tools.livestream.mcp_client import MCPClient
from tools.livestream.metrics_db import MetricsDatabase

class TUIDataProvider:
    """
    Data provider for TUI application.

    Combines data from multiple sources:
    - MCP Server (live task status)
    - SQLite Metrics DB (historical metrics)
    - File system (.context-foundry/current-phase.json)
    """

    def __init__(self, config: TUIConfig):
        self.config = config
        self.mcp_client = MCPClient()
        self.metrics_db = MetricsDatabase()
        self.cache = DataCache(ttl=config.cache_ttl)

    async def refresh(self) -> None:
        """Refresh all cached data."""
        self.cache.invalidate_all()

    async def get_active_builds(self) -> List[Dict]:
        """
        Get all active builds.

        Returns list of build summaries with:
        - task_id
        - project_name
        - current_phase
        - progress_percentage
        - status
        - elapsed_time
        """
        cache_key = "active_builds"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Get from MCP
        mcp_tasks = self.mcp_client.list_active_tasks()

        builds = []
        for task in mcp_tasks:
            task_id = task.get("task_id")

            # Get additional data from database
            db_task = self.metrics_db.get_task(task_id)

            # Get current phase from file if available
            phase_info = self._read_phase_file(task.get("cwd"))

            builds.append({
                "task_id": task_id,
                "project_name": task.get("project_name", db_task.get("project_name", "Unknown")),
                "current_phase": phase_info.get("current_phase", task.get("status", "Unknown")),
                "phase_number": phase_info.get("phase_number", "?/7"),
                "progress_percentage": self._calculate_progress(phase_info),
                "status": task.get("status", "running"),
                "elapsed_seconds": task.get("elapsed_seconds", 0),
                "test_iteration": phase_info.get("test_iteration", 0),
            })

        self.cache.set(cache_key, builds)
        return builds

    async def get_build_status(self, task_id: str) -> Optional[BuildStatus]:
        """
        Get detailed status for a specific build.

        Returns BuildStatus object with all available information.
        """
        cache_key = f"build_status_{task_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Get from MCP
        mcp_status = self.mcp_client.get_task_status(task_id)
        if not mcp_status:
            return None

        # Get from database
        db_task = self.metrics_db.get_task(task_id)
        db_metrics = self.metrics_db.get_task_metrics(task_id)

        # Get from phase file
        cwd = mcp_status.get("cwd") or db_task.get("working_directory")
        phase_info = self._read_phase_file(cwd)

        # Get logs
        recent_logs = self._read_recent_logs(cwd, limit=20)

        # Combine all sources into BuildStatus
        status = BuildStatus(
            task_id=task_id,
            project_name=mcp_status.get("project_name") or db_task.get("project_name", "Unknown"),
            status=mcp_status.get("status", "running"),
            current_phase=phase_info.get("current_phase", "Unknown"),
            phase_number=phase_info.get("phase_number", "?/7"),
            phases_completed=phase_info.get("phases_completed", []),
            progress_detail=phase_info.get("progress_detail", ""),
            test_iteration=phase_info.get("test_iteration", 0),
            max_iterations=3,  # From config
            elapsed_seconds=mcp_status.get("elapsed_seconds", 0),
            estimated_remaining=self._estimate_remaining(phase_info, mcp_status),
            tokens_used=self._get_token_usage(db_metrics),
            token_budget=200000,  # From config or detect from model
            estimated_cost=self._calculate_cost(db_metrics),
            model_name=self._get_model_name(cwd),
            provider=self._get_provider(cwd),
            context_window=200000,  # From model config
            recent_logs=recent_logs,
            start_time=db_task.get("start_time"),
            working_directory=cwd,
        )

        self.cache.set(cache_key, status)
        return status

    async def get_system_stats(self) -> SystemStats:
        """
        Get overall system statistics.

        Returns SystemStats with:
        - total_builds
        - success_rate
        - average_duration
        - total_cost
        - active_count
        """
        cache_key = "system_stats"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Query database for aggregated stats
        all_tasks = self.metrics_db.get_all_tasks()

        total_builds = len(all_tasks)
        completed = [t for t in all_tasks if t.get("status") == "completed"]
        failed = [t for t in all_tasks if t.get("status") == "failed"]

        success_rate = (len(completed) / total_builds * 100) if total_builds > 0 else 0

        # Calculate average duration for completed builds
        durations = [t.get("duration_seconds", 0) for t in completed if t.get("duration_seconds")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Get active count
        active_count = len([t for t in all_tasks if t.get("status") == "running"])

        stats = SystemStats(
            total_builds=total_builds,
            success_rate=success_rate,
            average_duration_seconds=avg_duration,
            total_cost=0.0,  # TODO: Calculate from metrics
            active_builds=active_count,
            completed_builds=len(completed),
            failed_builds=len(failed),
        )

        self.cache.set(cache_key, stats)
        return stats

    async def get_recent_activity(self, limit: int = 10) -> List[Dict]:
        """Get recent activity log entries."""
        cache_key = f"recent_activity_{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Get from database - query most recent events
        # This would require adding an events table to the database
        # For now, return mock data or parse from logs
        activity = []

        # Get all tasks and their latest updates
        tasks = self.metrics_db.get_all_tasks()

        # Sort by last update time
        sorted_tasks = sorted(
            tasks,
            key=lambda t: t.get("last_updated", ""),
            reverse=True
        )[:limit]

        for task in sorted_tasks:
            activity.append({
                "timestamp": task.get("last_updated", ""),
                "project": task.get("project_name", "Unknown"),
                "message": self._format_task_event(task),
            })

        self.cache.set(cache_key, activity)
        return activity

    async def get_agent_metrics(self, task_id: str) -> List[AgentMetrics]:
        """Get agent performance metrics for a task."""
        return self.metrics_db.get_agent_performance(task_id)

    async def get_pattern_effectiveness(self, task_id: str) -> List[Dict]:
        """Get pattern effectiveness data for a task."""
        return self.metrics_db.get_pattern_effectiveness(task_id)

    # Private helper methods

    def _read_phase_file(self, working_dir: Optional[str]) -> Dict:
        """Read current-phase.json from working directory."""
        if not working_dir:
            return {}

        phase_file = Path(working_dir) / ".context-foundry" / "current-phase.json"
        if not phase_file.exists():
            return {}

        try:
            with open(phase_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _read_recent_logs(self, working_dir: Optional[str], limit: int = 20) -> List[str]:
        """Read recent log entries from build-log.md."""
        if not working_dir:
            return []

        log_file = Path(working_dir) / ".context-foundry" / "build-log.md"
        if not log_file.exists():
            return []

        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()

            # Return last N lines
            return [line.strip() for line in lines[-limit:] if line.strip()]
        except FileNotFoundError:
            return []

    def _calculate_progress(self, phase_info: Dict) -> float:
        """Calculate overall progress percentage from phase info."""
        if not phase_info:
            return 0.0

        # Parse phase number like "3/7"
        phase_num_str = phase_info.get("phase_number", "0/7")
        try:
            current, total = map(int, phase_num_str.split("/"))
            return (current / total) * 100
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _estimate_remaining(self, phase_info: Dict, mcp_status: Dict) -> float:
        """Estimate remaining time in seconds."""
        # Simple estimation based on average phase time
        # More sophisticated: use historical data from database
        elapsed = mcp_status.get("elapsed_seconds", 0)
        progress = self._calculate_progress(phase_info)

        if progress > 0:
            total_estimate = (elapsed / progress) * 100
            return total_estimate - elapsed

        return 0.0

    def _get_token_usage(self, metrics: List[Dict]) -> int:
        """Get total token usage from metrics."""
        if not metrics:
            return 0

        # Sum token_usage from all metrics
        return sum(m.get("token_usage", 0) for m in metrics)

    def _calculate_cost(self, metrics: List[Dict]) -> float:
        """Calculate estimated cost from metrics."""
        # TODO: Implement cost calculation based on model pricing
        return 0.0

    def _get_model_name(self, working_dir: Optional[str]) -> str:
        """Get model name from config or phase file."""
        # TODO: Read from project config or environment
        return "claude-sonnet-4"

    def _get_provider(self, working_dir: Optional[str]) -> str:
        """Get provider name."""
        return "Anthropic"

    def _format_task_event(self, task: Dict) -> str:
        """Format task data into event message."""
        status = task.get("status", "unknown")
        phase = task.get("current_phase", "unknown")

        if status == "completed":
            return f"{phase} phase completed"
        elif status == "failed":
            return f"{phase} phase failed"
        else:
            return f"{phase} phase in progress"
```

### 5. Data Models (`tools/tui/data/models.py`)

**Purpose**: Type-safe data models for the TUI.

```python
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class BuildStatus:
    """Complete status of a build."""
    task_id: str
    project_name: str
    status: str  # running, completed, failed, healing
    current_phase: str
    phase_number: str  # e.g., "3/7"
    phases_completed: List[str]
    progress_detail: str
    test_iteration: int
    max_iterations: int
    elapsed_seconds: float
    estimated_remaining: float
    tokens_used: int
    token_budget: int
    estimated_cost: float
    model_name: str
    provider: str
    context_window: int
    recent_logs: List[str]
    start_time: Optional[str] = None
    working_directory: Optional[str] = None

@dataclass
class SystemStats:
    """Overall system statistics."""
    total_builds: int
    success_rate: float
    average_duration_seconds: float
    total_cost: float
    active_builds: int
    completed_builds: int
    failed_builds: int

@dataclass
class AgentMetrics:
    """Metrics for a single agent execution."""
    agent_type: str  # Scout, Architect, Builder, Test
    phase: str
    start_time: str
    end_time: Optional[str]
    duration_seconds: Optional[float]
    success: bool
    issues_found: int
    issues_fixed: int
    files_created: int
    files_modified: int
    tokens_used: int

@dataclass
class PatternInfo:
    """Information about a pattern being applied."""
    pattern_id: str
    pattern_type: str
    issue_description: str
    was_applied: bool
    prevented_issue: bool
```

### 6. Custom Widgets

#### Phase Progress Widget (`tools/tui/widgets/phase_progress.py`)

```python
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

class PhaseProgressWidget(Widget):
    """Widget showing progress bars for each phase."""

    phases_completed = reactive([])
    current_phase = reactive("")

    PHASES = ["Scout", "Architect", "Builder", "Test", "Deploy", "GitHub", "Complete"]

    def render(self) -> Text:
        """Render phase progress bars."""
        output = Text()

        for i, phase in enumerate(self.PHASES):
            # Determine status
            if phase in self.phases_completed:
                status = "✓"
                progress = 100
                style = "green"
            elif phase == self.current_phase:
                status = "→"
                progress = 50  # Simplified - could be more accurate
                style = "yellow"
            else:
                status = ""
                progress = 0
                style = "dim"

            # Create progress bar
            bar_width = 24
            filled = int((progress / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)

            # Format line
            line = f"{phase:12s} {bar} {progress:3d}% {status}\n"
            output.append(line, style=style)

        return output

    def update_phases(self, completed: List[str], current: str) -> None:
        """Update phase status."""
        self.phases_completed = completed
        self.current_phase = current
```

#### Token Gauge Widget (`tools/tui/widgets/token_gauge.py`)

```python
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

class TokenGaugeWidget(Widget):
    """Widget showing token usage gauge."""

    tokens_used = reactive(0)
    token_budget = reactive(200000)
    estimated_cost = reactive(0.0)

    def render(self) -> Text:
        """Render token usage gauge."""
        output = Text()

        # Calculate percentage
        percentage = (self.tokens_used / self.token_budget * 100) if self.token_budget > 0 else 0

        # Format numbers
        used_str = f"{self.tokens_used:,}"
        budget_str = f"{self.token_budget:,}"

        # Determine color based on usage
        if percentage < 50:
            color = "green"
        elif percentage < 80:
            color = "yellow"
        else:
            color = "red"

        # Create gauge bar
        bar_width = 20
        filled = int((percentage / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Build output
        output.append(f"{used_str} / {budget_str}\n")
        output.append(f"{percentage:.1f}% ", style=color)
        output.append(bar, style=color)
        output.append(f"\nEst. Cost: ${self.estimated_cost:.2f}")

        return output

    def update_usage(self, used: int, budget: int, cost: float) -> None:
        """Update token usage."""
        self.tokens_used = used
        self.token_budget = budget
        self.estimated_cost = cost
```

### 7. Configuration (`tools/tui/config.py`)

```python
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional

@dataclass
class TUIConfig:
    """TUI configuration."""

    # Display settings
    refresh_interval: float = 2.0  # seconds
    cache_ttl: int = 5  # seconds
    max_log_lines: int = 100

    # Theme
    theme: str = "dark"

    # Data sources
    mcp_server_url: Optional[str] = None
    metrics_db_path: Optional[Path] = None

    # Version
    version: str = "1.0.0"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "TUIConfig":
        """Load configuration from file or use defaults."""
        if config_path and config_path.exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
            return cls(**data)

        return cls()

    def save(self, config_path: Path) -> None:
        """Save configuration to file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(self.__dict__, f, indent=2)
```

### 8. CLI Entry Point (`tools/tui_monitor.py`)

```python
#!/usr/bin/env python3
"""
Context Foundry TUI Monitor - CLI Entry Point
"""
import sys
import argparse
from pathlib import Path

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from tools.tui.app import ContextFoundryTUI
from tools.tui.config import TUIConfig

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Context Foundry TUI Monitor - Real-time build monitoring"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
        default=None
    )
    parser.add_argument(
        "--refresh",
        type=float,
        help="Refresh interval in seconds (default: 2.0)",
        default=None
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit"
    )

    args = parser.parse_args()

    if args.version:
        print("Context Foundry TUI Monitor v1.0.0")
        return 0

    # Load configuration
    config = TUIConfig.load(args.config) if args.config else TUIConfig()

    # Override with CLI args
    if args.refresh:
        config.refresh_interval = args.refresh

    # Run the app
    app = ContextFoundryTUI(config)
    app.run()

    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 9. CSS Styling (`tools/tui/app.css`)

```css
/* Context Foundry TUI Styles */

Screen {
    background: $surface;
}

#dashboard-container {
    layout: vertical;
    height: 100%;
}

.section-title {
    color: $accent;
    text-style: bold;
    margin: 1 0;
}

.subsection-title {
    color: $text-muted;
    text-style: bold;
}

.info-bar {
    layout: horizontal;
    height: auto;
    padding: 1;
    background: $panel;
}

.time-bar {
    layout: horizontal;
    height: auto;
    padding: 0 1;
}

.metrics-grid {
    layout: grid;
    grid-size: 2 1;
    grid-gutter: 1;
    padding: 1;
}

.log-viewer {
    height: 10;
    overflow-y: auto;
    border: solid $primary;
    padding: 1;
}

BuildTable {
    height: 1fr;
}

DataTable {
    height: 100%;
}
```

## Dependencies

Create `requirements-tui.txt`:

```txt
# TUI framework
textual>=0.47.0

# Rich for text formatting (textual dependency)
rich>=13.0.0

# Async support
asyncio-mqtt>=0.16.1  # If adding MQTT support for live updates

# Existing Context Foundry dependencies
# (Already in requirements.txt)
```

## Implementation Phases

### Phase 1: Core Infrastructure (Days 1-2)
- [ ] Set up file structure
- [ ] Create data models (`models.py`)
- [ ] Implement basic `TUIDataProvider` with MCP integration
- [ ] Create simple cache system
- [ ] Write configuration system

**Deliverable**: Data layer that can fetch build status from MCP

### Phase 2: Basic Dashboard (Days 3-4)
- [ ] Create main `ContextFoundryTUI` app
- [ ] Implement `DashboardScreen` with basic layout
- [ ] Create `BuildTable` widget
- [ ] Add navigation between screens
- [ ] Implement auto-refresh

**Deliverable**: Working dashboard showing active builds

### Phase 3: Build Detail View (Days 5-6)
- [ ] Implement `BuildDetailScreen`
- [ ] Create custom widgets:
  - [ ] `PhaseProgressWidget`
  - [ ] `TokenGaugeWidget`
  - [ ] `LogViewerWidget`
- [ ] Add real-time updates for single build

**Deliverable**: Detailed build view with live updates

### Phase 4: Metrics & Analytics (Days 7-8)
- [ ] Implement `MetricsScreen`
- [ ] Create visualization widgets (ASCII charts)
- [ ] Add agent performance view
- [ ] Add pattern effectiveness view
- [ ] Integrate with metrics database

**Deliverable**: Comprehensive metrics and analytics screens

### Phase 5: Polish & Features (Days 9-10)
- [ ] Add help screen with keybindings
- [ ] Implement search/filter functionality
- [ ] Add color themes
- [ ] Optimize performance (lazy loading, efficient queries)
- [ ] Add error handling and edge cases
- [ ] Write documentation

**Deliverable**: Production-ready TUI with full feature set

### Phase 6: Testing & Integration (Days 11-12)
- [ ] Unit tests for data provider
- [ ] Integration tests with MCP server
- [ ] Test with real builds
- [ ] Performance testing (memory, CPU usage)
- [ ] Documentation and examples

**Deliverable**: Tested, documented, production-ready TUI

## Testing Strategy

### Unit Tests
```python
# tests/test_data_provider.py
import pytest
from tools.tui.data.provider import TUIDataProvider
from tools.tui.config import TUIConfig

@pytest.mark.asyncio
async def test_get_active_builds():
    provider = TUIDataProvider(TUIConfig())
    builds = await provider.get_active_builds()
    assert isinstance(builds, list)
```

### Integration Tests
- Test with mock MCP server
- Test with real SQLite database
- Test file watching for phase updates

### Manual Testing
- Run alongside real Context Foundry builds
- Test all navigation flows
- Verify real-time updates
- Test with multiple concurrent builds

## Integration Points

### With Existing Context Foundry

1. **MCP Server** (`tools/mcp_server.py`):
   - Import `list_delegations()`, `get_delegation_result()`
   - No modifications needed

2. **Metrics Database** (`tools/livestream/metrics_db.py`):
   - Import `MetricsDatabase` class
   - Use existing schema
   - No modifications needed

3. **MCP Client** (`tools/livestream/mcp_client.py`):
   - Import `MCPClient` class
   - Use existing methods
   - No modifications needed

4. **File System**:
   - Read `.context-foundry/current-phase.json`
   - Read `.context-foundry/build-log.md`
   - Read `.context-foundry/feedback/*.json`
   - All read-only, no modifications

### No Breaking Changes
The TUI is entirely additive:
- New directory `tools/tui/`
- New entry point `tools/tui_monitor.py`
- New dependencies in `requirements-tui.txt`
- Zero modifications to existing files

## Usage Examples

### Basic Usage
```bash
# Start the TUI monitor
python tools/tui_monitor.py

# Or with custom refresh rate
python tools/tui_monitor.py --refresh 1.0

# With custom config
python tools/tui_monitor.py --config ~/.config/cf-tui.json
```

### Installation as Command
```bash
# Add to setup.py
setup(
    ...
    entry_points={
        'console_scripts': [
            'cf-monitor=tools.tui_monitor:main',
        ],
    },
)

# Then use:
cf-monitor
```

### Tmux Integration
```bash
# .tmux.conf
bind-key M split-window -h "cf-monitor"
```

## Future Enhancements

1. **Interactive Build Control**:
   - Start new builds from TUI
   - Cancel running builds
   - Retry failed builds

2. **Advanced Visualizations**:
   - Token usage over time (sparklines)
   - Cost tracking graphs
   - Agent performance comparisons

3. **Notifications**:
   - Desktop notifications on build completion
   - Sound alerts for failures
   - Email/Slack integration

4. **Export & Reporting**:
   - Export metrics to CSV/JSON
   - Generate build reports
   - Session summaries

5. **Multi-Project Support**:
   - Filter by project
   - Compare builds across projects
   - Project-level statistics

6. **Remote Monitoring**:
   - Connect to remote MCP servers
   - Monitor multiple Context Foundry instances
   - SSH tunneling support

## Success Criteria

1. **Functional**:
   - ✓ Displays all active builds with real-time updates
   - ✓ Shows detailed build information including phase, tokens, agents
   - ✓ Updates every 1-2 seconds without performance issues
   - ✓ Runs independently without Claude Code

2. **Performance**:
   - ✓ < 50MB memory usage
   - ✓ < 5% CPU usage during idle
   - ✓ < 100ms UI response time
   - ✓ Handles 10+ concurrent builds

3. **UX**:
   - ✓ Intuitive keyboard navigation
   - ✓ Clear visual hierarchy
   - ✓ Helpful error messages
   - ✓ Responsive layout

4. **Reliability**:
   - ✓ Gracefully handles MCP server disconnections
   - ✓ Recovers from database errors
   - ✓ No crashes on missing data
   - ✓ Proper cleanup on exit

## Conclusion

This implementation plan provides a complete roadmap for building a production-quality TUI for Context Foundry. The design:

- **Integrates seamlessly** with existing Context Foundry infrastructure
- **Requires no modifications** to existing code
- **Provides comprehensive monitoring** of all build aspects
- **Runs independently** without Claude Code
- **Follows modern design patterns** (separation of concerns, reactive UI, async/await)
- **Is maintainable and extensible** with clear architecture

The estimated timeline is **10-12 days** for full implementation, with a working prototype available after Phase 2 (4 days).

---

**Ready to implement?** Start with Phase 1 to build the data foundation, then progressively add UI layers. Each phase delivers working functionality that can be tested and refined.
