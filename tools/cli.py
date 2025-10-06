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


def confirm_settings(settings: dict) -> bool:
    """Show settings summary and ask user to confirm before starting.

    Args:
        settings: Dictionary of settings to display

    Returns:
        True if user confirms, False otherwise
    """
    console.print("\n[bold yellow]📋 Configuration Summary[/bold yellow]")
    console.print("─" * 60)

    for key, value in settings.items():
        console.print(f"  [cyan]{key}:[/cyan] {value}")

    console.print("─" * 60)
    console.print("[dim]Review settings above. Type 'y' or 'yes' to proceed, or anything else to abort.[/dim]")

    response = input("\n👉 Proceed with these settings? (y/n): ").strip().lower()

    if response in ['y', 'yes']:
        console.print("[green]✓[/green] Starting workflow...\n")
        return True
    else:
        console.print("[yellow]⚠️  Aborted by user. Restart with different flags if needed.[/yellow]")
        return False


def check_provider_authentication():
    """Check if configured providers have API keys.

    Returns:
        List of tuples (provider_name, api_key_name) for missing authentication
    """
    # Get configured providers from environment
    scout_provider = os.getenv('SCOUT_PROVIDER', 'anthropic')
    architect_provider = os.getenv('ARCHITECT_PROVIDER', 'anthropic')
    builder_provider = os.getenv('BUILDER_PROVIDER', 'anthropic')

    # Get unique providers
    providers_needed = {scout_provider, architect_provider, builder_provider}

    # Map provider names to their API key environment variables
    provider_key_map = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'github': 'GITHUB_TOKEN',
        'zai': 'ZAI_API_KEY',
        'gemini': 'GOOGLE_API_KEY',
        'groq': 'GROQ_API_KEY',
        'cloudflare': 'CLOUDFLARE_API_KEY',
        'fireworks': 'FIREWORKS_API_KEY',
        'mistral': 'MISTRAL_API_KEY',
    }

    # Check each provider's API key
    missing = []
    for provider in providers_needed:
        key_name = provider_key_map.get(provider)
        if key_name and not os.getenv(key_name):
            missing.append((provider, key_name))

    return missing


