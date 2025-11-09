# Context Foundry MCP Setup for Flowise

This guide explains how to set up the Context Foundry chat interface in Flowise, enabling users to build and manage applications through natural conversation.

## Overview

The Context Foundry Flowise integration provides a conversational interface to Context Foundry's autonomous development platform. Users can:

- Create new applications through chat
- Monitor and manage running builds
- Get real-time status updates
- Enhance existing projects
- Create Flowise flows programmatically

## Architecture

```
User Chat → Flowise Agent → Context Foundry MCP Server → Autonomous Build System
                ↓
           AI Response
```

## Prerequisites

1. **Flowise** installed and running (local or deployed)
   - Installation: https://docs.flowiseai.com/getting-started

2. **Context Foundry MCP Server** configured
   - Location: `/Users/name/homelab/context-foundry`
   - MCP server running (via Claude Code or standalone)

3. **API Keys** for your chosen LLM:
   - Anthropic API Key (for Claude models) - Recommended
   - OpenAI API Key (for GPT models)
   - Google API Key (for Gemini models)

## Installation Steps

### Step 1: Import the Flow

1. Open Flowise UI in your browser
2. Click **"Agentflows"** in the sidebar
3. Click **"Add New"** button
4. Click **"Load Agentflow"**
5. Select the file: `context-foundry/extensions/flowise/templates/context-foundry-chat-interface.json`
6. Click **"Save Agentflow"**

### Step 2: Configure the AI Model

1. Open the imported flow
2. Click on the **"Context Foundry Assistant"** agent node
3. In the **"Model"** dropdown:
   - For **Claude** (Recommended): Select `ChatAnthropic`
   - For **GPT**: Select `ChatOpenAI`
   - For **Gemini**: Select `ChatGoogleGenerativeAI`

4. Configure model settings:
   - **Model Name**:
     - Claude: `claude-sonnet-4-5-20250929` (or latest)
     - GPT: `gpt-4o` or `gpt-4o-mini`
     - Gemini: `gemini-2.0-flash-exp`
   - **Temperature**: `0.7` (balanced creativity/accuracy)
   - **Max Tokens**: `4096`
   - **Streaming**: `true` (for real-time responses)

5. Add API credentials:
   - Click **"Credentials"** dropdown
   - Select existing credential or **"+ Add New Credential"**
   - Enter your API key
   - Click **"Save"**

### Step 3: Configure Context Foundry MCP Tools

This is the critical step that connects Flowise to Context Foundry.

#### Option A: Local Development (Stdio Transport)

If running Flowise **locally** on the same machine as Context Foundry:

1. In the agent node, scroll to **"Tools"** section
2. Click **"+ Add Tool"**
3. Select **"MCP Tool"** or **"Custom Tool"**
4. Configure MCP connection:

   **Transport Type**: `stdio`

   **Command**:
   ```bash
   node
   ```

   **Args**:
   ```json
   ["/Users/name/homelab/context-foundry/mcp-server/index.js"]
   ```

   **Environment Variables** (if needed):
   ```json
   {
     "NODE_ENV": "production"
   }
   ```

5. Click **"Refresh Actions"** to load available MCP tools
6. You should see tools like:
   - `autonomous_build_and_deploy`
   - `list_delegations`
   - `get_delegation_result`
   - `stream_delegation_output`
   - `cancel_delegation`
   - `delegate_to_claude_code_async`
   - `context_foundry_status`

7. Select **all** the Context Foundry tools

#### Option B: Remote/Cloud Deployment (HTTP Transport)

If Flowise is deployed to cloud (Vercel, Railway, etc.):

**Important**: You need to expose Context Foundry MCP server via HTTP first.

1. **Set up HTTP endpoint** for Context Foundry:

   Option 1: Use ngrok for testing:
   ```bash
   cd /Users/name/homelab/context-foundry
   npx http-server-mcp --port 3001
   ngrok http 3001
   ```

   Option 2: Deploy dedicated MCP HTTP server:
   ```bash
   # Create HTTP wrapper for MCP server
   cd /Users/name/homelab/context-foundry/mcp-server
   npm install express
   node http-server.js
   ```

