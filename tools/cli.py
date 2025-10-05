#!/usr/bin/env python3
"""
Context Foundry CLI
Unified command-line interface for the anti-vibe coding system.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import subprocess
import json

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from tabulate import tabulate
from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv()

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from workflows.autonomous_orchestrator import AutonomousOrchestrator
from tools.analyze_session import SessionAnalyzer
from tools.schedule_overnight import TaskQueue
from foundry.patterns.pattern_manager import PatternLibrary

console = Console()


@click.group()
@click.version_option(version="1.0.0")
def foundry():
    """
    🏭 Context Foundry - The Anti-Vibe Coding System

    Spec-first development through automated context engineering.
    Scout → Architect → Builder. Workflow over vibes.
    """
    # Check for authentication
    use_cli = os.getenv('USE_CLAUDE_CLI', '').lower() in ('true', '1', 'yes')
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY", '').strip())

    if not use_cli and not has_api_key:
        console.print("[yellow]⚠️  Warning: No authentication configured[/yellow]")
        console.print("[dim]Option 1: Set USE_CLAUDE_CLI=true (if you have Claude CLI)[/dim]")
        console.print("[dim]Option 2: Set ANTHROPIC_API_KEY=your_key[/dim]\n")


@foundry.command()
@click.argument('project')
@click.argument('task')
@click.option('--autonomous', is_flag=True, help='Skip human review checkpoints')
@click.option('--livestream', is_flag=True, help='Enable real-time dashboard')
@click.option('--overnight', type=int, metavar='HOURS', help='Schedule overnight run')
@click.option('--use-patterns/--no-patterns', default=True, help='Enable pattern injection')
@click.option('--context-manager/--no-context-manager', default=True, help='Enable smart context management')
@click.option('--project-dir', type=click.Path(), help='Custom project directory')
def build(project, task, autonomous, livestream, overnight, use_patterns, context_manager, project_dir):
    """
    Build a new project with Context Foundry.

    Examples:

    \b
      # Interactive build with reviews
      foundry build my-app "Build user authentication with JWT"

    \b
      # Autonomous build (no reviews)
      foundry build api-server "REST API with PostgreSQL" --autonomous

    \b
      # Overnight session (8 hours)
      foundry build ml-pipeline "Data pipeline with validation" --overnight 8

    \b
      # With livestream dashboard
      foundry build web-app "Todo app with React" --livestream
    """
    console.print(Panel.fit(
        "[bold blue]🏭 Context Foundry[/bold blue]\n"
        f"[cyan]Project:[/cyan] {project}\n"
        f"[cyan]Task:[/cyan] {task}",
        title="Starting Build",
        border_style="blue"
    ))

    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]❌ Error: ANTHROPIC_API_KEY not set[/red]")
        console.print("[yellow]Get your API key from: https://console.anthropic.com/[/yellow]")
        sys.exit(1)

    # Overnight mode
    if overnight:
        console.print(f"\n[yellow]🌙 Scheduling overnight session ({overnight} hours)[/yellow]")

        # Use the overnight_session.sh script
        script_path = Path(__file__).parent / "overnight_session.sh"
        cmd = [str(script_path), project, task, str(overnight)]

        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")
        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    # Livestream mode - start server first
    if livestream:
        console.print("\n[cyan]📡 Starting livestream server...[/cyan]")

        # Start livestream in background
        livestream_script = Path(__file__).parent / "start_livestream.sh"
        subprocess.Popen([str(livestream_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        console.print("[green]✓[/green] Livestream available at: [link]http://localhost:8080[/link]\n")

        # Give server time to start
        import time
        time.sleep(2)

    # Build the project
    console.print("[bold]Starting Scout → Architect → Builder workflow...[/bold]\n")

    try:
        orchestrator = AutonomousOrchestrator(
            project_name=project,
            task_description=task,
            autonomous=autonomous,
            project_dir=Path(project_dir) if project_dir else None,
            use_patterns=use_patterns,
            enable_livestream=livestream
        )

        result = orchestrator.run()

        if result.get("status") == "success":
            console.print("\n[green]✅ Build complete![/green]")
            console.print(f"\n[cyan]📁 Project files:[/cyan] {result.get('project_dir', 'N/A')}")
            console.print(f"[cyan]📊 Session ID:[/cyan] {result.get('session_id', 'N/A')}")
        else:
            console.print(f"\n[yellow]⚠️  Build incomplete: {result.get('status')}[/yellow]")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Build interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        sys.exit(1)


@foundry.command()
@click.argument('task')
@click.option('--autonomous', is_flag=True, help='Skip human review checkpoints')
@click.option('--use-patterns/--no-patterns', default=True, help='Enable pattern injection')
@click.option('--create-pr/--no-pr', default=True, help='Create pull request when complete')
def enhance(task, autonomous, use_patterns, create_pr):
    """
    Enhance an existing project with new features (🚧 Coming Soon).

    Run this command from within an existing git repository.
    Context Foundry will scout your codebase and make targeted changes.

    Examples:

    \b
      # Navigate to your repo
      cd ~/my-project

    \b
      # Add a feature
      foundry enhance "Add JWT authentication to the API"

    \b
      # Autonomous mode
      foundry enhance "Add rate limiting" --autonomous
    """
    console.print("[yellow]🚧 The 'enhance' command is coming soon![/yellow]\n")
    console.print("[dim]This feature will allow you to:")
    console.print("  • Scout existing codebases")
    console.print("  • Plan changes that fit your architecture")
    console.print("  • Make targeted modifications")
    console.print("  • Create pull requests for review\n")
    console.print("[dim]For now, use 'foundry build' to create new projects.")
    console.print("[dim]Track progress: https://github.com/snedea/context-foundry/issues[/dim]")
    sys.exit(0)


@foundry.command()
@click.option('--port', default=None, type=int, help='Port for server (stdio by default)')
@click.option('--config-help', is_flag=True, help='Show Claude Desktop configuration help')
def serve(port, config_help):
    """
    Start Context Foundry as an MCP server for Claude Desktop.

    This mode allows you to use Context Foundry through Claude Desktop
    without API charges - it uses your Claude Pro/Max subscription instead.

    Note: Requires Python 3.10+ and fastmcp package.
    Install with: pip install -r requirements-mcp.txt

    Examples:

    \b
      # Start MCP server (stdio transport for Claude Desktop)
      foundry serve

    \b
      # Show configuration help
      foundry serve --config-help
    """
    # Check Python version
    import sys
    if sys.version_info < (3, 10):
        console.print("[red]❌ MCP mode requires Python 3.10 or higher[/red]")
        console.print(f"[yellow]Current version: Python {sys.version_info.major}.{sys.version_info.minor}[/yellow]\n")
        console.print("[cyan]Options:[/cyan]")
        console.print("  1. Upgrade Python to 3.10+ and run: pip install -r requirements-mcp.txt")
        console.print("  2. Use API mode instead: foundry build <project> <task>\n")
        sys.exit(1)

    if config_help:
        console.print(Panel.fit(
            "[bold cyan]🔌 Claude Desktop MCP Configuration[/bold cyan]\n\n"
            "[yellow]1. Locate your Claude Desktop config file:[/yellow]\n"
            "   • macOS: ~/Library/Application Support/Claude/claude_desktop_config.json\n"
            "   • Windows: %APPDATA%/Claude/claude_desktop_config.json\n\n"
            "[yellow]2. Add Context Foundry to your config:[/yellow]\n"
            '   {\n'
            '     "mcpServers": {\n'
            '       "context-foundry": {\n'
            '         "command": "python",\n'
            '         "args": ["-m", "tools.mcp_server"],\n'
            f'         "cwd": "{Path.cwd()}"\n'
            '       }\n'
            '     }\n'
            '   }\n\n'
            "[yellow]3. Restart Claude Desktop[/yellow]\n\n"
            "[yellow]4. In Claude Desktop, type:[/yellow]\n"
            '   "Use context_foundry_build to create a todo app"\n\n'
            "[green]✅ Now using Context Foundry without API charges![/green]\n\n"
            "[dim]For more help, see: github.com/snedea/context-foundry/docs/MCP_SETUP.md[/dim]",
            title="MCP Server Setup",
            border_style="cyan"
        ))
        return

    console.print(Panel.fit(
        "[bold green]🔌 Starting Context Foundry MCP Server[/bold green]\n\n"
        "[cyan]Mode:[/cyan] Claude Desktop Integration\n"
        "[cyan]Transport:[/cyan] stdio\n"
        "[cyan]Status:[/cyan] Not yet functional (awaiting Claude Desktop sampling support)\n"
        "[cyan]Cost:[/cyan] Will use Claude Pro/Max subscription ($20/month) when available\n\n"
        "[yellow]Available Tools:[/yellow]\n"
        "  • context_foundry_build - Build new projects (returns error about sampling)\n"
        "  • context_foundry_enhance - Enhance existing projects (coming soon)\n"
        "  • context_foundry_status - Get server status\n\n"
        "[dim]Configure Claude Desktop with: foundry serve --config-help[/dim]",
        title="MCP Server",
        border_style="green"
    ))

    console.print("\n[yellow]Starting server...[/yellow]\n")

    # Run the MCP server
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tools.mcp_server"],
            cwd=Path.cwd()
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]❌ Error starting server: {e}[/red]")
        sys.exit(1)


@foundry.command()
@click.option('--session', help='Specific session ID to check')
@click.option('--all', 'show_all', is_flag=True, help='Show all sessions')
@click.option('--watch', is_flag=True, help='Watch mode (auto-refresh)')
def status(session, show_all, watch):
    """
    Check current session status and progress.

    Examples:

    \b
      # Show latest session
      foundry status

    \b
      # Show specific session
      foundry status --session my-app_20251002_210000

    \b
      # Show all sessions
      foundry status --all

    \b
      # Watch mode (refreshes every 5s)
      foundry status --watch
    """
    checkpoints_dir = Path("checkpoints/ralph")

    if not checkpoints_dir.exists():
        console.print("[yellow]No sessions found[/yellow]")
        return

    if show_all:
        _show_all_sessions(checkpoints_dir)
    elif session:
        _show_session_details(checkpoints_dir / session)
    else:
        # Show most recent session
        sessions = sorted(checkpoints_dir.glob("*"), key=os.path.getmtime, reverse=True)
        if sessions:
            if watch:
                import time
                try:
                    while True:
                        console.clear()
                        _show_session_details(sessions[0])
                        console.print("\n[dim]Refreshing every 5s... (Ctrl+C to stop)[/dim]")
                        time.sleep(5)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Watch stopped[/yellow]")
            else:
                _show_session_details(sessions[0])
        else:
            console.print("[yellow]No sessions found[/yellow]")


def _show_all_sessions(checkpoints_dir: Path):
    """Show all sessions in a table."""
    sessions = sorted(checkpoints_dir.glob("*"), key=os.path.getmtime, reverse=True)

    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    table = Table(title="Context Foundry Sessions", show_header=True, header_style="bold cyan")
    table.add_column("Session ID", style="cyan")
    table.add_column("Project", style="green")
    table.add_column("Phase", style="yellow")
    table.add_column("Progress", style="blue")
    table.add_column("Started", style="dim")

    for session_dir in sessions[:10]:  # Show last 10
        state_file = session_dir / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)

            session_id = session_dir.name
            project = state.get("project_name", "Unknown")
            phase = state.get("current_phase", "unknown")
            iterations = state.get("iterations", 0)
            start_time = state.get("start_time", "Unknown")

            # Parse start time
            try:
                dt = datetime.fromisoformat(start_time)
                start_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                start_str = "Unknown"

            table.add_row(session_id, project, phase, f"{iterations} iterations", start_str)

    console.print(table)


def _show_session_details(session_dir: Path):
    """Show detailed session information."""
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir.name}[/red]")
        return

    state_file = session_dir / "state.json"
    progress_file = session_dir / "progress.json"

    # Load state
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
    else:
        console.print("[red]No state file found[/red]")
        return

    # Load progress
    progress = {}
    if progress_file.exists():
        with open(progress_file) as f:
            progress = json.load(f)

    # Display
    console.print(Panel.fit(
        f"[bold cyan]Session:[/bold cyan] {session_dir.name}\n"
        f"[cyan]Project:[/cyan] {state.get('project_name', 'Unknown')}\n"
        f"[cyan]Task:[/cyan] {state.get('task_description', 'Unknown')}\n"
        f"[cyan]Phase:[/cyan] {state.get('current_phase', 'unknown')}\n"
        f"[cyan]Iterations:[/cyan] {state.get('iterations', 0)}",
        title="Session Status",
        border_style="cyan"
    ))

    # Progress
    completed = progress.get("completed", [])
    remaining = progress.get("remaining", [])
    total = len(completed) + len(remaining)

    if total > 0:
        progress_pct = (len(completed) / total) * 100
        console.print(f"\n[bold]Progress:[/bold] {progress_pct:.0f}% ({len(completed)}/{total} tasks)")

        if completed:
            console.print("\n[green]✓ Completed:[/green]")
            for task in completed[-5:]:  # Show last 5
                console.print(f"  [dim]•[/dim] {task}")

        if remaining:
            console.print("\n[yellow]○ Remaining:[/yellow]")
            for task in remaining[:5]:  # Show next 5
                console.print(f"  [dim]•[/dim] {task}")


@foundry.command()
@click.option('--list', 'list_patterns', is_flag=True, help='List all patterns')
@click.option('--search', metavar='QUERY', help='Search patterns')
@click.option('--add', type=click.Path(exists=True), metavar='FILE', help='Add pattern from file')
@click.option('--rate', nargs=2, metavar='ID RATING', help='Rate a pattern (1-5)')
@click.option('--top', type=int, default=10, metavar='N', help='Show top N patterns')
@click.option('--stats', is_flag=True, help='Show library statistics')
def patterns(list_patterns, search, add, rate, top, stats):
    """
    Manage the pattern library.

    Examples:

    \b
      # List top patterns
      foundry patterns --list

    \b
      # Search for patterns
      foundry patterns --search "authentication JWT"

    \b
      # Show statistics
      foundry patterns --stats

    \b
      # Rate a pattern
      foundry patterns --rate 42 5
    """
    library = PatternLibrary()

    try:
        if stats:
            _show_pattern_stats(library)
        elif list_patterns:
            _list_patterns(library, limit=top)
        elif search:
            _search_patterns(library, search)
        elif add:
            _add_pattern(library, Path(add))
        elif rate:
            pattern_id, rating = rate
            library.rate_pattern(int(pattern_id), int(rating), session_id="manual", task_id="cli_rating")
            console.print(f"[green]✓[/green] Rated pattern #{pattern_id} with {rating} stars")
        else:
            # Default: show stats
            _show_pattern_stats(library)
    finally:
        library.close()


def _show_pattern_stats(library: PatternLibrary):
    """Show pattern library statistics."""
    stats = library.get_pattern_stats()

    console.print(Panel.fit(
        f"[bold cyan]Total Patterns:[/bold cyan] {stats['total_patterns']}\n"
        f"[cyan]Total Uses:[/cyan] {stats['total_usage']}\n"
        f"[cyan]Average Rating:[/cyan] {stats['avg_rating']:.2f}/5.0",
        title="Pattern Library Stats",
        border_style="cyan"
    ))

    if stats['by_language']:
        console.print("\n[bold]By Language:[/bold]")
        for lang, count in sorted(stats['by_language'].items(), key=lambda x: x[1], reverse=True):
            console.print(f"  {lang}: [cyan]{count}[/cyan]")


def _list_patterns(library: PatternLibrary, limit: int = 10):
    """List top patterns."""
    patterns = library.get_top_patterns(limit=limit, min_usage=1)

    if not patterns:
        console.print("[yellow]No patterns found[/yellow]")
        return

    table = Table(title=f"Top {limit} Patterns", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Description", style="white")
    table.add_column("Success Rate", style="green", width=12)
    table.add_column("Uses", style="blue", width=8)
    table.add_column("Rating", style="yellow", width=10)

    for p in patterns:
        table.add_row(
            str(p['id']),
            p['description'][:50] + "..." if len(p['description']) > 50 else p['description'],
            f"{p['success_rate']:.0f}%",
            str(p['usage_count']),
            f"{p['avg_rating']:.1f}/5"
        )

    console.print(table)


def _search_patterns(library: PatternLibrary, query: str):
    """Search for patterns."""
    results = library.search_patterns(query, limit=10)

    if not results:
        console.print(f"[yellow]No patterns found for: {query}[/yellow]")
        return

    console.print(f"\n[bold]Search results for:[/bold] [cyan]{query}[/cyan]\n")

    for i, (p_id, code, desc, similarity) in enumerate(results, 1):
        console.print(f"[bold]{i}. Pattern #{p_id}[/bold] [dim](relevance: {similarity*100:.0f}%)[/dim]")
        console.print(f"   {desc}")
        console.print(f"   [dim]{code[:100]}...[/dim]\n")


def _add_pattern(library: PatternLibrary, file_path: Path):
    """Add pattern from file."""
    code = file_path.read_text()

    # Extract metadata from file
    metadata = {
        'description': f'Pattern from {file_path.name}',
        'tags': [],
        'language': file_path.suffix[1:] if file_path.suffix else 'unknown',
        'framework': ''
    }

    pattern_id = library.extract_pattern(code, metadata)
    console.print(f"[green]✓[/green] Added pattern #{pattern_id} from {file_path}")


@foundry.command()
@click.argument('session', required=False)
@click.option('--format', type=click.Choice(['text', 'json', 'markdown']), default='text', help='Output format')
@click.option('--save', type=click.Path(), help='Save report to file')
def analyze(session, format, save):
    """
    Analyze completed sessions for metrics and improvements.

    Examples:

    \b
      # Analyze latest session
      foundry analyze

    \b
      # Analyze specific session
      foundry analyze my-app_20251002_210000

    \b
      # Save as markdown report
      foundry analyze --format markdown --save report.md
    """
    if not session:
        # Find most recent session
        checkpoints_dir = Path("checkpoints/ralph")
        sessions = sorted(checkpoints_dir.glob("*"), key=os.path.getmtime, reverse=True)
        if sessions:
            session = sessions[0].name
        else:
            console.print("[yellow]No sessions found[/yellow]")
            return

    console.print(f"[cyan]📊 Analyzing session:[/cyan] {session}\n")

    try:
        library = PatternLibrary()
        analyzer = SessionAnalyzer(pattern_library=library)
        metrics = analyzer.analyze(session)
        library.close()

        if not metrics:
            console.print("[red]Failed to analyze session[/red]")
            return

        # Display results
        if format == 'json':
            console.print_json(data=metrics)
        elif format == 'markdown':
            _print_markdown_report(metrics)
        else:
            _print_text_report(metrics)

        # Save if requested
        if save:
            _save_report(metrics, Path(save), format)
            console.print(f"\n[green]✓[/green] Report saved to: {save}")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)


def _print_text_report(metrics: dict):
    """Print text report."""
    console.print(Panel.fit(
        f"[bold cyan]Session:[/bold cyan] {metrics.get('session_id', 'Unknown')}\n"
        f"[cyan]Completion:[/cyan] {metrics.get('completion', {}).get('rate', 0):.1f}%\n"
        f"[cyan]Tasks:[/cyan] {metrics.get('completion', {}).get('completed', 0)}/{metrics.get('completion', {}).get('total', 0)}",
        title="Session Analysis",
        border_style="cyan"
    ))

    if 'tokens' in metrics:
        console.print(f"\n[bold]Token Usage:[/bold]")
        console.print(f"  Total: {metrics['tokens'].get('total', 0):,}")
        console.print(f"  Input: {metrics['tokens'].get('input', 0):,}")
        console.print(f"  Output: {metrics['tokens'].get('output', 0):,}")

    if 'cost' in metrics:
        console.print(f"\n[bold]Estimated Cost:[/bold] ${metrics['cost'].get('total', 0):.2f}")


def _print_markdown_report(metrics: dict):
    """Print markdown report."""
    md = f"""# Session Analysis: {metrics.get('session_id', 'Unknown')}

