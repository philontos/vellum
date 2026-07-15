import type { ModelView } from "../../api/client";
import { useT } from "../../i18n";
import { TraitChart } from "../TraitChart";
import { SectionHeader } from "../ui/SectionHeader";
import type { ModelSection } from "./ModelTabs";

export function ModelSections({
  model,
  active,
}: {
  model: ModelView;
  active: ModelSection;
}) {
  const { t } = useT();
  const facts = model.facts.filter((fact) => fact.status === "active");

  return (
    <>
      <section
        id="model-panel-dossier"
        role="tabpanel"
        aria-labelledby="model-tab-dossier"
        hidden={active !== "dossier"}
        className="max-w-3xl lg:mt-8"
      >
        <SectionHeader label={t("model.dossierTitle")} />
        {model.dossier ? (
          <p className="v-dropcap whitespace-pre-wrap font-serif text-[17px] leading-[1.76] text-ink">
            {model.dossier}
          </p>
        ) : (
          <p className="font-serif text-[17px] text-muted">{t("model.dossierEmpty")}</p>
        )}
      </section>

      <section
        id="model-panel-facts"
        role="tabpanel"
        aria-labelledby="model-tab-facts"
        hidden={active !== "facts"}
        className="max-w-4xl lg:mt-8"
      >
        <SectionHeader label={t("model.factsTitle")} />
        <ul className="space-y-2.5 text-sm">
          {facts.map((fact) => (
            <li key={fact.id} className="flex gap-3 text-ink-soft">
              <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-gold" />
              <span>{fact.text}</span>
            </li>
          ))}
          {facts.length === 0 && <li className="text-muted">{t("model.factsEmpty")}</li>}
        </ul>
      </section>

      <section
        id="model-panel-traits"
        role="tabpanel"
        aria-labelledby="model-tab-traits"
        hidden={active !== "traits"}
        className="lg:mt-8"
      >
        <SectionHeader label={t("model.traitsTitle")} />
        <div className="grid gap-4 sm:grid-cols-2">
          {model.traits.map((dimension) => (
            <TraitChart key={dimension.dimension} dim={dimension} />
          ))}
          {model.traits.length === 0 && (
            <div className="text-sm text-muted">{t("model.traitsEmpty")}</div>
          )}
        </div>
      </section>
    </>
  );
}
