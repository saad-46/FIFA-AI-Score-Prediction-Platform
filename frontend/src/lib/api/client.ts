import axios, { type AxiosInstance } from "axios";
import { createClient } from "@/lib/supabase/client";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Lazily-created singleton so we don't spin up a new Supabase client per request.
let supabaseBrowserClient: ReturnType<typeof createClient> | null = null;

// Auth is Supabase-session-based everywhere in this app (see lib/supabase/*).
// The token is read fresh from the current session on every request rather
// than cached, since Supabase transparently refreshes it in the background.
apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    if (!supabaseBrowserClient) {
      supabaseBrowserClient = createClient();
    }
    const {
      data: { session },
    } = await supabaseBrowserClient.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  }
  return config;
});

/**
 * Extracts a human-readable message from an API error, matching FastAPI's
 * `{"detail": "..."}` error shape. Use this at every call site instead of
 * reading error.message directly.
 */
export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)
      ?.detail;
    if (typeof detail === "string" && detail.length > 0) return detail;
    if (error.code === "ECONNABORTED") return "The request timed out. Please try again.";
    if (!error.response) return "Could not reach the server. Check your connection.";
  }
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}