## Summary
- **Completion**: {metrics.get('completion', {}).get('rate', 0):.1f}%
- **Tasks**: {metrics.get('completion', {}).get('completed', 0)}/{metrics.get('completion', {}).get('total', 0)}

## Token Usage
- **Total**: {metrics.get('tokens', {}).get('total', 0):,}
- **Input**: {metrics.get('tokens', {}).get('input', 0):,}
- **Output**: {metrics.get('tokens', {}).get('output', 0):,}

## Cost
- **Estimated**: ${metrics.get('cost', {}).get('total', 0):.2f}
"""
    console.print(md)


def _save_report(metrics: dict, path: Path, format: str):
    """Save report to file."""
    if format == 'json':
        with open(path, 'w') as f:
            json.dump(metrics, f, indent=2)
    elif format == 'markdown':
        md = _generate_markdown_report(metrics)
        path.write_text(md)
    else:
        path.write_text(str(metrics))


def _generate_markdown_report(metrics: dict) -> str:
    """Generate markdown report."""
    return f"""# Session Analysis: {metrics.get('session_id', 'Unknown')}

## Summary
- **Completion**: {metrics.get('completion', {}).get('rate', 0):.1f}%
- **Tasks**: {metrics.get('completion', {}).get('completed', 0)}/{metrics.get('completion', {}).get('total', 0)}

