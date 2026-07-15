import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PromptWorkspace } from "../api/prompts";
import { I18nProvider } from "../i18n";
import { PromptWorkspaceView } from "./PromptsPanel";

const WORKSPACE: PromptWorkspace = {
  workspace_revision: 9,
  active_release: {
    id: 5,
    version: 4,
    note: "current",
    published_at: "2026-07-15T10:00:00Z",
  },
  has_unpublished_changes: true,
  prompts: [
    {
      key: "chat.system",
      name: "Chat system",
      description: "Controls the main conversation",
      category: "chat",
      template_format: "format",
      variables: ["context", "facts"],
      editable: true,
      draft_content: "Draft prompt",
      published_content: "Published prompt",
      is_modified: true,
      validation_errors: ["unknown variable: missing"],
      updated_at: "2026-07-15T11:00:00Z",
    },
    {
      key: "facts.extract",
      name: "Fact extraction",
      description: "Extracts durable facts",
      category: "modeling",
      template_format: "format",
      variables: [],
      editable: false,
      draft_content: "Extract facts",
      published_content: "Extract facts",
      is_modified: false,
      validation_errors: [],
      updated_at: null,
    },
  ],
  releases: [
    {
      id: 5,
      version: 4,
      note: "current",
      published_at: "2026-07-15T10:00:00Z",
      is_active: true,
    },
    {
      id: 4,
      version: 3,
      note: "before tuning",
      published_at: "2026-07-14T10:00:00Z",
      is_active: false,
    },
  ],
};

describe("PromptWorkspaceView", () => {
  it("renders the prompt list, editor metadata, validation, and release history", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptWorkspaceView
          workspace={WORKSPACE}
          selectedKey="chat.system"
          draft="Locally edited prompt"
          note="release note"
          dirty
          busy={null}
          error=""
          onSelect={() => undefined}
          onDraftChange={() => undefined}
          onNoteChange={() => undefined}
          onSave={() => undefined}
          onPublish={() => undefined}
          onRestore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Prompts");
    expect(html).toContain("Chat system");
    expect(html).toContain("Fact extraction");
    expect(html).toContain("chat.system");
    expect(html).toContain("context");
    expect(html).toContain("unknown variable: missing");
    expect(html).toContain("Locally edited prompt");
    expect(html).toContain("Published prompt");
    expect(html).toContain("v3");
    expect(html).toContain("Load as draft");
  });

  it("disables publishing while the selected prompt has unsaved local edits", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptWorkspaceView
          workspace={{
            ...WORKSPACE,
            prompts: WORKSPACE.prompts.map((prompt) => ({
              ...prompt,
              validation_errors: [],
            })),
          }}
          selectedKey="chat.system"
          draft="Locally edited prompt"
          note=""
          dirty
          busy={null}
          error=""
          onSelect={() => undefined}
          onDraftChange={() => undefined}
          onNoteChange={() => undefined}
          onSave={() => undefined}
          onPublish={() => undefined}
          onRestore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Publish all<\/button>/);
    expect(html).toContain("Save this draft before publishing");
  });

  it("keeps non-editable prompts visible but disables their editor", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptWorkspaceView
          workspace={WORKSPACE}
          selectedKey="facts.extract"
          draft="Extract facts"
          note=""
          dirty={false}
          busy={null}
          error=""
          onSelect={() => undefined}
          onDraftChange={() => undefined}
          onNoteChange={() => undefined}
          onSave={() => undefined}
          onPublish={() => undefined}
          onRestore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Fact extraction");
    expect(html).toContain("Read only");
    expect(html).toMatch(/<textarea[^>]*disabled=""/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Save draft<\/button>/);
  });

  it("allows publishing the built-in defaults as the first release", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptWorkspaceView
          workspace={{
            ...WORKSPACE,
            active_release: null,
            has_unpublished_changes: false,
            prompts: WORKSPACE.prompts.map((prompt) => ({
              ...prompt,
              is_modified: false,
              validation_errors: [],
            })),
            releases: [],
          }}
          selectedKey="chat.system"
          draft="Draft prompt"
          note="baseline"
          dirty={false}
          busy={null}
          error=""
          onSelect={() => undefined}
          onDraftChange={() => undefined}
          onNoteChange={() => undefined}
          onSave={() => undefined}
          onPublish={() => undefined}
          onRestore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toMatch(/<button(?![^>]*disabled="")[^>]*>Publish all<\/button>/);
    expect(html).not.toContain("There are no unpublished changes");
  });
});
