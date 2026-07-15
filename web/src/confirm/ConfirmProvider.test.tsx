import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ConfirmProvider, useConfirm } from "./ConfirmProvider";

function Consumer() {
  const confirm = useConfirm();
  return <span>confirm:{typeof confirm}</span>;
}

describe("ConfirmProvider", () => {
  it("provides one global async confirmation function", () => {
    const html = renderToStaticMarkup(
      <ConfirmProvider>
        <Consumer />
      </ConfirmProvider>,
    );

    expect(html).toContain("confirm:function");
    expect(html).not.toContain('role="alertdialog"');
  });
});
