import { useState } from "react";
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { ContextRail } from "./components/ContextRail";
import { ModelPanel } from "./components/ModelPanel";
import { TracesPanel } from "./components/TracesPanel";
import { EvalPanel } from "./components/EvalPanel";
import { AppShell, type View } from "./components/ui/AppShell";
import { useChat } from "./hooks/useChat";

export default function App() {
  const [view, setView] = useState<View>("chat");
  const { messages, streaming, send } = useChat();

  return (
    <AppShell view={view} onChange={setView}>
      {view === "chat" && (
        // A centered two-column spread: the conversation, and — on wide screens —
        // a live rail of what Vellum is reading about you. Below xl it's one column.
        <div className="mx-auto flex min-h-0 w-full max-w-[76rem] flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <MessageList messages={messages} streaming={streaming} />
            <Composer onSend={send} disabled={streaming} />
          </div>
          <ContextRail
            turns={messages.length}
            className="hidden w-[19rem] border-l border-line xl:flex 2xl:w-[21rem]"
          />
        </div>
      )}
      {view === "model" && <ModelPanel />}
      {view === "traces" && <TracesPanel />}
      {view === "evals" && <EvalPanel />}
    </AppShell>
  );
}
