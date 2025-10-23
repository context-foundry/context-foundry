// Socket.io client configuration

import { io, Socket } from 'socket.io-client';

const SOCKET_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000';

class SocketClient {
  private socket: Socket | null = null;
  private connecting = false;

  connect(token?: string): Socket {
    if (this.socket?.connected) {
      return this.socket;
    }

    if (this.connecting) {
      return this.socket!;
    }

    this.connecting = true;

    this.socket = io(SOCKET_URL, {
      auth: token ? { token } : undefined,
      autoConnect: true,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.connecting = false;
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.connecting = false;
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.connecting = false;
    });

    return this.socket;
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.connecting = false;
    }
  }

  getSocket(): Socket | null {
    return this.socket;
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }

  // Match room methods
  joinMatch(matchId: number): void {
    if (this.socket?.connected) {
      this.socket.emit('join-match', matchId);
    }
  }

  leaveMatch(matchId: number): void {
    if (this.socket?.connected) {
      this.socket.emit('leave-match', matchId);
    }
  }

  // Event listeners
  onScoreUpdate(callback: (data: any) => void): void {
    this.socket?.on('score-update', callback);
  }

  onMatchStatus(callback: (data: any) => void): void {
    this.socket?.on('match-status', callback);
  }

  onViewerJoined(callback: (data: any) => void): void {
    this.socket?.on('viewer-joined', callback);
  }

  onViewerLeft(callback: (data: any) => void): void {
    this.socket?.on('viewer-left', callback);
  }

  // Remove event listeners
  offScoreUpdate(callback?: (data: any) => void): void {
    this.socket?.off('score-update', callback);
  }

  offMatchStatus(callback?: (data: any) => void): void {
    this.socket?.off('match-status', callback);
  }

  offViewerJoined(callback?: (data: any) => void): void {
    this.socket?.off('viewer-joined', callback);
  }

  offViewerLeft(callback?: (data: any) => void): void {
    this.socket?.off('viewer-left', callback);
  }
}

// Export singleton instance
export const socketClient = new SocketClient();
