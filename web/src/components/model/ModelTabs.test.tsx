import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import { ModelTabs } from "./ModelTabs";

describe("ModelTabs", () => {
  it("renders three accessible model sections and marks the active one", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ModelTabs active="traits" onChange={() => undefined} />
      </I18nProvider>,
    );

    expect(html).toContain('role="tablist"');
    expect(html.match(/role="tab"/g)).toHaveLength(3);
    expect(html).toContain('id="model-tab-dossier"');
    expect(html).toContain('aria-controls="model-panel-traits"');
    expect(html).toContain('id="model-tab-traits" role="tab" aria-selected="true"');
    expect(html).toContain("Portrait");
    expect(html).toContain("Facts");
    expect(html).toContain("Traits");
  });
});
