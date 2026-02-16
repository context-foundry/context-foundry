use anyhow::Result;
use clap::{Parser, Subcommand};
use std::path::PathBuf;

mod agent;
mod app;
mod config;
mod git;
mod patterns;
mod prompts;
mod task;
mod tui;
mod update;
mod utils;

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
    },
    /// Show current progress
    Status,
    /// List all tasks from IMPL_PLAN.md
    Tasks,
    /// Update foundry to the latest version
    Update,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let project_dir = cli
        .dir
        .unwrap_or_else(|| std::env::current_dir().expect("cannot determine current directory"));

    let project_dir = project_dir.canonicalize().unwrap_or(project_dir);

    match cli.command.unwrap_or(Commands::Run { no_tui: false }) {
        Commands::Run { no_tui } => {
            if no_tui {
                app::run_headless(&project_dir).await?;
            } else {
                app::run_tui(&project_dir).await?;
            }
        }
        Commands::Status => {
            app::show_status(&project_dir)?;
        }
        Commands::Tasks => {
            app::show_tasks(&project_dir)?;
        }
        Commands::Update => {
            update::run_update()?;
        }
    }

    Ok(())
}
