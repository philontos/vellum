import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import { ModelTabs } from "./ModelTabs";

describe("ModelTabs", () => {
  it("renders four accessible model sections and marks the active one", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ModelTabs active="evidence" onChange={() => undefined} />
      </I18nProvider>,
    );

    expect(html).toContain('role="tablist"');
    expect(html.match(/role="tab"/g)).toHaveLength(4);
    expect(html).toContain('id="model-tab-dossier"');
    expect(html).toContain('aria-controls="model-panel-traits"');
    expect(html).toContain('id="model-tab-evidence" role="tab" aria-selected="true"');
    expect(html).toContain("Portrait");
    expect(html).toContain("Evidence");
    expect(html).toContain("Facts");
    expect(html).toContain("Traits");
    expect(html).not.toContain("lg:hidden");
  });
});
