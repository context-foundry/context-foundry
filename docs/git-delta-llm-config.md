# git-delta Configuration for LLM-Optimized Diff Parsing

Context Foundry agents read git diffs during Scout and Doubt stages. Configuring
git-delta properly improves the quality of AI-generated reviews by making diffs
unambiguous and token-efficient.

## Install

```bash
# macOS
brew install git-delta

# Linux
cargo install git-delta
```

## Recommended .gitconfig

Add to `~/.gitconfig`:

```ini
[core]
    pager = delta

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    line-numbers = true
    side-by-side = false
    syntax-theme = none
    file-style = bold yellow
    hunk-header-style = omit
    minus-style = red
    plus-style = green
    zero-style = dim syntax
    line-numbers-minus-style = red
    line-numbers-plus-style = green
    max-line-length = 512

[merge]
    conflictstyle = diff3

[diff]
    colorMoved = default
```

## Why these settings

| Setting | Reason |
|---------|--------|
| `line-numbers = true` | Gives LLMs unambiguous line references for findings |
| `side-by-side = false` | LLMs parse unified diffs better than side-by-side |
| `syntax-theme = none` | Reduces ANSI noise when output is captured as text |
| `hunk-header-style = omit` | Removes decorative `@@` lines that waste tokens |
| `navigate = true` | Adds file-level markers (`n`/`N` navigation in pager) |
| `max-line-length = 512` | Prevents truncation of wide lines in generated code |

## When agents read diffs without delta

If delta is not installed, agents fall back to plain `git diff` output. This works
but produces noisier context. The settings above are recommendations, not requirements.

## Verifying

```bash
# Check delta is active
git config core.pager
# Should output: delta

# Test with a small diff
echo "test" >> /tmp/test.txt && git diff
```
