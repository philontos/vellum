import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../i18n";
import {
  ModelCandidateEditor,
  candidateDraftFingerprint,
} from "./ModelCandidatesPanel";

const candidate = {
  id: "glm",
  name: "GLM",
  base_url: "https://open.bigmodel.cn/api/paas/v4",
  model: "glm-5.2",
  configured: false,
  source: "none" as const,
  has_saved_key: false,
  verified_at: null,
};
const draft = {
  base_url: candidate.base_url,
  model: candidate.model,
  api_key: "secret",
};

function render(validationFingerprint: string) {
  return renderToStaticMarkup(
    <I18nProvider>
      <ModelCandidateEditor
        candidate={candidate}
        draft={draft}
        validationFingerprint={validationFingerprint}
        busy={null}
        error=""
        onDraftChange={() => undefined}
        onValidate={() => undefined}
        onSave={() => undefined}
      />
    </I18nProvider>,
  );
}

describe("ModelCandidateEditor", () => {
  it("keeps Save disabled until this exact draft has passed validation", () => {
    const unchecked = render("");
    const checked = render(candidateDraftFingerprint(draft));

    expect(unchecked).toContain("Validate");
    const saveButton = /<button[^>]*>Save<\/button>/;
    expect(unchecked.match(saveButton)?.[0]).toContain('disabled=""');
    expect(checked.match(saveButton)?.[0]).not.toContain('disabled=""');
  });

  it("never renders a persisted secret value", () => {
    const stored = {
      ...candidate,
      configured: true,
      source: "stored" as const,
      has_saved_key: true,
    };
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ModelCandidateEditor
          candidate={stored}
          draft={{ ...draft, api_key: "" }}
          validationFingerprint=""
          busy={null}
          error=""
          onDraftChange={() => undefined}
          onValidate={() => undefined}
          onSave={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('type="password"');
    expect(html).toContain("Leave blank to keep the saved key");
    expect(html).not.toContain("secret");
  });
});
