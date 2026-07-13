import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getAuthState,
  login as requestLogin,
  logout as requestLogout,
  type AuthUser,
} from "./client";

type AuthValue = {
  loading: boolean;
  error: boolean;
  enabled: boolean | null;
  user: AuthUser | null;
  refresh: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthCtx = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const state = await getAuthState();
      setEnabled(state.enabled);
      setUser(state.user);
    } catch (err) {
      console.error("auth check failed", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    const authenticated = await requestLogin(username, password);
    setEnabled(true);
    setUser(authenticated);
  }, []);

  const logout = useCallback(async () => {
    await requestLogout();
    setUser(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ loading, error, enabled, user, refresh, login, logout }),
    [loading, error, enabled, user, refresh, login, logout],
  );
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthCtx);
  if (!value) throw new Error("useAuth must be used within <AuthProvider>");
  return value;
}
