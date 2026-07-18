import type {
  ManagedModelCandidate,
  ModelRoute,
  ModelScenario,
} from "../../api/modelCandidates";
import { useT } from "../../i18n";


const SCENARIOS: ModelScenario[] = ["chat", "background", "evaluation"];


export function ModelRouteSettings({
  candidates,
  routes,
  busyScenario,
  error,
  onChange,
}: {
  candidates: ManagedModelCandidate[];
  routes: ModelRoute[];
  busyScenario: ModelScenario | null;
  error: string;
  onChange: (scenario: ModelScenario, candidateId: string) => void;
}) {
  const { t } = useT();

  function label(scenario: ModelScenario): string {
    if (scenario === "chat") return t("models.routeChat");
    if (scenario === "background") return t("models.routeBackground");
    return t("models.routeEvaluation");
  }

  return (
    <section className="border-b border-line bg-surface/60 px-5 py-5">
      <h3 className="font-serif text-xl text-ink">{t("models.routingTitle")}</h3>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        {t("models.routingSubtitle")}
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {SCENARIOS.map((scenario) => {
          const route = routes.find((item) => item.scenario === scenario);
          return (
            <label key={scenario} className="block text-sm text-ink-soft">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
                {label(scenario)}
              </span>
              <select
                value={route?.candidate_id ?? ""}
                disabled={busyScenario !== null}
                onChange={(event) => onChange(scenario, event.target.value)}
                className="min-h-10 w-full rounded-lg border border-line bg-well px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
              >
                {candidates.map((candidate) => (
                  <option
                    key={candidate.id}
                    value={candidate.id}
                    disabled={!candidate.configured}
                  >
                    {candidate.name} · {candidate.model || t("models.notConfigured")}
                  </option>
                ))}
              </select>
            </label>
          );
        })}
      </div>
      <div className="mt-3 min-h-5 text-xs">
        {error && <p className="text-status-error-fg">{error}</p>}
        {!error && busyScenario && (
          <p className="text-muted">{t("models.routeSaving")}</p>
        )}
      </div>
    </section>
  );
}
