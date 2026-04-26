use anyhow::Result;
use std::path::Path;

// ─── Tech Stack Detection ────────────────────────────────────────

#[derive(Debug)]
struct TechStack {
    language: &'static str,
    framework: Option<&'static str>,
    build_cmd: Option<&'static str>,
    test_cmd: Option<&'static str>,
}

fn detect_tech_stack(project_dir: &Path) -> Vec<TechStack> {
    let mut stacks = Vec::new();

    let markers: &[(&str, TechStack)] = &[
        (
            "Cargo.toml",
            TechStack {
                language: "Rust",
                framework: None,
                build_cmd: Some("cargo build"),
                test_cmd: Some("cargo test"),
            },
        ),
        (
            "package.json",
            TechStack {
                language: "JavaScript/TypeScript",
                framework: None,
                build_cmd: Some("npm run build"),
                test_cmd: Some("npm test"),
            },
        ),
        (
            "pyproject.toml",
            TechStack {
                language: "Python",
                framework: None,
                build_cmd: None,
                test_cmd: Some("pytest"),
            },
        ),
        (
            "requirements.txt",
            TechStack {
                language: "Python",
                framework: None,
                build_cmd: None,
                test_cmd: Some("pytest"),
            },
        ),
        (
            "go.mod",
            TechStack {
                language: "Go",
                framework: None,
                build_cmd: Some("go build ./..."),
                test_cmd: Some("go test ./..."),
            },
        ),
        (
            "pom.xml",
            TechStack {
                language: "Java",
                framework: Some("Maven"),
                build_cmd: Some("mvn compile"),
                test_cmd: Some("mvn test"),
            },
        ),
        (
            "build.gradle",
            TechStack {
                language: "Java/Kotlin",
                framework: Some("Gradle"),
                build_cmd: Some("./gradlew build"),
                test_cmd: Some("./gradlew test"),
            },
        ),
        (
            "Gemfile",
            TechStack {
                language: "Ruby",
                framework: None,
                build_cmd: None,
                test_cmd: Some("bundle exec rspec"),
            },
        ),
        (
            "composer.json",
            TechStack {
                language: "PHP",
                framework: None,
                build_cmd: None,
                test_cmd: Some("./vendor/bin/phpunit"),
            },
        ),
        (
            "mix.exs",
            TechStack {
                language: "Elixir",
                framework: None,
                build_cmd: Some("mix compile"),
                test_cmd: Some("mix test"),
            },
        ),
        (
            "CMakeLists.txt",
            TechStack {
                language: "C/C++",
                framework: Some("CMake"),
                build_cmd: Some("cmake --build build"),
                test_cmd: Some("ctest --test-dir build"),
            },
        ),
        (
            "docker-compose.yaml",
            TechStack {
                language: "Docker",
                framework: Some("Compose"),
                build_cmd: Some("docker compose build"),
                test_cmd: None,
            },
        ),
        (
            "docker-compose.yml",
            TechStack {
                language: "Docker",
                framework: Some("Compose"),
                build_cmd: Some("docker compose build"),
                test_cmd: None,
            },
        ),
    ];

    for (marker, stack) in markers {
        if project_dir.join(marker).exists() {
            stacks.push(TechStack {
                language: stack.language,
                framework: stack.framework,
                build_cmd: stack.build_cmd,
                test_cmd: stack.test_cmd,
            });
        }
    }

    stacks
}

// ─── Provider Detection ──────────────────────────────────────────

#[derive(Debug)]
struct ProviderStatus {
    claude: bool,
    ollama: bool,
    opencode: bool,
}

