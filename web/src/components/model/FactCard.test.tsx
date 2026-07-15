import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import { FactEditor } from "./FactEditor";


describe("FactEditor", () => {
  it("turns the whole card into an accessible editor with save and cancel", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <FactEditor
          draft="editable fact"
          error=""
          busy={false}
          onDraft={() => undefined}
          onSave={() => undefined}
          onCancel={() => undefined}
          onLeave={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('data-editing="true"');
    expect(html).toContain("<textarea");
    expect(html).toContain("Save");
    expect(html).toContain("Cancel");
  });
});
