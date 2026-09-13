import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";

vi.mock("../../app/AuthContext", () => ({
  useAuth: () => ({ user: null, loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }),
}));

describe("ProtectedRoute", () => {
  it("redirects unauthenticated users to login", () => {
    render(<MemoryRouter initialEntries={["/dashboard"]}><Routes><Route element={<ProtectedRoute />}><Route path="/dashboard" element={<p>Dashboard</p>} /></Route><Route path="/login" element={<p>Login page</p>} /></Routes></MemoryRouter>);
    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });
});
