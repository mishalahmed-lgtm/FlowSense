import { useEffect, useRef, useState } from "react";

/**
 * Custom hook for WebSocket connection to dashboard stream.
 * 
 * @param {string} token - JWT authentication token
 * @param {Function} onMessage - Callback function when message is received
 * @param {Function} onError - Optional error callback
 * @returns {Object} WebSocket connection state and methods
 */
export function useDashboardWebSocket(token, onMessage, onError) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds

  useEffect(() => {
    if (!token) {
      return;
    }

    // Get WebSocket URL
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";
    const wsProtocol = apiBaseUrl.startsWith("https") ? "wss" : "ws";
    const wsHost = apiBaseUrl.replace(/^https?:\/\//, "");
    const wsUrl = `${wsProtocol}://${wsHost}/api/v1/ws/dashboard/stream?token=${token}`;

    console.log("Connecting to dashboard WebSocket:", wsUrl);

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log("Dashboard WebSocket connected");
          setConnected(true);
          setError(null);
          reconnectAttempts.current = 0;
          
          // Send ping to keep connection alive
          const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "ping" }));
            } else {
              clearInterval(pingInterval);
            }
          }, 30000); // Ping every 30 seconds

          // Store ping interval for cleanup
          ws._pingInterval = pingInterval;
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            // Handle pong
            if (message.type === "pong") {
              return;
            }
            
            // Call user's message handler
            if (onMessage) {
              onMessage(message);
            }
          } catch (err) {
            console.error("Error parsing WebSocket message:", err);
            if (onError) {
              onError(err);
            }
          }
        };

        ws.onerror = (err) => {
          console.error("WebSocket error:", err);
          setError("WebSocket connection error");
          if (onError) {
            onError(err);
          }
        };

        ws.onclose = (event) => {
          console.log("Dashboard WebSocket closed:", event.code, event.reason);
          setConnected(false);
          
          // Clear ping interval
          if (ws._pingInterval) {
            clearInterval(ws._pingInterval);
          }

          // Attempt to reconnect if not a normal closure
          if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current += 1;
            console.log(
              `Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})...`
            );
            
            reconnectTimeoutRef.current = setTimeout(() => {
              connect();
            }, reconnectDelay);
          } else if (reconnectAttempts.current >= maxReconnectAttempts) {
            setError("Failed to reconnect after multiple attempts");
            console.error("Max reconnection attempts reached");
          }
        };
      } catch (err) {
        console.error("Error creating WebSocket:", err);
        setError("Failed to create WebSocket connection");
        if (onError) {
          onError(err);
        }
      }
    };

    // Initial connection
    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        if (wsRef.current._pingInterval) {
          clearInterval(wsRef.current._pingInterval);
        }
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [token]); // Remove onMessage and onError from deps to prevent reconnections

  return {
    connected,
    error,
    send: (message) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(message));
      }
    },
  };
}

