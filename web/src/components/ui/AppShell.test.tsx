import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import type { AuthUser } from "../../auth/client";
import { AppShell } from "./AppShell";

const OWNER: AuthUser = {
  id: "owner-1",
  username: "owner",
  display_name: "Owner",
  role: "owner",
  status: "active",
};

function renderShell(user: AuthUser | null = OWNER) {
  return renderToStaticMarkup(
    <I18nProvider>
      <AppShell
        view="chat"
        onChange={() => undefined}
        user={user}
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
    expect(html).toContain("ml-auto truncate text-sm font-medium text-ink-soft");
    expect(html).toContain("border-transparent text-ink-soft");
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

  it("keeps diagnostic and tuning views out of the mobile navigation", () => {
    const html = renderShell();
    const mobileNavigation = html.match(/id="mobile-navigation"[\s\S]*?<\/nav>/)?.[0];

    expect(mobileNavigation).toBeDefined();
    expect(mobileNavigation).toContain("Chat");
    expect(mobileNavigation).toContain("Diary");
    expect(mobileNavigation).toContain("You");
    expect(mobileNavigation).not.toContain("Traces");
    expect(mobileNavigation).not.toContain("Probe");
    expect(mobileNavigation).not.toContain("Evals");
    expect(mobileNavigation).not.toContain("Prompts");

    // The full toolset remains available from the desktop navigation rail.
    expect(html).toContain("Traces");
    expect(html).toContain("Probe");
    expect(html).toContain("Evals");
    expect(html).toContain("Prompts");
  });

  it("keeps deployment-wide Prompts owner-only", () => {
    const memberHtml = renderShell({
      id: "member-1",
      username: "member",
      display_name: "Member",
      role: "member",
      status: "active",
    });
    const legacyHtml = renderShell(null);

    expect(memberHtml).not.toContain("Prompts");
    expect(memberHtml).not.toContain("Evals");
    expect(legacyHtml).toContain("Prompts");
  });
});
