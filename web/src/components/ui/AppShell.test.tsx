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
    expect(html).toContain('data-state="closed"');
    expect(html).toContain("transition-[visibility]");
    expect(html).toContain("transition-opacity");
    expect(html).toContain("transition-transform");
    expect(html).toContain("-translate-x-full");
    expect(html).toContain("motion-reduce:transition-none");
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

  it("keeps Admin out of mobile and consolidates desktop tools under one entry", () => {
    const html = renderShell();
    const mobileNavigation = html.match(/id="mobile-navigation"[\s\S]*?<\/nav>/)?.[0];
    const desktopNavigation = html
      .match(/<nav[\s\S]*?<\/nav>/g)
      ?.find((navigation) => navigation.includes("hidden md:flex"));

    expect(mobileNavigation).toBeDefined();
    expect(mobileNavigation).toContain("Chat");
    expect(mobileNavigation).toContain("Diary");
    expect(mobileNavigation).toContain("You");
    expect(mobileNavigation).not.toContain("Admin");
    expect(mobileNavigation).not.toContain("Traces");
    expect(mobileNavigation).not.toContain("Probe");
    expect(mobileNavigation).not.toContain("Evals");
    expect(mobileNavigation).not.toContain("Prompts");

    expect(desktopNavigation).toBeDefined();
    expect(desktopNavigation).toContain("Admin");
    expect(desktopNavigation).not.toContain("Traces");
    expect(desktopNavigation).not.toContain("Probe");
    expect(desktopNavigation).not.toContain("Evals");
    expect(desktopNavigation).not.toContain("Prompts");
  });

  it("shows the single desktop Admin entry without exposing its child labels", () => {
    const memberHtml = renderShell({
      id: "member-1",
      username: "member",
      display_name: "Member",
      role: "member",
      status: "active",
    });
    const legacyHtml = renderShell(null);

    expect(memberHtml).toContain("Admin");
    expect(legacyHtml).toContain("Admin");
    expect(memberHtml).not.toContain("Prompts");
    expect(memberHtml).not.toContain("Evals");
    expect(legacyHtml).not.toContain("Prompts");
  });
});