## Token Usage
- **Total**: {metrics.get('tokens', {}).get('total', 0):,}
- **Input**: {metrics.get('tokens', {}).get('input', 0):,}
- **Output**: {metrics.get('tokens', {}).get('output', 0):,}

## Cost
- **Estimated**: ${metrics.get('cost', {}).get('total', 0):.2f}
"""


@foundry.command()
@click.option('--init', is_flag=True, help='Initialize configuration')
@click.option('--show', is_flag=True, help='Show current configuration')
@click.option('--set', nargs=2, metavar='KEY VALUE', help='Set configuration value')
def config(init, show, set):
    """
    Manage Context Foundry configuration.

    Examples:

    \b
      # Initialize .env file
      foundry config --init

    \b
      # Show current config
      foundry config --show

    \b
      # Set a value
      foundry config --set CLAUDE_MODEL claude-sonnet-4-20250514
    """
    env_file = Path(".env")

    if init:
        if env_file.exists():
            console.print("[yellow]⚠️  .env already exists[/yellow]")
            if not click.confirm("Overwrite?"):
                return

        # Copy from .env.example
        example_file = Path(".env.example")
        if example_file.exists():
            env_file.write_text(example_file.read_text())
            console.print(f"[green]✓[/green] Created .env from template")
        else:
            # Create minimal .env
            env_file.write_text("ANTHROPIC_API_KEY=your_api_key_here\n")
            console.print(f"[green]✓[/green] Created minimal .env")

        console.print(f"\n[cyan]Edit {env_file} to set your API key[/cyan]")

    elif show:
        if not env_file.exists():
            console.print("[yellow]No .env file found. Run: foundry config --init[/yellow]")
            return

        console.print(Panel.fit(
            env_file.read_text(),
            title=".env Configuration",
            border_style="cyan"
        ))

    elif set:
        key, value = set
        # Simple key=value setter (doesn't handle existing keys)
        with open(env_file, 'a') as f:
            f.write(f"\n{key}={value}\n")
        console.print(f"[green]✓[/green] Set {key}={value}")

    else:
        console.print("[yellow]Use --init, --show, or --set[/yellow]")


if __name__ == "__main__":
    foundry()
