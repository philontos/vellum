import { useState } from "react";
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
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
        <>
          <MessageList messages={messages} streaming={streaming} />
          <Composer onSend={send} disabled={streaming} />
        </>
      )}
      {view === "model" && <ModelPanel />}
      {view === "traces" && <TracesPanel />}
      {view === "evals" && <EvalPanel />}
    </AppShell>
  );
}
