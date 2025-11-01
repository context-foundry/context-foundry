# Usage Guide

## Quick Start

The Flowise extension works automatically when Context Foundry detects Flowise JSON files in your project.

### Automatic Detection

When you run Context Foundry on a project containing Flowise flows:

```bash
cd your-flowise-project/
cf build "Improve my multi-agent workflow"
```

The extension automatically:
1. Detects Flowise JSON files
2. Classifies flow type (multi-agent, RAG, workflow, chatbot)
3. Enhances Scout with Flowise research checklist
4. Enhances Architect with proven patterns

No configuration needed!

## Manual Flow Detection

### Detect Single Flow

```bash
python3 detector.py path/to/flow.json
```

Example output:
```
Flowise Flow Detection Results:
==================================================
Is Flowise Flow: True
Flow Type: multi-agent
Complexity: moderate
Nodes: 8
Edges: 10
Agents: 3
Has Memory: True
Has Tools: True
Expertise Level: advanced
```

### Scan Directory for Flows

```python
from pathlib import Path
import detector

json_files = detector.scan_directory(Path('./flows'))

for json_file in json_files:
    result = detector.detect_flowise_flow(json_file)
    if result['is_flowise']:
        print(f"Found {result['flow_type']} flow: {json_file}")
```

## Template Analysis

### Analyze Single Template

```bash
python3 analyzer.py --analyze templates/SupervisorAgent.json
```

Output:
```
✅ Analysis successful: templates/SupervisorAgent.json
Nodes: 8
Edges: 10

Node Patterns:
  - AgentExecutor: 3 occurrences
  - LLMChain: 2 occurrences
  - BufferMemory: 1 occurrences

Connection Patterns:
  - supervisor-to-worker: AgentExecutor → AgentExecutor
  - agent-to-tool: AgentExecutor → CustomTool
```

### Analyze All Templates

```bash
python3 analyzer.py --analyze-all templates/
```

Output:
```
✅ Analyzed 12/15 files

Most Common Node Types:
  - AgentExecutor: 45 occurrences
  - LLMChain: 32 occurrences
  - VectorStoreRetriever: 18 occurrences
  - BufferMemory: 12 occurrences
  - CustomTool: 8 occurrences

Most Common Connection Patterns:
  - supervisor-to-worker: 23 occurrences
  - retrieval-to-llm: 18 occurrences
  - agent-to-tool: 15 occurrences
  - memory-to-conversation: 12 occurrences
```

### Export Patterns to JSON

```bash
python3 analyzer.py --analyze-all templates/ --export-patterns patterns/my-patterns.json
```

This creates a structured pattern file you can use for:
- Documenting best practices
- Training Context Foundry
- Sharing with team members

## Pattern Library

### Load Patterns Programmatically

```python
from flowise import extensions_loader

# Load pattern library
patterns = extensions_loader.load_extension_patterns('flowise')

if patterns:
    for pattern in patterns['patterns']:
        print(f"Pattern: {pattern['pattern_id']}")
        print(f"  Category: {pattern['category']}")
        print(f"  Applies to: {', '.join(pattern['applies_to'])}")
        print(f"  Best practices: {len(pattern['best_practices'])}")
        print()
```

### Filter Patterns by Flow Type

```python
patterns = extensions_loader.load_extension_patterns('flowise')

# Get patterns for RAG flows
rag_patterns = [
    p for p in patterns['patterns']
    if 'rag' in p['applies_to']
]

for pattern in rag_patterns:
    print(f"RAG Pattern: {pattern['pattern_id']}")
    print(f"  Description: {pattern['description']}")
```

### Load Flow Templates

```python
templates = extensions_loader.load_flow_templates()

if templates:
    # Get multi-agent templates
    multi_agent = templates['templates']['multi-agent']

    for template in multi_agent:
        print(f"Template: {template['name']}")
        print(f"  Complexity: {template['complexity']}")
        print(f"  Best for: {template['best_for']}")
```

## Working with Prompts

### Load Enhancement Prompts

```python
# Get Scout enhancement
scout_prompt = extensions_loader.get_extension_prompt('flowise', 'scout')

# Get Architect enhancement
architect_prompt = extensions_loader.get_extension_prompt('flowise', 'architect')

# Use in your workflow
if scout_prompt:
    # Format with flow details
    enhanced = scout_prompt.format(
        flow_type='multi-agent',
        complexity='moderate',
        node_count=8,
        agent_count=3,
        has_memory=True,
        has_tools=True
    )
    print(enhanced)
```

## Integration Examples

### Custom Detector

```python
from flowise import extensions_loader
from pathlib import Path

# Load detectors
detectors = extensions_loader.load_extension_detectors()

if detectors and 'flowise' in detectors:
    detector = detectors['flowise']

    # Check a file
    result = detector.detect_flowise_flow(Path('flow.json'))

    if result['is_flowise']:
        # Get appropriate patterns
        patterns = extensions_loader.load_extension_patterns('flowise')

        # Filter patterns for this flow type
        flow_type = result['flow_type']
        applicable = [
            p for p in patterns['patterns']
            if flow_type in p['applies_to']
        ]

        print(f"Found {len(applicable)} patterns for {flow_type} flows")
```

