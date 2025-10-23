# Architecture Document: Tennis Scoring Web Application

**Project:** High School Tennis Scoring Application
**Phase:** Architect (2/7)
**Date:** 2025-01-19
**Session ID:** tennis-scoring-cf

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer (Browsers)                  │
│              Mobile, Tablet, Desktop Devices                 │
└──────────────┬────────────────────┬──────────────────────────┘
               │ HTTPS              │ WebSocket (WSS)
               ↓                    ↓
┌──────────────────────────────────────────────────────────────┐
│                  Next.js 15 Frontend                         │
│                  (Port 3000 - Dev)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Pages: /, /login, /register, /dashboard,             │ │
│  │         /matches/[id], /coach/create-match             │ │
│  │  Components: ScoreBoard, MatchCard, MatchList,        │ │
│  │             AuthForm, CoachDashboard                   │ │
│  │  Hooks: useAuth, useMatches, useWebSocket             │ │
│  │  State: React Context API                              │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────┬────────────────────┬──────────────────────────┘
               │ REST API           │ Socket.io
               ↓                    ↓
┌──────────────────────────────────────────────────────────────┐
│              Express.js Backend API                          │
│                  (Port 4000 - Dev)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Routes: /api/auth, /api/matches, /api/users          │ │
│  │  Middleware: authMiddleware, roleMiddleware,          │ │
│  │              validateMiddleware, errorMiddleware       │ │
│  │  Controllers: authController, matchController,        │ │
│  │               userController                           │ │
│  │  Services: authService, matchService, scoringService  │ │
│  │  WebSocket: Socket.io server for real-time updates   │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬────────────────────────────────────┘
                           │ SQL Queries
                           ↓
┌──────────────────────────────────────────────────────────────┐
│                  PostgreSQL Database                         │
│                     (Port 5432)                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Tables: users, matches, sets, games, points          │ │
│  │  Indexes: Performance optimization                     │ │
│  │  Constraints: Foreign keys, unique, not null          │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Complete File and Directory Structure

