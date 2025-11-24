# Task Manager Web Application

A full-stack task management application built with React/TypeScript frontend and FastAPI Python backend.

## Features

- ✅ Create, read, update, and delete tasks
- ✅ Mark tasks as complete/incomplete
- ✅ Persistent SQLite database storage
- ✅ Responsive, professional UI
- ✅ Real-time updates
- ✅ Input validation
- ✅ Error handling
- ✅ Comprehensive test coverage

## Architecture

### Technology Stack

**Frontend:**
- React 18+ with TypeScript
- Vite (build tool and dev server)
- CSS for styling

**Backend:**
- FastAPI (Python async web framework)
- Pydantic (data validation)
- SQLite (database)
- Uvicorn (ASGI server)

**Testing:**
- pytest (backend tests)
- Vitest + React Testing Library (frontend tests)

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                     │
│  ┌───────────────────────────────────────────────────┐  │
│  │          React SPA (localhost:5173)               │  │
│  │  - TaskList Component                             │  │
│  │  - TaskItem Component                             │  │
│  │  - TaskForm Component                             │  │
│  │  - API Client (fetch)                             │  │
│  └─────────────────┬─────────────────────────────────┘  │
└────────────────────┼─────────────────────────────────────┘
                     │ HTTP/REST + CORS
                     │ (JSON payloads)
