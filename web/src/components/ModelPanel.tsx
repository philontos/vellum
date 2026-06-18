import { useEffect, useState } from "react";
import { getModel, type ModelView } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { TraitChart } from "./TraitChart";
import { SectionHeader } from "./ui/SectionHeader";

export function ModelPanel() {
  const { t } = useT();
  const blur = usePrivacyBlur();
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
    <div className="v-canvas flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-9 px-8 py-10">
        <h1 className="font-serif text-[26px] tracking-tight text-ink">{t("nav.you")}</h1>

        <section>
          <SectionHeader label={t("model.dossierTitle")} />
          {m.dossier ? (
            <p className={`v-dropcap whitespace-pre-wrap font-serif text-[17px] leading-[1.76] text-ink ${blur}`}>
              {m.dossier}
            </p>
          ) : (
            <p className="font-serif text-[17px] text-muted">{t("model.dossierEmpty")}</p>
          )}
        </section>

        <section>
          <SectionHeader label={t("model.factsTitle")} />
          <ul className="space-y-2.5 text-sm">
            {activeFacts.map((f) => (
              <li key={f.id} className="flex gap-3 text-ink-soft">
                <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-gold" />
                <span className={blur}>{f.text}</span>
              </li>
            ))}
            {oldFacts.map((f) => (
              <li key={f.id} className="flex gap-3 text-muted line-through decoration-line">
                <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-line" />
                <span className={blur}>{f.text}</span>
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
