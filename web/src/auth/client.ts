export type AuthUser = {
  id: string;
  username: string;
  display_name: string;
  role: "owner" | "member";
  status?: "active" | "disabled";
};

export type AuthState = { enabled: boolean; user: AuthUser | null };


export async function getAuthState(): Promise<AuthState> {
  const response = await fetch("/auth/me", { cache: "no-store" });
  if (response.status === 401) return { enabled: true, user: null };
  if (!response.ok) throw new Error(`auth check failed: ${response.status}`);
  const body = await response.json() as Partial<AuthState>;
  return {
    enabled: body.enabled ?? body.user != null,
    user: body.user ?? null,
  };
}


export async function login(username: string, password: string): Promise<AuthUser> {
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "invalid credentials" : `login failed: ${response.status}`);
  }
  const body = await response.json() as { user: AuthUser };
  return body.user;
}


export async function logout(): Promise<void> {
  const response = await fetch("/auth/logout", { method: "POST" });
  if (!response.ok) throw new Error(`logout failed: ${response.status}`);
}
