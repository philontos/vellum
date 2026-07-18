import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getModelCandidates,
  saveModelCandidate,
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
});
