import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ManagedPrompt } from "../../api/prompts";
import { I18nProvider } from "../../i18n";
import { PromptSelect } from "./PromptSelect";

const PROMPT: ManagedPrompt = {
  key: "memory.summary",
  name: "Memory summary",
  description: "Summarizes a conversation",
  documentation: {
    en: { usage: "Usage", runtime: "Runtime", editing_guidance: ["Guidance"] },
    zh: { usage: "用途", runtime: "运行时", editing_guidance: ["注意事项"] },
  },
  category: "memory",
  template_format: "format",
  variables: [],
  editable: false,
  draft_content: "Draft",
  published_content: "Published",
  is_modified: true,
  validation_errors: ["missing variable", "invalid placeholder"],
  updated_at: null,
};

describe("PromptSelect", () => {
  it("keeps prompt statuses visible in the compact index", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <PromptSelect
          prompts={[PROMPT]}
          selectedKey={PROMPT.key}
          disabled={false}
          onSelect={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('<optgroup label="Memory &amp; profile">');
    expect(html).toContain("Memory summary · memory.summary");
    expect(html).toContain("modified");
    expect(html).toContain("Read only");
    expect(html).toContain("Validation 2");
  });
});
