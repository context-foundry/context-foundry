# Context Foundry Desktop

A native desktop application for macOS (and Windows) that provides a visual dashboard for the Context Foundry Daemon (cfd).

## Overview

Context Foundry Desktop is built with:
- **[Tauri 2.0](https://tauri.app/)** - Rust-based native app framework
- **React 18** - Frontend UI library
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first styling
- **Zustand** - State management
- **Recharts** - Charts and graphs

The application wraps the existing `cfd` daemon and provides:
- Visual job management dashboard
- Real-time job status monitoring
- Phase timeline visualization
- System metrics and graphs
- System tray integration

## Prerequisites

Before building the desktop app, ensure you have:

1. **Rust** (1.70+): https://rustup.rs/
2. **Node.js** (18+): https://nodejs.org/
3. **Context Foundry** installed with `cfd` available in PATH

### macOS-specific

```bash
# Install Xcode Command Line Tools
xcode-select --install
```

### Windows-specific

```bash
# Install Visual Studio Build Tools
# See: https://tauri.app/v1/guides/getting-started/prerequisites#windows
```

## Development

### Setup

```bash
# Navigate to the desktop app directory
cd apps/context-foundry-desktop

# Install dependencies
npm install

# Run in development mode
npm run tauri:dev
```

This starts:
1. Vite dev server on port 5173
2. Tauri development window with hot reload

### Project Structure

```
context-foundry-desktop/
├── src/                      # React frontend source
│   ├── api/                  # Tauri IPC API client
│   ├── components/           # Reusable UI components
│   ├── stores/               # Zustand state stores
│   ├── types/                # TypeScript type definitions
│   ├── views/                # Page components
│   │   ├── Dashboard.tsx     # Job list view
│   │   ├── JobDetail.tsx     # Job detail view
│   │   └── Metrics.tsx       # System metrics view
│   ├── styles/               # CSS styles
│   ├── App.tsx               # Main app component
│   └── main.tsx              # Entry point
├── src-tauri/                # Rust backend source
│   ├── src/
│   │   ├── lib.rs            # Main library with Tauri commands
│   │   ├── main.rs           # Binary entry point
│   │   ├── daemon.rs         # Daemon management
│   │   ├── api.rs            # HTTP API client
│   │   └── tray.rs           # System tray setup
│   ├── tests/                # Rust integration tests
│   ├── icons/                # App icons
│   ├── Cargo.toml            # Rust dependencies
│   └── tauri.conf.json       # Tauri configuration
├── scripts/                  # Build and test scripts
├── package.json              # Node.js dependencies
├── vite.config.ts            # Vite configuration
├── tailwind.config.js        # Tailwind CSS configuration
└── tsconfig.json             # TypeScript configuration
```

## Daemon Management

The desktop app manages the `cfd` daemon automatically:

### Startup Behavior

1. On app launch, checks if daemon is running via `/health` endpoint
2. If not running, spawns `cfd start` as a child process
3. Waits for daemon to become healthy (30s timeout)
4. Displays error UI if daemon fails to start

### Daemon Discovery

The app looks for `cfd` binary in these locations (in order):
1. System PATH
2. `~/Library/Application Support/ContextFoundry/bin/cfd` (macOS)
3. `~/.local/bin/cfd`
4. `/opt/homebrew/bin/cfd` (Homebrew Apple Silicon)
5. `/usr/local/bin/cfd` (Homebrew Intel)

### Configuration

Environment variables:
- `CFD_HTTP_API_PORT` - Override daemon API port (default: 8421)

## Building for Production

### macOS (.app + .dmg)

```bash
# Build release artifacts
npm run tauri:build

# Output locations:
# - App: target/release/bundle/macos/Context Foundry.app
# - DMG: target/release/bundle/dmg/Context Foundry_0.1.0_aarch64.dmg
```

### Code Signing (macOS)

For distribution, you need to sign and notarize the app:

1. Set up an Apple Developer account
2. Create a Developer ID certificate
3. Configure signing in `tauri.conf.json`:

```json
{
  "bundle": {
    "macOS": {
      "signingIdentity": "Developer ID Application: Your Name (TEAM_ID)",
      "providerShortName": "TEAM_ID"
    }
  }
}
```

4. Set environment variables:
```bash
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"
export APPLE_ID="your-apple-id@example.com"
export APPLE_PASSWORD="app-specific-password"
```

5. Build with signing:
```bash
npm run tauri:build
```

### Windows (.exe)

```bash
# Build for Windows (from Windows or cross-compile)
npm run tauri:build

# Output: target/release/bundle/msi/Context Foundry_0.1.0_x64_en-US.msi
```

For code signing on Windows, configure the certificate thumbprint in `tauri.conf.json`:

```json
{
  "bundle": {
    "windows": {
      "certificateThumbprint": "YOUR_CERT_THUMBPRINT"
    }
  }
}
```

## Testing

### Run Smoke Tests

```bash
npm run desktop:test
```

This verifies:
- npm dependencies are installed
- Rust/Cargo is available
- Tauri CLI is working
- TypeScript types are valid
- Daemon health (if running)

### Run Rust Tests

```bash
cd src-tauri
cargo test
```

## MCP Integration

The desktop app does NOT interfere with existing MCP (Model Context Protocol) workflows:

- Claude Code continues to use the `cfd` daemon via MCP tools
- The desktop app only provides a visual interface to the same daemon
- No changes to MCP tool definitions or behavior
- Both can run simultaneously

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Context Foundry Desktop                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              React Frontend (Webview)                    ││
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐          ││
│  │  │ Dashboard  │ │ Job Detail │ │  Metrics   │          ││
│  │  └────────────┘ └────────────┘ └────────────┘          ││
│  │         ▲              ▲              ▲                 ││
│  │         │    Tauri IPC Commands       │                 ││
│  └─────────┼──────────────┼──────────────┼─────────────────┘│
│            ▼              ▼              ▼                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Rust Backend (Tauri)                        ││
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐          ││
│  │  │  Daemon    │ │    API     │ │   Tray     │          ││
│  │  │  Manager   │ │   Client   │ │   Menu     │          ││
│  │  └────────────┘ └────────────┘ └────────────┘          ││
│  └─────────────────────────────────────────────────────────┘│
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (localhost:8421)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    CF Daemon (cfd)                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │   Jobs     │ │   HTTP     │ │   MCP      │              │
│  │  Manager   │ │    API     │ │  Server    │              │
│  └────────────┘ └────────────┘ └────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## Extending the UI

To add new views or features:

1. Create a new view component in `src/views/`
2. Add a route in `src/App.tsx`
3. If needed, add new Tauri commands in `src-tauri/src/lib.rs`
4. Create corresponding API functions in `src/api/daemon.ts`
5. Add state management in `src/stores/` if needed

## Troubleshooting

### App won't start

1. Check if `cfd` is installed: `which cfd`
2. Try starting daemon manually: `cfd start`
3. Check daemon logs: `~/.context-foundry/cfd/logs/cfd.log`

### Blank screen in development

1. Ensure Vite server is running on port 5173
2. Check browser console for errors
3. Verify `npm install` completed successfully

### Build fails on macOS

1. Ensure Xcode Command Line Tools are installed
2. Check Rust is up to date: `rustup update`
3. Clear build cache: `rm -rf target/`

### Icons not showing

Generate icons using Tauri's icon generator:
```bash
npx tauri icon path/to/source-icon.png
```

## License

Part of Context Foundry. See main repository for license information.