2. In Flowise agent node **"Tools"** section:
   - Click **"+ Add Tool"**
   - Select **"MCP Tool"** with HTTP transport

   **Transport Type**: `http` or `sse`

   **URL**:
   ```
   https://your-ngrok-url.ngrok.io/mcp
   ```
   Or your deployed endpoint URL

   **Headers** (if authentication needed):
   ```json
   {
     "Authorization": "Bearer {{$vars.mcpToken}}"
   }
   ```

3. Click **"Refresh Actions"** to load tools
4. Select all Context Foundry tools

#### Option C: Use Flowise Variables for Configuration

For better security and flexibility:

1. Go to Flowise **Settings** → **Variables**
2. Create variables:
   - `mcpServerUrl` - The MCP server endpoint
   - `mcpToken` - Authentication token (if needed)

3. In agent tools configuration, reference:
   ```
   URL: {{$vars.mcpServerUrl}}
   Headers: {"Authorization": "Bearer {{$vars.mcpToken}}"}
   ```

### Step 4: Test the Configuration

1. Click **"Save Agentflow"**
2. Click **"Start Chat"** in the top right
3. Try a test message:
   ```
   What can you help me with?
   ```

4. The assistant should respond explaining it can build apps, check status, etc.

5. Test MCP tool access:
   ```
   Check if there are any running builds
   ```

6. The assistant should use `list_delegations` tool and return results

### Step 5: Verify MCP Tools Are Working

Send test commands:

```
Test 1: "What's the status of Context Foundry?"
→ Should call context_foundry_status

Test 2: "Show me all my builds"
→ Should call list_delegations

Test 3: "Read the global patterns"
→ Should call read_global_patterns
```

If tools aren't working:
- Check MCP server is running
- Verify tool configuration in agent node
- Check Flowise logs for errors
- Ensure correct transport type (stdio vs http)

## Deployment Options

### Local Development

**Best for**: Testing, development, personal use

```bash
# Terminal 1: Start Flowise
cd flowise
npx flowise start

# Terminal 2: Ensure Context Foundry MCP is accessible
cd /Users/name/homelab/context-foundry
# MCP server runs automatically with Claude Code
# Or start standalone if needed
```

Access at: `http://localhost:3000`

### Docker Deployment

**Best for**: Team deployment, production

```dockerfile
# docker-compose.yml
version: '3'
services:
  flowise:
    image: flowiseai/flowise
    ports:
      - "3000:3000"
    environment:
      - FLOWISE_USERNAME=admin
      - FLOWISE_PASSWORD=secure_password
    volumes:
      - ./flowise-data:/root/.flowise

  context-foundry-mcp:
    build: ./context-foundry/mcp-server
    ports:
      - "3001:3001"
    environment:
      - NODE_ENV=production
```

```bash
docker-compose up -d
```

### Cloud Deployment (Vercel/Railway/Render)

**Best for**: Public access, scalability

1. **Deploy Flowise**:
   - Follow Flowise deployment guide: https://docs.flowiseai.com/deployment
   - Set environment variables for API keys

2. **Deploy Context Foundry MCP Server**:
   - Create HTTP wrapper (see Option B above)
   - Deploy to same platform or separate service
   - Use environment variables for configuration

3. **Configure MCP connection** in Flowise to use HTTP transport with deployed URL

## Configuration Reference

### MCP Tools Available

| Tool | Purpose | Parameters |
|------|---------|------------|
| `autonomous_build_and_deploy` | Build complete apps | task, working_directory, github_repo_name |
| `delegate_to_claude_code_async` | General coding tasks | task, working_directory, timeout_minutes |
| `list_delegations` | Show all builds | None |
| `get_delegation_result` | Get build results | task_id, include_full_output |
| `stream_delegation_output` | Real-time build output | task_id, lines, filter_pattern |
| `cancel_delegation` | Cancel a build | task_id, reason |
| `read_global_patterns` | Read learned patterns | pattern_type |
| `context_foundry_status` | System status | None |

### Recommended Model Settings

