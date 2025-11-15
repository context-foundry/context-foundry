# Glass Pane - Local Development Setup

This guide will help you set up Glass Pane for local development.

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.10+
- **Context Foundry** CLI installed and configured
- **Git** for version control

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/glass-pane.git
cd glass-pane
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
.\venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your configuration
# Set DB_PATH to your Context Foundry jobs database
# Default: ~/.context-foundry/cfd/jobs.db
nano .env
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory (in a new terminal)
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env

# Edit .env if needed (optional for local dev)
nano .env
```

### 4. Start Development Servers

#### Terminal 1 - Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at http://localhost:8000

#### Terminal 2 - Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at http://localhost:5173

### 5. Test the Setup

1. Open http://localhost:5173 in your browser
2. Start a Context Foundry build in another terminal:
   ```bash
   cfd build "Create a todo app" ~/test-project
   ```
3. Watch the Glass Pane dashboard update in real-time!

## Project Structure

```
glass-pane/
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── contexts/     # React contexts
│   │   ├── hooks/        # Custom hooks
│   │   ├── types/        # TypeScript types
│   │   └── utils/        # Utility functions
│   ├── public/           # Static assets
│   └── package.json
│
├── backend/              # FastAPI backend
│   ├── api/             # API endpoints
│   ├── services/        # Business logic
│   ├── models/          # Pydantic models
│   ├── main.py          # Application entry point
│   └── requirements.txt
│
├── deployment/          # Deployment files
│   ├── nginx.conf
│   ├── glass-pane.service
│   └── deploy.sh
│
└── docs/               # Documentation
    ├── SETUP.md
    ├── DEPLOYMENT.md
    └── API.md
```

## Configuration

### Backend (.env)

```bash
# Database path
DB_PATH=/Users/yourname/.context-foundry/cfd/jobs.db

# CORS origins
CORS_ORIGINS=http://localhost:5173

# Server config
HOST=0.0.0.0
PORT=8000

# Logging
LOG_LEVEL=debug
```

### Frontend (.env)

```bash
# API URL (optional, defaults to relative paths)
VITE_API_URL=http://localhost:8000
```

## Development Commands

### Frontend

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check

# Lint
npm run lint
```

### Backend

```bash
# Start with auto-reload
uvicorn main:app --reload

# Run with specific host/port
uvicorn main:app --host 0.0.0.0 --port 8000

# Run with multiple workers (production)
uvicorn main:app --workers 4
```

## Troubleshooting

### Backend won't start

**Error**: `Database file not found`

**Solution**: Ensure Context Foundry is installed and has created the jobs database:
```bash
# Check if database exists
ls ~/.context-foundry/cfd/jobs.db

# If not, run a test build to create it
cfd build "test" ~/test
```

### Frontend can't connect to backend

**Error**: `Failed to fetch` or CORS errors

**Solution**:
1. Ensure backend is running on port 8000
2. Check Vite proxy configuration in `vite.config.ts`
3. Verify CORS_ORIGINS in backend .env includes http://localhost:5173

### SSE connection drops

**Error**: Connection keeps reconnecting

**Solution**:
1. Check backend logs for errors
2. Ensure file watcher has permissions to read .context-foundry directory
3. Verify no firewall blocking localhost connections

### No jobs appearing

**Issue**: Dashboard shows "No jobs found"

**Solution**:
1. Ensure Context Foundry has run at least one build
2. Check DB_PATH points to correct database file
3. Verify database file permissions allow read access

## API Documentation

Once the backend is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Hot Reload

Both frontend and backend support hot reload:

- **Frontend**: Vite HMR - changes reflect instantly
- **Backend**: Uvicorn --reload - auto-restarts on file changes

## Testing

### Frontend Tests

```bash
cd frontend
npm run test
```

### Backend Tests

```bash
cd backend
pytest tests/ -v
```

## Next Steps

- Read [API.md](./API.md) for API documentation
- Read [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment
- Check out the architecture in `.context-foundry/architecture.md`

## Support

For issues or questions:
- Open an issue on GitHub
- Check Context Foundry documentation
- Review API docs at http://localhost:8000/docs
