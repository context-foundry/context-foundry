import { Server as SocketIOServer } from 'socket.io';

let io: SocketIOServer | null = null;

/**
 * Initialize WebSocket service
 */
export function initializeWebSocket(socketServer: SocketIOServer): void {
  io = socketServer;
}

/**
 * Broadcast score update to match room
 */
export function broadcastScoreUpdate(matchId: number, data: any): void {
  if (!io) {
    console.error('WebSocket not initialized');
    return;
  }

  io.to(`match-${matchId}`).emit('score-update', {
    matchId,
    timestamp: new Date().toISOString(),
    ...data,
  });
}

/**
 * Broadcast match status change
 */
export function broadcastMatchStatus(matchId: number, status: string): void {
  if (!io) {
    console.error('WebSocket not initialized');
    return;
  }

  io.to(`match-${matchId}`).emit('match-status', {
    matchId,
    status,
    timestamp: new Date().toISOString(),
  });
}

/**
 * Get connected clients count for a match
 */
export function getMatchViewers(matchId: number): number {
  if (!io) {
    return 0;
  }

  const room = io.sockets.adapter.rooms.get(`match-${matchId}`);
  return room ? room.size : 0;
}
