import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import { AppShell } from "./AppShell";

function renderShell() {
  return renderToStaticMarkup(
    <I18nProvider>
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

  it("does not render a second device PIN or privacy mask after account login", () => {
    const html = renderShell();

    expect(html).not.toContain("Click to reveal");
    expect(html).not.toContain(">Hidden<");
  });
});
