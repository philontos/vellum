import { useEffect, useRef, useState } from "react";
import { getModel, type ModelView } from "../api/client";
import { useT } from "../i18n";
import { TraitChart } from "./TraitChart";
import { ModelTabs, type ModelSection } from "./model/ModelTabs";
import { SectionHeader } from "./ui/SectionHeader";

export function ModelPanel() {
  const { t } = useT();
  const [m, setM] = useState<ModelView | null>(null);
  const [err, setErr] = useState("");
  const [section, setSection] = useState<ModelSection>("dossier");
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    getModel().then(setM).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div className="p-8 text-sm text-status-fail-fg">{err}</div>;
  if (!m) return <div className="p-8 text-sm text-muted">{t("model.loading")}</div>;

  const facts = m.facts.filter((f) => f.status === "active");

  function selectSection(next: ModelSection) {
    setSection(next);
    scrollRef.current?.scrollTo({ top: 0 });
  }

  return (
    <div ref={scrollRef} className="v-canvas flex-1 overflow-y-auto">
      <ModelTabs active={section} onChange={selectSection} />
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
        <h1 className="hidden font-serif text-[26px] tracking-tight text-ink lg:block">{t("nav.you")}</h1>

        {/* Dossier — full-width narrative banner */}
        <section
          id="model-panel-dossier"
          role="tabpanel"
          aria-labelledby="model-tab-dossier"
          className={`${section === "dossier" ? "block" : "hidden"} lg:mt-8 lg:block`}
        >
          <SectionHeader label={t("model.dossierTitle")} />
          {m.dossier ? (
            <p className="v-dropcap whitespace-pre-wrap font-serif text-[17px] leading-[1.76] text-ink">
              {m.dossier}
            </p>
          ) : (
            <p className="font-serif text-[17px] text-muted">{t("model.dossierEmpty")}</p>
          )}
        </section>

        {/* Facts (narrow) + Personality (wide grid) */}
        <div className="lg:mt-11 lg:grid lg:gap-10 lg:grid-cols-[minmax(0,17rem)_1fr]">
          <section
            id="model-panel-facts"
            role="tabpanel"
            aria-labelledby="model-tab-facts"
            className={`${section === "facts" ? "block" : "hidden"} lg:block`}
          >
            <SectionHeader label={t("model.factsTitle")} />
            <ul className="space-y-2.5 text-sm">
              {facts.map((f) => (
                <li key={f.id} className="flex gap-3 text-ink-soft">
                  <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-gold" />
                  <span>{f.text}</span>
                </li>
              ))}
              {facts.length === 0 && <li className="text-muted">{t("model.factsEmpty")}</li>}
            </ul>
          </section>

          <section
            id="model-panel-traits"
            role="tabpanel"
            aria-labelledby="model-tab-traits"
            className={`${section === "traits" ? "block" : "hidden"} lg:block`}
          >
            <SectionHeader label={t("model.traitsTitle")} />
            <div className="grid gap-4 sm:grid-cols-2">
              {m.traits.map((d) => <TraitChart key={d.dimension} dim={d} />)}
              {m.traits.length === 0 && <div className="text-sm text-muted">{t("model.traitsEmpty")}</div>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
