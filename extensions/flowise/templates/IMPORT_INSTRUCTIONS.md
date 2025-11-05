# How to Import Context Foundry Chat Interface

## Quick Import Steps

### 1. Load the Flow

1. Open Flowise UI (http://localhost:3000 or your deployed URL)
2. Click **"Agentflows"** in the left sidebar
3. Click **"+ Add New"** button (top right)
4. Click **"Load Agentflow"** button
5. Select file: `context-foundry-chat-interface.json`
6. The flow will load with 2 nodes:
   - **Chat Start** (green start node)
   - **Context Foundry Assistant** (blue agent node)

### 2. Configure API Credentials

The flow imports with empty credentials. You MUST add your API key:

1. Click on the **"Context Foundry Assistant"** node
2. Scroll to **"Model"** section
3. Click **"Credential"** dropdown
4. Select **"+ Add New Credential"**
5. Choose credential type:
   - **Anthropic API** (for Claude) - Recommended
   - **OpenAI API** (for GPT-4)
   - **Google GenerativeAI API** (for Gemini)
6. Enter your API key
7. Click **"Save"**

**Get API Keys:**
- Anthropic: https://console.anthropic.com/settings/keys
- OpenAI: https://platform.openai.com/api-keys
- Google: https://aistudio.google.com/apikey

### 3. Add Context Foundry MCP Tools

The flow imports without tools configured. You MUST add MCP tools:

#### Option A: Local Development (stdio transport)

1. In the agent node, scroll to **"Tools"** section
2. Click **"+ Add Item"** in the Tools array
3. For each tool you want to add:
   - Click **"Tool"** dropdown
   - Look for MCP tools (if MCP integration is set up in Flowise)
   - Or manually add custom tools

**Note**: MCP tool integration in Flowise is still evolving. If you don't see MCP tools in the dropdown, you may need to:
- Configure MCP servers in Flowise settings first
- Or use custom tools with function calling
- Or wait for MCP support in your Flowise version

#### Option B: Use Custom Tools (Workaround)

If MCP tools aren't available in your Flowise version:

1. Create custom tools for each Context Foundry function
2. Use Function Calling to connect to Context Foundry API
3. See: [Creating Custom Tools Guide](../docs/CUSTOM_TOOLS_WORKAROUND.md)

### 4. Adjust Model Settings (Optional)

Default settings:
- **Model**: Claude Sonnet 4.5
- **Temperature**: 0.7
- **Max Tokens**: 4096
- **Streaming**: true

To change:
1. Click agent node
2. Modify settings in **"Model"** section
3. For different model, change **"Model Name"**:
   - Claude: `claude-sonnet-4-5-20250929`
   - GPT-4o: `gpt-4o`
   - GPT-4o-mini: `gpt-4o-mini`

### 5. Test the Flow

1. Click **"Save Agentflow"** (top right)
2. Click **"Start Chat"** button
3. Try a test message:
   ```
   Hello! What can you help me with?
   ```

Expected response: The assistant should explain it can build apps, check status, etc.

## Common Import Issues

### Issue: "Credential is required"
**Solution**: You must add an API key (see Step 2 above). The flow imports with empty credentials intentionally so you can add your own.

### Issue: "No tools available"
**Solution**:
- MCP integration may not be set up yet
- Follow Step 3 to add MCP tools
- Or use custom tools as workaround

### Issue: "Flow loads but appears blank"
**Solution**:
- Check browser console (F12) for errors
- Ensure you're using a compatible Flowise version
- Try importing a different template first to verify Flowise is working

### Issue: "Agent doesn't respond"
**Solution**:
- Verify API key is valid and has credits
- Check credential is selected in agent node
- Look for error messages in chat window
- Check Flowise server logs

## After Import Checklist

- [ ] Flow imported successfully
- [ ] API credentials added and selected
- [ ] MCP tools configured (or custom tools added)
- [ ] Model settings reviewed
- [ ] Test chat completed successfully
- [ ] System prompt customized (optional)

## Next Steps

1. **Configure MCP Server**: Follow [CONTEXT_FOUNDRY_MCP_SETUP.md](../docs/CONTEXT_FOUNDRY_MCP_SETUP.md) for detailed MCP configuration

2. **Customize System Prompt**: Edit the agent's Messages to change behavior

3. **Add Knowledge Base**: Optionally connect document stores for RAG

4. **Deploy**: See deployment options in setup guide

## File Locations

- **Flow JSON**: `context-foundry-chat-interface.json`
- **System Prompt**: `../prompts/CONTEXT-FOUNDRY-ASSISTANT-PROMPT.md`
- **Setup Guide**: `../docs/CONTEXT_FOUNDRY_MCP_SETUP.md`
- **README**: `CONTEXT_FOUNDRY_CHAT_README.md`

## Support

If you encounter issues:

1. Check this guide first
2. Review [CONTEXT_FOUNDRY_MCP_SETUP.md](../docs/CONTEXT_FOUNDRY_MCP_SETUP.md) troubleshooting section
3. Check Flowise documentation: https://docs.flowiseai.com
4. Report issues: context-foundry GitHub repo

---

**Important Notes**:

- The flow imports with **empty credentials** by design - you add your own API key
- MCP tools must be **configured after import** - they don't auto-connect
- **Test in local environment first** before deploying to production
- Keep API keys secure - don't share the exported flow with credentials!

Happy building! 🚀
