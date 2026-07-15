import { useEffect, useState } from "react";

import {
  getPromptWorkspace,
  publishPromptWorkspace,
  restorePromptRelease,
  savePromptDraft,
  type PromptRelease,
  type PromptWorkspace,
} from "../api/prompts";
import { useT } from "../i18n";
import type { PromptBusy } from "./prompts/PromptEditor";
import { PromptManagementPanel } from "./prompts/PromptManagementPanel";
import { PromptPublishBar } from "./prompts/PromptPublishBar";
import { ReleaseHistory } from "./prompts/ReleaseHistory";
import {
  PromptWorkspaceTabs,
  type PromptWorkspaceTab,
} from "./prompts/PromptWorkspaceTabs";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function PromptsPanel({
  onDirtyChange,
}: {
  onDirtyChange?: (dirty: boolean) => void;
} = {}) {
  const { t } = useT();
  const [workspace, setWorkspace] = useState<PromptWorkspace | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [activeTab, setActiveTab] = useState<PromptWorkspaceTab>("manage");
  const [busy, setBusy] = useState<PromptBusy>("refresh");
  const [error, setError] = useState("");

  const selectedPrompt = workspace?.prompts.find((prompt) => prompt.key === selectedKey);
  const dirty = Boolean(selectedPrompt && draft !== selectedPrompt.draft_content);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  useEffect(() => () => {
    onDirtyChange?.(false);
  }, [onDirtyChange]);

  function installWorkspace(next: PromptWorkspace, preferredKey = selectedKey) {
    const nextPrompt = next.prompts.find((prompt) => prompt.key === preferredKey) ?? next.prompts[0];
    setWorkspace(next);
    setSelectedKey(nextPrompt?.key ?? "");
    setDraft(nextPrompt?.draft_content ?? "");
  }

  useEffect(() => {
    let cancelled = false;
    getPromptWorkspace()
      .then((next) => {
        if (cancelled) return;
        const first = next.prompts[0];
        setWorkspace(next);
        setSelectedKey(first?.key ?? "");
        setDraft(first?.draft_content ?? "");
      })
      .catch((loadError) => {
        if (!cancelled) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (!cancelled) setBusy(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  async function refresh() {
    if (busy) return;
    if (dirty && !window.confirm(t("prompts.discardConfirm"))) return;
    setBusy("refresh");
    setError("");
    try {
      installWorkspace(await getPromptWorkspace());
    } catch (refreshError) {
      setError(errorMessage(refreshError));
    } finally {
      setBusy(null);
    }
  }

  function selectPrompt(key: string) {
    if (!workspace || busy || key === selectedKey) return;
    if (dirty && !window.confirm(t("prompts.discardConfirm"))) return;
    const next = workspace.prompts.find((prompt) => prompt.key === key);
    if (!next) return;
    setSelectedKey(key);
    setDraft(next.draft_content);
    setError("");
  }

  async function save() {
    if (!workspace || !selectedPrompt?.editable || !dirty || busy) return;
    setBusy("save");
    setError("");
    try {
      const next = await savePromptDraft(selectedPrompt.key, draft, workspace.workspace_revision);
      installWorkspace(next, selectedPrompt.key);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    const hasPublishableChanges = Boolean(
      workspace && (workspace.has_unpublished_changes || workspace.active_release === null),
    );
    if (!workspace || busy || dirty || !hasPublishableChanges) return;
    if (workspace.prompts.some((prompt) => prompt.validation_errors.length > 0)) return;
    if (!window.confirm(t("prompts.publishConfirm"))) return;
    setBusy("publish");
    setError("");
    try {
      installWorkspace(await publishPromptWorkspace(workspace.workspace_revision, note));
      setNote("");
    } catch (publishError) {
      setError(errorMessage(publishError));
    } finally {
      setBusy(null);
    }
  }

  async function restore(release: PromptRelease) {
    if (!workspace || busy || release.is_active) return;
    if (dirty && !window.confirm(t("prompts.discardConfirm"))) return;
    if (!window.confirm(t("prompts.restoreConfirm", { version: release.version }))) return;
    setBusy("restore");
    setError("");
    try {
      installWorkspace(
        await restorePromptRelease(release.id, workspace.workspace_revision),
      );
      setActiveTab("manage");
    } catch (restoreError) {
      setError(errorMessage(restoreError));
    } finally {
      setBusy(null);
    }
  }

  if (!workspace) {
    return (
      <div className="v-canvas flex h-full flex-col">
        <div className="border-b border-line px-4 py-4">
          <h1 className="font-serif text-2xl text-ink">{t("prompts.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("prompts.subtitle")}</p>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-sm text-muted">
          {error || t("prompts.loading")}
          {error && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void refresh()}
              className="min-h-10 rounded-lg border border-line bg-surface px-3 text-ink-soft"
            >
              {t("prompts.refresh")}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <PromptWorkspaceView
      workspace={workspace}
      selectedKey={selectedKey}
      draft={draft}
      note={note}
      dirty={dirty}
      busy={busy}
      error={error}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onSelect={selectPrompt}
      onDraftChange={setDraft}
      onNoteChange={setNote}
      onSave={() => void save()}
      onPublish={() => void publish()}
      onRestore={(release) => void restore(release)}
      onRefresh={() => void refresh()}
    />
  );
}

export function PromptWorkspaceView({
  workspace,
  selectedKey,
  draft,
  note,
  dirty,
  busy,
  error,
  activeTab,
  onTabChange,
  onSelect,
  onDraftChange,
  onNoteChange,
  onSave,
  onPublish,
  onRestore,
  onRefresh,
}: {
  workspace: PromptWorkspace;
  selectedKey: string;
  draft: string;
  note: string;
  dirty: boolean;
  busy: PromptBusy;
  error: string;
  activeTab: PromptWorkspaceTab;
  onTabChange: (tab: PromptWorkspaceTab) => void;
  onSelect: (key: string) => void;
  onDraftChange: (content: string) => void;
  onNoteChange: (note: string) => void;
  onSave: () => void;
  onPublish: () => void;
  onRestore: (release: PromptRelease) => void;
  onRefresh: () => void;
}) {
  const { t } = useT();
  const hasValidationErrors = workspace.prompts.some(
    (prompt) => prompt.validation_errors.length > 0,
  );
  const hasPublishableChanges = (
    workspace.has_unpublished_changes || workspace.active_release === null
  );
  const publishDisabled = Boolean(
    busy || dirty || hasValidationErrors || !hasPublishableChanges,
  );
  const publishBlocker = dirty
    ? t("prompts.publishBlockedDirty")
    : hasValidationErrors
      ? t("prompts.publishBlockedValidation")
      : !hasPublishableChanges
        ? t("prompts.publishBlockedNoChanges")
        : "";

  return (
    <div
      aria-busy={busy !== null}
      className="v-canvas flex h-full min-h-0 flex-col overflow-hidden"
    >
      <header className="flex flex-none flex-wrap items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1 className="font-serif text-2xl text-ink">{t("prompts.title")}</h1>
            <span className="font-mono text-[10px] text-muted">
              {t("prompts.revision", { revision: workspace.workspace_revision })}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted">{t("prompts.subtitle")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-status-neutral-bg px-2 py-1 text-status-neutral-fg">
            {workspace.active_release
              ? t("prompts.active", { version: workspace.active_release.version })
              : t("prompts.noActive")}
          </span>
          <span className={workspace.has_unpublished_changes ? "text-status-warn-fg" : "text-status-pass-fg"}>
            {workspace.has_unpublished_changes ? t("prompts.unpublished") : t("prompts.synced")}
          </span>
          <button
            type="button"
            disabled={busy !== null}
            onClick={onRefresh}
            className="min-h-10 rounded-lg border border-line bg-surface px-3 text-ink-soft transition-colors hover:bg-white/5 disabled:opacity-60"
          >
            {t("prompts.refresh")}
          </button>
        </div>
      </header>
      <PromptWorkspaceTabs
        active={activeTab}
        dirty={dirty}
        releaseCount={workspace.releases.length}
        onChange={onTabChange}
      />

      <div className="min-h-0 flex-1 overflow-hidden">
        <div
          id="prompt-workspace-panel-manage"
          role="tabpanel"
          aria-labelledby="prompt-workspace-tab-manage"
          hidden={activeTab !== "manage"}
          className="h-full min-h-0"
        >
          <PromptManagementPanel
            workspace={workspace}
            selectedKey={selectedKey}
            draft={draft}
            dirty={dirty}
            busy={busy}
            error={error}
            onSelect={onSelect}
            onDraftChange={onDraftChange}
            onSave={onSave}
          />
        </div>

        <div
          id="prompt-workspace-panel-history"
          role="tabpanel"
          aria-labelledby="prompt-workspace-tab-history"
          hidden={activeTab !== "history"}
          className="h-full min-h-0"
        >
          <div className="mx-auto flex h-full min-h-0 w-full max-w-7xl flex-col px-3 py-3 sm:px-5 sm:py-4">
            {error && (
              <div role="alert" className="mb-3 flex-none rounded-lg border border-status-fail-fg/30 bg-status-fail-bg px-3 py-2 text-sm text-status-fail-fg">
                {error}
              </div>
            )}
            <div className="flex-none pb-3">
              <PromptPublishBar
                note={note}
                busy={busy}
                disabled={publishDisabled}
                blocker={publishBlocker}
                onNoteChange={onNoteChange}
                onPublish={onPublish}
              />
            </div>
            <div className="min-h-0 flex-1">
              <ReleaseHistory
                releases={workspace.releases}
                busy={busy}
                onRestore={onRestore}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
