export type ModelCandidateSource = "stored" | "environment" | "none";

export type ManagedModelCandidate = {
  id: string;
  name: string;
  base_url: string;
  model: string;
  configured: boolean;
  source: ModelCandidateSource;
  has_saved_key: boolean;
  has_api_key: boolean;
  verified_at: string | null;
  editable: boolean;
};

export type ModelScenario = "chat" | "background" | "evaluation";

export type ModelRoute = {
  scenario: ModelScenario;
  candidate_id: string;
  source: "stored" | "environment";
};

export type ModelCandidateWorkspace = {
  candidates: ManagedModelCandidate[];
  routes: ModelRoute[];
};

export type ModelCandidateDraft = {
  base_url: string;
  api_key: string;
  model: string;
};

export type ModelCandidateValidation = {
  validation_token: string;
  validated_at: string;
};

async function responseError(response: Response, action: string): Promise<Error> {
  try {
    const body = await response.json() as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return new Error(body.detail);
    }
  } catch {
    // Use the status fallback for non-JSON responses.
  }
  return new Error(`${action} failed: ${response.status}`);
}

function jsonRequest(method: "POST" | "PUT", body: Record<string, unknown>): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export async function getModelCandidates(): Promise<ModelCandidateWorkspace> {
  const response = await fetch("/admin/model-candidates", { cache: "no-store" });
  if (!response.ok) throw await responseError(response, "load model candidates");
  return response.json() as Promise<ModelCandidateWorkspace>;
}

export async function validateModelCandidate(
  candidateId: string,
  draft: ModelCandidateDraft,
): Promise<ModelCandidateValidation> {
  const response = await fetch(
    `/admin/model-candidates/${encodeURIComponent(candidateId)}/validate`,
    jsonRequest("POST", draft),
  );
  if (!response.ok) throw await responseError(response, "validate model candidate");
  return response.json() as Promise<ModelCandidateValidation>;
}

export async function saveModelCandidate(
  candidateId: string,
  draft: ModelCandidateDraft,
  validationToken: string,
): Promise<ManagedModelCandidate> {
  const response = await fetch(
    `/admin/model-candidates/${encodeURIComponent(candidateId)}`,
    jsonRequest("PUT", { ...draft, validation_token: validationToken }),
  );
  if (!response.ok) throw await responseError(response, "save model candidate");
  return response.json() as Promise<ManagedModelCandidate>;
}

export async function revealModelCandidateApiKey(
  candidateId: string,
): Promise<string> {
  const response = await fetch(
    `/admin/model-candidates/${encodeURIComponent(candidateId)}/api-key`,
    { cache: "no-store" },
  );
  if (!response.ok) throw await responseError(response, "reveal model API key");
  const body = await response.json() as { api_key?: unknown };
  if (typeof body.api_key !== "string") {
    throw new Error("reveal model API key failed: invalid response");
  }
  return body.api_key;
}

export async function saveModelRoute(
  scenario: ModelScenario,
  candidateId: string,
): Promise<ModelRoute> {
  const response = await fetch(
    `/admin/model-routes/${encodeURIComponent(scenario)}`,
    jsonRequest("PUT", { candidate_id: candidateId }),
  );
  if (!response.ok) throw await responseError(response, "save model route");
  return response.json() as Promise<ModelRoute>;
}
