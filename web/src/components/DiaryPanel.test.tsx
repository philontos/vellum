import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../i18n";
import { DiaryPanel } from "./DiaryPanel";

afterEach(() => vi.unstubAllGlobals());

describe("DiaryPanel entry modal", () => {
  it("keeps the timeline mounted behind an open diary entry", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => "neutral",
      setItem: () => undefined,
    });

    const html = renderToStaticMarkup(
      <I18nProvider>
        <DiaryPanel
          entryId={42}
          onOpenEntry={() => undefined}
          onCloseEntry={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('data-diary-timeline="true"');
    expect(html).toContain('role="radiogroup"');
    expect(html).toContain('role="dialog"');
  });
});
