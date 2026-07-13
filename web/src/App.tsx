import { useState } from "react";
import { ChatLayout } from "./components/ChatLayout";
import { DiaryPanel } from "./components/DiaryPanel";
import { ModelPanel } from "./components/ModelPanel";
import { TracesPanel } from "./components/TracesPanel";
import { EvalPanel } from "./components/EvalPanel";
import { ProbePanel } from "./components/ProbePanel";
import { AppShell, type View } from "./components/ui/AppShell";
import { useChat } from "./hooks/useChat";
import type { AuthUser } from "./auth/client";

export default function App({
  user,
  onLogout,
}: {
  user: AuthUser | null;
  onLogout?: () => Promise<void>;
}) {
  const [view, setView] = useState<View>("chat");
  const { messages, streaming, persona, setPersona, send, stop, retry, remove, loadEarlier, canLoadEarlier, cappedEarlier } = useChat(user?.id);

  return (
    <AppShell view={view} onChange={setView} user={user} onLogout={onLogout}>
      {view === "chat" && (
        <ChatLayout
          messages={messages}
          streaming={streaming}
          persona={persona}
          onPersonaChange={setPersona}
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
      {view === "diary" && <DiaryPanel userId={user?.id} />}
      {view === "model" && <ModelPanel />}
      {view === "traces" && <TracesPanel />}
      {view === "probe" && <ProbePanel />}
      {view === "evals" && <EvalPanel />}
    </AppShell>
  );
}
