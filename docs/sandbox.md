# Docker Sandbox Isolation

Context Foundry can run agent subprocesses inside Docker containers, isolating them from the host filesystem. Only the project directory is mounted into the container.

## Prerequisites

- Docker Engine or Docker Desktop installed and running
- The `docker` CLI must be on PATH
- The sandbox image must be built locally

## Setup

1. Build the sandbox image:

   ```bash
   # Unix/macOS
   ./docker/build-sandbox.sh

   # Windows (PowerShell)
   .\docker\build-sandbox.ps1
   ```

2. Verify the image exists:

   ```bash
   docker image inspect foundry-sandbox:latest
   ```

3. Run Foundry normally. Sandbox is enabled by default when Docker and the image are detected.

## Configuration

Add these fields to `.foundry.json` or `~/.foundry/config.json`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sandbox` | bool | `true` | Enable/disable sandbox isolation |
| `sandbox_image` | string | `"foundry-sandbox:latest"` | Docker image name for sandbox containers |
| `sandbox_extra_mounts` | string[] | `[]` | Additional bind mounts (e.g. `["/data:/data:ro"]`) |

### Disabling Sandbox

```json
{
  "sandbox": false
}
```

### Custom Image

```json
{
  "sandbox_image": "my-registry/custom-sandbox:v2"
}
```

### Extra Mounts

```json
{
  "sandbox_extra_mounts": [
    "/home/user/.cache:/cache:ro",
    "/shared/data:/data"
  ]
}
```

## How It Works

When sandbox is active, Foundry wraps each agent subprocess in a `docker run` command:

```
# Without sandbox:
claude -p "prompt" --dangerously-skip-permissions --output-format stream-json

# With sandbox:
docker run --rm -i \
  -v /path/to/project:/work \
  -w /work \
  -e ANTHROPIC_API_KEY \
  foundry-sandbox:latest \
  claude -p "prompt" --dangerously-skip-permissions --output-format stream-json
```

Key behaviors:

- **Project mount**: The project directory is bind-mounted to `/work` inside the container
- **API key forwarding**: `ANTHROPIC_API_KEY` is passed through automatically
- **Fresh containers**: Each agent invocation gets a new container (`--rm` flag)
- **PTY forced**: Sandbox mode forces the PTY backend (tmux is incompatible with containerized agents)
- **Extra mounts**: Additional directories can be mounted via `sandbox_extra_mounts`

## TUI Indicators

- **Running header**: Shows `[sandboxed]` (green) or `[unsandboxed]` (yellow) badge
- **Dashboard stats**: Shows sandbox status with image name when active
- **Startup status bar**: Shows `[sandbox: on]` or `[sandbox: off]`

## Status Detection

Foundry checks sandbox availability at startup:

| Status | Condition | Behavior |
|--------|-----------|----------|
| **Active** | Docker found + image found + config enabled | Agents run in containers |
| **Docker not found** | `docker` not on PATH | Warning logged, agents run unsandboxed |
| **Image not found** | Docker available but image not built | Warning logged, agents run unsandboxed |
| **Disabled** | `sandbox: false` in config | No Docker checks, agents run directly |

## Troubleshooting

### "sandbox image not found"

Build the image:
```bash
./docker/build-sandbox.sh
```

### "Docker not found"

Ensure Docker is installed and the `docker` CLI is on your PATH:
```bash
docker --version
```

### Agent fails inside container

Check that the sandbox image has the required tools:
```bash
docker run --rm foundry-sandbox:latest claude --version
docker run --rm foundry-sandbox:latest git --version
```

### Windows path issues

Docker Desktop on Windows requires paths in `/c/Users/...` format. Foundry handles this translation automatically for the project directory mount. If you use `sandbox_extra_mounts`, provide Unix-style paths.

## Security Model

The sandbox provides filesystem isolation only:

- Agents can only access the project directory (mounted at `/work`)
- Agents cannot access the host filesystem outside of explicit mounts
- Each agent runs in a fresh container with no persistent state
- Network access is unrestricted (agents need to call the Anthropic API)
- The `ANTHROPIC_API_KEY` environment variable is forwarded into the container

The sandbox does NOT provide:
- Network isolation (agents need API access)
- Resource limits (CPU/memory) -- add these via Docker if needed
- User namespace isolation -- containers run as root by default inside the image
- Protection against malicious Docker images -- only use trusted images
