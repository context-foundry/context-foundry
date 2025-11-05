# Context Foundry Chat Interface for Flowise

> Build and deploy applications through natural conversation using Context Foundry's autonomous development platform

## What is This?

This Flowise flow provides a conversational chat interface to [Context Foundry](https://github.com/yourusername/context-foundry), enabling users to:

- 🏗️ **Build complete applications** - From idea to deployed GitHub repo
- 📊 **Monitor builds** - Real-time status updates and progress tracking
- 🔧 **Enhance projects** - Add features or fix bugs in existing apps
- 🎨 **Create Flowise flows** - Generate workflow JSONs programmatically
- ⚡ **Manage deployments** - Track multiple concurrent builds

## Quick Start

### 1. Prerequisites

- ✅ [Flowise](https://docs.flowiseai.com) installed and running
- ✅ [Context Foundry](https://github.com/yourusername/context-foundry) MCP server configured
- ✅ API key for Claude, GPT-4, or Gemini

### 2. Import Flow

1. Open Flowise UI
2. Go to **Agentflows** → **Add New** → **Load Agentflow**
3. Select: `context-foundry-chat-interface.json`
4. Click **Save**

### 3. Configure

#### Set up AI Model

1. Open the flow
2. Click **"Context Foundry Assistant"** node
3. Select your model:
   - **Claude Sonnet 4.5** (Recommended) - Best reasoning
   - **GPT-4o** - Great all-around
   - **GPT-4o-mini** - Fast & economical

4. Add your API key in credentials

#### Connect to Context Foundry MCP

**For Local Development (Recommended)**:

1. In agent node, scroll to **"Tools"**
2. Click **"+ Add Tool"** → **"MCP Tool"**
3. Configure:
   - **Transport**: `stdio`
   - **Command**: `node`
   - **Args**: `["/Users/name/homelab/context-foundry/mcp-server/index.js"]`

4. Click **"Refresh Actions"**
5. Select all Context Foundry tools:
   - `autonomous_build_and_deploy`
   - `list_delegations`
   - `get_delegation_result`
   - `stream_delegation_output`
   - `cancel_delegation`
   - And more...

**For Cloud Deployment**:

See [CONTEXT_FOUNDRY_MCP_SETUP.md](../docs/CONTEXT_FOUNDRY_MCP_SETUP.md) for HTTP transport configuration.

### 4. Start Chatting!

Click **"Start Chat"** and try:

```
Build me a weather app with OpenWeatherMap API
```

```
Show me all my running builds
```

```
Create a Flowise flow for customer support
```

## Example Conversations

### Building an App

**You**: "I need a todo app with user authentication"

**Assistant**:
```
I'll help you build a todo app! A few questions:
1. Auth method: Email/password, Google OAuth, or both?
2. Database: PostgreSQL, MongoDB, or Firebase?
3. Frontend: React, Next.js, or Vue?

I'd recommend Next.js + NextAuth + Prisma + PostgreSQL.
Sound good?
```

**You**: "Perfect!"

**Assistant**:
```
✓ Build started!
  Task ID: abc-123-def-456
  Project: todo-app-with-auth
  Directory: /Users/name/homelab/todo-app-with-auth

Building your app with:
- Next.js 14 + TypeScript
- NextAuth.js authentication
- Prisma + PostgreSQL
- Full CRUD operations
- Modern UI with TailwindCSS

Running in background. Want to see real-time progress?
```

### Checking Status

**You**: "What's the status of my builds?"

**Assistant**:
```
📊 Build Status:

Running:
- todo-app-with-auth (abc-123) - Testing phase, 75% done

Completed:
- weather-dashboard (def-456) ✅ Deployed
  https://github.com/you/weather-dashboard

- blog-platform (ghi-789) ✅ Deployed
  https://github.com/you/blog-platform

Want details on any build?
```

### Real-time Progress

**You**: "Show me what's happening with the todo app"

**Assistant**:
```
📡 Real-time output:

[Builder] ✓ Created Next.js project
[Builder] ✓ Set up Prisma schema
[Builder] ✓ Configured NextAuth
[Builder] ✓ Built auth pages
[Builder] ✓ Created todo CRUD
[Tester] ✓ 32/32 tests passed
[Deployer] Pushing to GitHub...

Almost done! Deployment in progress...
```

## Features

### Autonomous Development
- **Full-stack applications** from requirements to deployed code
- **Self-healing builds** with automated testing and fixes
- **Multiple tech stacks** - React, Next.js, Node.js, Python, and more
- **GitHub integration** - Auto-create repos and push code

### Build Management
- **Concurrent builds** - Run multiple projects simultaneously
- **Real-time monitoring** - Stream live build output
- **Status tracking** - Check progress at any time
- **Cancel builds** - Stop runaway or unwanted builds

### Intelligent Assistant
- **Context-aware** - Remembers conversation history
- **Proactive** - Offers status updates and suggestions
- **Educational** - Explains what it's doing and why
- **Flexible** - Works with your preferred tech stack

## Available Commands

### Building
```
"Build me a [type] app with [features]"
"Create a REST API for [purpose]"
"Generate a [framework] project with [integrations]"
```

### Monitoring
```
"Show my builds"
"What's the status of [project]?"
"Stream output from [task-id]"
"Is [project] done yet?"
```

### Managing
```
"Cancel build [task-id]"
"Stop the [project] build"
"Read global patterns"
"Check Context Foundry status"
```

### Flowise
```
"Create a Flowise flow for [purpose]"
"Build a multi-agent workflow for [task]"
"Generate a RAG flow with [data sources]"
```

## System Architecture

```
┌─────────────┐
│   User      │
│   Chat      │
└──────┬──────┘
       │
       ↓
┌─────────────────────┐
│  Flowise Agent      │
│  - Claude/GPT       │
│  - System Prompt    │
│  - Memory           │
└──────┬──────────────┘
       │
       ↓ MCP Protocol
┌─────────────────────┐
│ Context Foundry     │
│ MCP Server          │
└──────┬──────────────┘
       │
       ↓
┌─────────────────────┐
│ Autonomous Build    │
│ System              │
│  - Scout            │
│  - Architect        │
│  - Builder          │
│  - Tester           │
│  - Deployer         │
└─────────────────────┘
```

## MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `autonomous_build_and_deploy` | Build complete apps with full deployment |
| `delegate_to_claude_code_async` | Execute general coding tasks |
| `list_delegations` | Show all builds (running and completed) |
| `get_delegation_result` | Get results from specific build |
| `stream_delegation_output` | Real-time build output streaming |
| `cancel_delegation` | Stop a running build |
| `read_global_patterns` | Read learned best practices |
| `context_foundry_status` | Check system status and version |

## Configuration Files

- **Flow**: `context-foundry-chat-interface.json` - The Flowise flow definition
- **System Prompt**: `../prompts/CONTEXT-FOUNDRY-ASSISTANT-PROMPT.md` - AI behavior guide
- **Setup Guide**: `../docs/CONTEXT_FOUNDRY_MCP_SETUP.md` - Detailed configuration
- **MCP Server**: `/Users/name/homelab/context-foundry/mcp-server/` - MCP implementation

## Customization

### Modify System Prompt

Edit the agent node's system message to change behavior:

```markdown
You are a specialized assistant for [your use case]...

Focus on [your domain]...

Always [your specific rules]...
```

### Add Tools

Extend capabilities by adding more tools in Flowise:

- **Web Search** - Look up latest docs and APIs
- **Calculator** - For math and data processing
- **Custom Tools** - Your domain-specific functionality
- **Document Retrieval** - RAG for knowledge base

### Multi-Agent Setup

Create specialized agents:

1. **Architect Agent** - Designs app structure
2. **Builder Agent** - Executes builds
3. **Monitor Agent** - Tracks progress
4. **Supervisor** - Coordinates all agents

See: `../templates/Supervisor Worker Agents.json`

## Deployment

### Local (Development)
```bash
# Start Flowise
npx flowise start

# Access at http://localhost:3000
```

### Docker (Team)
```bash
# Use docker-compose.yml in setup docs
docker-compose up -d
```

### Cloud (Production)
Deploy to Vercel, Railway, or Render following the [setup guide](../docs/CONTEXT_FOUNDRY_MCP_SETUP.md).

## Troubleshooting

### Tools Not Appearing
- ✓ Verify MCP server is running
- ✓ Check transport configuration (stdio vs HTTP)
- ✓ Click "Refresh Actions" button
- ✓ Check Flowise logs for errors

### Connection Errors
- ✓ For stdio: Verify server path
- ✓ For HTTP: Check server is running
- ✓ Ensure firewall allows connections
- ✓ Test MCP server independently

### Slow Responses
- ✓ Enable streaming mode
- ✓ Use faster model (GPT-4o-mini)
- ✓ Lower max_tokens
- ✓ Check MCP server performance

Full troubleshooting: [CONTEXT_FOUNDRY_MCP_SETUP.md](../docs/CONTEXT_FOUNDRY_MCP_SETUP.md#troubleshooting)

## Security

- 🔐 Use environment variables for API keys
- 🔐 Enable Flowise authentication for team deployments
- 🔐 Use HTTPS for cloud deployments
- 🔐 Implement authentication tokens for MCP HTTP
- 🔐 Monitor API usage and set cost limits

## Examples & Templates

Check the `templates/` directory for more flows:

- **Multi-Agent Systems** - `Supervisor Worker Agents.json`
- **RAG Workflows** - `Simple Rag Agents.json`
- **Enterprise Ops** - `flowise-enterprise-ops-center.json`

## Contributing

Improvements welcome! Add features, fix bugs, enhance prompts:

1. Fork the repo
2. Make changes
3. Test thoroughly
4. Submit PR

## Support

- 📖 [Full Setup Guide](../docs/CONTEXT_FOUNDRY_MCP_SETUP.md)
- 📖 [System Prompt Reference](../prompts/CONTEXT-FOUNDRY-ASSISTANT-PROMPT.md)
- 📖 [Context Foundry Docs](https://github.com/yourusername/context-foundry)
- 📖 [Flowise Docs](https://docs.flowiseai.com)
- 🐛 [Report Issues](https://github.com/yourusername/context-foundry/issues)

## License

Same as Context Foundry (MIT)

---

**Built with**:
- [Context Foundry](https://github.com/yourusername/context-foundry) - Autonomous development platform
- [Flowise](https://flowiseai.com) - LLM orchestration framework
- [Model Context Protocol](https://modelcontextprotocol.io) - AI tool integration standard

**Created**: 2025-11-04

**Status**: ✅ Production Ready

---

Start building through conversation! 🚀
