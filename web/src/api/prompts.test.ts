import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getPromptWorkspace,
  publishPromptWorkspace,
  restorePromptRelease,
  savePromptDraft,
  type PromptWorkspace,
} from "./prompts";

const WORKSPACE: PromptWorkspace = {
  workspace_revision: 7,
  active_release: {
    id: 3,
    version: 2,
    note: "stable",
    published_at: "2026-07-15T10:00:00Z",
  },
  has_unpublished_changes: true,
  prompts: [
    {
      key: "chat/system prompt",
      name: "Chat system",
      description: "Main conversation instructions",
      category: "chat",
      template_format: "format",
      variables: ["context"],
      editable: true,
      draft_content: "draft {{ context }}",
      published_content: "published {{ context }}",
      is_modified: true,
      validation_errors: [],
      updated_at: "2026-07-15T11:00:00Z",
    },
  ],
  releases: [
    {
      id: 3,
      version: 2,
      note: "stable",
      published_at: "2026-07-15T10:00:00Z",
      is_active: true,
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

function okJson(body: unknown = WORKSPACE): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe("prompt workspace client", () => {
  it("loads the complete prompt workspace", async () => {
    const fetchMock = vi.fn(async () => okJson());
    vi.stubGlobal("fetch", fetchMock);

    const workspace = await getPromptWorkspace();
    expect(workspace).toEqual(WORKSPACE);
    expect(workspace.prompts[0].editable).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/admin/prompts");
  });

  it("saves one encoded prompt key with optimistic revision control", async () => {
    const fetchMock = vi.fn(async () => okJson());
    vi.stubGlobal("fetch", fetchMock);

    await savePromptDraft("chat/system prompt", "new body", 7);

    expect(fetchMock).toHaveBeenCalledWith(
      "/admin/prompts/chat%2Fsystem%20prompt/draft",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: "new body", expected_revision: 7 }),
      },
    );
  });

  it("publishes the workspace with a release note", async () => {
    const fetchMock = vi.fn(async () => okJson());
    vi.stubGlobal("fetch", fetchMock);

    await publishPromptWorkspace(7, "ship prompt fixes");

    expect(fetchMock).toHaveBeenCalledWith("/admin/prompts/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_revision: 7, note: "ship prompt fixes" }),
    });
  });

  it("loads a historical release back into the draft workspace", async () => {
    const fetchMock = vi.fn(async () => okJson());
    vi.stubGlobal("fetch", fetchMock);

    await restorePromptRelease(19, 7);

    expect(fetchMock).toHaveBeenCalledWith("/admin/prompts/releases/19/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_revision: 7 }),
    });
  });

  it("surfaces a server detail on revision conflicts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({ detail: "workspace changed; refresh and retry" }),
      }) as Response),
    );

    await expect(savePromptDraft("chat", "body", 7)).rejects.toThrow(
      "workspace changed; refresh and retry",
    );
  });

  it("keeps prompt keys and messages from structured validation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        json: async () => ({
          detail: { "memory.summary": ["missing required field: summary"] },
        }),
      }) as Response),
    );

    await expect(publishPromptWorkspace(7, "broken")).rejects.toThrow(
      "memory.summary: missing required field: summary",
    );
  });
});