#### Claude Sonnet (Recommended)
```json
{
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.7,
  "max_tokens": 4096,
  "streaming": true
}
```

**Why**: Best reasoning, tool use, and code generation

#### GPT-4o
```json
{
  "model": "gpt-4o",
  "temperature": 0.7,
  "max_tokens": 4096,
  "streaming": true
}
```

**Why**: Good balance of speed and capability

#### GPT-4o-mini (Budget)
```json
{
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 4096,
  "streaming": true
}
```

**Why**: Fast and cost-effective for simple tasks

## Troubleshooting

### Issue: MCP tools not appearing

**Solutions**:
1. Check MCP server is running: `ps aux | grep context-foundry`
2. Verify transport configuration (stdio vs http)
3. Check Flowise logs: Docker logs or terminal output
4. Ensure correct path to MCP server
5. Try clicking "Refresh Actions" button

### Issue: "Connection refused" error

**Solutions**:
1. For stdio: Check server path is correct
2. For HTTP: Verify server is running on specified port
3. Check firewall settings
4. Ensure MCP server process hasn't crashed

### Issue: Tools execute but return errors

**Solutions**:
1. Check Context Foundry is properly installed
2. Verify working_directory paths are valid
3. Ensure GitHub credentials are configured (for deploy)
4. Check Context Foundry logs for detailed errors

### Issue: Slow responses

**Solutions**:
1. Use streaming mode: `streaming: true`
2. Lower max_tokens if responses are too long
3. Use gpt-4o-mini for faster but simpler tasks
4. Check MCP server performance

### Issue: Authentication errors

**Solutions**:
1. Verify API key is valid and has credits
2. Check credential is properly selected in model config
3. For MCP HTTP: Verify bearer token is correct
4. Regenerate API key if needed

## Advanced Configuration

### Custom System Prompt

To modify the assistant's behavior:

1. Edit the agent node
2. Go to **"Messages"** section
3. Modify the system message content
4. Reference: `extensions/flowise/prompts/CONTEXT-FOUNDRY-ASSISTANT-PROMPT.md`

### Adding Custom Tools

To extend functionality:

1. In agent **"Tools"** section
2. Add **"Custom Tool"** or **"Calculator"**, **"Web Browser"**, etc.
3. Combine with MCP tools for enhanced capabilities

Example: Add web search for looking up latest documentation

### Multi-Agent Setup

For complex workflows:

1. Create multiple agents:
   - **Architect Agent**: Designs apps
   - **Builder Agent**: Creates apps via Context Foundry
   - **Monitor Agent**: Tracks build status

2. Use **Supervisor Agent** pattern to coordinate

3. See template: `templates/Supervisor Worker Agents.json`

### Integration with RAG

To give assistant knowledge of your docs:

1. Add **Document Store** node
2. Upload Context Foundry documentation
3. Connect to agent's **"Knowledge"** input
4. Assistant can reference docs when helping users

## Security Best Practices

1. **Protect API Keys**:
   - Use Flowise variables, not hardcoded values
   - Rotate keys regularly
   - Use environment variables in production

2. **MCP Server Security**:
   - Use authentication tokens for HTTP transport
   - Restrict network access to MCP server
   - Use HTTPS for deployed instances
   - Don't expose stdio transport publicly

3. **Access Control**:
   - Enable Flowise authentication: `FLOWISE_USERNAME`, `FLOWISE_PASSWORD`
   - Use OAuth/SSO for team deployments
   - Implement rate limiting

4. **Monitor Usage**:
   - Track API costs
   - Monitor MCP server logs
   - Set up alerts for errors
   - Review build history regularly

## Next Steps

1. ✅ Import and configure the flow
2. ✅ Test basic functionality
3. 📝 Customize system prompt for your needs
4. 🚀 Deploy to production (if needed)
5. 📊 Monitor usage and costs
6. 🔧 Extend with additional tools and agents

## Support

- **Context Foundry Docs**: `/Users/name/homelab/context-foundry/README.md`
- **Flowise Docs**: https://docs.flowiseai.com
- **MCP Specification**: https://modelcontextprotocol.io
- **Issues**: Report at context-foundry GitHub repo

