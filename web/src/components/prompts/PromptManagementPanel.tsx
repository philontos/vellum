import type { PromptWorkspace } from "../../api/prompts";
import { useT } from "../../i18n";
import { PromptEditor, type PromptBusy } from "./PromptEditor";
import { PromptList } from "./PromptList";
import { PromptSelect } from "./PromptSelect";

export function PromptManagementPanel({
  workspace,
  selectedKey,
  draft,
  dirty,
  busy,
  error,
  onSelect,
  onDraftChange,
  onSave,
}: {
  workspace: PromptWorkspace;
  selectedKey: string;
  draft: string;
  dirty: boolean;
  busy: PromptBusy;
  error: string;
  onSelect: (key: string) => void;
  onDraftChange: (content: string) => void;
  onSave: () => void;
}) {
  const { t } = useT();
  const selected = workspace.prompts.find((prompt) => prompt.key === selectedKey);

  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-7xl flex-col px-3 py-3 sm:px-5 sm:py-4">
      {error && (
        <div role="alert" className="mb-3 flex-none rounded-lg border border-status-fail-fg/30 bg-status-fail-bg px-3 py-2 text-sm text-status-fail-fg">
          {error}
        </div>
      )}
      <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)] gap-3 lg:grid-cols-[16rem_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] lg:gap-4 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="lg:hidden">
          <PromptSelect
            prompts={workspace.prompts}
            selectedKey={selectedKey}
            disabled={busy !== null}
            onSelect={onSelect}
          />
        </div>
        <div className="hidden min-h-0 lg:block lg:h-full">
          <PromptList
            prompts={workspace.prompts}
            selectedKey={selectedKey}
            disabled={busy !== null}
            onSelect={onSelect}
          />
        </div>
        <div
          data-scroll-region="prompt-editor"
          role="region"
          aria-label={t("prompts.editorScrollLabel")}
          className="min-h-0 min-w-0 overflow-y-auto overscroll-contain lg:pr-1"
        >
          {selected ? (
            <PromptEditor
              prompt={selected}
              draft={draft}
              dirty={dirty}
              busy={busy}
              onDraftChange={onDraftChange}
              onSave={onSave}
            />
          ) : (
            <div className="rounded-xl border border-line bg-surface p-8 text-sm text-muted">
              {t("prompts.empty")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
