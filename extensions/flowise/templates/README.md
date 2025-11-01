# Flowise Templates Directory

This directory stores Flowise agent flow templates for pattern analysis and expertise building.

## How to Export Flows from Your Flowise Installation

### Method 1: Export from Flowise UI (Recommended)
1. Open your Flowise instance in browser
2. Navigate to **Agentflows** section
3. For each flow you want to export:
   - Click on the flow to open it
   - Click the **Export** button (usually top-right)
   - Save the `.json` file to this directory

### Method 2: Export from Flowise Database
If you have direct access to your Flowise installation:

```bash
# Navigate to your Flowise installation directory
cd /path/to/your/flowise

# Copy the chatflow JSON files from the database export
# (Path varies depending on your Flowise setup)
```

### Method 3: API Export
If you have Flowise API access:

```bash
# Export all flows via API (requires API key)
curl -X GET http://localhost:3000/api/v1/chatflows \
  -H "Authorization: Bearer YOUR_API_KEY" \
  | jq '.[] | {id, name, flowData}' > template-name.json
```

## File Naming Convention

Use descriptive names for your templates:
- `chatbot-simple.json` - Basic chatbot flow
- `rag-qa-system.json` - RAG Q&A system
- `multi-agent-research.json` - Multi-agent research workflow
- `tool-calling-agent.json` - Agent with tool integration
- etc.

## Expected Template Count

Target: **14 agent flow templates** from your Flowise installation

These templates mentioned in your Flowise Agentflows:
- Multi-agent systems
- Workflow orchestration
- [Other templates from your list]

## Next Steps After Downloading

Once you've placed all 14 templates here:

1. **Analyze templates** to extract patterns:
   ```bash
   cd extensions/flowise/
   python3 analyzer.py --analyze-all templates/
   ```

2. **Export learned patterns**:
   ```bash
   python3 analyzer.py --export-patterns patterns/flowise-expertise.json
   ```

3. **Verify patterns** were learned:
   ```bash
   cat patterns/flowise-expertise.json
   ```

## Template Structure

Expected Flowise JSON structure:
```json
{
  "nodes": [
    {
      "id": "node_id",
      "data": {
        "label": "Node Label",
        "name": "nodeName",
        "type": "NodeType"
      }
    }
  ],
  "edges": [
    {
      "source": "source_node_id",
      "target": "target_node_id"
    }
  ],
  "chatflowid": "flow_id"
}
```
