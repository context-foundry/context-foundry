# Tennis Scoring Web Application

A complete, production-ready tennis scoring application for high school coaches and public viewers. Features real-time score updates, role-based access control, and comprehensive tennis scoring logic.

## Features

### Core Functionality
- **Role-Based Access Control**: Coaches can create and manage matches, viewers can watch in real-time
- **Complete Tennis Scoring**: Accurate implementation of tennis rules including deuce, advantage, tiebreaks
- **Real-Time Updates**: WebSocket-powered live score streaming
- **Match Management**: Create, update, delete, and track tennis matches
- **Historical Data**: Complete point-by-point history for every match
- **Mobile-Responsive**: Optimized for coaches using tablets/phones courtside

### Security
- JWT authentication with refresh tokens
- Bcrypt password hashing (12 rounds)
- CORS protection
- Rate limiting
- Input validation and sanitization
- SQL injection prevention

## Tech Stack

### Backend
- **Framework**: Express.js with TypeScript
- **Database**: PostgreSQL
- **Authentication**: JWT (jsonwebtoken) + bcrypt
- **Real-Time**: Socket.io
- **Validation**: express-validator
- **Testing**: Jest + Supertest

### Frontend
- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React Context API
- **Real-Time**: Socket.io client
- **Testing**: Vitest + Playwright

## Prerequisites

- Node.js 18+ and npm
- Docker and Docker Compose (for PostgreSQL)
- Git

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd tennis-scoring-cf
```

### 2. Set Up Database

```bash
# Start PostgreSQL with Docker
docker-compose up -d

# Wait for database to be ready
docker-compose ps
```

### 3. Set Up Backend

```bash
cd backend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
# Default values work for local development

# Run database migrations
npm run migrate:up

# (Optional) Seed with test data
npm run seed
```

### 4. Set Up Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Edit .env.local if needed
# Default values work for local development
```

## Running the Application

### Development Mode

```bash
# Terminal 1: Start backend
cd backend
npm run dev

# Terminal 2: Start frontend
cd frontend
npm run dev
```

- Backend API: http://localhost:4000
- Frontend: http://localhost:3000
- Database: localhost:5432

### Production Build

```bash
# Build backend
cd backend
npm run build
npm start

# Build frontend
cd frontend
npm run build
npm start
```

## Testing

### Backend Tests

```bash
cd backend

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

Target coverage: 85%+

### Frontend Tests

```bash
cd frontend

# Run unit tests
npm test

# Run with coverage
npm run test:coverage

# Run with UI
npm run test:ui
```

Target coverage: 80%+

### End-to-End Tests

```bash
cd frontend

# Run E2E tests (starts servers automatically)
npm run e2e

# Run with UI
npm run e2e:ui
```

## API Documentation

### Authentication Endpoints

```
POST /api/auth/register - Register new user
POST /api/auth/login - Login user
POST /api/auth/refresh - Refresh access token
POST /api/auth/logout - Logout user
GET  /api/auth/me - Get current user profile
```

### Match Endpoints

```
GET    /api/matches - List all matches (public)
GET    /api/matches/:id - Get match details (public)
POST   /api/matches - Create match (coaches only)
PUT    /api/matches/:id - Update match (coaches only)
DELETE /api/matches/:id - Delete match (coaches only)
GET    /api/matches/:id/history - Get match history (public)
```

### Score Management Endpoints

```
POST /api/matches/:id/start - Start match (coaches only)
POST /api/matches/:id/point - Record point (coaches only)
POST /api/matches/:id/complete - Complete match (coaches only)
```

## Database Schema

### Tables
- **users**: User accounts with authentication
- **matches**: Match information and metadata
- **sets**: Set-level scores
- **games**: Game-level scores
- **points**: Point-by-point history

See `/backend/src/database/migrations/` for complete schema definitions.

## Tennis Scoring Rules

### Points
- 0, 15, 30, 40
- Deuce: 40-40
- Advantage: Win point from deuce
- Win game: 4 points with 2-point margin

### Games
- First to 6 games wins set
- Must win by 2 games (e.g., 6-4, 7-5)
- Tiebreak at 6-6

### Tiebreak
- First to 7 points
- Must win by 2 points
- Winner gets set 7-6

### Match
- Best of 3 sets: First to win 2 sets
- Best of 5 sets: First to win 3 sets

## Project Structure

```
tennis-scoring-cf/
├── backend/              # Express API
│   ├── src/
│   │   ├── config/       # Configuration files
│   │   ├── controllers/  # Route controllers
│   │   ├── middleware/   # Express middleware
│   │   ├── models/       # Database models
│   │   ├── routes/       # API routes
│   │   ├── services/     # Business logic
│   │   ├── utils/        # Helper functions
│   │   ├── validators/   # Input validation
│   │   ├── types/        # TypeScript types
│   │   └── database/     # Migrations and seeds
│   └── tests/            # Backend tests
├── frontend/             # Next.js app
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── components/   # React components
│   │   ├── contexts/     # React contexts
│   │   ├── hooks/        # Custom hooks
│   │   ├── lib/          # API client
│   │   └── types/        # TypeScript types
│   └── tests/            # Frontend tests
└── docker-compose.yml    # PostgreSQL setup
```

## Environment Variables

### Backend (.env)
```
NODE_ENV=development
PORT=4000
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tennis_scoring
DB_USER=postgres
DB_PASSWORD=postgres
JWT_ACCESS_SECRET=your-secret-key
JWT_REFRESH_SECRET=your-refresh-key
CORS_ORIGIN=http://localhost:3000
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:4000
NEXT_PUBLIC_WS_URL=http://localhost:4000
```

## Deployment

### Backend (Railway/Render)
1. Create PostgreSQL database
2. Set environment variables
3. Run migrations
4. Deploy backend
5. Configure custom domain

### Frontend (Vercel)
1. Connect repository
2. Set environment variables
3. Deploy
4. Configure custom domain

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
docker-compose ps

# View logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### Port Already in Use
```bash
# Find process using port
lsof -i :4000  # Backend
lsof -i :3000  # Frontend

# Kill process
kill -9 <PID>
```

### Migration Issues
```bash
# Roll back migrations
npm run migrate:down

# Re-run migrations
npm run migrate:up
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open a GitHub issue.

---

Built with autonomy by the Context Foundry multi-agent system.
