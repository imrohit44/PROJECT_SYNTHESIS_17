import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { api } from "../lib/api";
import { tokenStorage } from "../lib/storage";

vi.mock("../lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span>{auth.loading ? "loading" : auth.user?.email ?? "anonymous"}</span>
      <button
        onClick={() => auth.login({ email: "alice@example.com", password: "secret" })}
      >
        login
      </button>
      <button onClick={auth.logout}>logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    tokenStorage.clear();
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  it("logs in, stores tokens, and loads the current user", async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { access_token: "access-token", refresh_token: "refresh-token" },
    });
    vi.mocked(api.get).mockResolvedValue({
      data: {
        user_id: "user-1",
        customer_id: "customer-1",
        email: "alice@example.com",
        role: "customer",
        is_active: true,
      },
    });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: "login" }));

    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    expect(tokenStorage.accessToken).toBe("access-token");
    expect(tokenStorage.refreshToken).toBe("refresh-token");
  });

  it("clears an expired stored session without exposing token data", async () => {
    tokenStorage.set("expired-access-token", "expired-refresh-token");
    vi.mocked(api.get).mockRejectedValue(new Error("jwt decode stack trace"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("anonymous")).toBeInTheDocument());
    expect(tokenStorage.accessToken).toBeNull();
    expect(screen.queryByText(/jwt/i)).not.toBeInTheDocument();
  });

  it("logs out and clears session storage", async () => {
    tokenStorage.set("access-token", "refresh-token");
    vi.mocked(api.get).mockResolvedValue({
      data: {
        user_id: "user-1",
        customer_id: "customer-1",
        email: "alice@example.com",
        role: "customer",
        is_active: true,
      },
    });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "logout" }));

    expect(screen.getByText("anonymous")).toBeInTheDocument();
    expect(tokenStorage.accessToken).toBeNull();
  });
});
