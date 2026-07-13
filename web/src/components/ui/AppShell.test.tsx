import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import { createPrivacyStore } from "../../privacy/store";
import { PrivacyProvider } from "../../privacy/PrivacyProvider";
import { AppShell } from "./AppShell";

function renderShell() {
  const store = createPrivacyStore({
    read: () => null,
    write: () => undefined,
    clear: () => undefined,
  });

  return renderToStaticMarkup(
    <I18nProvider>
      <PrivacyProvider store={store}>
        <AppShell
          view="chat"
          onChange={() => undefined}
          user={{
            id: "owner-1",
            username: "owner",
            display_name: "Owner",
            role: "owner",
            status: "active",
          }}
          onLogout={async () => undefined}
        >
          <div>content</div>
        </AppShell>
      </PrivacyProvider>
    </I18nProvider>,
  );
}

describe("AppShell responsive navigation", () => {
  it("renders a compact mobile header and an accessible navigation drawer", () => {
    const html = renderShell();

    expect(html).toContain('aria-controls="mobile-navigation"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('id="mobile-navigation"');
    expect(html).toContain('aria-hidden="true"');
  });

  it("uses the dynamic viewport and keeps the desktop rail out of mobile layout", () => {
    const html = renderShell();

    expect(html).toContain("h-dvh");
    expect(html).toContain("hidden md:flex");
  });
});
