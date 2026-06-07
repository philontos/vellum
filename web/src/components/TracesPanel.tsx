import { useEffect, useState } from "react";
import { getTraces, patchTrace, type Trace } from "../api/client";

const STAGES = ["", "chat", "facts", "trait", "summary", "dossier"];

export function TracesPanel() {
  const [stage, setStage] = useState("");
  const [rows, setRows] = useState<Trace[]>([]);
  const [open, setOpen] = useState<number | null>(null);

  async function load() {
    setRows(await getTraces(stage || undefined));
  }
  useEffect(() => { load().catch(() => void 0); }, [stage]);

  async function pin(t: Trace) {
    await patchTrace(t.id, { pinned: !t.pinned });
    load();
  }
  async function note(t: Trace, value: string) {
    await patchTrace(t.id, { note: value });
    load();
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-gray-200 p-2 text-sm">
        <select value={stage} onChange={(e) => setStage(e.target.value)} className="rounded border px-2 py-1">
          {STAGES.map((s) => <option key={s} value={s}>{s || "all stages"}</option>)}
        </select>
        <button onClick={() => load()} className="rounded border px-2 py-1">刷新</button>
        <span className="text-gray-400">{rows.length} 条</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {rows.map((t) => (
          <div key={t.id} className="border-b border-gray-100 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <button onClick={() => pin(t)} title="pin (protect from prune)">
                {t.pinned ? "★" : "☆"}
              </button>
              <span className="rounded bg-gray-100 px-1.5 text-xs">{t.stage}</span>
              <span className="text-gray-500">{t.model}</span>
              <span className="text-xs text-gray-400">
                {t.prompt_tokens ?? "?"}→{t.completion_tokens ?? "?"} tok · {t.duration_ms ?? "?"}ms
              </span>
              <span className="ml-auto text-xs text-gray-400">{t.created_at}</span>
              <button className="text-blue-600" onClick={() => setOpen(open === t.id ? null : t.id)}>
                {open === t.id ? "收起" : "展开"}
              </button>
            </div>
            {open === t.id && (
              <div className="mt-2 space-y-2">
                <input
                  defaultValue={t.note ?? ""}
                  placeholder="备注（好/塌了/抽错了…）"
                  className="w-full rounded border px-2 py-1 text-xs"
                  onBlur={(e) => note(t, e.target.value)}
                />
                <Field label="PROMPT" body={t.prompt} />
                <Field label="OUTPUT" body={t.output} />
              </div>
            )}
          </div>
        ))}
        {rows.length === 0 && <div className="p-4 text-gray-400">还没有 trace（聊几句、等后台建模触发）。</div>}
      </div>
    </div>
  );
}

function Field({ label, body }: { label: string; body: string | null }) {
  return (
    <div>
      <div className="text-xs font-semibold text-gray-500">{label}</div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs">
        {body ?? <span className="text-gray-400">（已滚动清除；pin 可保护未来的）</span>}
      </pre>
    </div>
  );
}
