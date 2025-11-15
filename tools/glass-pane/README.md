# Glass Pane Dashboard

> Real-time visualization dashboard for Context Foundry autonomous builds

## Overview

Glass Pane provides complete transparency into Context Foundry build processes through a beautiful, mobile-responsive web interface. Watch your AI agents work in real-time with live phase updates, file creation animations, streaming logs, and comprehensive metrics.

## Features

- **Real-Time Updates**: Server-Sent Events (SSE) deliver phase changes within 2 seconds
- **Visual Phase Pipeline**: Track progress through Scout → Architect → Builder → Test → Deploy
- **Animated File Tree**: Watch files appear with smooth slide+fade animations
- **Live Log Streaming**: Virtual-scrolled logs with filtering and search
- **Token Budget Visualization**: Circular gauge with green/yellow/red zones
- **Code Preview**: Syntax-highlighted file viewer for all created files
- **Mobile-First Design**: Fully responsive with bottom tab navigation
- **Historical Review**: Browse completed builds with full data retention

## Technology Stack

### Frontend
- React 18.3 + TypeScript 5.5
- Vite 5.4 (dev server, HMR, production builds)
- Tailwind CSS 3.4 (Context Foundry brand theme)
- Framer Motion 11.5 (animations)
- react-window 1.8 (virtual scrolling)

### Backend
- FastAPI 0.114 (async Python web framework)
- Uvicorn 0.30 (ASGI server)
- SQLite (via Context Foundry Store API)
- watchdog 4.0 (file system monitoring)
- Server-Sent Events (real-time updates)

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- Context Foundry CLI installed

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/context-foundry/glass-pane.git
cd glass-pane
```

2. **Setup Backend**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to set DB_PATH to your Context Foundry database
```

3. **Setup Frontend**
```bash
cd frontend
npm install
cp .env.example .env
# VITE_API_URL defaults to http://localhost:8000
```

4. **Start Development Servers**
```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

5. **Open Browser**
```
http://localhost:5173
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed local development setup
- [Deployment Guide](docs/DEPLOYMENT.md) - VPS production deployment
- [API Reference](docs/API.md) - REST and SSE endpoint documentation

## Architecture

```
Browser → NGINX → FastAPI Backend → Context Foundry Store
                      ↓
                 File Watcher (.context-foundry/)
                      ↓
                 SSE Broadcaster
                      ↓
                 React Frontend (real-time updates)
```

## Production Deployment

Deploy to https://glass.contextfoundry.dev:

```bash
# Build frontend
cd frontend
npm run build

# Deploy (automated script)
cd deployment
./deploy.sh
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions.

## Development

### Running Tests

**Backend Unit Tests:**
```bash
cd backend
pytest tests/ -v --cov=.
```

**Frontend Tests:**
```bash
cd frontend
npm run test
```

### Code Structure

```
glass-pane/
├── backend/           # FastAPI server
│   ├── api/          # REST and SSE endpoints
│   ├── services/     # Business logic (Store, FileWatcher, Broadcaster)
│   └── models/       # Pydantic models
├── frontend/         # React SPA
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── contexts/    # State management
│   │   ├── hooks/       # Custom hooks
│   │   └── types/       # TypeScript interfaces
│   └── public/
├── deployment/       # NGINX, systemd configs
└── docs/            # Documentation
```

## License

MIT License - see [LICENSE](LICENSE) for details

## Contributing

Contributions welcome! Please read our contributing guidelines first.

## Support

- Documentation: [docs/](docs/)
- Issues: https://github.com/context-foundry/glass-pane/issues
- Context Foundry: https://contextfoundry.dev
