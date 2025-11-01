# Installation Guide

## Prerequisites

- Python 3.9 or higher
- Context Foundry installed and working
- Git (for version control)

## Installation Steps

### 1. Locate Context Foundry Installation

Find your Context Foundry installation directory:

```bash
# Usually one of these locations:
cd ~/homelab/context-foundry          # Typical location
cd /usr/local/context-foundry         # System installation
cd ~/.context-foundry                 # User installation
```

### 2. Create Extensions Directory

If it doesn't exist, create the extensions directory:

```bash
mkdir -p extensions
```

### 3. Install Flowise Extension

Clone or copy the Flowise extension:

```bash
cd extensions
git clone <repository-url> flowise

# Or copy from local source:
cp -r /path/to/flowise-extension flowise
```

### 4. Verify Installation

```bash
cd flowise
python3 -m unittest discover tests/ -v
```

Expected output:
```
Ran 44 tests in 0.004s

OK
```

### 5. Test Detection

Create a test Flowise JSON file and run detector:

```bash
python3 detector.py tests/fixtures/supervisor_multi_agent.json
```

Expected output:
```
Flowise Flow Detection Results:
==================================================
Is Flowise Flow: True
Flow Type: multi-agent
Complexity: complex
Nodes: 5
...
```

## Integration with Context Foundry

### Step 1: MCP Server Integration

1. Open `context-foundry/mcp_server.py`

2. Locate the `_detect_existing_codebase()` method (around line 250-300)

3. Add the code from `integration/mcp_server_hook.py`:

```python
# FLOWISE EXTENSION HOOK
try:
    import sys
    from pathlib import Path

    cf_base = Path(__file__).parent.parent
    flowise_ext_path = cf_base / 'extensions' / 'flowise'

    if flowise_ext_path.exists():
        ext_parent = str(flowise_ext_path.parent)
        if ext_parent not in sys.path:
            sys.path.insert(0, ext_parent)

        from flowise import extensions_loader

        flowise_detectors = extensions_loader.load_extension_detectors()

        if flowise_detectors and 'flowise' in flowise_detectors:
            json_files = list(directory.glob("*.json"))

            for json_file in json_files[:10]:
                try:
                    detection = flowise_detectors['flowise'].detect_flowise_flow(json_file)

                    if detection.get('is_flowise'):
                        project_indicators['flowise_flow'] = True
                        project_indicators['flowise_flow_type'] = detection.get('flow_type')
                        project_indicators['flowise_complexity'] = detection.get('complexity')

                        if project_type is None or confidence != 'high':
                            project_type = 'flowise-workflow'
                            confidence = 'high'

                        if 'flowise' not in languages:
                            languages.append('flowise')

                        project_files.append(str(json_file))
                        break

                except Exception as e:
                    continue

except ImportError:
    pass
except Exception as e:
    pass
# END FLOWISE EXTENSION HOOK
```

### Step 2: Orchestrator Prompt Integration

1. Open `context-foundry/orchestrator_prompt.txt`

2. Find Scout phase section (around line 470)

3. Add after Scout phase introduction:

```
**IF FLOWISE FLOW DETECTED** (check project_indicators['flowise_flow']):

Load Flowise Scout enhancements from extensions/flowise/prompts/scout-enhancement.txt
```

4. Find Architect phase section (around line 636)

5. Add after Architect phase introduction:

```
**IF FLOWISE FLOW DETECTED**:

Load Flowise Architect enhancements from extensions/flowise/prompts/architect-enhancement.txt
Load pattern library from extensions/flowise/patterns/flowise-expertise.json
```

See `integration/orchestrator_prompt_injection.txt` for complete code examples.

### Step 3: Verify Integration

1. Create a test project with Flowise JSON:

```bash
mkdir ~/test-flowise-project
cd ~/test-flowise-project
cp ~/path/to/flowise-extension/tests/fixtures/supervisor_multi_agent.json ./
```

2. Run Context Foundry:

```bash
cf build "Analyze this Flowise workflow"
```

3. Check Scout report for Flowise mentions:

```bash
cat .context-foundry/scout-report.md | grep -i flowise
```

Expected: Flowise flow type and analysis should appear

## Troubleshooting

### Extension Not Found

**Symptom**: ImportError when loading extension

**Solution**:
1. Verify path: `ls -la ~/homelab/context-foundry/extensions/flowise/`
2. Check Python path includes extensions directory
3. Ensure `__init__.py` exists in flowise directory

### Tests Failing

**Symptom**: unittest errors

**Solution**:
1. Check Python version: `python3 --version` (must be 3.9+)
2. Verify fixtures exist: `ls tests/fixtures/`
3. Run individual test to isolate: `python3 -m unittest tests.test_detector.TestFlowiseDetector.test_detect_valid_rag_flow`

### Pattern Files Not Loading

**Symptom**: `load_extension_patterns()` returns None

**Solution**:
1. Remove `.example` extension: `mv patterns/flowise-expertise.json.example patterns/flowise-expertise.json`
2. Verify JSON is valid: `python3 -c "import json; json.load(open('patterns/flowise-expertise.json'))"`

### Integration Not Working

**Symptom**: Flowise flows not detected by Context Foundry

**Solution**:
1. Test detector manually: `python3 detector.py path/to/flow.json`
2. Check MCP server logs for import errors
3. Verify conditional checks in orchestrator prompt
4. Ensure `project_indicators` are being set correctly

## Uninstallation

To remove the extension:

```bash
cd ~/homelab/context-foundry/extensions
rm -rf flowise
```

Remove integration code from:
- `mcp_server.py` (remove FLOWISE EXTENSION HOOK block)
- `orchestrator_prompt.txt` (remove Flowise conditional blocks)

## Upgrading

To upgrade to a new version:

```bash
cd ~/homelab/context-foundry/extensions/flowise
git pull origin main

# Or replace with new version:
cd ~/homelab/context-foundry/extensions
rm -rf flowise
cp -r /path/to/new/flowise-extension flowise

# Always test after upgrade:
cd flowise
python3 -m unittest discover tests/ -v
```

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review integration documentation
3. Test components individually (detector, analyzer, loader)
4. Check Context Foundry logs for errors

## Next Steps

After installation:
1. Read [USAGE.md](USAGE.md) for usage examples
2. Review [API.md](API.md) for programming interface
3. Explore [PATTERNS.md](PATTERNS.md) for Flowise pattern library
4. See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
