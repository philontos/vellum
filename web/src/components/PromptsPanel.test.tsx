import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PromptWorkspace } from "../api/prompts";
import { I18nProvider } from "../i18n";
import { PromptWorkspaceView } from "./PromptsPanel";
import { PromptEditorView } from "./prompts/PromptEditor";

const DOCUMENTATION = {
  en: {
    usage: "Used for the main conversation whenever the default persona is selected.",
    runtime: "Loaded once at the beginning of a chat turn and pinned for the whole response.",
    editing_guidance: [
      "Keep persona style here and put cross-cutting safety rules in the shared protocol.",
      "Do not force one output language because the response protocol handles language matching.",
    ],
  },
  zh: {
    usage: "用户选择默认人格时，用于控制主对话的表达风格和互动方式。",
    runtime: "每轮聊天开始时载入一次，并在整次回答期间固定使用同一个发布版本。",
    editing_guidance: [
      "这里只维护人格风格，跨场景安全规则应放在共享响应协议中。",
      "不要固定输出语言，语言匹配由共享响应协议统一处理。",
    ],
  },
};

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
      documentation: DOCUMENTATION,
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
      documentation: DOCUMENTATION,
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
    expect(html).toContain('role="tablist"');
    expect(html).toContain("Edit prompt");
    expect(html).toContain("Usage guide");
    expect(html).toContain("When it is used");
    expect(html).toContain("Where and when it runs");
    expect(html).toContain("Editing guidance");
    expect(html).toContain(DOCUMENTATION.en.usage);
    expect(html).toContain(DOCUMENTATION.en.runtime);
    expect(html).toContain(DOCUMENTATION.en.editing_guidance[0]);
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

  it("shows the guide tab without unmounting a dirty editor", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptEditorView
          prompt={WORKSPACE.prompts[0]}
          draft="Locally edited prompt"
          dirty
          busy={null}
          activeTab="guide"
          onTabChange={() => undefined}
          onDraftChange={() => undefined}
          onSave={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toMatch(
      /id="prompt-tab-guide" role="tab" aria-selected="true"/,
    );
    expect(html).toMatch(
      /id="prompt-panel-edit" role="tabpanel" aria-labelledby="prompt-tab-edit" hidden=""/,
    );
    expect(html).toMatch(
      /id="prompt-panel-guide" role="tabpanel" aria-labelledby="prompt-tab-guide" tabindex="0">/,
    );
    expect(html).toContain('aria-label="unsaved local edit"');
    expect(html).toContain("Locally edited prompt");
    expect(html).toContain(DOCUMENTATION.en.usage);
  });
});
