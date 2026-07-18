import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ManagedModelCandidate, ModelRoute } from "../../api/modelCandidates";
import { I18nProvider } from "../../i18n";
import { ModelRouteSettings } from "./ModelRouteSettings";


const candidates: ManagedModelCandidate[] = [
  {
    id: "primary", name: "Primary model", base_url: "https://api.deepseek.com",
    model: "deepseek-chat", configured: true, source: "environment",
    has_saved_key: false, has_api_key: true, verified_at: null, editable: true,
  },
  {
    id: "glm", name: "GLM", base_url: "https://glm.example/v1",
    model: "glm-5.2", configured: true, source: "stored",
    has_saved_key: true, has_api_key: true, verified_at: "now", editable: true,
  },
];
const routes: ModelRoute[] = [
  { scenario: "chat", candidate_id: "primary", source: "environment" },
  { scenario: "background", candidate_id: "glm", source: "stored" },
  { scenario: "evaluation", candidate_id: "primary", source: "environment" },
];


describe("ModelRouteSettings", () => {
  it("shows an independent model selector for every supported scenario", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ModelRouteSettings
          candidates={candidates}
          routes={routes}
          busyScenario={null}
          error=""
          onChange={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Chat replies");
    expect(html).toContain("Background modeling");
    expect(html).toContain("Evaluation default");
    expect(html).toContain("deepseek-chat");
    expect(html).toContain("glm-5.2");
    expect((html.match(/<select/g) ?? []).length).toBe(3);
  });
});
