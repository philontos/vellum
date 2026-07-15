import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../auth/AuthProvider";
import { LoginScreen } from "../auth/LoginScreen";
import { ConfirmProvider } from "../confirm/ConfirmProvider";
import { I18nProvider } from "../i18n";
import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";

function withLanguage(child: React.ReactNode) {
  return renderToStaticMarkup(
    <I18nProvider>
      <ConfirmProvider>{child}</ConfirmProvider>
    </I18nProvider>,
  );
}

describe("mobile controls", () => {
  it("keeps the composer above the phone safe area and avoids iOS input zoom", () => {
    const html = withLanguage(
      <Composer onSend={() => undefined} onStop={() => undefined} streaming={false} />,
    );

    expect(html).toContain("v-safe-bottom");
    expect(html).toContain("text-base sm:text-sm");
  });

  it("keeps message actions visible on touch screens", () => {
    const html = withLanguage(
      <MessageBubble
        m={{ turn: 1, role: "user", content: "hello" }}
        latest
        streaming={false}
        onDelete={() => undefined}
      />,
    );

    expect(html).toContain("opacity-70 sm:opacity-0");
  });

  it("uses compact responsive type only for assistant replies", () => {
    const assistantHtml = withLanguage(
      <MessageBubble
        m={{ turn: 1, role: "assistant", content: "A considered answer" }}
        latest
        streaming={false}
      />,
    );
    const userHtml = withLanguage(
      <MessageBubble
        m={{ turn: 2, role: "user", content: "A personal message" }}
        latest
        streaming={false}
      />,
    );

    expect(assistantHtml).toContain(
      "v-md text-[15px] font-medium leading-[1.68] sm:text-base sm:font-normal sm:leading-[1.72]",
    );
    expect(userHtml).toContain("text-[13.5px]");
    expect(userHtml).toContain("text-ink-soft");
    expect(userHtml).not.toContain("text-[15px]");
  });

  it("does not reserve a right-side action gutter beside assistant text on mobile", () => {
    const assistantHtml = withLanguage(
      <MessageBubble
        m={{ turn: 1, role: "assistant", content: "A full-width answer" }}
        latest={false}
        streaming={false}
        onDelete={() => undefined}
      />,
    );

    expect(assistantHtml).toContain("min-w-0 w-full md:max-w-[88%]");
    expect(assistantHtml).not.toContain("max-w-[calc(100%_-_2.5rem)]");
    expect(assistantHtml).toContain("absolute right-0 top-0 md:static md:pt-5");
  });

  it("uses a keyboard-safe viewport and 16px login inputs", () => {
    const html = withLanguage(
      <AuthProvider>
        <LoginScreen />
      </AuthProvider>,
    );

    expect(html).toContain("h-dvh");
    expect(html.match(/text-base sm:text-sm/g)).toHaveLength(2);
  });
});
