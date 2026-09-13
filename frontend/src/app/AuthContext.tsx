import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { tokenStorage } from "../lib/storage";
import type { CurrentUser, LoginRequest, RegisterRequest, TokenResponse } from "../types/api";

interface AuthValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (request: LoginRequest) => Promise<void>;
  register: (request: RegisterRequest) => Promise<CurrentUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(Boolean(tokenStorage.accessToken));

  useEffect(() => {
    if (!tokenStorage.accessToken) { setLoading(false); return; }
    api.get<CurrentUser>("/auth/me").then(({ data }) => setUser(data)).catch(() => tokenStorage.clear()).finally(() => setLoading(false));
  }, []);

  async function login(request: LoginRequest) {
    const { data } = await api.post<TokenResponse>("/auth/login", request);
    tokenStorage.set(data.access_token, data.refresh_token);
    const current = await api.get<CurrentUser>("/auth/me");
    setUser(current.data);
  }

  async function register(request: RegisterRequest) {
    const { data } = await api.post<CurrentUser>("/auth/register", request);
    return data;
  }

  function logout() { tokenStorage.clear(); setUser(null); }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
