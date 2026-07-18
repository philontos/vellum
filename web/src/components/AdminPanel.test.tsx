import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { AuthUser } from "../auth/client";
import { I18nProvider } from "../i18n";
import {
  AdminPanel,
  adminSectionsForUser,
  allowAdminSectionChange,
} from "./AdminPanel";

const OWNER: AuthUser = {
  id: "owner-1",
  username: "owner",
  display_name: "Owner",
  role: "owner",
  status: "active",
};

const MEMBER: AuthUser = {
  id: "member-1",
  username: "member",
  display_name: "Member",
  role: "member",
  status: "active",
};

function renderPanel(user: AuthUser | null) {
  return renderToStaticMarkup(
    <I18nProvider>
      <AdminPanel
        user={user}
        promptDirty={false}
        onPromptDirtyChange={() => undefined}
      />
    </I18nProvider>,
  );
}

describe("AdminPanel", () => {
  it("preserves the existing owner-only boundary for Prompt and Eval tools", () => {
    expect(adminSectionsForUser(OWNER)).toEqual(["prompts", "traces", "probe", "evals"]);
    expect(adminSectionsForUser(MEMBER)).toEqual(["traces", "probe"]);
    expect(adminSectionsForUser(null)).toEqual(["prompts", "traces", "probe", "evals"]);
  });

  it("renders one stable desktop-only workspace with accessible child tabs", () => {
    const html = renderPanel(OWNER);

    expect(html).toContain("hidden h-full min-h-0 flex-col overflow-hidden md:flex");
    expect(html).toContain('role="tablist"');
    expect(html).toContain('aria-label="Admin tools"');
    expect(html).toContain("Prompts");
    expect(html).toContain("Traces");
    expect(html).toContain("Recall");
    expect(html).toContain("Evals");
  });

  it("does not render owner-only child tabs for a member", () => {
    const html = renderPanel(MEMBER);

    expect(html).toContain("Traces");
    expect(html).toContain("Recall");
    expect(html).not.toContain("Prompts");
    expect(html).not.toContain("Evals");
  });

  it("protects an unsaved Prompt when switching Admin sections", () => {
    const decline = vi.fn(() => false);
    const untouched = vi.fn(() => false);

    expect(allowAdminSectionChange("prompts", "traces", true, decline)).toBe(false);
    expect(decline).toHaveBeenCalledOnce();
    expect(allowAdminSectionChange("traces", "probe", true, untouched)).toBe(true);
    expect(untouched).not.toHaveBeenCalled();
  });
});
