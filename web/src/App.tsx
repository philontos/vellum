import { useState } from "react";
import { ChatLayout } from "./components/ChatLayout";
import { DiaryPanel } from "./components/DiaryPanel";
import { ModelPanel } from "./components/ModelPanel";
import { TracesPanel } from "./components/TracesPanel";
import { EvalPanel } from "./components/EvalPanel";
import { AppShell, type View } from "./components/ui/AppShell";
import { useChat } from "./hooks/useChat";

export default function App() {
  const [view, setView] = useState<View>("chat");
  const { messages, streaming, send, stop, retry, remove, loadEarlier, canLoadEarlier, cappedEarlier } = useChat();

  return (
    <AppShell view={view} onChange={setView}>
      {view === "chat" && (
        <ChatLayout
          messages={messages}
          streaming={streaming}
          onSend={send}
          onStop={stop}
          onRetry={retry}
          onDelete={remove}
          canLoadEarlier={canLoadEarlier}
          cappedEarlier={cappedEarlier}
          onLoadEarlier={loadEarlier}
          onOpenDiary={() => setView("diary")}
        />
      )}
      {view === "diary" && <DiaryPanel />}
      {view === "model" && <ModelPanel />}
      {view === "traces" && <TracesPanel />}
      {view === "evals" && <EvalPanel />}
    </AppShell>
  );
}
