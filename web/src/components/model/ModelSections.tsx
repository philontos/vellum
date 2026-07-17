import type { ModelView } from "../../api/client";
import { useT } from "../../i18n";
import { TraitChart } from "../TraitChart";
import { SectionHeader } from "../ui/SectionHeader";
import { FactCard } from "./FactCard";
import type { ModelSection } from "./ModelTabs";
import { PortraitClaimCard } from "./PortraitClaimCard";

export function ModelSections({
  model,
  active,
  onFactSave,
  onFactDelete,
}: {
  model: ModelView;
  active: ModelSection;
  onFactSave: (id: number, text: string) => Promise<void>;
  onFactDelete: (id: number) => Promise<void>;
}) {
  const { t } = useT();
  const facts = model.facts.filter((fact) => fact.status === "active");
  const claims = model.portrait_claims ?? [];

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
        id="model-panel-evidence"
        role="tabpanel"
        aria-labelledby="model-tab-evidence"
        hidden={active !== "evidence"}
        className="max-w-4xl lg:mt-8"
      >
        <SectionHeader label={t("model.evidenceTitle")} />
        <ul className="space-y-2.5">
          {claims.map((claim) => (
            <PortraitClaimCard key={claim.id} claim={claim} />
          ))}
          {claims.length === 0 && (
            <li className="text-sm text-muted">{t("model.evidenceEmpty")}</li>
          )}
        </ul>
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
            <FactCard
              key={fact.id}
              fact={fact}
              onSave={onFactSave}
              onDelete={onFactDelete}
            />
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
