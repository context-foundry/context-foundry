# Context Foundry Prompt Management

This directory manages versioned prompts for Context Foundry's autonomous agents.

## Directory Structure

```
prompts/
├── README.md                      # This file
├── VERSIONS.md                    # Version history and changelog
├── OPTIMIZATION_ANALYSIS.md       # Optimization opportunities and analysis
├── switch_version.sh              # Script to switch between versions
└── archive/                       # All archived prompt versions
    ├── orchestrator_prompt_v1.0.0_baseline.txt
    ├── github_agent_prompt_v1.0.0_baseline.txt
    └── ...
```

## Quick Start

### List Available Versions
```bash
./switch_version.sh list
```

### Switch to a Version
```bash
./switch_version.sh switch v1.0.0
```

### Backup Current Version
```bash
./switch_version.sh backup my-experiment
```

### Compare Versions
```bash
./switch_version.sh compare v1.0.0 v1.1.0
```

## Version Naming Convention

Format: `vMAJOR.MINOR.PATCH_description`

Examples:
- `v1.0.0_baseline` - Initial baseline version
- `v1.1.0_quick-wins` - Phase 1 optimizations
- `v1.2.0_restructure` - Phase 2 optimizations
- `v2.0.0_modular` - Major architectural change

## Creating a New Version

1. **Make changes** to `tools/orchestrator_prompt.txt`
2. **Update version** in prompt header:
   ```
   Version: v1.1.0 (Quick Wins)
   ```
3. **Archive the version:**
   ```bash
   cp tools/orchestrator_prompt.txt tools/prompts/archive/orchestrator_prompt_v1.1.0_quick-wins.txt
   ```
4. **Update VERSIONS.md** with changes and metrics
5. **Git tag** the version:
   ```bash
   git tag -a prompt-v1.1.0 -m "Prompt v1.1.0: Quick wins optimization"
   git push --tags
   ```

## Performance Tracking

Each build's `session-summary.json` tracks which prompt version was used:

```json
{
  "prompt_metadata": {
    "orchestrator_version": "v1.1.0",
    "orchestrator_tokens": 9800,
    "github_agent_version": "v1.0.0"
  }
}
```

Track metrics over time to compare version performance:
- Build success rate
- Average test iterations
- Average duration
- Common failure patterns

## Rollback Procedure

If a new version causes issues:

```bash
# Option 1: Use switcher script
./switch_version.sh switch v1.0.0

# Option 2: Manual rollback
cp tools/prompts/archive/orchestrator_prompt_v1.0.0_baseline.txt tools/orchestrator_prompt.txt
```

## Optimization Guidelines

See `OPTIMIZATION_ANALYSIS.md` for detailed analysis.

### Safe Optimizations (Low Risk)
- Remove redundant boilerplate
- Consolidate repeated instructions
- Delete deprecated sections
- Reduce emphasis overuse (CRITICAL, ⚠️)

### Medium Risk Optimizations
- Restructure sections
- Move examples to appendix
- Create reference macros
- Compress verbose explanations

### High Risk Optimizations
- Change instruction semantics
- Remove entire sections
- Split into multiple prompts
- Create dynamic loading system

## Testing New Versions

1. **Create backup** of current version
2. **A/B test** new version on 5-10 builds
3. **Compare metrics** against baseline
4. **Keep better performer** or iterate

## Current Version

Active: `v1.0.0 (Baseline)`
- Orchestrator: 1996 lines, ~12,000 tokens
- GitHub Agent: ~800 lines, ~2,500 tokens

See `VERSIONS.md` for full history.
