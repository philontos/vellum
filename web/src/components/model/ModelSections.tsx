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
  const states = model.current_states ?? [];

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
        id="model-panel-state"
        role="tabpanel"
        aria-labelledby="model-tab-state"
        hidden={active !== "state"}
        className="max-w-4xl lg:mt-8"
      >
        <SectionHeader label={t("model.stateTitle")} />
        <p className="mb-4 text-sm text-muted">{t("model.stateHint")}</p>
        <div className="space-y-3">
          {states.map((snapshot) => (
            <article key={snapshot.id} className="rounded-xl border border-line bg-surface p-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                <span className="font-mono">turn {snapshot.user_turn}</span>
                <span>{snapshot.stream}</span>
                {snapshot.inquiry_id !== null && <span>Inquiry #{snapshot.inquiry_id}</span>}
                <span className="ml-auto">{snapshot.created_at}</span>
              </div>
              <StateItems
                label={t("model.stateCurrent")}
                items={snapshot.snapshot.states ?? []}
              />
              <StateItems
                label={t("model.stateChanges")}
                items={snapshot.snapshot.deltas ?? []}
              />
            </article>
          ))}
          {states.length === 0 && (
            <div className="text-sm text-muted">{t("model.stateEmpty")}</div>
          )}
        </div>
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


function StateItems({
  label,
  items,
}: {
  label: string;
  items: ModelView["current_states"][number]["snapshot"]["states"];
}) {
  if (items.length === 0) return null;
  return (
    <section className="mt-3">
      <h3 className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
        {label}
      </h3>
      <ul className="mt-1.5 space-y-2">
        {items.map((item, index) => (
          <li key={`${item.dimension}:${index}`} className="border-l-2 border-line pl-3">
            <div className="text-sm text-ink-soft">
              <span className="mr-2 rounded bg-well px-1.5 py-0.5 font-mono text-[10px] text-muted">
                {item.dimension.replace(/_/g, " ")}
              </span>
              {item.reference && (
                <span className="mr-2 rounded bg-well px-1.5 py-0.5 font-mono text-[10px] text-muted">
                  {item.reference.replace(/_/g, " ")}
                </span>
              )}
              {item.text}
            </div>
            {item.evidence.length > 0 && (
              <div className="mt-1 text-xs text-muted">
                {item.evidence.map((evidence, evidenceIndex) => (
                  <span key={`${evidence.turn}:${evidenceIndex}`} className="mr-2">
                    turn {evidence.turn} · “{evidence.quote}”
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
