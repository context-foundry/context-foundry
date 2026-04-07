use anyhow::Result;
use clap::{Parser, Subcommand};
use std::path::PathBuf;

mod agent;
mod app;
mod complexity;
mod config;
mod doubt_confidence;
mod embeddings;
mod extensions;
mod git;
mod isolation;
mod mcp;
mod observatory;
mod orchestrator;
mod tmux;
mod sandbox;
mod stats;
mod review_pr;
mod budget;
mod patterns;
mod prompts;
mod task;
mod tui;
mod update;
mod utils;
mod dashboard;

#[derive(Parser)]
#[command(
    name = "foundry",
    about = "Autonomous build loop — plans, builds, validates, discovers, forever.",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    /// Project directory (defaults to current directory)
    #[arg(short, long, global = true)]
    dir: Option<PathBuf>,
}

#[derive(Subcommand)]
enum Commands {
    /// Start the endless build loop (default)
    Run {
        /// Run without TUI (streaming log mode)
        #[arg(long)]
        no_tui: bool,
        /// Output format for headless mode (e.g., "json")
        #[arg(long, value_name = "FORMAT")]
        output_format: Option<String>,
    },
    /// Show current progress
    Status,
    /// List all tasks from TASKS.md (legacy: IMPL_PLAN.md)
    Tasks,
    /// Run dedicated planning mode (gap analysis, no building)
    Plan {
        /// Maximum planning iterations (0 = unlimited, stops when plan stabilizes)
        #[arg(short = 'n', long)]
        iterations: Option<u64>,
    },
    /// Design with cross-model review (proposer + reviewer loop)
    Design {
        /// What you want designed or reviewed
        intent: Vec<String>,
    },
    /// Run as an MCP server (stdio transport)
    Mcp,
    /// Update foundry to the latest version
    Update,
    /// Extract patterns from build artifacts (.buildloop/)
    Extract,
    /// Review a GitHub PR with the foundry reviewer agent
    ReviewPr {
        /// PR number to review
        pr_number: u32,
        /// Repository in OWNER/REPO format (defaults to git remote origin)
        #[arg(long)]
        repo: Option<String>,
        /// Output format: stdout, json, or comment (default: stdout)
        #[arg(long, default_value = "stdout")]
        output: String,
        /// Ignore project .foundry.json (use global config only).
        /// Use in CI to prevent untrusted PR branches from influencing review config.
        #[arg(long)]
        ignore_project_config: bool,
    },
    /// Manage learned patterns
    Patterns {
        #[command(subcommand)]
        action: PatternAction,
    },
    /// Show observatory analytics
    Stats {
        /// Number of days to look back (default: 7)
        #[arg(long, default_value = "7")]
        days: u32,
        /// Project directory to filter by (default: current directory)
        #[arg(long)]
        project: Option<PathBuf>,
        /// Output format: table or json (default: table)
        #[arg(long, default_value = "table")]
        output: String,
        /// Show daily trend sparklines
        #[arg(long)]
        trend: bool,
    },
    /// Start the observatory web dashboard
    Dashboard {
        /// Port to serve on (default: 9400, binds to 127.0.0.1 only)
        #[arg(long, default_value = "9400")]
        port: u16,
    },
}

#[derive(Subcommand)]
enum PatternAction {
    /// Prune zero-citation patterns from the global pattern store
    Prune {
        /// Skip confirmation prompt
        #[arg(long)]
        yes: bool,
    },
    /// Promote high-citation patterns into extension CLAUDE.md prose
    Promote {
        /// Actually write files (default is dry-run)
        #[arg(long)]
        apply: bool,
        /// Number of days to look back for observatory events (default: 90)
        #[arg(long, default_value = "90")]
        days: u32,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let project_dir = cli
        .dir
        .unwrap_or_else(|| std::env::current_dir().expect("cannot determine current directory"));

    let project_dir = dunce::canonicalize(&project_dir).unwrap_or(project_dir);

    match cli.command.unwrap_or(Commands::Run {
        no_tui: false,
        output_format: None,
    }) {
        Commands::Run {
            no_tui,
            output_format,
        } => {
            if no_tui {
                app::run_headless(&project_dir, output_format).await?;
            } else {
                app::run_tui(&project_dir).await?;
            }
        }
        Commands::Plan { iterations } => {
            app::run_plan_mode(&project_dir, iterations.unwrap_or(0)).await?;
        }
        Commands::Status => {
            app::show_status(&project_dir)?;
        }
        Commands::Tasks => {
            app::show_tasks(&project_dir)?;
        }
        Commands::Design { intent } => {
            let intent = intent.join(" ");
            if intent.is_empty() {
                anyhow::bail!("Usage: foundry design <intent>");
            }
            orchestrator::run_design_command(&project_dir, &intent).await?;
        }
        Commands::Mcp => {
            mcp::run_mcp_server(&project_dir)?;
        }
        Commands::Update => {
            update::run_update()?;
        }
        Commands::Extract => {
            app::run_extract(&project_dir)?;
        }
        Commands::ReviewPr {
            pr_number,
            repo,
            output,
            ignore_project_config,
        } => {
            review_pr::run(&project_dir, pr_number, repo, &output, ignore_project_config).await?;
        }
        Commands::Patterns { action } => match action {
            PatternAction::Prune { yes } => {
                app::run_patterns_prune(yes)?;
            }
            PatternAction::Promote { apply, days } => {
                app::run_patterns_promote(apply, days)?;
            }
        },
        Commands::Stats {
            days,
            project,
            output,
            trend,
        } => {
            let stats_project = project.unwrap_or_else(|| project_dir.clone());
            stats::run_stats(days, &stats_project, &output, trend)?;
        }
        Commands::Dashboard { port } => {
            let config = config::Config::load(&project_dir);
            let effective_port = if port == 9400 { config.dashboard_port } else { port };
            dashboard::run_dashboard(effective_port, &project_dir).await?;
        }
    }

    Ok(())
}
