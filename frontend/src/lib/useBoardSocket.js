import { useEffect, useRef } from "react";

/**
 * Opens a WebSocket to the backend and calls onMessage whenever the server
 * broadcasts. Auto-reconnects with backoff. Silently falls back — the caller
 * still has interval polling as a safety net.
 */
export default function useBoardSocket(onMessage) {
  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const attemptsRef = useRef(0);
  const cbRef = useRef(onMessage);

  useEffect(() => { cbRef.current = onMessage; }, [onMessage]);

  useEffect(() => {
    let closed = false;

    const connect = () => {
      const backend = process.env.REACT_APP_BACKEND_URL || "";
      if (!backend) return;
      const wsUrl = backend.replace(/^http/i, "ws") + "/api/ws/board";
      let ws;
      try {
        ws = new WebSocket(wsUrl);
      } catch { return; }
      wsRef.current = ws;

      ws.onopen = () => { attemptsRef.current = 0; };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data && data.type === "board_update") {
            cbRef.current && cbRef.current(data);
          }
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        if (closed) return;
        attemptsRef.current += 1;
        const wait = Math.min(30_000, 1000 * Math.pow(2, attemptsRef.current));
        timerRef.current = setTimeout(connect, wait);
      };
      ws.onerror = () => {
        try { ws.close(); } catch { /* ignore */ }
      };
    };

    connect();
    return () => {
      closed = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (wsRef.current) try { wsRef.current.close(); } catch { /* ignore */ }
    };
  }, []);
}
