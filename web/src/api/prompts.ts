export type PromptReleaseSummary = {
  id: number;
  version: number;
  note: string;
  published_at: string;
};

export type PromptRelease = PromptReleaseSummary & {
  is_active: boolean;
};

export type ManagedPrompt = {
  key: string;
  name: string;
  description: string;
  category: string;
  template_format: string;
  variables: string[];
  editable: boolean;
  draft_content: string;
  published_content: string;
  is_modified: boolean;
  validation_errors: string[];
  updated_at: string | null;
};

export type PromptWorkspace = {
  workspace_revision: number;
  active_release: PromptReleaseSummary | null;
  has_unpublished_changes: boolean;
  prompts: ManagedPrompt[];
  releases: PromptRelease[];
};

function detailMessage(detail: object): string {
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        return String((item as { msg: unknown }).msg);
      }
      return typeof item === "string" ? item : JSON.stringify(item);
    }).join("; ");
  }
  return Object.entries(detail).map(([key, value]) => {
    const message = Array.isArray(value)
      ? value.map(String).join("; ")
      : typeof value === "string"
        ? value
        : JSON.stringify(value);
    return `${key}: ${message}`;
  }).join("\n");
}

async function responseError(response: Response, action: string): Promise<Error> {
  try {
    const body = await response.json() as {
      detail?: unknown;
      error?: unknown;
      message?: unknown;
    };
    const detail = body.detail ?? body.error ?? body.message;
    if (typeof detail === "string" && detail.trim()) return new Error(detail);
    if (detail && typeof detail === "object") {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) return new Error(message);
      const structured = detailMessage(detail);
      if (structured) return new Error(structured);
    }
  } catch {
    // The status fallback below also covers an empty or non-JSON error response.
  }
  return new Error(`${action} failed: ${response.status}`);
}

async function workspaceResponse(response: Response, action: string): Promise<PromptWorkspace> {
  if (!response.ok) throw await responseError(response, action);
  return response.json() as Promise<PromptWorkspace>;
}

function jsonRequest(method: "POST" | "PUT", body: Record<string, unknown>): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export async function getPromptWorkspace(): Promise<PromptWorkspace> {
  return workspaceResponse(await fetch("/admin/prompts"), "load prompts");
}

export async function savePromptDraft(
  key: string,
  content: string,
  expectedRevision: number,
): Promise<PromptWorkspace> {
  const response = await fetch(
    `/admin/prompts/${encodeURIComponent(key)}/draft`,
    jsonRequest("PUT", { content, expected_revision: expectedRevision }),
  );
  return workspaceResponse(response, "save prompt draft");
}

export async function publishPromptWorkspace(
  expectedRevision: number,
  note: string,
): Promise<PromptWorkspace> {
  const response = await fetch(
    "/admin/prompts/publish",
    jsonRequest("POST", { expected_revision: expectedRevision, note }),
  );
  return workspaceResponse(response, "publish prompts");
}

export async function restorePromptRelease(
  releaseId: number,
  expectedRevision: number,
): Promise<PromptWorkspace> {
  const response = await fetch(
    `/admin/prompts/releases/${releaseId}/restore`,
    jsonRequest("POST", { expected_revision: expectedRevision }),
  );
  return workspaceResponse(response, "load release as draft");
}