┌────────────────────▼─────────────────────────────────────┐
│           FastAPI Server (localhost:8000)                │
│  ┌───────────────────────────────────────────────────┐  │
│  │  API Routes Layer                                 │  │
│  │  - GET /tasks           - POST /tasks             │  │
│  │  - PUT /tasks/{id}      - DELETE /tasks/{id}      │  │
│  └─────────────────┬─────────────────────────────────┘  │
│  ┌─────────────────▼─────────────────────────────────┐  │
│  │  Business Logic Layer                             │  │
│  │  - Task CRUD operations                           │  │
│  │  - Input validation (Pydantic models)             │  │
│  │  - Error handling                                 │  │
│  └─────────────────┬─────────────────────────────────┘  │
│  ┌─────────────────▼─────────────────────────────────┐  │
│  │  Database Layer                                   │  │
│  │  - Connection management                          │  │
│  │  - SQL query execution                            │  │
│  │  - Transaction handling                           │  │
│  └─────────────────┬─────────────────────────────────┘  │
└────────────────────┼─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              SQLite Database (tasks.db)                  │
│  - tasks table (id, title, description, completed, ...)  │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Python 3.8+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** - [Download Node.js](https://nodejs.org/)
- **pip** (comes with Python)
- **npm** (comes with Node.js)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd task-manager-app
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-asyncio httpx
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

## Running the Application

You'll need to run both the backend and frontend servers.

### Terminal 1: Start Backend Server

```bash
cd backend

# Activate virtual environment if not already active
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Start the FastAPI server
uvicorn main:app --reload
```

The backend API will be available at `http://localhost:8000`

API documentation (auto-generated): `http://localhost:8000/docs`

### Terminal 2: Start Frontend Dev Server

```bash
cd frontend

# Start the Vite dev server
npm run dev
```

The frontend application will be available at `http://localhost:5173`

### Access the Application

Open your browser and navigate to:
```
http://localhost:5173
```

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Frontend Tests

```bash
cd frontend

# Run all tests
npm run test

# Run tests in watch mode
npm run test -- --watch
```

### Manual Testing

1. **Create Task**: Fill in the form and click "Add Task"
2. **View Tasks**: All tasks display in a list below the form
3. **Toggle Complete**: Click the checkbox to mark complete/incomplete
4. **Edit Task**: Click "Edit" button, modify fields, click "Save"
5. **Delete Task**: Click "Delete" button (confirms before deleting)
6. **Persistence**: Refresh the page - all data persists in SQLite database

## API Endpoints

### `GET /`
Health check endpoint
```json
{
  "status": "healthy",
  "service": "task-manager-api"
}
```

### `GET /tasks`
Retrieve all tasks
```json
[
  {
    "id": 1,
    "title": "Buy groceries",
    "description": "Milk, eggs, bread",
    "completed": false,
    "created_at": "2025-11-16T10:00:00",
    "updated_at": "2025-11-16T10:00:00"
  }
]
```

### `POST /tasks`
Create new task

**Request:**
```json
{
  "title": "Buy groceries",
  "description": "Milk, eggs, bread"
}
```

**Response:** (201 Created)
```json
{
  "id": 1,
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "completed": false,
  "created_at": "2025-11-16T10:00:00",
  "updated_at": "2025-11-16T10:00:00"
}
```

### `PUT /tasks/{id}`
Update existing task

**Request:**
```json
{
  "title": "Buy groceries",
  "description": "Milk, eggs, bread, cheese",
  "completed": true
}
```

**Response:** (200 OK) - Updated task object

### `DELETE /tasks/{id}`
Delete task

**Response:** (204 No Content)

## Project Structure

```
task-manager-app/
├── frontend/
│   ├── index.html                    # Vite entry point
│   ├── package.json                  # Frontend dependencies
│   ├── tsconfig.json                 # TypeScript config
│   ├── tsconfig.node.json            # Vite tooling config
│   ├── vite.config.ts                # Vite configuration
│   ├── src/
│   │   ├── main.tsx                  # App entry point
│   │   ├── App.tsx                   # Root component
│   │   ├── vite-env.d.ts             # Vite environment types
│   │   ├── api/
│   │   │   └── tasks.ts              # API client functions
│   │   ├── components/
│   │   │   ├── TaskList.tsx          # Task list container
│   │   │   ├── TaskItem.tsx          # Individual task display
│   │   │   └── TaskForm.tsx          # Create/edit task form
│   │   ├── types/
│   │   │   └── task.ts               # Task interface
│   │   └── styles/
│   │       └── app.css               # Global styles
│   └── tests/
│       ├── setup.ts                  # Test configuration
│       └── TaskList.test.tsx         # Component tests
├── backend/
│   ├── main.py                       # FastAPI app entry point
│   ├── models.py                     # Pydantic models
│   ├── database.py                   # Database connection and queries
│   ├── requirements.txt              # Python dependencies
│   ├── tests/
│   │   ├── test_api.py               # API endpoint tests
│   │   └── test_database.py          # Database operation tests
│   └── tasks.db                      # SQLite database (created at runtime)
├── .gitignore                        # Git ignore rules
└── README.md                         # This file
```

## Development

### Adding New Features

1. **Backend**: Add new endpoints in `backend/main.py` and database operations in `backend/database.py`
2. **Frontend**: Add new components in `frontend/src/components/` and API calls in `frontend/src/api/tasks.ts`
3. **Types**: Update TypeScript interfaces in `frontend/src/types/task.ts` and Pydantic models in `backend/models.py`

### Code Quality

- **TypeScript**: Strict mode enabled for type safety
- **Linting**: Follow ESLint and Prettier configurations
- **Testing**: Maintain test coverage for new features
- **Error Handling**: Add proper error handling at all layers

## Troubleshooting

### CORS Errors

If you see CORS errors in the browser console:
- Ensure backend is running on port 8000
- Ensure frontend is running on port 5173
- Check that `CORSMiddleware` is configured in `backend/main.py`

### Database Issues

If database operations fail:
- Check that `backend/tasks.db` has write permissions
- Delete the database file to reset: `rm backend/tasks.db`
- Restart the backend server to recreate the database

### Port Already in Use

If ports 5173 or 8000 are already in use:
- Kill the process using the port
- Or change the port in configuration files

## License

MIT License - Feel free to use this project for learning or production.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Submit a pull request

## Support

For issues or questions, please open an issue on the GitHub repository.
