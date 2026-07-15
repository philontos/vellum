import { useEffect, useRef, useState } from "react";
import { getModel, type ModelView } from "../api/client";
import { useT } from "../i18n";
import { ModelSections } from "./model/ModelSections";
import { ModelTabs, type ModelSection } from "./model/ModelTabs";

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

  function selectSection(next: ModelSection) {
    setSection(next);
    scrollRef.current?.scrollTo({ top: 0 });
  }

  return (
    <div ref={scrollRef} className="v-canvas flex-1 overflow-y-auto">
      <ModelTabs active={section} onChange={selectSection} />
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
        <h1 className="hidden font-serif text-[26px] tracking-tight text-ink lg:block">{t("nav.you")}</h1>
        <ModelSections model={m} active={section} />
      </div>
    </div>
  );
}
