import { afterEach, describe, expect, it, vi } from "vitest";
import { getAuthState, login, logout } from "./client";


afterEach(() => vi.unstubAllGlobals());


describe("auth client", () => {
  it("maps a 401 /auth/me response to signed-out family mode", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 401 }) as Response));

    await expect(getAuthState()).resolves.toEqual({ enabled: true, user: null });
  });

  it("keeps legacy mode usable when server auth is disabled", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({ enabled: false, user: null }),
    }) as Response));

    await expect(getAuthState()).resolves.toEqual({ enabled: false, user: null });
  });

  it("posts credentials and returns the authenticated user", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return {
        ok: true,
        json: async () => ({
          user: { id: "u1", username: "alice", display_name: "Alice", role: "owner" },
        }),
      } as Response;
    }));

    const user = await login("alice", "secret password");

    expect(user.id).toBe("u1");
    expect(calls[0].url).toBe("/auth/login");
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      username: "alice",
      password: "secret password",
    });
  });

  it("posts logout", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true }) as Response);
    vi.stubGlobal("fetch", fetchMock);

    await logout();

    expect(fetchMock).toHaveBeenCalledWith("/auth/logout", { method: "POST" });
  });
});
