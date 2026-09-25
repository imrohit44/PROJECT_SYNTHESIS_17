import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "./api";
import { tokenStorage } from "../lib/storage";
import type { ConnectionStatus, RealtimeMessage, RealtimeNotification } from "../types/realtime";

/** Bounded exponential backoff: 1s, 2s, 4s, 8s, capped at 16s. */
export const MAX_RECONNECT_BACKOFF_MS = 16000;
export const MAX_RECONNECT_ATTEMPTS = 10;

export function getWebSocketUrl(ticket: string): string {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const url = new URL(apiBase);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  // Only the short-lived, single-use ticket travels in the URL. The JWT stays
  // in the Authorization header of the ticket request, so it never reaches
  // access logs or browser history.
  return `${protocol}//${url.host}/api/v1/ws?ticket=${encodeURIComponent(ticket)}`;
}

export function useRealtime() {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [notifications, setNotifications] = useState<RealtimeNotification[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimeout = useRef<number | null>(null);
  const unmounted = useRef(false);
  // In-flight ticket request, so a rerender cannot open a second socket.
  const connecting = useRef<Promise<void> | null>(null);

  const clearNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  // `openSocket` schedules reconnects, and `connect` opens sockets. A ref
  // breaks the cycle so neither callback has to change identity, which keeps
  // the mount effect from tearing down and re-opening the socket on rerender.
  const connectRef = useRef<(() => Promise<void>) | null>(null);

  const openSocket = useCallback((ticket: string) => {
    let ws: WebSocket;
    try {
      ws = new WebSocket(getWebSocketUrl(ticket));
    } catch {
      setStatus("disconnected");
      return;
    }
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      if (unmounted.current) {
        ws.close();
        return;
      }
      setStatus("connected");
      reconnectAttempt.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const parsed: RealtimeMessage = JSON.parse(event.data);
        if (parsed.type === "connection.established") {
          return;
        }
        const notification: RealtimeNotification = {
          id: parsed.event_id || `${Date.now()}-${Math.random()}`,
          title: parsed.data.title || "Banking Update",
          message: parsed.data.message || "New event received.",
          severity: parsed.data.severity || "info",
          occurredAt: parsed.occurred_at || new Date().toISOString(),
          type: parsed.type,
        };
        setNotifications((prev) => [notification, ...prev.slice(0, 9)]);
      } catch {
        // Non-JSON or ping/pong message
      }
    };

    ws.onclose = () => {
      if (unmounted.current) return;
      setStatus("disconnected");
      if (wsRef.current === ws) {
        wsRef.current = null;
      }

      // Bounded reconnect: 1s, 2s, 4s, 8s, capped at MAX_RECONNECT_BACKOFF_MS.
      const backoff = Math.min(
        1000 * Math.pow(2, reconnectAttempt.current),
        MAX_RECONNECT_BACKOFF_MS,
      );
      reconnectAttempt.current += 1;
      if (reconnectAttempt.current <= MAX_RECONNECT_ATTEMPTS) {
        reconnectTimeout.current = window.setTimeout(() => {
          if (!unmounted.current) {
            void connectRef.current?.();
          }
        }, backoff);
      }
    };

    ws.onerror = () => {
      // Connection errors are always followed by onclose, which owns cleanup
      // and the reconnect policy. Nothing to do here.
    };
  }, []);

  const connect = useCallback(async () => {
    if (unmounted.current) return;
    // Guard against duplicate sockets from a rerender or a racing reconnect.
    if (connecting.current) return connecting.current;
    if (!tokenStorage.accessToken) {
      setStatus("disconnected");
      return;
    }

    setStatus("connecting");
    const attempt = (async () => {
      try {
        // The JWT is exchanged for a short-lived, single-use ticket so it
        // never appears in a WebSocket URL or an access log.
        const { data } = await api.post<{ ticket: string }>("/ws/ticket");
        if (unmounted.current) return;
        openSocket(data.ticket);
      } catch {
        // An unauthenticated or offline backend must not break the dashboard.
        setStatus("disconnected");
      } finally {
        connecting.current = null;
      }
    })();
    connecting.current = attempt;
    return attempt;
  }, [openSocket]);

  connectRef.current = connect;

  useEffect(() => {
    unmounted.current = false;
    void connect();

    return () => {
      unmounted.current = true;
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
        reconnectTimeout.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { status, notifications, clearNotification };
}
