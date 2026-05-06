import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export type DaemonConnectionState =
  | "checking"
  | "starting"
  | "connected"
  | "missing-token"
  | "unauthorised"
  | "unavailable"
  | "failed";

interface UseDaemonConnectionResult {
  state: DaemonConnectionState;
  error: string | null;
  token: string | null;
  retry: () => void;
  startLocal: () => Promise<void>;
}

const API_BASE = "http://127.0.0.1:9876";
const TOKEN_RETRY_BUDGET = 3;
const TOKEN_RETRY_DELAY_MS = 750;
const HEALTH_POLL_INTERVAL_MS = 750;
const HEALTH_POLL_TIMEOUT_MS = 20_000;

async function fetchHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

async function readToken(): Promise<string | null> {
  try {
    const token = (await invoke("read_auth_token")) as string | null;
    return token && token.length > 0 ? token : null;
  } catch {
    return null;
  }
}

async function verifyToken(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Tracks the daemon connection lifecycle so the UI can render a recovery
 * screen when the local FastAPI daemon is unreachable, missing, or
 * rejecting auth. Auto-starts the bundled daemon on first probe via the
 * `start_daemon` Tauri command, retries token reads, and verifies auth
 * before declaring the connection healthy.
 */
export function useDaemonConnection(): UseDaemonConnectionResult {
  const [state, setState] = useState<DaemonConnectionState>("checking");
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const autoStartTriedRef = useRef(false);
  const tokenAttemptsRef = useRef(0);
  const cancelledRef = useRef(false);

  const probe = useCallback(async () => {
    if (cancelledRef.current) return;
    setError(null);
    setState("checking");

    let healthy = await fetchHealth();

    if (!healthy && !autoStartTriedRef.current) {
      autoStartTriedRef.current = true;
      setState("starting");
      try {
        await invoke("start_daemon");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
      const deadline = Date.now() + HEALTH_POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        if (cancelledRef.current) return;
        if (await fetchHealth()) {
          healthy = true;
          break;
        }
        await new Promise((r) => setTimeout(r, HEALTH_POLL_INTERVAL_MS));
      }
    }

    if (!healthy) {
      setToken(null);
      setState("unavailable");
      return;
    }

    const candidate = await readToken();
    if (!candidate) {
      if (tokenAttemptsRef.current < TOKEN_RETRY_BUDGET) {
        tokenAttemptsRef.current += 1;
        setTimeout(() => probe(), TOKEN_RETRY_DELAY_MS);
        return;
      }
      setToken(null);
      setState("missing-token");
      return;
    }

    const authorised = await verifyToken(candidate);
    if (!authorised) {
      setToken(null);
      setState("unauthorised");
      return;
    }

    tokenAttemptsRef.current = 0;
    setToken(candidate);
    setState("connected");
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    void probe();
    return () => {
      cancelledRef.current = true;
    };
  }, [probe]);

  const retry = useCallback(() => {
    tokenAttemptsRef.current = 0;
    void probe();
  }, [probe]);

  const startLocal = useCallback(async () => {
    setState("starting");
    try {
      await invoke("start_daemon");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState("failed");
      return;
    }
    void probe();
  }, [probe]);

  return { state, error, token, retry, startLocal };
}
