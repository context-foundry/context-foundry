# GitHub Actions Workflows

## CI (`ci.yml`)

Runs `cargo check`, `cargo test`, and `cargo clippy` on every push to `main` and on pull requests targeting `main`.

## Release (`release.yml`)

Builds signed binaries for all platforms and publishes a GitHub Release when a `v*` tag is pushed.

## Foundry PR Review (`foundry-review.yml`)

Automated code review powered by [Context Foundry](https://github.com/context-foundry/context-foundry). Runs the foundry reviewer agent against every PR diff and posts findings as a PR comment.

### Trigger

Runs on `pull_request` events: `opened` and `synchronize` (new pushes to an open PR).

### Required Secrets

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | API key for Claude. Required for the reviewer agent to function. Must be added as a repository secret in Settings > Secrets and variables > Actions. |

`GITHUB_TOKEN` is provided automatically by GitHub Actions and does not need manual configuration. The workflow uses it to post PR comments via `gh pr comment`.

### Configuration

The following environment variables can be set as **GitHub repository variables** (Settings > Secrets and variables > Actions > Variables tab) to customize review behavior:

| Variable | Description | Default |
|----------|-------------|---------|
| `FOUNDRY_PR_REVIEW_MODEL` | Model for PR review (e.g., `"opus"`, `"sonnet"`) | Foundry default |
| `FOUNDRY_PR_REVIEW_PROVIDER` | Provider for PR review (`"claude"` or `"codex"`) | Foundry default |
| `FOUNDRY_AGENT_TIMEOUT_SECS` | Agent timeout in seconds (e.g., `"900"`) | Foundry default |
| `FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD` | File count threshold for multi-pass review | Foundry default |

These are repository **variables** (not secrets) because they contain no sensitive data.

### Behavior

1. Checks out the PR at the head commit.
2. Downloads and installs the latest `foundry` binary from GitHub Releases.
3. Runs `foundry review-pr <PR_NUMBER> --repo <OWNER/REPO> --output comment --ignore-project-config`, which:
   - Fetches the PR diff and metadata via `gh`
   - Runs a Claude-powered reviewer agent against the changes
   - Posts the review findings as a PR comment
   - Uses `--ignore-project-config` to prevent the PR checkout's config files from influencing review behavior (security measure against untrusted CLAUDE.md / .claude/rules/ in PRs)
4. If `foundry review-pr` fails (non-zero exit), a fallback comment is posted indicating the review could not complete. The workflow itself does not fail -- the PR is not blocked.
5. If the PR changes more files than the `FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD`, the reviewer automatically uses a multi-pass strategy: per-file analysis followed by an integration review that catches cross-file issues.

### Concurrency

The workflow uses a concurrency group keyed on the PR number with `cancel-in-progress: true`. When multiple commits are pushed to the same PR in quick succession, only the most recent push triggers a review -- earlier in-progress runs are cancelled. This prevents duplicate review comments and reduces API costs.

### Disabling for Specific PRs

Add the **`skip-foundry-review`** label to a PR before opening it (or before pushing a synchronize event) to skip the review. The workflow checks for this label and exits early if present.

To create the label: go to the repository's Issues > Labels > New label, name it `skip-foundry-review`.

### Cost

Each PR review invokes one Claude agent session. Approximate cost depends on the size of the diff:
- Small PRs (< 200 lines changed): ~$0.05-0.15
- Medium PRs (200-1000 lines): ~$0.15-0.50
- Large PRs (1000+ lines): ~$0.50-2.00

The review runs on every `synchronize` event (every push to the PR branch). To limit cost on active PRs with frequent pushes, consider adding the `skip-foundry-review` label during active development and removing it when the PR is ready for review.

## Pages (`pages.yml`)

Deploys static content to GitHub Pages.

## Living Gallery (`living-gallery.yml`)

Automated living gallery updates.

## Release Desktop (`release-desktop.yml`)

Builds and releases the desktop application.
