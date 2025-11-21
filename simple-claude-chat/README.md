# Claude Chat UI

A minimal full-stack web application providing a chat interface for Claude API (Sonnet 4). This project uses a backend proxy pattern to securely handle API authentication while providing a clean React-based chat UI.

## Features

- 💬 Clean, modern chat interface
- 🔒 Secure API key handling (backend proxy)
- ⚡ Real-time responses from Claude Sonnet 4
- 📝 Conversation history during session
- 🎨 Responsive design with smooth animations
- ⚠️ Error handling and user feedback

## Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  React Frontend │────────▶│  Express Backend│────────▶│   Claude API    │
│   (Vite Dev)    │  HTTP   │   API Proxy     │  HTTPS  │  (Anthropic)    │
│   Port 5173     │◀────────│   Port 3001     │◀────────│                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

**Tech Stack:**
- **Backend**: Node.js, Express, Anthropic SDK
- **Frontend**: React 18, Vite 5
- **Security**: Environment variables, CORS, backend API key proxy

## Prerequisites

- Node.js 18+ and npm
- Anthropic API key (get one at https://console.anthropic.com/)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd claude-chat-ui
```

### 2. Set Up Backend

```bash
cd backend
npm install
```

Create a `.env` file in the `backend` directory:

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```env
ANTHROPIC_API_KEY=sk-ant-your-actual-api-key-here
PORT=3001
```

### 3. Set Up Frontend

```bash
cd ../frontend
npm install
```

## Running the Application

You need to run both the backend and frontend servers.

### Terminal 1: Start Backend Server

```bash
cd backend
npm start
```

Expected output:
```
🚀 Backend server running on http://localhost:3001
📡 CORS enabled for http://localhost:5173
✅ Claude API key configured
```

### Terminal 2: Start Frontend Dev Server

```bash
cd frontend
npm run dev
```

Expected output:
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
```

### 4. Open the Application

Open your browser to **http://localhost:5173**

## Usage

1. Type your message in the input field at the bottom
2. Press **Enter** to send (or click the **Send** button)
3. Wait for Claude's response
4. Continue the conversation!

**Tips:**
- Press **Shift+Enter** for multi-line messages
- Conversation history is maintained during the session
- Error messages will appear if the backend is down or API key is invalid

## Testing

### Manual Functional Tests

**Test 1: Basic Chat Flow**
1. Start both backend and frontend
2. Send message: "Hello"
3. Verify Claude responds

**Test 2: Conversation Context**
1. Send: "My name is Alex"
2. Send: "What's my name?"
3. Verify Claude remembers "Alex"

**Test 3: Error Handling**
1. Stop backend server
2. Try sending a message
3. Verify error message displays

### Backend API Test (with curl)

```bash
curl -X POST http://localhost:3001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

Expected response:
```json
{
  "role": "assistant",
  "content": "Hello! How can I help you today?"
}
```

## Project Structure

```
claude-chat-ui/
├── backend/
│   ├── server.js              # Express server + API routes
│   ├── package.json           # Backend dependencies
│   ├── .env                   # API key (git-ignored)
│   ├── .env.example           # Environment template
│   └── .gitignore
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Main app component
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx   # Main chat container
│   │   │   ├── MessageList.jsx     # Display messages
│   │   │   └── MessageInput.jsx    # Input field + button
│   │   ├── main.jsx           # React entry point
│   │   └── styles/
│   │       └── App.css        # Global styles
│   ├── index.html             # HTML entry point
│   ├── package.json           # Frontend dependencies
│   ├── vite.config.js         # Vite configuration
│   └── .gitignore
│
├── .context-foundry/          # BAML tracking artifacts
│   ├── scout-report.md
│   ├── architecture.md
│   ├── current-phase.json
│   └── session-log.jsonl
│
└── README.md                  # This file
```

## API Reference

### POST /api/chat

Send a message to Claude and receive a response.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
    {"role": "user", "content": "How are you?"}
  ]
}
```

**Response (200 OK):**
```json
{
  "role": "assistant",
  "content": "I'm doing well, thank you for asking!"
}
```

**Error Responses:**
- `400`: Invalid request (missing/invalid messages)
- `429`: Rate limit exceeded
- `500`: Server error (API key invalid, network issues)

## Security

- ✅ API key stored in backend `.env` file (never exposed to frontend)
- ✅ `.env` file excluded from git via `.gitignore`
- ✅ CORS configured for local development only
- ⚠️ For production: Use environment variables, restrict CORS origins, add rate limiting

## Troubleshooting

### Backend won't start

**Error:** "ANTHROPIC_API_KEY is not set"
- **Solution:** Create `.env` file in `backend/` directory with your API key

### Frontend shows connection errors

**Error:** "Failed to send message"
- **Solution:** Ensure backend is running on port 3001
- Check backend terminal for errors

### API key errors

**Error:** "Invalid API key"
- **Solution:** Verify your API key in `backend/.env` is correct
- Get a new key from https://console.anthropic.com/

### CORS errors

**Error:** "CORS policy blocked"
- **Solution:** Ensure frontend is running on port 5173
- Check `server.js` CORS configuration

## Development

### Backend Development Mode

Uses `nodemon` for auto-reload:

```bash
cd backend
npm run dev
```

### Frontend Development

Vite provides Hot Module Replacement (HMR) automatically:

```bash
cd frontend
npm run dev
```

### Build for Production

Frontend production build:

```bash
cd frontend
npm run build
```

Output will be in `frontend/dist/`

## BAML Phase Tracking

This project was built using the Context Foundry BAML-based workflow:

1. **Scout Phase**: Analyzed requirements and patterns
2. **Architect Phase**: Designed system architecture
3. **Builder Phase**: Implemented code (this phase)
4. **Test Phase**: Validates functionality

Phase tracking artifacts are in `.context-foundry/`

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues or questions:
- Check the Troubleshooting section
- Review Claude API documentation: https://docs.anthropic.com/
- Check Vite documentation: https://vitejs.dev/

---

**Built with Context Foundry** 🔨
