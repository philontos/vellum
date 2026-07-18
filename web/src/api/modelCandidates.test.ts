import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getModelCandidates,
  revealModelCandidateApiKey,
  saveModelCandidate,
  saveModelRoute,
  validateModelCandidate,
} from "./modelCandidates";

const fetchMock = vi.fn<typeof fetch>();
vi.stubGlobal("fetch", fetchMock);

afterEach(() => fetchMock.mockReset());

function ok(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const config = {
  base_url: "https://api.example/v1",
  api_key: "secret",
  model: "model-x",
};

describe("model candidate admin API", () => {
  it("loads only server-redacted candidate metadata", async () => {
    fetchMock.mockResolvedValue(ok({ candidates: [] }));

    expect(await getModelCandidates()).toEqual({ candidates: [] });
    expect(fetchMock).toHaveBeenCalledWith("/admin/model-candidates", {
      cache: "no-store",
    });
  });

  it("validates the exact draft before saving it with the returned ticket", async () => {
    fetchMock
      .mockResolvedValueOnce(ok({ validation_token: "ticket", validated_at: "now" }))
      .mockResolvedValueOnce(ok({ id: "glm", configured: true }));

    await validateModelCandidate("glm", config);
    await saveModelCandidate("glm", config, "ticket");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/admin/model-candidates/glm/validate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      },
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/admin/model-candidates/glm",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...config, validation_token: "ticket" }),
      },
    );
  });

  it("retrieves a key only through the explicit owner reveal request", async () => {
    fetchMock.mockResolvedValue(ok({ api_key: "revealed-secret" }));

    expect(await revealModelCandidateApiKey("primary")).toBe("revealed-secret");
    expect(fetchMock).toHaveBeenCalledWith(
      "/admin/model-candidates/primary/api-key",
      { cache: "no-store" },
    );
  });

  it("saves one scenario route without changing the others", async () => {
    const route = {
      scenario: "background" as const,
      candidate_id: "glm",
      source: "stored" as const,
    };
    fetchMock.mockResolvedValue(ok(route));

    expect(await saveModelRoute("background", "glm")).toEqual(route);
    expect(fetchMock).toHaveBeenCalledWith("/admin/model-routes/background", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: "glm" }),
    });
  });
});