def test_provider_connectivity():
    """Test that each configured provider can connect successfully.

    Returns:
        True if all providers connect successfully, False otherwise
    """
    from ace.ai_client import AIClient
    from ace.provider_registry import get_registry

    console.print("\n[bold]🔍 Testing model connectivity...[/bold]")

    # Get configured providers
    scout_provider = os.getenv('SCOUT_PROVIDER', 'anthropic')
    scout_model = os.getenv('SCOUT_MODEL', 'claude-sonnet-4-20250514')
    architect_provider = os.getenv('ARCHITECT_PROVIDER', 'anthropic')
    architect_model = os.getenv('ARCHITECT_MODEL', 'claude-sonnet-4-20250514')
    builder_provider = os.getenv('BUILDER_PROVIDER', 'anthropic')
    builder_model = os.getenv('BUILDER_MODEL', 'claude-sonnet-4-20250514')

    # Get unique provider/model combinations to test
    configs = [
        ('Scout', scout_provider, scout_model),
        ('Architect', architect_provider, architect_model),
        ('Builder', builder_provider, builder_model),
    ]

    all_ok = True
    registry = get_registry()

    for phase, provider_name, model_name in configs:
        try:
            # Get provider instance
            provider = registry.get(provider_name)
            provider_display = provider.get_display_name()

            # Test connection with minimal API call
            console.print(f"  • {phase} ({provider_display} {model_name})... ", end="")

            test_response = provider.call_api(
                messages=[{"role": "user", "content": "test"}],
                model=model_name,
                max_tokens=1
            )

            if test_response and test_response.content:
                console.print("[green]✓ Connected[/green]")
            else:
                console.print("[red]✗ Invalid response[/red]")
                all_ok = False

        except Exception as e:
            console.print(f"[red]✗ Error[/red]")
            console.print(f"    [dim]{str(e)}[/dim]")
            all_ok = False

    return all_ok


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
@click.option('--push', is_flag=True, help='Automatically push to GitHub after successful build')
@click.option('--livestream', is_flag=True, help='Enable real-time dashboard')
@click.option('--overnight', type=int, metavar='HOURS', help='Schedule overnight run')
@click.option('--use-patterns/--no-patterns', default=True, help='Enable pattern injection')
@click.option('--context-manager/--no-context-manager', default=True, help='Enable smart context management')
@click.option('--project-dir', type=click.Path(), help='Custom project directory')
def build(project, task, autonomous, push, livestream, overnight, use_patterns, context_manager, project_dir):
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
      # Auto-push to GitHub after successful build
      foundry build web-app "Todo app with React" --push

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
        f"[cyan]Task:[/cyan] {task}\n"
        f"[cyan]Ralph Wiggum mode:[/cyan] {'🤖 On (autonomous)' if autonomous else '👤 Off (interactive)'}",
        title="Starting Build",
        border_style="blue"
    ))

    # Check for provider authentication
    missing_auth = check_provider_authentication()
    if missing_auth:
        console.print("[red]❌ Error: Missing authentication for configured providers[/red]")
        for provider, key_name in missing_auth:
            console.print(f"[yellow]  • Provider '{provider}' requires: {key_name}[/yellow]")
        console.print("\n[dim]Check your .env file configuration.[/dim]")
        sys.exit(1)

    # Test provider connectivity
    if not test_provider_connectivity():
        console.print("\n[red]❌ Fix connectivity errors above before proceeding[/red]")
        sys.exit(1)
    console.print("[green]✓ All models connected successfully![/green]")

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

    # Pre-flight confirmation
    scout_provider = os.getenv('SCOUT_PROVIDER', 'anthropic')
    scout_model = os.getenv('SCOUT_MODEL', 'claude-sonnet-4-20250514')
    architect_provider = os.getenv('ARCHITECT_PROVIDER', 'anthropic')
    architect_model = os.getenv('ARCHITECT_MODEL', 'claude-sonnet-4-20250514')
    builder_provider = os.getenv('BUILDER_PROVIDER', 'anthropic')
    builder_model = os.getenv('BUILDER_MODEL', 'claude-sonnet-4-20250514')

    settings = {
        "Project": project,
        "Task": task,
        "Mode": "Build (new project)",
        "Scout": f"{scout_provider} / {scout_model}",
        "Architect": f"{architect_provider} / {architect_model}",
        "Builder": f"{builder_provider} / {builder_model}",
        "Ralph Wiggum (autonomous)": "🤖 On" if autonomous else "👤 Off",
        "Livestream": "📡 Enabled" if livestream else "Disabled",
        "Auto-push to GitHub": "✓ On" if push else "Off",
        "Pattern injection": "✓ On" if use_patterns else "Off",
        "Context management": "✓ On" if context_manager else "Off"
    }

    if not confirm_settings(settings):
        sys.exit(0)

    try:
        orchestrator = AutonomousOrchestrator(
            project_name=project,
            task_description=task,
            autonomous=autonomous,
            project_dir=Path(project_dir) if project_dir else None,
            use_patterns=use_patterns,
            enable_livestream=livestream,
            auto_push=push
        )

        result = orchestrator.run()

        if result.get("status") == "success":
            console.print("\n[green]✅ Build complete![/green]")
            console.print(f"\n[cyan]📁 Project files:[/cyan] {result.get('project_dir', 'N/A')}")
            console.print(f"[cyan]📊 Session ID:[/cyan] {result.get('session_id', 'N/A')}")

            if push:
                if result.get('pushed_to_github'):
                    console.print(f"[green]✓[/green] [cyan]Pushed to GitHub[/cyan]")
                else:
                    console.print(f"[yellow]⚠[/yellow] [cyan]Push to GitHub failed (see output above)[/cyan]")
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
@click.argument('project')
@click.argument('issue')
@click.option('--session', type=str, help='Session ID to resume (for foundry projects)')
@click.option('--tasks', type=str, help='Comma-separated task numbers to re-run (e.g. "12,14")')
@click.option('--autonomous', is_flag=True, help='Skip human review checkpoints')
@click.option('--push', is_flag=True, help='Push to GitHub after successful fix')
@click.option('--use-patterns/--no-patterns', default=True, help='Enable pattern injection')
def fix(project, issue, session, tasks, autonomous, push, use_patterns):
    """
    Fix issues in an existing project.

    PROJECT can be: GitHub URL, local path, or project name in examples/
    ISSUE is a natural language description of what to fix

    Examples:

    \b
      # Fix a specific issue
      foundry fix weather-web "CSS files are missing from the build"

    \b
      # Resume a foundry session and re-run failed tasks
      foundry fix weather-web "Fix tasks 12 and 14" --session 20251004_214024 --tasks 12,14

    \b
      # Fix a GitHub repo
      foundry fix https://github.com/user/repo "Login button doesn't work"

    \b
      # Autonomous mode with auto-push
      foundry fix ./my-app "Fix broken API endpoints" --autonomous --push
    """
    from utils.project_detector import ProjectDetector
    from workflows.autonomous_orchestrator import AutonomousOrchestrator

    console.print(Panel.fit(
        "[bold yellow]🔧 Context Foundry - Fix[/bold yellow]\n"
        f"[cyan]Project:[/cyan] {project}\n"
        f"[cyan]Issue:[/cyan] {issue}\n"
        f"[cyan]Ralph Wiggum mode:[/cyan] {'🤖 On (autonomous)' if autonomous else '👤 Off (interactive)'}",
        title="Fix Mode",
        border_style="yellow"
    ))

    # Check for provider authentication
    missing_auth = check_provider_authentication()
    if missing_auth:
        console.print("[red]❌ Error: Missing authentication for configured providers[/red]")
        for provider, key_name in missing_auth:
            console.print(f"[yellow]  • Provider '{provider}' requires: {key_name}[/yellow]")
        console.print("\n[dim]Check your .env file configuration.[/dim]")
        sys.exit(1)

    try:
        # Detect project location
        detector = ProjectDetector()
        project_path, source_type = detector.detect(project)

        console.print(f"\n[green]✓[/green] Project found: {project_path} ({source_type})")

        # Extract project name from path
        project_name = project_path.name

        # Check for session resume mode
        if session or tasks:
            # Session resume mode
            if not session:
                # Try to find latest session
                session = detector.get_latest_session_id(project_name)
                if session:
                    console.print(f"[cyan]📋 Using latest session:[/cyan] {session}")
                else:
                    console.print("[yellow]⚠️  No session found. Running in smart fix mode.[/yellow]")

            if session:
                console.print(f"\n[bold]Resuming session: {session}[/bold]")
                if tasks:
                    task_list = [int(t.strip()) for t in tasks.split(',')]
                    console.print(f"[cyan]Re-running tasks:[/cyan] {task_list}\n")
                else:
                    console.print("[yellow]No tasks specified. Will analyze and fix issues.[/yellow]\n")

        console.print("[bold]Starting Scout → Architect → Builder workflow...[/bold]\n")

        # Pre-flight confirmation
        settings = {
            "Project": project_name,
            "Issue": issue,
            "Mode": "Fix (repair existing)",
            "Ralph Wiggum (autonomous)": "🤖 On" if autonomous else "👤 Off",
            "Auto-push to GitHub": "✓ On" if push else "Off",
            "Pattern injection": "✓ On" if use_patterns else "Off"
        }

        if session:
            settings["Session resume"] = f"📋 {session}"
        if tasks:
            settings["Re-run tasks"] = tasks

        if not confirm_settings(settings):
            sys.exit(0)

        orchestrator = AutonomousOrchestrator(
            project_name=project_name,
            task_description=issue,
            autonomous=autonomous,
            project_dir=project_path,
            use_patterns=use_patterns,
            mode="fix",
            auto_push=push
        )

        # Pass session and task info if in resume mode
        if session:
            orchestrator.resume_session = session
        if tasks:
            orchestrator.resume_tasks = [int(t.strip()) for t in tasks.split(',')]

        result = orchestrator.run()

        if result.get("status") == "success":
            console.print("\n[green]✅ Fix complete![/green]")
            console.print(f"\n[cyan]📁 Project:[/cyan] {result.get('project_dir', 'N/A')}")
            console.print(f"[cyan]📊 Session:[/cyan] {result.get('session_id', 'N/A')}")

            if push and result.get('pushed_to_github'):
                console.print(f"[green]✓[/green] [cyan]Pushed to GitHub[/cyan]")
        else:
            console.print(f"\n[yellow]⚠️  Fix incomplete: {result.get('status')}[/yellow]")
            sys.exit(1)

    except ValueError as e:
        console.print(f"\n[red]❌ {e}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Fix interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@foundry.command()
@click.argument('project')
@click.argument('feature')
@click.option('--autonomous', is_flag=True, help='Skip human review checkpoints')
@click.option('--push', is_flag=True, help='Push to GitHub after successful enhancement')
@click.option('--use-patterns/--no-patterns', default=True, help='Enable pattern injection')
@click.option('--create-pr/--no-pr', default=False, help='Create pull request when complete')
def enhance(project, feature, autonomous, push, use_patterns, create_pr):
    """
    Enhance an existing project with new features.

    PROJECT can be: GitHub URL, local path, or project name in examples/
    FEATURE is a natural language description of what to add

    Examples:

    \b
      # Enhance a local project
      foundry enhance ./my-app "Add dark mode toggle to settings"

    \b
      # Enhance a GitHub repo
      foundry enhance https://github.com/user/repo "Add rate limiting to API"

    \b
      # Enhance a foundry project
      foundry enhance weather-web "Add 7-day forecast view"

    \b
      # Autonomous mode with auto-push
      foundry enhance my-project "Add JWT authentication" --autonomous --push
    """
    from utils.project_detector import ProjectDetector
    from workflows.autonomous_orchestrator import AutonomousOrchestrator

    console.print(Panel.fit(
        "[bold green]🔧 Context Foundry - Enhance[/bold green]\n"
        f"[cyan]Project:[/cyan] {project}\n"
        f"[cyan]Feature:[/cyan] {feature}\n"
        f"[cyan]Ralph Wiggum mode:[/cyan] {'🤖 On (autonomous)' if autonomous else '👤 Off (interactive)'}",
        title="Enhancement Mode",
        border_style="green"
    ))

    # Check for provider authentication
    missing_auth = check_provider_authentication()
    if missing_auth:
        console.print("[red]❌ Error: Missing authentication for configured providers[/red]")
        for provider, key_name in missing_auth:
            console.print(f"[yellow]  • Provider '{provider}' requires: {key_name}[/yellow]")
        console.print("\n[dim]Check your .env file configuration.[/dim]")
        sys.exit(1)

    try:
        # Detect project location
        detector = ProjectDetector()
        project_path, source_type = detector.detect(project)

        console.print(f"\n[green]✓[/green] Project found: {project_path} ({source_type})")

        # Extract project name from path
        project_name = project_path.name

        console.print("\n[bold]Starting Scout → Architect → Builder workflow...[/bold]\n")

        # Pre-flight confirmation
        settings = {
            "Project": project_name,
            "Feature": feature,
            "Mode": "Enhance (add features)",
            "Ralph Wiggum (autonomous)": "🤖 On" if autonomous else "👤 Off",
            "Auto-push to GitHub": "✓ On" if push else "Off",
            "Pattern injection": "✓ On" if use_patterns else "Off",
            "Create PR": "✓ On" if create_pr else "Off"
        }

        if not confirm_settings(settings):
            sys.exit(0)

        orchestrator = AutonomousOrchestrator(
            project_name=project_name,
            task_description=feature,
            autonomous=autonomous,
            project_dir=project_path,
            use_patterns=use_patterns,
            mode="enhance",
            auto_push=push
        )

        result = orchestrator.run()

        if result.get("status") == "success":
            console.print("\n[green]✅ Enhancement complete![/green]")
            console.print(f"\n[cyan]📁 Project:[/cyan] {result.get('project_dir', 'N/A')}")
            console.print(f"[cyan]📊 Session:[/cyan] {result.get('session_id', 'N/A')}")

            if push and result.get('pushed_to_github'):
                console.print(f"[green]✓[/green] [cyan]Pushed to GitHub[/cyan]")

            if create_pr:
                console.print("\n[yellow]🚧 PR creation coming soon![/yellow]")
        else:
            console.print(f"\n[yellow]⚠️  Enhancement incomplete: {result.get('status')}[/yellow]")
            sys.exit(1)

    except ValueError as e:
        console.print(f"\n[red]❌ {e}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Enhancement interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


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


@foundry.command()
@click.option('--list', 'list_models', is_flag=True, help='List all available models')
@click.option('--provider', help='Filter by provider')
def models(list_models, provider):
    """
    List available AI models and providers.

    Examples:

    \b
      # List all models from all providers
      foundry models --list

    \b
      # List models from specific provider
      foundry models --list --provider anthropic
    """
    from ace.provider_registry import get_registry
    from ace.pricing_database import PricingDatabase

    registry = get_registry()
    db = PricingDatabase()

    if not list_models:
        # Show quick summary
        providers = registry.list_providers()
        console.print(f"\n[bold]Available Providers:[/bold] {', '.join(providers)}\n")
        console.print("[dim]Use --list to see all models[/dim]")
        return

    # List all models
    all_models = registry.list_all_models()

    if provider:
        # Filter by provider
        if provider not in all_models:
            console.print(f"[red]Provider '{provider}' not found[/red]")
            return
        all_models = {provider: all_models[provider]}

    # Display models by provider
    for provider_name, models_list in all_models.items():
        if not models_list:
            continue

        provider_obj = registry.get(provider_name)
        console.print(f"\n[bold cyan]{provider_obj.get_display_name()}[/bold cyan]")

        # Create table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Model", style="white")
        table.add_column("Context", style="dim")
        table.add_column("Pricing (per 1M tokens)", style="green")
        table.add_column("Description", style="dim")

        for model in models_list:
            # Get pricing
            pricing = db.get_pricing(provider_name, model.name)

            if pricing:
                price_str = f"${pricing.input_cost_per_1m:.2f} / ${pricing.output_cost_per_1m:.2f}"
            else:
                price_str = "N/A"

            table.add_row(
                model.name,
                f"{model.context_window:,}",
                price_str,
                model.description[:50] + "..." if len(model.description) > 50 else model.description
            )

        console.print(table)

    db.close()


@foundry.command()
@click.option('--update', is_flag=True, help='Update pricing from all providers')
@click.option('--list', 'list_pricing', is_flag=True, help='List current pricing')
@click.option('--force', is_flag=True, help='Force update even if not stale')
def pricing(update, list_pricing, force):
    """
    Manage AI model pricing.

    Examples:

    \b
      # Update pricing from all providers
      foundry pricing --update

    \b
      # Force update
      foundry pricing --update --force

    \b
      # List current pricing
      foundry pricing --list
    """
    from ace.pricing_fetcher import PricingFetcher
    from ace.pricing_database import PricingDatabase

    fetcher = PricingFetcher()

    if update:
        console.print("\n[bold]Updating pricing from providers...[/bold]\n")

        results = fetcher.fetch_all(force=force)

        # Display results
        success_count = sum(1 for r in results.values() if r.get('status') == 'success')
        failed_count = sum(1 for r in results.values() if r.get('status') == 'failed')
        skipped_count = sum(1 for r in results.values() if r.get('status') == 'skipped')

        for provider_name, result in results.items():
            if result['status'] == 'success':
                console.print(f"[green]✅ {provider_name}[/green] - {result['models_updated']} models updated")
            elif result['status'] == 'failed':
                console.print(f"[red]❌ {provider_name}[/red] - {result.get('error', 'Unknown error')}")
            elif result['status'] == 'skipped':
                console.print(f"[dim]⏭️  {provider_name}[/dim] - {result.get('message', 'Skipped')}")

        console.print(f"\n[bold]Summary:[/bold] {success_count} updated, {failed_count} failed, {skipped_count} skipped\n")

    elif list_pricing:
        db = PricingDatabase()
        all_pricing = db.get_all_pricing()

        if not all_pricing:
            console.print("[yellow]No pricing data available. Run: foundry pricing --update[/yellow]")
            db.close()
            return

        # Group by provider
        by_provider = {}
        for provider, model, pricing in all_pricing:
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append((model, pricing))

        # Display
        for provider_name, models in by_provider.items():
            console.print(f"\n[bold cyan]{provider_name.title()}[/bold cyan]")

            table = Table(show_header=True, header_style="bold")
            table.add_column("Model")
            table.add_column("Input (per 1M)")
            table.add_column("Output (per 1M)")
            table.add_column("Updated")

            for model_name, pricing in models:
                table.add_row(
                    model_name,
                    f"${pricing.input_cost_per_1m:.2f}",
                    f"${pricing.output_cost_per_1m:.2f}",
                    pricing.updated_at.strftime("%Y-%m-%d")
                )

            console.print(table)

        db.close()

    else:
        # Show status
        status = fetcher.get_pricing_status()

        console.print("\n[bold]Pricing Status[/bold]\n")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Provider")
        table.add_column("Status")
        table.add_column("Last Updated")
        table.add_column("Needs Update")

        for provider_name, provider_status in status.items():
            if provider_status['status'] == 'never_updated':
                table.add_row(
                    provider_name,
                    "[yellow]Never updated[/yellow]",
                    "N/A",
                    "[red]Yes[/red]"
                )
            else:
                last_updated = provider_status['last_updated'].strftime("%Y-%m-%d")
                needs_update = "[yellow]Yes[/yellow]" if provider_status['needs_update'] else "[green]No[/green]"

                table.add_row(
                    provider_name,
                    provider_status['status'],
                    last_updated,
                    needs_update
                )

        console.print(table)
        console.print("\n[dim]Run 'foundry pricing --update' to update pricing[/dim]\n")


@foundry.command()
@click.argument('task_description')
def estimate(task_description):
    """
    Estimate cost for a project before building.

    Examples:

    \b
      # Estimate cost for a project
      foundry estimate "Build a todo app with React"
    """
    from ace.cost_estimator import CostEstimator
    from ace.ai_client import AIClient

    # Load current configuration
    try:
        client = AIClient()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[yellow]Make sure you have providers configured in .env[/yellow]")
        sys.exit(1)

    # Show configuration
    console.print("\n[bold]Current Configuration:[/bold]")
    console.print(client.get_config_summary())
    console.print()

    # Estimate cost
    try:
        estimator = CostEstimator()

        estimate = estimator.estimate(
            task_description,
            client.config.scout.provider,
            client.config.scout.model,
            client.config.architect.provider,
            client.config.architect.model,
            client.config.builder.provider,
            client.config.builder.model
        )

        # Display estimate
        console.print(Panel.fit(
            estimator.format_estimate(estimate),
            title="Cost Estimate",
            border_style="green"
        ))

        console.print("[dim]Note: Actual costs may vary based on task complexity[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error estimating cost: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    foundry()