```
tennis-scoring-cf/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx                    # Root layout with providers
│   │   │   ├── page.tsx                      # Home page (public matches)
│   │   │   ├── login/
│   │   │   │   └── page.tsx                  # Login page
│   │   │   ├── register/
│   │   │   │   └── page.tsx                  # Registration page
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx                  # Coach dashboard
│   │   │   ├── matches/
│   │   │   │   ├── [id]/
│   │   │   │   │   └── page.tsx              # Match detail view
│   │   │   │   └── create/
│   │   │   │       └── page.tsx              # Create match (coaches)
│   │   │   └── api/
│   │   │       └── (Next.js API routes if needed)
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   ├── RegisterForm.tsx
│   │   │   │   └── ProtectedRoute.tsx
│   │   │   ├── matches/
│   │   │   │   ├── MatchCard.tsx
│   │   │   │   ├── MatchList.tsx
│   │   │   │   ├── MatchFilters.tsx
│   │   │   │   └── MatchDetail.tsx
│   │   │   ├── scoring/
│   │   │   │   ├── ScoreBoard.tsx
│   │   │   │   ├── ScoreEntry.tsx           # Coach score input
│   │   │   │   ├── SetScore.tsx
│   │   │   │   └── GameScore.tsx
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Footer.tsx
│   │   │   │   └── Navigation.tsx
│   │   │   └── ui/
│   │   │       ├── Button.tsx
│   │   │       ├── Input.tsx
│   │   │       ├── Card.tsx
│   │   │       └── Modal.tsx
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx              # Authentication state
│   │   │   └── WebSocketContext.tsx         # WebSocket connection
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useMatches.ts
│   │   │   └── useWebSocket.ts
│   │   ├── lib/
│   │   │   ├── api.ts                       # API client
│   │   │   ├── socket.ts                    # Socket.io client
│   │   │   └── utils.ts
│   │   └── types/
│   │       ├── auth.ts
│   │       ├── match.ts
│   │       └── api.ts
│   ├── public/
│   │   └── (static assets)
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── components/
│   │   │   │   ├── ScoreBoard.test.tsx
│   │   │   │   └── MatchCard.test.tsx
│   │   │   └── hooks/
│   │   │       └── useAuth.test.ts
│   │   └── e2e/
│   │       ├── auth.spec.ts
│   │       ├── match-creation.spec.ts
│   │       └── score-entry.spec.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── next.config.js
│   ├── playwright.config.ts
│   └── vitest.config.ts
│
├── backend/
│   ├── src/
│   │   ├── config/
│   │   │   ├── database.ts                  # PostgreSQL config
│   │   │   ├── auth.ts                      # JWT config
│   │   │   └── socket.ts                    # Socket.io config
│   │   ├── middleware/
│   │   │   ├── auth.middleware.ts           # JWT verification
│   │   │   ├── role.middleware.ts           # RBAC
│   │   │   ├── validate.middleware.ts       # Input validation
│   │   │   ├── error.middleware.ts          # Error handling
│   │   │   └── rateLimit.middleware.ts      # Rate limiting
│   │   ├── controllers/
│   │   │   ├── auth.controller.ts
│   │   │   ├── match.controller.ts
│   │   │   ├── score.controller.ts
│   │   │   └── user.controller.ts
│   │   ├── services/
│   │   │   ├── auth.service.ts              # Auth business logic
│   │   │   ├── match.service.ts             # Match CRUD
│   │   │   ├── scoring.service.ts           # Tennis scoring engine
│   │   │   └── websocket.service.ts         # Socket.io broadcasts
│   │   ├── models/
│   │   │   ├── User.ts
│   │   │   ├── Match.ts
│   │   │   ├── Set.ts
│   │   │   ├── Game.ts
│   │   │   └── Point.ts
│   │   ├── routes/
│   │   │   ├── auth.routes.ts
│   │   │   ├── match.routes.ts
│   │   │   ├── score.routes.ts
│   │   │   └── user.routes.ts
│   │   ├── validators/
│   │   │   ├── auth.validator.ts
│   │   │   ├── match.validator.ts
│   │   │   └── score.validator.ts
│   │   ├── utils/
│   │   │   ├── jwt.util.ts
│   │   │   ├── bcrypt.util.ts
│   │   │   └── response.util.ts
│   │   ├── types/
│   │   │   ├── auth.types.ts
│   │   │   ├── match.types.ts
│   │   │   └── express.d.ts                # Extended Express types
│   │   ├── database/
│   │   │   ├── migrations/
│   │   │   │   ├── 001_create_users.sql
│   │   │   │   ├── 002_create_matches.sql
│   │   │   │   ├── 003_create_sets.sql
│   │   │   │   ├── 004_create_games.sql
│   │   │   │   └── 005_create_points.sql
│   │   │   ├── seeds/
│   │   │   │   └── dev-data.sql
│   │   │   └── pool.ts                      # PostgreSQL connection pool
│   │   ├── app.ts                           # Express app setup
│   │   └── server.ts                        # Server entry point
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── services/
│   │   │   │   ├── scoring.service.test.ts
│   │   │   │   └── auth.service.test.ts
│   │   │   └── utils/
│   │   │       └── jwt.util.test.ts
│   │   └── integration/
│   │       ├── auth.test.ts
│   │       ├── matches.test.ts
│   │       └── scoring.test.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── jest.config.js
│
├── .context-foundry/
│   ├── current-phase.json
│   ├── scout-report.md
│   ├── architecture.md                      # This file
│   └── (other build artifacts)
│
├── .github/
│   └── workflows/
│       └── ci.yml                           # GitHub Actions CI/CD
│
├── docs/
│   ├── screenshots/                         # From Phase 4.5
│   ├── INSTALLATION.md
│   ├── USAGE.md
│   ├── ARCHITECTURE.md
│   └── TESTING.md
│
├── .gitignore
├── README.md
└── docker-compose.yml                       # PostgreSQL for local dev
```

---

## 3. Database Schema Design

