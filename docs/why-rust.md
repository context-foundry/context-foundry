# Why Rust?

Context Foundry is a Rust application that runs AI agents (Claude, Codex) in an autonomous build loop and an interactive multi-model studio. This document explains why Rust was chosen and what alternatives were considered.

## What the App Actually Does

Context Foundry has two modes:

1. **Autonomous Builder** (`foundry run`) -- an automated pipeline that runs Claude agents in sequence (Planner, Builder, Reviewer, Fixer) to complete tasks from an implementation plan, with a live TUI dashboard.

2. **Studio** (`foundry studio`) -- an interactive multi-pane terminal workspace where you run multiple Claude/Codex sessions side-by-side, attach execution contracts, and compare outputs.

Both modes do several things simultaneously:

- Read PTY output from **multiple AI processes** in real time
- Handle **keyboard and mouse events** (clicks, drags for pane resizing, scrolling)
- Render an **interactive TUI at 10fps** on a tick timer
- Run **background probes** to check provider availability
- Fan output from agents into the UI via **async channels**

## Why Rust Specifically

### 1. Concurrency Without Race Conditions

The app multiplexes PTY streams from multiple child processes while rendering a live UI and handling input events. Rust's ownership model makes data races a **compile-time error**, not a 2 AM runtime surprise.

The codebase uses `tokio` for async orchestration, `mpsc::unbounded_channel` for fan-out event streams, and `spawn_blocking` for PTY reads. These patterns compose cleanly because the compiler enforces that shared state is accessed safely.

### 2. Terminal UI Performance

The TUI is built with **Ratatui**, which provides a React-like declarative rendering model -- you describe what each frame should look like, and it diffs against the previous frame, only updating changed terminal cells. This gives smooth, flicker-free rendering at 10fps with no GC pauses.

The Studio UI includes resizable split panes with drag handles, mouse click targets, scroll regions, focus tracking, spinners, and color-coded borders. This is a real interactive application, not ASCII art.

### 3. Single Static Binary

`cargo build --release` produces one self-contained executable with no runtime dependencies. The release profile uses LTO and strip for a small binary. No Python venv, no Node modules, no system library requirements. The binary includes a self-updater that downloads a new version from GitHub and replaces itself.

### 4. Startup Time

The binary launches in ~5ms. A comparable Python app would spend ~150ms just on imports before doing anything. For a CLI tool you invoke frequently, this matters.

## What About Python?

Python would work fine for the **headless build loop** (`--no-tui` mode). That's just: read a file, build a prompt, shell out to `claude`, parse JSON, shell out to `git`. Python excels at this.

The tipping point is the **interactive TUI with concurrent PTY multiplexing**:

| Concern | Python | Rust |
|---|---|---|
| Two agents writing output at once | GIL + threading bugs | Ownership prevents races at compile time |
| 10fps render loop | GC pauses cause flicker | Zero-cost, no GC |
| PTY read + event loop + render | Messy asyncio/thread mix | `tokio::spawn_blocking` + `mpsc` channels |
| Distribution | venv / PyInstaller / pip | Single static binary |
| Bad state at runtime | `TypeError` at 2 AM | Compiler catches it before you ship |

Python TUI libraries (`curses`, `textual`, `rich`) can handle some of these requirements individually, but doing all of them reliably at once is where it falls apart.

## Alternatives Considered

### Go -- Very Close Second

Go is the most realistic alternative. **Bubble Tea** is an excellent TUI framework (Elm-architecture, declarative, well-maintained). Goroutines and channels make concurrency arguably easier than Rust's async. Single static binary, easy cross-compilation.

The tradeoff: no compile-time race safety (you'd rely on `go vet` and the `-race` flag, which catch issues at runtime instead). Error handling is more verbose (`if err != nil` everywhere vs Rust's `?` operator).

If Context Foundry were started today, Go would be a perfectly valid choice. Slightly easier to write, slightly less safe.

### Zig -- Not Ready Yet

Zig produces tiny, fast binaries and compiles faster than Rust. But it has no mature TUI framework -- you'd be wrapping termios calls yourself. The async ecosystem is also immature compared to tokio. Great language, wrong ecosystem maturity for this use case today.

### C# / .NET -- Technically Capable, Culturally Mismatched

**Terminal.Gui** is arguably the most feature-rich terminal UI framework in any language, with built-in windows, dialogs, layout managers, and mouse support. `async/await` with `Channel<T>` handles concurrency cleanly. `dotnet publish` can produce a single-file binary (though 15-30MB vs Rust's ~3MB).

Would work technically, but the .NET ecosystem skews enterprise. Nobody in the CLI tooling world ships .NET.

### Others

| Language | Why not |
|---|---|
| **C/C++** | Manual memory management with concurrent PTY streams is asking for use-after-free bugs. |
| **TypeScript/Node** | Ink exists for React-in-terminal, but Node's PTY handling is fragile. Single binary distribution requires bundlers. |
| **Swift** | Terminal UI ecosystem is nearly nonexistent. Apple-ecosystem bias. |
| **Java/Kotlin** | JVM startup time and distribution story kills it for CLI tools. |

## Ranking for This Specific App

1. **Rust** -- best fit (safety + performance + ecosystem + single binary)
2. **Go** -- very close second (easier to write, slightly less safe)
3. **C#** -- distant third (would work, wrong audience)
4. Everything else -- meaningful compromises

The gap between Rust and Go is small. The gap between Go and everything else is large. Rust was chosen because the combination of compile-time safety, zero-cost concurrency, mature TUI ecosystem, and single-binary distribution is exactly what this kind of application needs.
