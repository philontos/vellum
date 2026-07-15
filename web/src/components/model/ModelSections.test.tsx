import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ModelView } from "../../api/client";
import { ConfirmProvider } from "../../confirm/ConfirmProvider";
import { I18nProvider } from "../../i18n";
import { ModelSections } from "./ModelSections";

const model: ModelView = {
  dossier: "portrait",
  facts: [{ id: 1, text: "fact", status: "active", source_turn: 1 }],
  traits: [],
};

function sectionTag(html: string, id: string) {
  return html.match(new RegExp(`<section(?=[^>]*id="${id}")[^>]*>`))?.[0] ?? "";
}

describe("ModelSections", () => {
  it("keeps inactive sections hidden at every viewport size", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConfirmProvider>
          <ModelSections
            model={model}
            active="facts"
            onFactSave={async () => undefined}
            onFactDelete={async () => undefined}
          />
        </ConfirmProvider>
      </I18nProvider>,
    );

    expect(sectionTag(html, "model-panel-dossier")).toContain('hidden=""');
    expect(sectionTag(html, "model-panel-facts")).not.toContain("hidden");
    expect(sectionTag(html, "model-panel-traits")).toContain('hidden=""');
    expect(html).not.toContain("lg:block");
    expect(html).toContain("Edit fact");
    expect(html).toContain("Delete fact");
  });
});
