import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DiaryPager } from "./DiaryPager";

describe("DiaryPager", () => {
  it("moves the timeline aside and exposes a separate detail page", () => {
    const html = renderToStaticMarkup(
      <DiaryPager
        detailOpen
        timeline={<button type="button">Timeline entry</button>}
        detail={<button type="button">Back from detail</button>}
      />,
    );

    expect(html).toContain('data-diary-page="detail"');
    expect(html).toContain('data-diary-surface="timeline"');
    expect(html).toContain('data-diary-surface="detail"');
    expect(html).toContain('data-active="false"');
    expect(html).toContain('data-active="true"');
    expect(html).toContain("-translate-x-1/2");
  });

  it("slides back to the preserved timeline instead of collapsing inline content", () => {
    const html = renderToStaticMarkup(
      <DiaryPager
        detailOpen={false}
        timeline={<span>Timeline stays mounted</span>}
        detail={<span>Detail stays mounted</span>}
      />,
    );

    expect(html).toContain('data-diary-page="timeline"');
    expect(html).toContain("translate-x-0");
    expect(html).toContain("Timeline stays mounted");
    expect(html).toContain("Detail stays mounted");
  });
});
