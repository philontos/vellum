import { useEffect, useState } from "react";

import {
  getModelCandidates,
  revealModelCandidateApiKey,
  saveModelCandidate,
  saveModelRoute,
  validateModelCandidate,
  type ManagedModelCandidate,
  type ModelCandidateDraft,
  type ModelCandidateWorkspace,
  type ModelScenario,
} from "../api/modelCandidates";
import { useT } from "../i18n";
import { ModelRouteSettings } from "./models/ModelRouteSettings";


type CandidateBusy = "reveal" | "validate" | "save" | null;
type ValidationState = { token: string; fingerprint: string };


export function candidateDraftFingerprint(draft: ModelCandidateDraft): string {
  return JSON.stringify([draft.base_url.trim(), draft.model.trim(), draft.api_key]);
}


function initialDraft(candidate: ManagedModelCandidate): ModelCandidateDraft {
  return {
    base_url: candidate.base_url,
    model: candidate.model,
    api_key: "",
  };
}


function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}


export function ModelCandidatesPanel() {
  const { t } = useT();
  const [workspace, setWorkspace] = useState<ModelCandidateWorkspace | null>(null);
  const [drafts, setDrafts] = useState<Record<string, ModelCandidateDraft>>({});
  const [validations, setValidations] = useState<Record<string, ValidationState>>({});
  const [busy, setBusy] = useState<Record<string, CandidateBusy>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiKeyVisible, setApiKeyVisible] = useState<Record<string, boolean>>({});
  const [busyScenario, setBusyScenario] = useState<ModelScenario | null>(null);
  const [routeError, setRouteError] = useState("");
  const [loadError, setLoadError] = useState("");

  function install(next: ModelCandidateWorkspace) {
    setWorkspace(next);
    setDrafts(Object.fromEntries(
      next.candidates.map((candidate) => [candidate.id, initialDraft(candidate)]),
    ));
  }

  useEffect(() => {
    let cancelled = false;
    getModelCandidates()
      .then((next) => {
        if (!cancelled) install(next);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(message(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function changeDraft(candidateId: string, next: ModelCandidateDraft) {
    setDrafts((current) => ({ ...current, [candidateId]: next }));
    setValidations((current) => {
      const updated = { ...current };
      delete updated[candidateId];
      return updated;
    });
    setErrors((current) => ({ ...current, [candidateId]: "" }));
  }

  async function toggleApiKey(candidateId: string) {
    if (apiKeyVisible[candidateId]) {
      setApiKeyVisible((current) => ({ ...current, [candidateId]: false }));
      return;
    }
    const candidate = workspace?.candidates.find((item) => item.id === candidateId);
    const draft = drafts[candidateId];
    if (!candidate || !draft || busy[candidateId]) return;
    if (draft.api_key || !candidate.has_api_key) {
      setApiKeyVisible((current) => ({ ...current, [candidateId]: true }));
      return;
    }
    setBusy((current) => ({ ...current, [candidateId]: "reveal" }));
    setErrors((current) => ({ ...current, [candidateId]: "" }));
    try {
      const apiKey = await revealModelCandidateApiKey(candidateId);
      changeDraft(candidateId, { ...draft, api_key: apiKey });
      setApiKeyVisible((current) => ({ ...current, [candidateId]: true }));
    } catch (error) {
      setErrors((current) => ({ ...current, [candidateId]: message(error) }));
    } finally {
      setBusy((current) => ({ ...current, [candidateId]: null }));
    }
  }

  async function changeRoute(scenario: ModelScenario, candidateId: string) {
    if (!workspace || busyScenario) return;
    setBusyScenario(scenario);
    setRouteError("");
    try {
      const saved = await saveModelRoute(scenario, candidateId);
      setWorkspace((current) => current ? {
        ...current,
        routes: current.routes.map(
          (route) => route.scenario === scenario ? saved : route,
        ),
      } : current);
    } catch (error) {
      setRouteError(message(error));
    } finally {
      setBusyScenario(null);
    }
  }

  async function validate(candidateId: string) {
    const draft = drafts[candidateId];
    if (!draft || busy[candidateId]) return;
    setBusy((current) => ({ ...current, [candidateId]: "validate" }));
    setErrors((current) => ({ ...current, [candidateId]: "" }));
    try {
      const result = await validateModelCandidate(candidateId, draft);
      setValidations((current) => ({
        ...current,
        [candidateId]: {
          token: result.validation_token,
          fingerprint: candidateDraftFingerprint(draft),
        },
      }));
    } catch (error) {
      setValidations((current) => {
        const next = { ...current };
        delete next[candidateId];
        return next;
      });
      setErrors((current) => ({ ...current, [candidateId]: message(error) }));
    } finally {
      setBusy((current) => ({ ...current, [candidateId]: null }));
    }
  }

  async function save(candidateId: string) {
    const draft = drafts[candidateId];
    const validation = validations[candidateId];
    if (
      !workspace
      || !draft
      || !validation
      || validation.fingerprint !== candidateDraftFingerprint(draft)
      || busy[candidateId]
    ) return;
    setBusy((current) => ({ ...current, [candidateId]: "save" }));
    setErrors((current) => ({ ...current, [candidateId]: "" }));
    try {
      const saved = await saveModelCandidate(
        candidateId, draft, validation.token,
      );
      setWorkspace((current) => current ? {
        ...current,
        candidates: current.candidates.map(
          (candidate) => candidate.id === candidateId ? saved : candidate,
        ),
      } : current);
      setDrafts((current) => ({
        ...current,
        [candidateId]: initialDraft(saved),
      }));
      setValidations((current) => {
        const next = { ...current };
        delete next[candidateId];
        return next;
      });
      setApiKeyVisible((current) => ({ ...current, [candidateId]: false }));
    } catch (error) {
      setErrors((current) => ({ ...current, [candidateId]: message(error) }));
    } finally {
      setBusy((current) => ({ ...current, [candidateId]: null }));
    }
  }

  if (!workspace) {
    return (
      <div className="v-canvas flex h-full items-center justify-center p-8 text-sm text-muted">
        {loadError || t("models.loading")}
      </div>
    );
  }

  return (
    <div className="v-canvas h-full overflow-y-auto">
      <header className="border-b border-line px-5 py-5">
        <h2 className="font-serif text-2xl text-ink">{t("models.title")}</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted">{t("models.subtitle")}</p>
      </header>
      <ModelRouteSettings
        candidates={workspace.candidates}
        routes={workspace.routes}
        busyScenario={busyScenario}
        error={routeError}
        onChange={(scenario, candidateId) => {
          void changeRoute(scenario, candidateId);
        }}
      />
      <div className="grid gap-4 p-5 xl:grid-cols-2">
        {workspace.candidates.map((candidate) => (
          <ModelCandidateEditor
            key={candidate.id}
            candidate={candidate}
            draft={drafts[candidate.id] ?? initialDraft(candidate)}
            validationFingerprint={validations[candidate.id]?.fingerprint ?? ""}
            busy={busy[candidate.id] ?? null}
            error={errors[candidate.id] ?? ""}
            apiKeyVisible={apiKeyVisible[candidate.id] ?? false}
            onDraftChange={(draft) => changeDraft(candidate.id, draft)}
            onApiKeyVisibilityChange={() => void toggleApiKey(candidate.id)}
            onValidate={() => void validate(candidate.id)}
            onSave={() => void save(candidate.id)}
          />
        ))}
      </div>
    </div>
  );
}


export function ModelCandidateEditor({
  candidate,
  draft,
  validationFingerprint,
  busy,
  error,
  apiKeyVisible,
  onDraftChange,
  onApiKeyVisibilityChange,
  onValidate,
  onSave,
}: {
  candidate: ManagedModelCandidate;
  draft: ModelCandidateDraft;
  validationFingerprint: string;
  busy: CandidateBusy;
  error: string;
  apiKeyVisible: boolean;
  onDraftChange: (draft: ModelCandidateDraft) => void;
  onApiKeyVisibilityChange: () => void;
  onValidate: () => void;
  onSave: () => void;
}) {
  const { t } = useT();
  const exactDraftValidated = (
    validationFingerprint !== ""
    && validationFingerprint === candidateDraftFingerprint(draft)
  );
  const hasKey = Boolean(draft.api_key.trim() || candidate.has_api_key);
  const canValidate = Boolean(
    candidate.editable
    && draft.base_url.trim()
    && draft.model.trim()
    && hasKey
    && !busy,
  );
  const sourceLabel = candidate.source === "stored"
    ? t("models.sourceStored")
    : candidate.source === "environment"
      ? t("models.sourceEnvironment")
      : t("models.notConfigured");

  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-serif text-xl text-ink">{candidate.name}</h3>
          <p className="mt-1 text-xs text-muted">{sourceLabel}</p>
        </div>
        <span className={
          "rounded-full px-2.5 py-1 text-xs "
          + (candidate.configured
            ? "bg-status-ok-bg text-status-ok-fg"
            : "bg-status-warn-bg text-status-warn-fg")
        }>
          {candidate.configured ? t("models.configured") : t("models.notConfigured")}
        </span>
      </div>

      <div className="mt-5 grid gap-4">
        <label className="block text-sm text-ink-soft">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
            {t("models.baseUrl")}
          </span>
          <input
            type="url"
            value={draft.base_url}
            disabled={!candidate.editable || busy !== null}
            onChange={(event) => onDraftChange({
              ...draft, base_url: event.target.value,
            })}
            className="min-h-10 w-full rounded-lg border border-line bg-well px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </label>
        <label className="block text-sm text-ink-soft">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
            {t("models.model")}
          </span>
          <input
            type="text"
            value={draft.model}
            disabled={!candidate.editable || busy !== null}
            onChange={(event) => onDraftChange({
              ...draft, model: event.target.value,
            })}
            className="min-h-10 w-full rounded-lg border border-line bg-well px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </label>
        <div className="block text-sm text-ink-soft">
          <label
            htmlFor={`model-api-key-${candidate.id}`}
            className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted"
          >
            {t("models.apiKey")}
          </label>
          <div className="flex gap-2">
            <input
              id={`model-api-key-${candidate.id}`}
              type={apiKeyVisible ? "text" : "password"}
              autoComplete="new-password"
              value={draft.api_key}
              placeholder={candidate.has_api_key
                ? t("models.keepSavedKey")
                : t("models.enterApiKey")}
              disabled={!candidate.editable || busy !== null}
              onChange={(event) => onDraftChange({
                ...draft, api_key: event.target.value,
              })}
              className="min-h-10 min-w-0 flex-1 rounded-lg border border-line bg-well px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
            <button
              type="button"
              disabled={!candidate.editable || busy !== null}
              onClick={onApiKeyVisibilityChange}
              className="min-h-10 rounded-lg border border-line bg-well px-3 text-sm text-ink-soft disabled:opacity-50"
            >
              {apiKeyVisible ? t("models.hideApiKey") : t("models.showApiKey")}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4 min-h-5 text-xs">
        {error && <p className="text-status-error-fg">{error}</p>}
        {!error && exactDraftValidated && (
          <p className="text-status-ok-fg">{t("models.validationPassed")}</p>
        )}
        {!error && !exactDraftValidated && candidate.verified_at && (
          <p className="text-muted">
            {t("models.lastVerified", { time: candidate.verified_at })}
          </p>
        )}
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          disabled={!canValidate}
          onClick={onValidate}
          className="min-h-10 rounded-lg border border-line bg-well px-4 text-sm text-ink-soft disabled:opacity-50"
        >{busy === "validate" ? t("models.validating") : t("models.validate")}</button>
        <button
          type="button"
          disabled={!candidate.editable || !exactDraftValidated || busy !== null}
          onClick={onSave}
          className="min-h-10 rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg disabled:bg-well disabled:text-muted"
        >{busy === "save" ? t("models.saving") : t("models.save")}</button>
      </div>
    </section>
  );
}
