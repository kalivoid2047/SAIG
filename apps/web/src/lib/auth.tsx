import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setAccessToken, tryRefresh } from "./api";
import type { MeResponse, TokenResponse, User } from "./types";

interface AuthState {
  status: "loading" | "anonymous" | "authenticated";
  user: User | null;
  permissions: ReadonlySet<string>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (code: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<ReadonlySet<string>>(new Set());

  const loadMe = useCallback(async () => {
    const me = await api<MeResponse>("/api/v1/auth/me");
    setUser(me.user);
    setPermissions(new Set(me.permissions));
    setStatus("authenticated");
  }, []);

  // Session bootstrap: the refresh cookie (if present) silently restores the session.
  useEffect(() => {
    (async () => {
      if (await tryRefresh()) {
        try {
          await loadMe();
          return;
        } catch {
          /* fall through to anonymous */
        }
      }
      setStatus("anonymous");
    })();
  }, [loadMe]);

  // Global session-expiry signal from the API client.
  useEffect(() => {
    const onExpired = () => {
      setAccessToken(null);
      setUser(null);
      setPermissions(new Set());
      setStatus("anonymous");
    };
    window.addEventListener("saig:session-expired", onExpired);
    return () => window.removeEventListener("saig:session-expired", onExpired);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setAccessToken(res.accessToken);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(async () => {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      setUser(null);
      setPermissions(new Set());
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      permissions,
      login,
      logout,
      hasPermission: (code) => permissions.has(code),
    }),
    [status, user, permissions, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
