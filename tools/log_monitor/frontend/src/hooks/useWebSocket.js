/**
 * Custom React hook for WebSocket connection
 */

import { useEffect, useState, useCallback } from 'react';
import WebSocketClient from '../services/websocket';

export function useWebSocket(channel = 'all') {
  const [isConnected, setIsConnected] = useState(false);
  const [logs, setLogs] = useState([]);
  const [ws, setWs] = useState(null);

  useEffect(() => {
    // Create WebSocket client
    const client = new WebSocketClient(channel);

    // Set up event listeners
    client.on('connected', () => {
      setIsConnected(true);
    });

    client.on('disconnected', () => {
      setIsConnected(false);
    });

    client.on('message', (data) => {
      setLogs((prevLogs) => [...prevLogs, data]);
    });

    // Connect
    client.connect();

    // Save client reference
    setWs(client);

    // Cleanup on unmount
    return () => {
      client.disconnect();
    };
  }, [channel]);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  return { isConnected, logs, clearLogs, ws };
}
