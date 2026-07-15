import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FactActions } from "./FactActions";

describe("FactActions", () => {
  it("keeps mobile actions in a narrow vertical icon rail", () => {
    const html = renderToStaticMarkup(
      <FactActions
        editLabel="Edit"
        deleteLabel="Delete"
        busy={false}
        onEdit={() => undefined}
        onDelete={() => undefined}
      />,
    );

    expect(html).toContain('data-fact-actions="compact"');
    expect(html).toContain('data-layout="vertical"');
    expect(html).toMatch(/class="[^"]*w-10[^"]*flex-col/);
    expect(html).toContain('aria-label="Edit"');
    expect(html).toContain('aria-label="Delete"');
    expect(html.match(/<svg/g)).toHaveLength(2);
    expect(html).not.toContain(">Edit</button>");
    expect(html).not.toContain(">Delete</button>");
  });
});