### Batch Analysis

```python
import detector
import analyzer
from pathlib import Path

# Scan for all Flowise flows
flows_dir = Path('./flowise-flows')
json_files = detector.scan_directory(flows_dir)

results = {
    'multi-agent': [],
    'rag': [],
    'workflow': [],
    'chatbot': [],
    'unknown': []
}

# Classify all flows
for json_file in json_files:
    detection = detector.detect_flowise_flow(json_file)
    if detection['is_flowise']:
        flow_type = detection['flow_type']
        results[flow_type].append(str(json_file))

# Print summary
for flow_type, files in results.items():
    if files:
        print(f"\n{flow_type.upper()} flows ({len(files)}):")
        for f in files:
            print(f"  - {f}")
```

## Common Use Cases

### 1. Flow Quality Assessment

Analyze a flow and check against quality benchmarks:

```python
detection = detector.detect_flowise_flow(Path('my-flow.json'))

if detection['is_flowise']:
    print(f"Flow Type: {detection['flow_type']}")
    print(f"Complexity: {detection['complexity']}")
    print(f"Expertise Level: {detection['expertise_level']}")

    # Load patterns to check best practices
    patterns = extensions_loader.load_extension_patterns('flowise')

    # Find relevant patterns
    flow_patterns = [
        p for p in patterns['patterns']
        if detection['flow_type'] in p['applies_to']
    ]

    print(f"\nRecommended Best Practices:")
    for pattern in flow_patterns:
        for bp in pattern['best_practices']:
            print(f"  ✓ {bp}")
```

### 2. Flow Comparison

Compare complexity of multiple flows:

```python
import json

flows = [
    'flow1.json',
    'flow2.json',
    'flow3.json'
]

for flow_file in flows:
    result = detector.detect_flowise_flow(Path(flow_file))
    if result['is_flowise']:
        print(f"{flow_file}:")
        print(f"  Type: {result['flow_type']}")
        print(f"  Complexity: {result['complexity']}")
        print(f"  Nodes: {result['node_count']}")
        print(f"  Agents: {result['agent_count']}")
```

### 3. Pattern Extraction from Team's Flows

Extract common patterns from your team's Flowise flows:

```bash
# Analyze all team flows
python3 analyzer.py --analyze-all team-flows/ --export-patterns team-patterns.json

# Now you have a custom pattern library for your team!
```

### 4. Pre-deployment Validation

Before deploying a Flowise flow:

```python
# Check flow structure
detection = detector.detect_flowise_flow(Path('production-flow.json'))

if not detection['is_flowise']:
    print("ERROR: Invalid Flowise flow")
    exit(1)

if detection['complexity'] == 'complex':
    print("WARNING: Complex flow - ensure thorough testing")

if not detection['has_memory'] and detection['flow_type'] == 'chatbot':
    print("WARNING: Chatbot without memory")

print("✅ Flow structure validated")
```

## Advanced Usage

### Custom Pattern Matching

```python
# Define custom pattern
custom_pattern = {
    "pattern_id": "my-custom-pattern",
    "category": "architecture",
    "description": "My organization's standard pattern",
    "applies_to": ["multi-agent"],
    "best_practices": [...]
}

# Load existing patterns
patterns = extensions_loader.load_extension_patterns('flowise')

# Add custom pattern
if patterns:
    patterns['patterns'].append(custom_pattern)

# Save back
analyzer.export_patterns(patterns, Path('my-patterns.json'))
```

### Integration with CI/CD

```bash
#!/bin/bash
# validate-flows.sh

for flow in flows/*.json; do
    python3 detector.py "$flow" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "FAIL: $flow is not a valid Flowise flow"
        exit 1
    fi
done

echo "✅ All flows validated"
```

## Tips & Best Practices

1. **Cache Pattern Library**: Load patterns once and reuse
2. **Batch Processing**: Process multiple flows together for efficiency
3. **Version Control**: Store extracted patterns in git
4. **Team Sharing**: Export patterns for team collaboration
5. **Validation**: Always validate flows before deployment

## Error Handling

```python
from flowise import extensions_loader

try:
    detectors = extensions_loader.load_extension_detectors()

    if not detectors:
        print("Extension not installed - graceful degradation")
        # Continue with normal operation

    elif 'flowise' in detectors:
        result = detectors['flowise'].detect_flowise_flow(path)
        # Process result

except Exception as e:
    print(f"Error: {e}")
    # Handle error appropriately
```

## Next Steps

- Review [API.md](API.md) for complete API reference
- See [PATTERNS.md](PATTERNS.md) for pattern library details
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for technical implementation
