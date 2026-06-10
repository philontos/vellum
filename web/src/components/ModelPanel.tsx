import { useEffect, useState } from "react";
import { getModel, type ModelView } from "../api/client";
import { useT } from "../i18n";
import { TraitChart } from "./TraitChart";
import { Card } from "./ui/Card";
import { SectionHeader } from "./ui/SectionHeader";

export function ModelPanel() {
  const { t } = useT();
  const [m, setM] = useState<ModelView | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getModel().then(setM).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div className="p-8 text-sm text-status-fail-fg">{err}</div>;
  if (!m) return <div className="p-8 text-sm text-muted">{t("model.loading")}</div>;

  const activeFacts = m.facts.filter((f) => f.status === "active");
  const oldFacts = m.facts.filter((f) => f.status !== "active");

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-9 px-8 py-10">
        <section>
          <SectionHeader label={t("model.dossierTitle")} />
          <Card className="px-5 py-4">
            <div className="whitespace-pre-wrap font-serif text-[15.5px] leading-[1.72] text-ink-soft">
              {m.dossier || <span className="text-muted">{t("model.dossierEmpty")}</span>}
            </div>
          </Card>
        </section>

        <section>
          <SectionHeader label={t("model.factsTitle")} />
          <ul className="space-y-1.5 text-sm text-ink-soft">
            {activeFacts.map((f) => (
              <li key={f.id} className="flex gap-2.5">
                <span className="text-terracotta">—</span>
                <span>{f.text}</span>
              </li>
            ))}
            {oldFacts.map((f) => (
              <li key={f.id} className="flex gap-2.5 text-muted line-through">
                <span className="text-line">—</span>
                <span>{f.text}</span>
              </li>
            ))}
            {m.facts.length === 0 && <li className="text-muted">{t("model.factsEmpty")}</li>}
          </ul>
        </section>

        <section>
          <SectionHeader label={t("model.traitsTitle")} />
          <div className="grid gap-4 sm:grid-cols-2">
            {m.traits.map((d) => (
              <TraitChart key={d.dimension} dim={d} />
            ))}
            {m.traits.length === 0 && <div className="text-sm text-muted">{t("model.traitsEmpty")}</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
