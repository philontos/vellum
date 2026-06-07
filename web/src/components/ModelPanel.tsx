import { useEffect, useState } from "react";
import { getModel, type ModelView } from "../api/client";
import { TraitChart } from "./TraitChart";

export function ModelPanel() {
  const [m, setM] = useState<ModelView | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getModel().then(setM).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div className="p-4 text-sm text-red-600">{err}</div>;
  if (!m) return <div className="p-4 text-sm text-gray-400">加载中…</div>;

  const activeFacts = m.facts.filter((f) => f.status === "active");
  const oldFacts = m.facts.filter((f) => f.status !== "active");

  return (
    <div className="space-y-5 overflow-y-auto p-4">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">Dossier — 你是谁</h2>
        <div className="whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm">
          {m.dossier || <span className="text-gray-400">（还没生成）</span>}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">Facts</h2>
        <ul className="space-y-1 text-sm">
          {activeFacts.map((f) => <li key={f.id}>• {f.text}</li>)}
          {oldFacts.map((f) => <li key={f.id} className="text-gray-400 line-through">• {f.text}</li>)}
          {m.facts.length === 0 && <li className="text-gray-400">（还没抽到事实）</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">人格维度</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {m.traits.map((d) => <TraitChart key={d.dimension} dim={d} />)}
          {m.traits.length === 0 && <div className="text-sm text-gray-400">（还没建模，多聊几轮）</div>}
        </div>
      </section>
    </div>
  );
}
