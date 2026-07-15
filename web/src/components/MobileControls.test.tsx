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
