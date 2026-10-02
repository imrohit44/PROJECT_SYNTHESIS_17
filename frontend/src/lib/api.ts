import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { tokenStorage } from "./storage";
import type {
  AssistantChatResponse,
  AssistantStatus,
  ErrorResponse,
  TokenResponse,
} from "../types/api";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

let refreshPromise: Promise<string | null> | null = null;

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStorage.accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    if (error.response?.status !== 401 || !original || original._retry || original.url?.includes("/auth/")) {
      return Promise.reject(error);
    }
    original._retry = true;
    refreshPromise ??= api.post<TokenResponse>("/auth/refresh", { refresh_token: tokenStorage.refreshToken })
      .then(({ data }) => {
        tokenStorage.set(data.access_token, data.refresh_token);
        return data.access_token;
      })
      .catch(() => {
        tokenStorage.clear();
        return null;
      })
      .finally(() => { refreshPromise = null; });
    const token = await refreshPromise;
    if (!token) return Promise.reject(error);
    original.headers.Authorization = `Bearer ${token}`;
    return api(original);
  },
);

export function apiMessage(error: unknown, fallback = "Something went wrong.") {
  if (axios.isAxiosError<ErrorResponse>(error)) return error.response?.data.error.message ?? fallback;
  return fallback;
}

export async function sendAssistantMessage(message: string) {
  const { data } = await api.post<AssistantChatResponse>("/assistant/chat", { message });
  return data;
}

/**
 * Availability and answering mode only: the backend never exposes provider
 * name, endpoint, or credentials to the client.
 */
export async function getAssistantStatus() {
  const { data } = await api.get<AssistantStatus>("/assistant/status");
  return data;
}
