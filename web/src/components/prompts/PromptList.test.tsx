import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ManagedPrompt } from "../../api/prompts";
import { I18nProvider } from "../../i18n";
import { PromptList } from "./PromptList";
import { groupPromptsByCategory } from "./promptCategories";

function managedPrompt(
  key: string,
  category: string,
  overrides: Partial<ManagedPrompt> = {},
): ManagedPrompt {
  return {
    key,
    name: key,
    description: `${key} description`,
    documentation: {
      en: { usage: "Usage", runtime: "Runtime", editing_guidance: ["Guidance"] },
      zh: { usage: "用途", runtime: "运行时", editing_guidance: ["注意事项"] },
    },
    category,
    template_format: "literal",
    variables: [],
    editable: true,
    draft_content: "Draft",
    published_content: "Published",
    is_modified: false,
    validation_errors: [],
    updated_at: null,
    ...overrides,
  };
}

const INTERLEAVED = [
  managedPrompt("memory.first", "memory"),
  managedPrompt("custom.first", "custom"),
  managedPrompt("chat.first", "chat"),
  managedPrompt("traits.first", "traits"),
  managedPrompt("memory.second", "memory"),
  managedPrompt("tools.first", "tools"),
  managedPrompt("protocol.first", "protocol"),
];

afterEach(() => vi.unstubAllGlobals());

describe("Prompt categories", () => {
  it("uses a stable purpose order while preserving order inside each group", () => {
    const groups = groupPromptsByCategory(INTERLEAVED);

    expect(groups.map((group) => group.category)).toEqual([
      "chat",
      "memory",
      "traits",
      "tools",
      "protocol",
      "custom",
    ]);
    expect(groups.find((group) => group.category === "memory")?.prompts.map(
      (prompt) => prompt.key,
    )).toEqual(["memory.first", "memory.second"]);
  });

  it("renders localized group headings, counts, descriptions, and unknown groups", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptList
          prompts={INTERLEAVED}
          selectedKey="memory.second"
          disabled={false}
          onSelect={() => undefined}
        />
      </I18nProvider>,
    );

    const headings = [
      "Chat responses",
      "Memory &amp; profile",
      "Trait modeling",
      "Tool guidance",
      "Output protocol",
      "custom",
    ];
    headings.reduce((previous, heading) => {
      const position = html.indexOf(heading);
      expect(position).toBeGreaterThan(previous);
      return position;
    }, -1);
    expect(html).toContain("Controls user-facing personas, response stance, and shared context.");
    expect(html).toContain('aria-label="Prompt count: 2"');
    expect(html.match(/memory\.second/g)).toHaveLength(2);
    expect(html).toMatch(/aria-current="true"[^>]*>[\s\S]*memory\.second/);
    expect(html).toContain('aria-label="Prompt index"');
  });

  it("uses Chinese category names when the interface language is Chinese", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => "zh",
      setItem: () => undefined,
    });

    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptList
          prompts={[managedPrompt("chat.first", "chat")]}
          selectedKey="chat.first"
          disabled={false}
          onSelect={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("对话响应");
    expect(html).toContain("控制用户可见回复的人格、回应立场与共享上下文。");
  });

  it("preserves selection, disabled state, and prompt status indicators", () => {
    const prompt = managedPrompt("protocol.first", "protocol", {
      editable: false,
      is_modified: true,
      validation_errors: ["missing required fragment"],
    });
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptList
          prompts={[prompt]}
          selectedKey={prompt.key}
          disabled
          onSelect={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-current="true"/);
    expect(html).toContain("modified");
    expect(html).toContain("Read only");
    expect(html).toContain("Validation 1");
  });
});
