import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Login } from "./Login";

const login = vi.fn();

vi.mock("../app/AuthContext", () => ({
  useAuth: () => ({
    login,
    register: vi.fn(),
    logout: vi.fn(),
    user: null,
    loading: false,
  }),
}));

describe("Login", () => {
  // Keep the body braced: `mockReset()` returns the mock function, and an
  // expression-bodied hook would make the runner invoke the mock again as a
  // post-test cleanup (see Assistant.test.tsx).
  beforeEach(() => {
    login.mockReset();
  });

  it("submits credentials and navigates after success", async () => {
    login.mockResolvedValue(undefined);
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "alice@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({
        email: "alice@example.com",
        password: "password",
      }),
    );
  });

  it("shows a safe authentication error", async () => {
    login.mockRejectedValueOnce(new Error("database password hash details"));
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText("Email address"), "alice@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("database");
  });
});
