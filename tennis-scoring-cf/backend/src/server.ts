import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import dotenv from 'dotenv';
import app from './app';
import pool from './database/pool';
import { initializeWebSocket } from './services/websocket.service';
import socketConfig from './config/socket';
import { verifyAccessToken } from './utils/jwt.util';

dotenv.config();

const PORT = process.env.PORT || 4000;

// Create HTTP server
const httpServer = createServer(app);

// Initialize Socket.io
const io = new SocketIOServer(httpServer, {
  cors: socketConfig.cors,
  path: socketConfig.path,
});

// WebSocket authentication middleware
io.use((socket, next) => {
  const token = socket.handshake.auth.token;

  if (!token) {
    // Allow unauthenticated connections for viewing
    return next();
  }

  try {
    const decoded = verifyAccessToken(token);
    socket.data.user = decoded;
    next();
  } catch (err) {
    console.error('Socket authentication error:', err);
    // Allow connection but without user data
    next();
  }
});

// WebSocket connection handling
io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Join match room
  socket.on('join-match', (matchId: number) => {
    socket.join(`match-${matchId}`);
    console.log(`Client ${socket.id} joined match ${matchId}`);

    // Notify others in the room
    socket.to(`match-${matchId}`).emit('viewer-joined', {
      matchId,
      viewerCount: io.sockets.adapter.rooms.get(`match-${matchId}`)?.size || 0,
    });
  });

  // Leave match room
  socket.on('leave-match', (matchId: number) => {
    socket.leave(`match-${matchId}`);
    console.log(`Client ${socket.id} left match ${matchId}`);

    // Notify others in the room
    socket.to(`match-${matchId}`).emit('viewer-left', {
      matchId,
      viewerCount: io.sockets.adapter.rooms.get(`match-${matchId}`)?.size || 0,
    });
  });

  // Handle disconnection
  socket.on('disconnect', () => {
    console.log(`Client disconnected: ${socket.id}`);
  });
});

// Initialize WebSocket service
initializeWebSocket(io);

// Test database connection
async function testDatabaseConnection() {
  try {
    const result = await pool.query('SELECT NOW()');
    console.log('Database connected successfully:', result.rows[0].now);
  } catch (error) {
    console.error('Database connection error:', error);
    process.exit(1);
  }
}

// Start server
async function startServer() {
  await testDatabaseConnection();

  httpServer.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
    console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
    console.log(`WebSocket server initialized`);
  });
}

// Handle graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM signal received: closing HTTP server');
  httpServer.close(() => {
    console.log('HTTP server closed');
    pool.end(() => {
      console.log('Database pool closed');
      process.exit(0);
    });
  });
});

startServer().catch((error) => {
  console.error('Failed to start server:', error);
  process.exit(1);
});

export { httpServer, io };
