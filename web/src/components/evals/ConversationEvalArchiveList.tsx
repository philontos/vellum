import type { ConversationEvalRecordSummary } from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";

export function ConversationEvalArchiveList({
  records,
  hasMore,
  loading,
  loadingMore,
  error,
  onOpen,
  onNew,
  onRefresh,
  onLoadMore,
}: {
  records: ConversationEvalRecordSummary[];
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  error: string;
  onOpen: (recordId: number) => void;
  onNew: () => void;
  onRefresh: () => void;
  onLoadMore: () => void;
}) {
  const { t } = useT();
  return (
    <div className="v-canvas flex h-full min-h-0 flex-col">
      <header className="flex flex-none items-center gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-serif text-xl text-ink">{t("eval.archive")}</h2>
          <p className="mt-0.5 text-xs text-muted">{t("eval.archiveSubtitle")}</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="ml-auto min-h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50"
        >
          {t("eval.refresh")}
        </button>
        <button
          type="button"
          onClick={onNew}
          className="min-h-9 rounded-lg bg-accent px-3 text-sm font-medium text-accent-fg hover:bg-accent-ink"
        >
          {t("eval.newEvaluation")}
        </button>
      </header>

      {error && (
        <div role="alert" className="flex-none border-b border-status-warn-fg/30 bg-status-warn-bg px-4 py-2 text-sm text-status-warn-fg">
          {error}
        </div>
      )}

      <div data-scroll-region="eval-archive" className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-3 xl:grid-cols-2">
          {records.map((record) => (
            <button
              key={record.id}
              type="button"
              data-eval-record={record.id}
              onClick={() => onOpen(record.id)}
              className="rounded-xl border border-line bg-surface p-4 text-left shadow-card transition-colors hover:border-accent/45 hover:bg-white/5"
            >
              <div className="flex items-center gap-2">
                <h3 className="font-serif text-base text-ink">
                  {t("eval.recordTitle", { id: record.id })}
                </h3>
                {record.latest_status && <Tag>{record.latest_status}</Tag>}
                <span className="ml-auto text-xs text-muted">
                  {t("eval.count", { n: record.run_count })}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs text-muted">
                <span className="font-mono">{record.prompt_label}</span>
                <span>←</span>
                <span>{record.baseline_prompt_label}</span>
              </div>
              <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-ink-soft">
                {record.source_user_content}
              </p>
              {record.latest_output && (
                <p className="mt-2 line-clamp-2 border-l-2 border-accent/35 pl-3 text-xs leading-relaxed text-muted">
                  {record.latest_output}
                </p>
              )}
              <div className="mt-3 font-mono text-[10px] text-muted">
                {record.created_at}
              </div>
            </button>
          ))}
        </div>

        {records.length === 0 && !loading && (
          <div className="mx-auto max-w-xl py-20 text-center text-sm text-muted">
            {t("eval.archiveEmpty")}
          </div>
        )}
        {loading && records.length === 0 && (
          <div className="py-20 text-center text-sm text-muted">{t("eval.loading")}</div>
        )}
        {hasMore && (
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loadingMore}
            className="mx-auto mt-4 block min-h-10 rounded-lg border border-line bg-surface px-5 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50"
          >
            {loadingMore ? t("eval.loading") : t("eval.loadMoreArchives")}
          </button>
        )}
      </div>
    </div>
  );
}
