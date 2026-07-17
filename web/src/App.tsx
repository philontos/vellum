import { useEffect, useState } from "react";
import { ChatLayout } from "./components/ChatLayout";
import { DiaryPanel } from "./components/DiaryPanel";
import { ModelPanel } from "./components/ModelPanel";
import { AdminPanel } from "./components/AdminPanel";
import { AppShell, type View } from "./components/ui/AppShell";
import { useChat } from "./hooks/useChat";
import type { AuthUser } from "./auth/client";
import { diaryEntryPath, diaryTimelinePath, parseDiaryRoute } from "./diary/route";
import { useT } from "./i18n";

const VELLUM_PAGE_STATE = "vellumPage";

export function allowViewChange(
  currentView: View,
  promptDirty: boolean,
  confirmDiscard: () => boolean,
): boolean {
  return currentView !== "admin" || !promptDirty || confirmDiscard();
}

export default function App({
  user,
  onLogout,
}: {
  user: AuthUser | null;
  onLogout?: () => Promise<void>;
}) {
  const { t } = useT();
  const initialDiaryRoute = parseDiaryRoute(window.location.pathname);
  const [view, setView] = useState<View>(
    () => initialDiaryRoute.kind === "other" ? "chat" : "diary",
  );
  const [diaryEntryId, setDiaryEntryId] = useState<number | null>(
    () => initialDiaryRoute.kind === "entry" ? initialDiaryRoute.entryId : null,
  );
  const [promptDirty, setPromptDirty] = useState(false);
  const { messages, streaming, persona, setPersona, send, stop, retry, remove, loadEarlier, canLoadEarlier, cappedEarlier } = useChat(user?.id);

  useEffect(() => {
    function followBrowserHistory() {
      const route = parseDiaryRoute(window.location.pathname);
      if (route.kind === "timeline") {
        setView("diary");
        setDiaryEntryId(null);
      } else if (route.kind === "entry") {
        setView("diary");
        setDiaryEntryId(route.entryId);
      } else {
        setView("chat");
        setDiaryEntryId(null);
      }
    }
    window.addEventListener("popstate", followBrowserHistory);
    return () => window.removeEventListener("popstate", followBrowserHistory);
  }, []);

  function showDiaryTimeline() {
    window.history.replaceState(
      { [VELLUM_PAGE_STATE]: "diary" },
      "",
      diaryTimelinePath(),
    );
    setDiaryEntryId(null);
  }

  function changeView(next: View) {
    if (next === view) {
      if (next === "diary" && diaryEntryId !== null) showDiaryTimeline();
      return;
    }
    if (!allowViewChange(
      view,
      promptDirty,
      () => window.confirm(t("prompts.discardConfirm")),
    )) return;
    setPromptDirty(false);
    if (next === "diary") {
      showDiaryTimeline();
    } else if (view === "diary") {
      window.history.replaceState({ [VELLUM_PAGE_STATE]: next }, "", "/");
      setDiaryEntryId(null);
    }
    setView(next);
  }

  function openDiaryEntry(entryId: number) {
    window.history.pushState(
      { [VELLUM_PAGE_STATE]: "diary-entry" },
      "",
      diaryEntryPath(entryId),
    );
    setDiaryEntryId(entryId);
  }

  function closeDiaryEntry() {
    if (window.history.state?.[VELLUM_PAGE_STATE] === "diary-entry") {
      window.history.back();
      return;
    }
    showDiaryTimeline();
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
          onOpenDiary={() => changeView("diary")}
        />
      )}
      {view === "diary" && (
        <DiaryPanel
          userId={user?.id}
          entryId={diaryEntryId}
          onOpenEntry={openDiaryEntry}
          onCloseEntry={closeDiaryEntry}
        />
      )}
      {view === "model" && <ModelPanel />}
      {view === "admin" && (
        <AdminPanel
          user={user}
          promptDirty={promptDirty}
          onPromptDirtyChange={setPromptDirty}
        />
      )}
    </AppShell>
  );
}
