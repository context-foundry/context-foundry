'use client';

import React, { createContext, useEffect, useState, useCallback } from 'react';
import { Socket } from 'socket.io-client';
import { socketClient } from '@/lib/socket';

export interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  joinMatch: (matchId: number) => void;
  leaveMatch: (matchId: number) => void;
}

export const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Get access token from localStorage
    const token = localStorage.getItem('accessToken') || undefined;

    // Connect socket
    const newSocket = socketClient.connect(token);
    setSocket(newSocket);

    // Update connection status
    newSocket.on('connect', () => {
      setIsConnected(true);
    });

    newSocket.on('disconnect', () => {
      setIsConnected(false);
    });

    // Cleanup on unmount
    return () => {
      socketClient.disconnect();
      setSocket(null);
      setIsConnected(false);
    };
  }, []);

  const joinMatch = useCallback((matchId: number) => {
    socketClient.joinMatch(matchId);
  }, []);

  const leaveMatch = useCallback((matchId: number) => {
    socketClient.leaveMatch(matchId);
  }, []);

  const value: WebSocketContextType = {
    socket,
    isConnected,
    joinMatch,
    leaveMatch,
  };

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}
