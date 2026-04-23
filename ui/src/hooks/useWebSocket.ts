import { useEffect, useRef, useCallback, useState } from "react";
import { WS_URL } from "../lib/constants";
import { getAuthToken } from "../lib/api";
import type { WSEvent } from "../lib/types";

const BASE_DELAY = 3000;
const MAX_DELAY = 30000;

export function useWebSocket(onEvent: (event: WSEvent) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const attemptRef = useRef(0);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const token = getAuthToken();
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        // Send auth token as first message instead of in URL.
        if (token) {
          ws.send(JSON.stringify({ type: "auth", token }));
        }
        setConnected(true);
        attemptRef.current = 0;
      };

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data) as WSEvent;
          onEventRef.current(event);
        } catch {
          // Ignore malformed messages.
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        const delay = Math.min(
          BASE_DELAY * Math.pow(2, attemptRef.current),
          MAX_DELAY,
        );
        const jitter = Math.random() * 1000;
        attemptRef.current++;
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = setTimeout(connect, delay + jitter);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      const delay = Math.min(
        BASE_DELAY * Math.pow(2, attemptRef.current),
        MAX_DELAY,
      );
      const jitter = Math.random() * 1000;
      attemptRef.current++;
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(connect, delay + jitter);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
