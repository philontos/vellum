import { useState } from "react";
import { ChatLayout } from "./components/ChatLayout";
import { DiaryPanel } from "./components/DiaryPanel";
import { ModelPanel } from "./components/ModelPanel";
import { TracesPanel } from "./components/TracesPanel";
import { EvalPanel } from "./components/EvalPanel";
import { ProbePanel } from "./components/ProbePanel";
import { PromptsPanel } from "./components/PromptsPanel";
import { AppShell, type View } from "./components/ui/AppShell";
import { useChat } from "./hooks/useChat";
import type { AuthUser } from "./auth/client";
import { useT } from "./i18n";

export function allowViewChange(
  currentView: View,
  promptDirty: boolean,
  confirmDiscard: () => boolean,
): boolean {
  return currentView !== "prompts" || !promptDirty || confirmDiscard();
}

export default function App({
  user,
  onLogout,
}: {
  user: AuthUser | null;
  onLogout?: () => Promise<void>;
}) {
  const { t } = useT();
  const [view, setView] = useState<View>("chat");
  const [promptDirty, setPromptDirty] = useState(false);
  const { messages, streaming, persona, setPersona, send, stop, retry, remove, loadEarlier, canLoadEarlier, cappedEarlier } = useChat(user?.id);

  function changeView(next: View) {
    if (next === view) return;
    if (!allowViewChange(
      view,
      promptDirty,
      () => window.confirm(t("prompts.discardConfirm")),
    )) return;
    setPromptDirty(false);
    setView(next);
  }

  async function logout() {
    if (!onLogout) return;
    if (!allowViewChange(
      view,
      promptDirty,
      () => window.confirm(t("prompts.discardConfirm")),
    )) return;
    setPromptDirty(false);
    await onLogout();
  }

  return (
    <AppShell
      view={view}
      onChange={changeView}
      user={user}
      onLogout={onLogout ? logout : undefined}
    >
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
      {view === "prompts" && <PromptsPanel onDirtyChange={setPromptDirty} />}
      {view === "evals" && <EvalPanel />}
    </AppShell>
  );
}
