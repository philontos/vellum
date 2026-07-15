import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders an accessible destructive confirmation", () => {
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Delete this fact?"
        message="It will leave future context."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        tone="danger"
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );

    expect(html).toContain('role="alertdialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('data-tone="danger"');
    expect(html).toContain("Delete this fact?");
    expect(html).toContain("It will leave future context.");
    expect(html).toContain("Delete");
    expect(html).toContain("Cancel");
  });
});
