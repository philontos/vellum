import { useState } from "react";
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { ModelPanel } from "./components/ModelPanel";
import { TracesPanel } from "./components/TracesPanel";
import { useChat } from "./hooks/useChat";
import { useT } from "./i18n";

type View = "chat" | "model" | "traces";

export default function App() {
  const [view, setView] = useState<View>("chat");
  const { messages, streaming, send } = useChat();
  const { t, lang, setLang } = useT();

  const tab = (v: View, label: string) => (
    <button
      onClick={() => setView(v)}
      className={`px-3 py-2 text-sm ${view === v ? "border-b-2 border-blue-600 font-medium" : "text-gray-500"}`}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col">
      <header className="flex items-center gap-1 border-b border-gray-200 px-2">
        <span className="px-2 text-sm font-semibold text-gray-700">Vellum</span>
        {tab("chat", t("nav.chat"))}
        {tab("model", t("nav.you"))}
        {tab("traces", t("nav.traces"))}
        <button
          onClick={() => setLang(lang === "en" ? "zh" : "en")}
          className="ml-auto px-2 py-2 text-sm text-gray-500 hover:text-gray-700"
          title={lang === "en" ? "切换到中文" : "Switch to English"}
        >
          {lang === "en" ? "中" : "EN"}
        </button>
      </header>
      {view === "chat" && (
        <>
          <MessageList messages={messages} />
          <Composer onSend={send} disabled={streaming} />
        </>
      )}
      {view === "model" && <ModelPanel />}
      {view === "traces" && <TracesPanel />}
    </div>
  );
}