### 3.1 Users Table

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'viewer',
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  school_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_role CHECK (role IN ('coach', 'viewer', 'admin'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

### 3.2 Matches Table

```sql
CREATE TABLE matches (
  id SERIAL PRIMARY KEY,
  created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  player1_name VARCHAR(255) NOT NULL,
  player2_name VARCHAR(255) NOT NULL,
  player3_name VARCHAR(255),                    -- For doubles
  player4_name VARCHAR(255),                    -- For doubles
  match_type VARCHAR(20) NOT NULL DEFAULT 'singles',
  format VARCHAR(20) NOT NULL DEFAULT 'best_of_3',
  status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
  winner INTEGER,                                -- 1 or 2
  location VARCHAR(255),
  scheduled_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  metadata JSONB,                                -- Additional flexible data
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_match_type CHECK (match_type IN ('singles', 'doubles')),
  CONSTRAINT chk_format CHECK (format IN ('best_of_3', 'best_of_5')),
  CONSTRAINT chk_status CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
  CONSTRAINT chk_winner CHECK (winner IN (1, 2))
);

CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_created_by ON matches(created_by);
CREATE INDEX idx_matches_scheduled_at ON matches(scheduled_at);
CREATE INDEX idx_matches_status_date ON matches(status, scheduled_at);
```

### 3.3 Sets Table

```sql
CREATE TABLE sets (
  id SERIAL PRIMARY KEY,
  match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  set_number INTEGER NOT NULL,
  player1_games INTEGER DEFAULT 0,
  player2_games INTEGER DEFAULT 0,
  tiebreak_score JSONB,                          -- {player1: 7, player2: 5}
  winner INTEGER,                                 -- 1 or 2
  completed_at TIMESTAMP,

  CONSTRAINT chk_set_winner CHECK (winner IN (1, 2)),
  UNIQUE(match_id, set_number)
);

CREATE INDEX idx_sets_match_id ON sets(match_id);
```

### 3.4 Games Table

```sql
CREATE TABLE games (
  id SERIAL PRIMARY KEY,
  set_id INTEGER NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
  game_number INTEGER NOT NULL,
  server INTEGER NOT NULL,                        -- 1 or 2
  player1_points INTEGER DEFAULT 0,
  player2_points INTEGER DEFAULT 0,
  winner INTEGER,                                  -- 1 or 2
  completed_at TIMESTAMP,

  CONSTRAINT chk_server CHECK (server IN (1, 2)),
  CONSTRAINT chk_game_winner CHECK (winner IN (1, 2)),
  UNIQUE(set_id, game_number)
);

CREATE INDEX idx_games_set_id ON games(set_id);
```

### 3.5 Points Table

```sql
CREATE TABLE points (
  id SERIAL PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  point_number INTEGER NOT NULL,
  winner INTEGER NOT NULL,                         -- 1 or 2
  score_after VARCHAR(20),                         -- "15-0", "30-15", "deuce", etc.
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_point_winner CHECK (winner IN (1, 2))
);

CREATE INDEX idx_points_game_id ON points(game_id);
```

---

## 4. API Endpoint Specifications

### 4.1 Authentication Endpoints

```
POST /api/auth/register
Body: { email, password, firstName, lastName, role, schoolName? }
Response: { success, data: { user, accessToken, refreshToken }, message }
Status: 201 Created

POST /api/auth/login
Body: { email, password }
Response: { success, data: { user, accessToken, refreshToken }, message }
Status: 200 OK

POST /api/auth/refresh
Body: { refreshToken }
Response: { success, data: { accessToken }, message }
Status: 200 OK

POST /api/auth/logout
Headers: { Authorization: Bearer <token> }
Response: { success, message }
Status: 200 OK

GET /api/auth/me
Headers: { Authorization: Bearer <token> }
Response: { success, data: { user }, message }
Status: 200 OK
```

### 4.2 Match Endpoints

```
GET /api/matches
Query: ?status=live&page=1&limit=20&search=player&date=2025-01-19
Response: { success, data: { matches, total, page, limit }, message }
Status: 200 OK
Public access

GET /api/matches/:id
Response: { success, data: { match, sets, currentGame }, message }
Status: 200 OK
Public access

POST /api/matches
Headers: { Authorization: Bearer <token> }
Body: { player1Name, player2Name, player3Name?, player4Name?, matchType, format, location?, scheduledAt? }
Response: { success, data: { match }, message }
Status: 201 Created
Coaches only

PUT /api/matches/:id
Headers: { Authorization: Bearer <token> }
Body: { location?, scheduledAt?, status? }
Response: { success, data: { match }, message }
Status: 200 OK
Coaches only (own matches)

DELETE /api/matches/:id
Headers: { Authorization: Bearer <token> }
Response: { success, message }
Status: 200 OK
Coaches only (own matches)
```

### 4.3 Score Management Endpoints

```
POST /api/matches/:id/point
Headers: { Authorization: Bearer <token> }
Body: { winner: 1 | 2 }
Response: { success, data: { match, currentSet, currentGame, score }, message }
Status: 200 OK
Coaches only (own matches)
WebSocket broadcast to match room

POST /api/matches/:id/start
Headers: { Authorization: Bearer <token> }
Response: { success, data: { match }, message }
Status: 200 OK
Coaches only (own matches)

POST /api/matches/:id/complete
Headers: { Authorization: Bearer <token> }
Response: { success, data: { match }, message }
Status: 200 OK
Coaches only (own matches)

GET /api/matches/:id/history
Response: { success, data: { sets, games, points }, message }
Status: 200 OK
Public access
```

---

## 5. Tennis Scoring Engine Logic

### 5.1 Point Scoring Logic

```typescript
// Point values: 0, 15, 30, 40, deuce, advantage
function recordPoint(game: Game, winner: 1 | 2): GameResult {
  const loser = winner === 1 ? 2 : 1;
  const winnerPoints = game[`player${winner}_points`];
  const loserPoints = game[`player${loser}_points`];

  // Increment winner's points
  const newWinnerPoints = winnerPoints + 1;

  // Check for game completion
  if (newWinnerPoints >= 4) {
    // Winner needs 2-point margin to win game
    if (newWinnerPoints - loserPoints >= 2) {
      return {
        gameComplete: true,
        gameWinner: winner,
        score: getScoreString(newWinnerPoints, loserPoints)
      };
    }
  }

  return {
    gameComplete: false,
    score: getScoreString(newWinnerPoints, loserPoints)
  };
}

function getScoreString(p1Points: number, p2Points: number): string {
  const pointMap = [0, 15, 30, 40];

  if (p1Points < 4 && p2Points < 4) {
    return `${pointMap[p1Points]}-${pointMap[p2Points]}`;
  }

  if (p1Points === p2Points) {
    return 'deuce';
  }

  if (p1Points > p2Points) {
    return 'advantage player 1';
  } else {
    return 'advantage player 2';
  }
}
```

### 5.2 Game Completion Logic

```typescript
function completeGame(set: Set, winner: 1 | 2): SetResult {
  const loser = winner === 1 ? 2 : 1;
  const winnerGames = set[`player${winner}_games`] + 1;
  const loserGames = set[`player${loser}_games`];

  // Check for set completion
  if (winnerGames >= 6) {
    // Winner needs 2-game margin
    if (winnerGames - loserGames >= 2) {
      return {
        setComplete: true,
        setWinner: winner,
        score: `${winnerGames}-${loserGames}`
      };
    }

    // Tiebreak at 6-6
    if (winnerGames === 6 && loserGames === 6) {
      return {
        setComplete: false,
        tiebreakRequired: true,
        score: '6-6'
      };
    }
  }

  return {
    setComplete: false,
    score: `${winnerGames}-${loserGames}`
  };
}
```

### 5.3 Tiebreak Logic

```typescript
function recordTiebreakPoint(tiebreak: Tiebreak, winner: 1 | 2): TiebreakResult {
  const loser = winner === 1 ? 2 : 1;
  const winnerPoints = tiebreak[`player${winner}_points`] + 1;
  const loserPoints = tiebreak[`player${loser}_points`];

  // First to 7 points with 2-point margin
  if (winnerPoints >= 7 && winnerPoints - loserPoints >= 2) {
    return {
      tiebreakComplete: true,
      setComplete: true,
      setWinner: winner,
      score: `7-6 (${winnerPoints}-${loserPoints})`
    };
  }

  return {
    tiebreakComplete: false,
    score: `${winnerPoints}-${loserPoints}`
  };
}
```

### 5.4 Match Completion Logic

```typescript
function checkMatchCompletion(match: Match, sets: Set[]): MatchResult {
  const player1Sets = sets.filter(s => s.winner === 1).length;
  const player2Sets = sets.filter(s => s.winner === 2).length;

  const setsToWin = match.format === 'best_of_3' ? 2 : 3;

  if (player1Sets >= setsToWin) {
    return { matchComplete: true, matchWinner: 1 };
  }

  if (player2Sets >= setsToWin) {
    return { matchComplete: true, matchWinner: 2 };
  }

  return { matchComplete: false };
}
```

---

## 6. Security Implementation Details

### 6.1 JWT Authentication

```typescript
// JWT Configuration
const JWT_CONFIG = {
  accessTokenSecret: process.env.JWT_ACCESS_SECRET,
  refreshTokenSecret: process.env.JWT_REFRESH_SECRET,
  accessTokenExpiry: '15m',
  refreshTokenExpiry: '7d',
  issuer: 'tennis-scoring-app',
  audience: 'tennis-users'
};

// Generate tokens
function generateTokens(user: User) {
  const accessToken = jwt.sign(
    { userId: user.id, email: user.email, role: user.role },
    JWT_CONFIG.accessTokenSecret,
    { expiresIn: JWT_CONFIG.accessTokenExpiry, issuer: JWT_CONFIG.issuer }
  );

  const refreshToken = jwt.sign(
    { userId: user.id },
    JWT_CONFIG.refreshTokenSecret,
    { expiresIn: JWT_CONFIG.refreshTokenExpiry, issuer: JWT_CONFIG.issuer }
  );

  return { accessToken, refreshToken };
}
```

### 6.2 Password Hashing

```typescript
import bcrypt from 'bcrypt';

const SALT_ROUNDS = 12;

async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, SALT_ROUNDS);
}

async function comparePassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}
```

### 6.3 RBAC Middleware

```typescript
function requireRole(...allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    const user = req.user; // Set by authMiddleware

    if (!user) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    if (!allowedRoles.includes(user.role)) {
      return res.status(403).json({ success: false, error: 'Forbidden' });
    }

    next();
  };
}

// Usage: router.post('/matches', authMiddleware, requireRole('coach'), createMatch);
```

### 6.4 CORS Configuration

```typescript
const corsOptions = {
  origin: process.env.NODE_ENV === 'production'
    ? ['https://tennis-scoring-app.vercel.app']
    : ['http://localhost:3000'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
};

app.use(cors(corsOptions));
```

---

## 7. WebSocket Implementation

### 7.1 Socket.io Setup

```typescript
// Server-side
const io = new Server(httpServer, {
  cors: corsOptions,
  path: '/socket.io'
});

// Authentication middleware for WebSocket
io.use((socket, next) => {
  const token = socket.handshake.auth.token;
  try {
    const decoded = jwt.verify(token, JWT_CONFIG.accessTokenSecret);
    socket.data.user = decoded;
    next();
  } catch (err) {
    next(new Error('Authentication error'));
  }
});

// Join match room
io.on('connection', (socket) => {
  socket.on('join-match', (matchId) => {
    socket.join(`match-${matchId}`);
  });

  socket.on('leave-match', (matchId) => {
    socket.leave(`match-${matchId}`);
  });
});

// Broadcast score update
function broadcastScoreUpdate(matchId: number, data: any) {
  io.to(`match-${matchId}`).emit('score-update', data);
}
```

### 7.2 Client-side Socket.io

```typescript
// WebSocketContext.tsx
import { io, Socket } from 'socket.io-client';

const socket = io('http://localhost:4000', {
  auth: { token: accessToken },
  autoConnect: false
});

function joinMatch(matchId: number) {
  socket.emit('join-match', matchId);
}

socket.on('score-update', (data) => {
  // Update local state with new score
  updateMatchScore(data);
});
```

---

## 8. Testing Requirements

### 8.1 Backend Unit Tests (Jest)

**Target Coverage:** 85%

**Test Files:**
- `tests/unit/services/scoring.service.test.ts`
- `tests/unit/services/auth.service.test.ts`
- `tests/unit/utils/jwt.util.test.ts`

**Key Test Cases:**
```
Scoring Service:
✓ Records point correctly (0-15-30-40)
✓ Handles deuce situation
✓ Awards game with 2-point advantage
✓ Completes set with 6+ games and 2-game margin
✓ Triggers tiebreak at 6-6
✓ Completes tiebreak with 7+ points and 2-point margin
✓ Determines match winner in best-of-3
✓ Determines match winner in best-of-5

Auth Service:
✓ Registers user with valid data
✓ Rejects duplicate email
✓ Hashes password with bcrypt
✓ Generates JWT tokens
✓ Verifies valid JWT
✓ Rejects expired JWT
✓ Refreshes access token
```

### 8.2 Backend Integration Tests (Supertest)

**Test Files:**
- `tests/integration/auth.test.ts`
- `tests/integration/matches.test.ts`
- `tests/integration/scoring.test.ts`

**Key Test Cases:**
```
POST /api/auth/register:
✓ Returns 201 with valid data
✓ Returns 400 with invalid email
✓ Returns 400 with weak password
✓ Returns 409 for duplicate email

POST /api/auth/login:
✓ Returns 200 with valid credentials
✓ Returns 401 with invalid password
✓ Returns 404 with non-existent email
✓ Returns tokens in response

GET /api/matches:
✓ Returns paginated matches
✓ Filters by status
✓ Searches by player name
✓ Allows public access

POST /api/matches:
✓ Returns 201 with valid data (coach)
✓ Returns 401 without auth
✓ Returns 403 for non-coach
✓ Creates match in database

POST /api/matches/:id/point:
✓ Records point successfully
✓ Updates game score
✓ Completes game when winner reaches 4 points with 2-point margin
✓ Broadcasts update via WebSocket
✓ Returns 403 for non-owner coach
```

### 8.3 Frontend Unit Tests (Vitest)

**Target Coverage:** 80%

**Test Files:**
- `tests/unit/components/ScoreBoard.test.tsx`
- `tests/unit/components/MatchCard.test.tsx`
- `tests/unit/hooks/useAuth.test.ts`

**Key Test Cases:**
```
ScoreBoard Component:
✓ Renders current match score
✓ Updates when score changes
✓ Shows deuce correctly
✓ Shows advantage correctly
✓ Displays tiebreak score

LoginForm Component:
✓ Validates email format
✓ Requires password
✓ Calls login API on submit
✓ Displays error messages
✓ Redirects on success

useAuth Hook:
✓ Returns current user
✓ Handles login
✓ Handles logout
✓ Refreshes token automatically
✓ Redirects to login on 401
```

### 8.4 E2E Tests (Playwright) - MANDATORY

**Test Files:**
- `tests/e2e/auth.spec.ts`
- `tests/e2e/match-creation.spec.ts`
- `tests/e2e/score-entry.spec.ts`

**Critical User Flows:**
```typescript
// tests/e2e/auth.spec.ts
test('complete authentication flow', async ({ page }) => {
  // Start servers first
  await page.goto('http://localhost:3000');

  // Register
  await page.click('text=Register');
  await page.fill('[name="email"]', 'coach@test.com');
  await page.fill('[name="password"]', 'SecurePass123!');
  await page.fill('[name="firstName"]', 'John');
  await page.fill('[name="lastName"]', 'Doe');
  await page.selectOption('[name="role"]', 'coach');
  await page.click('button[type="submit"]');

  // Verify redirect to dashboard
  await page.waitForURL('**/dashboard');
  expect(await page.textContent('h1')).toContain('Dashboard');

  // Check no console errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  expect(errors).toHaveLength(0);
});

// tests/e2e/match-creation.spec.ts
test('coach can create and manage match', async ({ page, context }) => {
  // Login as coach
  await loginAsCoach(page);

  // Navigate to create match
  await page.click('text=Create Match');
  await page.fill('[name="player1Name"]', 'Roger Federer');
  await page.fill('[name="player2Name"]', 'Rafael Nadal');
  await page.selectOption('[name="matchType"]', 'singles');
  await page.selectOption('[name="format"]', 'best_of_3');
  await page.fill('[name="location"]', 'Wimbledon');
  await page.click('button[type="submit"]');

  // Verify match created
  await page.waitForSelector('text=Match created successfully');
  expect(await page.locator('.match-card').count()).toBeGreaterThan(0);
});

// tests/e2e/score-entry.spec.ts
test('complete match scoring with real-time updates', async ({ page, context }) => {
  // Open two browser contexts (coach and viewer)
  const coachPage = page;
  const viewerPage = await context.newPage();

  // Coach logs in and starts match
  await loginAsCoach(coachPage);
  const matchId = await createAndStartMatch(coachPage);

  // Viewer opens same match (no auth)
  await viewerPage.goto(`http://localhost:3000/matches/${matchId}`);

  // Coach records points
  await coachPage.click('button:has-text("Player 1 Point")');
  await coachPage.waitForTimeout(500); // WebSocket propagation

  // Verify viewer sees update in real-time
  expect(await viewerPage.textContent('.score')).toContain('15-0');

  // Complete a full game
  await recordFullGame(coachPage, 1); // Player 1 wins game

  // Verify both pages show updated score
  expect(await coachPage.textContent('.game-score')).toContain('1-0');
  expect(await viewerPage.textContent('.game-score')).toContain('1-0');
});
```

**E2E Test Setup:**
```typescript
// playwright.config.ts
export default defineConfig({
  testDir: './tests/e2e',
  webServer: [
    {
      command: 'cd backend && npm run dev',
      port: 4000,
      timeout: 120000,
      reuseExistingServer: true
    },
    {
      command: 'cd frontend && npm run dev',
      port: 3000,
      timeout: 120000,
      reuseExistingServer: true
    }
  ],
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  }
});
```

---

## 9. Implementation Steps (Ordered)

### Step 1: Project Setup (Day 1)
1. Initialize Git repository
2. Create frontend/ and backend/ directories
3. Initialize Next.js: `npx create-next-app@latest frontend --typescript --tailwind --app`
4. Initialize Express backend: `npm init` in backend/
5. Install backend dependencies: express, typescript, pg, bcrypt, jsonwebtoken, socket.io, cors, helmet
6. Install dev dependencies: jest, supertest, ts-node, nodemon
7. Set up TypeScript configs
8. Create docker-compose.yml for PostgreSQL
9. Start PostgreSQL: `docker-compose up -d`
10. Create .gitignore files

### Step 2: Database Setup (Day 1)
1. Create database migrations in backend/src/database/migrations/
2. Run migrations to create tables
3. Add indexes
4. Create seed data for development
5. Test database connections

### Step 3: Backend Authentication (Days 2-3)
1. Implement User model
2. Create auth service with bcrypt and JWT
3. Build auth routes and controllers
4. Add auth middleware for JWT verification
5. Add role middleware for RBAC
6. Implement validation middleware
7. Write unit tests for auth service
8. Write integration tests for auth endpoints
9. Test with Postman/curl

### Step 4: Backend Match Management (Days 3-4)
1. Implement Match, Set, Game, Point models
2. Create match service for CRUD operations
3. Build match routes and controllers
4. Add authorization (coaches can only edit own matches)
5. Implement filtering and pagination
6. Write unit tests
7. Write integration tests

### Step 5: Tennis Scoring Engine (Days 4-5)
1. Implement scoring service with tennis rules
2. Add point recording logic
3. Add game completion logic
4. Add set completion logic with tiebreak
5. Add match completion logic
6. Write comprehensive unit tests for all scoring scenarios
7. Test edge cases (deuce, tiebreak, etc.)

### Step 6: WebSocket Implementation (Day 5)
1. Set up Socket.io server
2. Add WebSocket authentication
3. Implement room-based broadcasting
4. Create websocket service for score broadcasts
5. Test with multiple connections

### Step 7: Frontend Authentication (Days 6-7)
1. Create AuthContext
2. Build LoginForm component
3. Build RegisterForm component
4. Implement useAuth hook
5. Create API client with axios/fetch
6. Add token storage (localStorage)
7. Implement token refresh logic
8. Create ProtectedRoute component
9. Write component tests

### Step 8: Frontend Match Views (Days 7-8)
1. Create Match types
2. Build MatchCard component
3. Build MatchList component
4. Build MatchFilters component
5. Build MatchDetail component
6. Implement match fetching with useMatches hook
7. Add loading and error states
8. Style with Tailwind CSS
9. Test responsive design

### Step 9: Frontend Scoring Components (Days 8-9)
1. Build ScoreBoard component
2. Build ScoreEntry component (coach UI)
3. Build SetScore component
4. Build GameScore component
5. Implement optimistic UI updates
6. Add score submission logic
7. Style for mobile-first
8. Write component tests

### Step 10: WebSocket Integration (Day 9)
1. Create WebSocketContext
2. Implement useWebSocket hook
3. Add socket connection logic
4. Handle reconnection
5. Subscribe to score updates
6. Update UI on real-time events
7. Test with multiple browser tabs

### Step 11: Pages and Routing (Day 10)
1. Create home page (/)
2. Create login page (/login)
3. Create register page (/register)
4. Create dashboard page (/dashboard)
5. Create match detail page (/matches/[id])
6. Create create match page (/matches/create)
7. Add navigation
8. Test all routes

### Step 12: Testing (Days 11-12)
1. Write all missing unit tests
2. Verify 85% backend coverage
3. Verify 80% frontend coverage
4. Write E2E tests with Playwright
5. Test authentication flow
6. Test match creation flow
7. Test score entry flow
8. Test real-time updates
9. Fix all bugs

### Step 13: Documentation (Day 13)
1. Write README.md
2. Create docs/INSTALLATION.md
3. Create docs/USAGE.md
4. Create docs/ARCHITECTURE.md
5. Create docs/TESTING.md
6. Add API documentation

### Step 14: Deployment (Day 14)
1. Set up GitHub repository
2. Configure GitHub Actions CI/CD
3. Set up PostgreSQL on Railway/Neon
4. Deploy backend to Railway
5. Deploy frontend to Vercel
6. Configure environment variables
7. Test production deployment
8. Set up monitoring

---

## 10. Success Criteria

### Functionality
- ✅ Users can register and login
- ✅ JWT authentication working with refresh tokens
- ✅ Coaches can create matches
- ✅ Coaches can record points, games, sets
- ✅ Tennis scoring rules correctly implemented
- ✅ Real-time score updates via WebSocket
- ✅ Public can view matches without auth
- ✅ Filtering and search working
- ✅ Mobile-responsive design

### Testing
- ✅ 85%+ backend test coverage
- ✅ 80%+ frontend test coverage
- ✅ All E2E tests passing
- ✅ No console errors in browser
- ✅ WebSocket connections stable

### Performance
- ✅ API responses < 200ms
- ✅ Page load < 2 seconds
- ✅ WebSocket latency < 500ms

### Security
- ✅ Passwords hashed with bcrypt (12 rounds)
- ✅ JWT tokens secure with proper expiry
- ✅ RBAC working (coaches vs viewers)
- ✅ SQL injection prevented (parameterized queries)
- ✅ XSS prevented (input sanitization)
- ✅ CORS properly configured

### Deployment
- ✅ Application deployed to production
- ✅ GitHub repository created
- ✅ Complete documentation
- ✅ CI/CD pipeline working

---

## 11. Preventive Measures

### CORS Issues
- Configure CORS with specific origin whitelist
- Enable credentials for cookies
- Test cross-origin requests in E2E tests

### WebSocket Reliability
- Implement auto-reconnection
- Add sequence numbers for updates
- Fallback to HTTP polling if needed
- Handle connection errors gracefully

### Authentication Security
- Short-lived access tokens (15 min)
- httpOnly, secure cookies
- Rate limiting on auth endpoints
- CSRF protection

### Database Performance
- Add indexes on frequently queried columns
- Use connection pooling
- Optimize queries with EXPLAIN ANALYZE
- Implement pagination

### Mobile Responsiveness
- Mobile-first design with Tailwind
- Large tap targets (44x44px minimum)
- Test on real devices
- Optimize for slow networks

---

**Architect Agent**
**Date:** 2025-01-19
**Next Phase:** Builder (Phase 3/7)