## Examples

### Example 1: Building an App

**User**: "I need a todo app with user authentication"

**Assistant**:
```
I'll help you build a todo app with authentication! Let me clarify a few things:

1. Authentication method: Email/password, Google OAuth, or both?
2. Database: PostgreSQL, MongoDB, or Firebase?
3. Frontend: React, Next.js, or Vue?

For a standard setup, I'd recommend:
- Next.js with TypeScript
- NextAuth for authentication
- Prisma + PostgreSQL
- TailwindCSS for styling

Sound good?
```

**User**: "Yes, that sounds perfect!"

**Assistant** (uses `autonomous_build_and_deploy`):
```
✓ Build started!
  Task ID: abc-123-def-456
  Project: todo-app-with-auth
  Directory: /Users/name/homelab/todo-app-with-auth
  Status: Running

I'm building your todo app with:
- Next.js 14 + TypeScript
- NextAuth.js for authentication
- Prisma + PostgreSQL database
- Full CRUD for todos
- User authentication & authorization
- Modern UI with TailwindCSS

The build is running in the background. I'll monitor progress and let you know when it's ready.
Want to see real-time build output?
```

### Example 2: Monitoring Builds

**User**: "Show me the status of my builds"

**Assistant** (uses `list_delegations`):
```
📊 Here's your build status:

**Running:**
1. todo-app-with-auth (Task ID: abc-123)
   - Started: 8 minutes ago
   - Phase: Testing
   - Progress: 75%

**Completed:**
2. weather-dashboard (Task ID: def-456)
   - Finished: 2 hours ago
   - Status: ✅ Deployed
   - URL: https://github.com/yourusername/weather-dashboard

3. blog-platform (Task ID: ghi-789)
   - Finished: 1 day ago
   - Status: ✅ Deployed
   - URL: https://github.com/yourusername/blog-platform

Would you like details on any specific build?
```

### Example 3: Real-time Progress

**User**: "Show me what's happening with the todo app"

**Assistant** (uses `stream_delegation_output`):
```
📡 Real-time output from todo-app-with-auth build:

[Scout] ✓ Analyzed requirements
[Scout] ✓ Determined tech stack
[Architect] ✓ Designed database schema
[Architect] ✓ Planned component structure
[Builder] ✓ Created Next.js project
[Builder] ✓ Installed dependencies
[Builder] ✓ Set up Prisma schema
[Builder] ✓ Configured NextAuth
[Builder] ✓ Built authentication pages
[Builder] ✓ Created todo CRUD operations
[Builder] ✓ Implemented API routes
[Tester] Running tests...
[Tester] ✓ 32/32 unit tests passed
[Tester] ✓ Authentication flow validated
[Tester] ✓ CRUD operations working
[Deployer] Pushing to GitHub...

Almost done! Deployment in progress...
```

### Example 4: Creating a Flowise Flow

**User**: "Create a Flowise flow for customer support with AI"

**Assistant** (uses `delegate_to_claude_code_async`):
```
I'll design a customer support flow for you!

**Proposed Architecture:**
1. Start Node - Chat input
2. RAG Agent - Searches knowledge base (FAQs, docs)
3. Customer Support Agent - Responds to queries
4. Ticket Creation Tool - For complex issues
5. Conversation Memory - Maintains context

I'll create the complete Flowise JSON with:
- Document store integration
- AI-powered responses
- Fallback to human agent
- Ticket creation capability

Starting the flow generation now...

✓ Task started! (Task ID: xyz-123)

I'll have the Flowise JSON ready in about 2 minutes.
```

## Summary

You now have a fully configured Context Foundry chat interface in Flowise! Users can:

- 🏗️ Build applications through natural conversation
- 📊 Monitor build progress in real-time
- 🔧 Enhance existing projects
- 🎨 Create Flowise flows programmatically
- ⚡ Get instant status updates

The integration combines Flowise's conversational UI with Context Foundry's autonomous development capabilities, making app creation accessible through simple chat interactions.

Happy building! 🚀
