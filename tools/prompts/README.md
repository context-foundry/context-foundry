# Context Foundry Prompt Management

This directory manages versioned prompts for Context Foundry's autonomous agents.

## 🆕 Modular Prompt Architecture

The orchestrator prompt now uses a **modular architecture** for easier maintenance:

```
prompts/
├── README.md                          # This file
├── VERSIONS.md                        # Version history and changelog
├── build_orchestrator_prompt.py       # Builder script (combines modules)
├── phase_loader.py                    # Runtime phase loader
├── orchestrator_header.txt            # Common sections (git, BAML, etc.)
├── orchestrator_footer.txt            # Final output, rules, error handling
├── phase_0_codebase_analysis.md       # Phase 0: Codebase Analysis
├── phase_1_scout.md                   # Phase 1: Scout
├── phase_2_architect.md               # Phase 2: Architect
├── phase_2_5_parallel_build.md        # Phase 2.5: Parallel Build
├── phase_3_5_integration_precheck.md  # Phase 3.5: Integration Pre-check
├── phase_4_test.md                    # Phase 4: Test
├── phase_4_5_screenshot.md            # Phase 4.5: Screenshot
├── phase_5_documentation.md           # Phase 5: Documentation
├── phase_6_deployment.md              # Phase 6: Deployment
├── phase_7_feedback.md                # Phase 7: Feedback
├── phase_7_5_github.md                # Phase 7.5: GitHub Integration
└── archive/                           # All archived prompt versions
    ├── orchestrator_prompt_v1.0.0_baseline.txt
    └── ...
```

### Benefits of Modular Structure

1. **Easier Editing**: Edit individual phases without scrolling through 3,000+ lines
2. **Reduced Conflicts**: Multiple people can edit different phases simultaneously
3. **Better Organization**: Clear separation between phases and common sections
4. **Maintainability**: Changes to one phase don't affect others
5. **Smaller Base Size**: Core prompt is smaller, phases loaded on demand
6. **Flowise Integration**: Seamlessly adds Flowise enhancements per phase

### Building the Orchestrator Prompt

The modular files are combined into `tools/orchestrator_prompt.txt` using:

```bash
# Build with all enhancements (default)
python3 tools/prompts/build_orchestrator_prompt.py

# Build without Flowise enhancements
python3 tools/prompts/build_orchestrator_prompt.py --no-flowise

# Dry run (test without writing)
python3 tools/prompts/build_orchestrator_prompt.py --dry-run

# Build to custom location
python3 tools/prompts/build_orchestrator_prompt.py -o /path/to/output.txt
```

### Editing Workflow

1. **Edit a phase**: Modify the appropriate `phase_*.md` file
2. **Edit common sections**: Modify `orchestrator_header.txt` or `orchestrator_footer.txt`
3. **Rebuild**: Run `python3 tools/prompts/build_orchestrator_prompt.py`
4. **Test**: Run Flowise detection tests or full build tests

**IMPORTANT**: Always rebuild after editing modular files! The runtime uses `tools/orchestrator_prompt.txt`.

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
