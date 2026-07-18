import { useState } from "react";

import type { ConversationPromptMessage } from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { diffPromptLines } from "./promptDiff";

type PromptView = "diff" | "candidate" | "baseline" | "inputs";

export function PromptInspector({
  baseline,
  candidate,
  baselineInput,
  candidateInput,
}: {
  baseline: string | null;
  candidate: string;
  baselineInput: ConversationPromptMessage[] | null;
  candidateInput: ConversationPromptMessage[];
}) {
  const { t } = useT();
  const [view, setView] = useState<PromptView>("diff");
  const tabs: Array<[PromptView, string]> = [
    ["diff", t("eval.promptDiff")],
    ["candidate", t("eval.evaluatedPrompt")],
    ["baseline", t("eval.baselinePrompt")],
    ["inputs", t("eval.fullInputs")],
  ];

  return (
    <section className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex items-center gap-1 overflow-x-auto border-b border-line bg-well/45 p-1.5">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={view === key}
            onClick={() => setView(key)}
            className={
              "min-h-8 flex-none rounded-md px-3 text-xs transition-colors " +
              (view === key
                ? "bg-surface text-ink shadow-card"
                : "text-muted hover:bg-white/5 hover:text-ink-soft")
            }
          >
            {label}
          </button>
        ))}
      </div>

      {view === "diff" && (
        <PromptDiff baseline={baseline} candidate={candidate} />
      )}
      {view === "candidate" && (
        <PromptText value={candidate} emptyLabel={t("eval.noPromptSnapshot")} />
      )}
      {view === "baseline" && (
        <PromptText value={baseline} emptyLabel={t("eval.noBaselinePrompt")} />
      )}
      {view === "inputs" && (
        <div className="grid min-h-[18rem] grid-cols-2 divide-x divide-line">
          <MessageSnapshot
            title={t("eval.baselineInput")}
            messages={baselineInput}
            emptyLabel={t("eval.noBaselinePrompt")}
          />
          <MessageSnapshot
            title={t("eval.evaluatedInput")}
            messages={candidateInput}
            emptyLabel={t("eval.noPromptSnapshot")}
          />
        </div>
      )}
    </section>
  );
}

function PromptDiff({
  baseline,
  candidate,
}: {
  baseline: string | null;
  candidate: string;
}) {
  const { t } = useT();
  const rows = diffPromptLines(baseline ?? "", candidate);
  return (
    <div data-prompt-diff className="max-h-[28rem] min-h-[18rem] overflow-auto bg-well/25 font-mono text-xs leading-5">
      {baseline === null && (
        <div className="border-b border-line px-4 py-2 text-muted">
          {t("eval.noBaselinePrompt")}
        </div>
      )}
      {rows.map((row, index) => {
        const tone = row.kind === "added"
          ? "bg-status-pass-bg/70 text-status-pass-fg"
          : row.kind === "removed"
            ? "bg-status-warn-bg/70 text-status-warn-fg"
            : "text-ink-soft";
        return (
          <div
            key={`${index}:${row.kind}:${row.text}`}
            className={`grid min-w-max grid-cols-[3rem_3rem_1.5rem_minmax(36rem,1fr)] border-b border-line/35 ${tone}`}
          >
            <span className="select-none border-r border-line/40 px-2 text-right text-muted">
              {row.baselineLine ?? ""}
            </span>
            <span className="select-none border-r border-line/40 px-2 text-right text-muted">
              {row.candidateLine ?? ""}
            </span>
            <span className="select-none text-center">
              {row.kind === "added" ? "+" : row.kind === "removed" ? "−" : " "}
            </span>
            <span className="whitespace-pre-wrap break-words px-2">{row.text || " "}</span>
          </div>
        );
      })}
    </div>
  );
}

function PromptText({ value, emptyLabel }: { value: string | null; emptyLabel: string }) {
  return (
    <pre className="max-h-[28rem] min-h-[18rem] overflow-auto whitespace-pre-wrap break-words bg-well/25 px-4 py-3 font-mono text-xs leading-5 text-ink-soft">
      {value || emptyLabel}
    </pre>
  );
}

function MessageSnapshot({
  title,
  messages,
  emptyLabel,
}: {
  title: string;
  messages: ConversationPromptMessage[] | null;
  emptyLabel: string;
}) {
  return (
    <div className="max-h-[28rem] overflow-auto p-3">
      <h4 className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
        {title}
      </h4>
      {!messages?.length && <p className="text-sm text-muted">{emptyLabel}</p>}
      {messages?.map((message, index) => (
        <div key={`${index}:${message.role}`} className="mb-2 rounded-lg border border-line bg-well/55 p-3">
          <div className="mb-1 font-mono text-[10px] uppercase text-muted">
            {message.role}{message.name ? ` · ${message.name}` : ""}
          </div>
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-ink-soft">
            {message.content}
          </pre>
        </div>
      ))}
    </div>
  );
}
