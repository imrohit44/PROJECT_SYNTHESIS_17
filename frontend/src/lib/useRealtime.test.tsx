import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildWebSocketUrl, getWebSocketUrl, useRealtime } from "./useRealtime";
import { tokenStorage } from "./storage";

// The JWT is never placed in the socket URL: the client exchanges it for a
// short-lived, single-use ticket over the normal authenticated API.
// `vi.mock` is hoisted above imports, so the mock fn must be hoisted with it.
const { post } = vi.hoisted(() => ({
  post: vi.fn(async () => ({
    data: { ticket: "short-lived-ticket" },
  })),
}));
vi.mock("./api", () => ({ api: { post } }));

type Handler = ((event: MessageEvent) => void) | null;
type CloseHandler = ((event: CloseEvent) => void) | null;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  readyState = 0; // CONNECTING
  onopen: Handler = null;
  onmessage: Handler = null;
  onclose: CloseHandler = null;
  onerror: CloseHandler = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.readyState = 1; // OPEN
    this.onopen?.(new MessageEvent("open"));
  }

  push(message: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  close() {
    this.closed = true;
    this.readyState = 3; // CLOSED
    this.onclose?.(new CloseEvent("close"));
  }
}

describe("buildWebSocketUrl", () => {
  // Regression cover for the production image, which is built with the
  // relative base `/api/v1`. `new URL("/api/v1")` used to throw
  // "Invalid URL"; the base is now resolved against the page origin.
  it("resolves a relative API base against an HTTPS page origin", () => {
    expect(buildWebSocketUrl("/api/v1", "https://example.com", "tok")).toBe(
      "wss://example.com/api/v1/ws?ticket=tok",
    );
  });

  it("resolves a relative API base against an HTTP page origin", () => {
    expect(buildWebSocketUrl("/api/v1", "http://localhost:5173", "tok")).toBe(
      "ws://localhost:5173/api/v1/ws?ticket=tok",
    );
  });

  it("keeps an absolute HTTP API base on ws://", () => {
    expect(buildWebSocketUrl("http://localhost:8000/api/v1", "https://example.com", "tok")).toBe(
      "ws://localhost:8000/api/v1/ws?ticket=tok",
    );
  });

  it("keeps an absolute HTTPS API base on wss://", () => {
    expect(buildWebSocketUrl("https://api.example.com/api/v1", "http://localhost:5173", "tok")).toBe(
      "wss://api.example.com/api/v1/ws?ticket=tok",
    );
  });

  it("carries only the encoded ticket, never a token", () => {
    const url = buildWebSocketUrl("/api/v1", "https://example.com", "a b&c=d");

    expect(url).toBe("wss://example.com/api/v1/ws?ticket=a%20b%26c%3Dd");
    expect(url).not.toContain("access-token");
    expect(new URL(url).searchParams.get("ticket")).toBe("a b&c=d");
  });
});

describe("getWebSocketUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses the browser origin when the production base is relative", () => {
    // Exactly how the published image is built (VITE_API_BASE_URL=/api/v1).
    vi.stubEnv("VITE_API_BASE_URL", "/api/v1");
    vi.stubGlobal("location", { origin: "https://example.com" });

    expect(getWebSocketUrl("tok")).toBe("wss://example.com/api/v1/ws?ticket=tok");
  });

  it("uses the configured absolute base when one is set", () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal("location", { origin: "http://localhost:5173" });

    expect(getWebSocketUrl("tok")).toBe("ws://localhost:8000/api/v1/ws?ticket=tok");
  });
});

describe("useRealtime", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    tokenStorage.set("access-token-1", "refresh-token-1");
  });

  afterEach(() => {
    tokenStorage.clear();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("builds a ws URL from the API base and the ticket", () => {
    expect(getWebSocketUrl("tok")).toBe("ws://localhost:8000/api/v1/ws?ticket=tok");
  });

  it("never places the JWT in the WebSocket URL", async () => {
    renderHook(() => useRealtime());
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    expect(FakeWebSocket.instances[0].url).not.toContain("access-token-1");
  });

  it("connects once, stays idle on rerender, and disconnects on unmount", async () => {
    const { rerender, unmount } = renderHook(() => useRealtime());
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));

    // React rerender must not open a duplicate socket.
    rerender();
    rerender();
    expect(FakeWebSocket.instances).toHaveLength(1);

    act(() => FakeWebSocket.instances[0].open());
    unmount();
    expect(FakeWebSocket.instances[0].closed).toBe(true);
  });

  it("does not connect when no access token exists", async () => {
    tokenStorage.clear();
    renderHook(() => useRealtime());
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("parses typed messages into notifications and ignores the handshake", async () => {
    const { result } = renderHook(() => useRealtime());
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const socket = FakeWebSocket.instances[0];
    act(() => socket.open());
    await waitFor(() => expect(result.current.status).toBe("connected"));

    act(() =>
      socket.push({
        type: "connection.established",
        event_id: "conn-1",
        occurred_at: "2026-01-01T00:00:00+00:00",
        data: { customer_id: "c-1" },
      }),
    );
    expect(result.current.notifications).toHaveLength(0);

    act(() =>
      socket.push({
        type: "transfer.completed",
        event_id: "evt-1",
        occurred_at: "2026-01-01T00:00:00+00:00",
        correlation_id: "corr-1",
        data: {
          title: "Transfer completed",
          message: "Your transfer of Rs.2500 was sent.",
          severity: "info",
        },
      }),
    );
    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0].title).toBe("Transfer completed");
    expect(result.current.notifications[0].type).toBe("transfer.completed");

    act(() => result.current.clearNotification("evt-1"));
    expect(result.current.notifications).toHaveLength(0);
  });

  it("marks the connection disconnected when the server closes the socket", async () => {
    const { result } = renderHook(() => useRealtime());
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    const socket = FakeWebSocket.instances[0];
    act(() => socket.open());
    await waitFor(() => expect(result.current.status).toBe("connected"));

    // Server-side close moves the client to disconnected (a reconnect timer
    // may be scheduled afterwards, bounded by the hook's backoff policy).
    socket.readyState = 3;
    act(() => socket.onclose?.(new CloseEvent("close")));
    expect(result.current.status).toBe("disconnected");
  });
});