fn detect_providers() -> ProviderStatus {
    let claude = std::process::Command::new("claude")
        .arg("--version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false);

    let ollama = std::process::Command::new("curl")
        .args(["-s", "--connect-timeout", "2", "http://127.0.0.1:11434/api/version"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false);

    let opencode = std::process::Command::new("opencode")
        .arg("--version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false);

    ProviderStatus {
        claude,
        ollama,
        opencode,
    }
}

// ─── Config Generation ───────────────────────────────────────────

fn build_config(
    project_dir: &Path,
    stacks: &[TechStack],
    providers: &ProviderStatus,
) -> serde_json::Value {
    let mut config = serde_json::json!({});

    // Prefer justfile if present
    if project_dir.join("justfile").exists() || project_dir.join("Justfile").exists() {
        config["build_command"] = serde_json::json!("just build");
    } else if let Some(stack) = stacks.first() {
        if let Some(cmd) = stack.build_cmd {
            config["build_command"] = serde_json::json!(cmd);
        }
    }

    if providers.opencode && !providers.claude {
        for key in &[
            "builder_provider",
            "planner_provider",
            "reviewer_provider",
            "fixer_provider",
            "discovery_provider",
            "scout_provider",
            "query_provider",
            "research_provider",
        ] {
            config[*key] = serde_json::json!("opencode");
        }
    }

    config["run_mode"] = serde_json::json!("auto");

    config
}

// ─── TASKS.md Generation ─────────────────────────────────────────

fn build_tasks_content(stacks: &[TechStack]) -> String {
    let mut content = String::from("# Task Queue\n\n");

    if stacks.is_empty() {
        content.push_str("<!-- Add tasks below. Format: - [ ] T1.1: Description -->\n");
        content.push_str("- [ ] T1.1: Set up project structure and initial implementation\n");
    } else {
        content.push_str("<!-- Add tasks below. Format: - [ ] T1.1: Description -->\n");
    }

    content
}

// ─── Public Entry Point ──────────────────────────────────────────

pub fn run_init(project_dir: &Path) -> Result<()> {
    let config_path = project_dir.join(".foundry.json");
    let tasks_path = project_dir.join("TASKS.md");

    println!("  Initializing foundry in {}\n", project_dir.display());

    // 1. Detect tech stack
    let stacks = detect_tech_stack(project_dir);
    if stacks.is_empty() {
        println!("  Stack     (none detected)");
    } else {
        for stack in &stacks {
            let label = match stack.framework {
                Some(fw) => format!("{} ({})", stack.language, fw),
                None => stack.language.to_string(),
            };
            println!("  Stack     {label}");
        }
    }

    // 2. Detect providers
    let providers = detect_providers();
    let mut provider_labels = Vec::new();
    if providers.claude {
        provider_labels.push("claude");
    }
    if providers.opencode {
        provider_labels.push("opencode");
    }
    if providers.ollama {
        provider_labels.push("ollama");
    }
    if provider_labels.is_empty() {
        println!("  Providers (none found -- install claude CLI or opencode)");
    } else {
        println!("  Providers {}", provider_labels.join(", "));
    }

    println!();

    // 3. Write .foundry.json (only if it doesn't exist)
    if config_path.exists() {
        println!("  [skip] .foundry.json already exists");
    } else {
        let config = build_config(project_dir, &stacks, &providers);
        let json = serde_json::to_string_pretty(&config)?;
        crate::utils::atomic_write_file(&config_path, json.as_bytes())?;
        println!("  [create] .foundry.json");
    }

    // 4. Write TASKS.md (only if it doesn't exist)
    if tasks_path.exists() {
        println!("  [skip] TASKS.md already exists");
    } else {
        let content = build_tasks_content(&stacks);
        crate::utils::atomic_write_file(&tasks_path, content.as_bytes())?;
        println!("  [create] TASKS.md");
    }

    // 5. Ensure .buildloop/ exists
    let buildloop_dir = project_dir.join(".buildloop");
    if !buildloop_dir.exists() {
        std::fs::create_dir_all(&buildloop_dir)?;
        println!("  [create] .buildloop/");
    }

    // 6. Ensure .buildloop/ is gitignored
    let gitignore_path = project_dir.join(".gitignore");
    if gitignore_path.exists() {
        let content = std::fs::read_to_string(&gitignore_path).unwrap_or_default();
        let has_entry = content.lines().any(|l| l.trim() == ".buildloop" || l.trim() == ".buildloop/");
        if !has_entry {
            let mut appended = content;
            if !appended.ends_with('\n') {
                appended.push('\n');
            }
            appended.push_str(".buildloop/\n");
            crate::utils::atomic_write_file_best_effort(&gitignore_path, appended.as_bytes());
            println!("  [update] .gitignore (added .buildloop/)");
        }
    } else {
        crate::utils::atomic_write_file_best_effort(&gitignore_path, b".buildloop/\n");
        println!("  [create] .gitignore");
    }

    // 7. Ensure global dirs exist
    if let Ok(home) = std::env::var("HOME") {
        let home = std::path::PathBuf::from(home);
        let patterns_dir = home.join(".foundry").join("patterns");
        let history_dir = home.join(".foundry").join("history");
        if !patterns_dir.exists() {
            std::fs::create_dir_all(&patterns_dir)?;
        }
        if !history_dir.exists() {
            std::fs::create_dir_all(&history_dir)?;
        }
    }

    println!("\n  Ready. Run `foundry` to start the build loop.");

    if !providers.claude && !providers.opencode {
        println!("\n  Note: No AI provider detected. Install claude CLI:");
        println!("    npm install -g @anthropic-ai/claude-code");
    }

    Ok(())
}
