import type { ModelCapabilities, ModelCapabilityStatus } from "../../api/modelCandidates";
import { useT } from "../../i18n";


const CAPABILITIES = ["basic", "structured_json", "streaming", "tools"] as const;


export function ModelCapabilityResults({
  capabilities,
}: {
  capabilities?: ModelCapabilities;
}) {
  const { t } = useT();
  if (!capabilities) return null;

  function label(key: typeof CAPABILITIES[number]): string {
    if (key === "basic") return t("models.capabilityBasic");
    if (key === "structured_json") return t("models.capabilityStructured");
    if (key === "streaming") return t("models.capabilityStreaming");
    return t("models.capabilityTools");
  }

  function statusLabel(status: ModelCapabilityStatus): string {
    if (status === "passed") return t("models.capabilityPassed");
    if (status === "failed") return t("models.capabilityFailed");
    return t("models.capabilityUnknown");
  }

  return (
    <div className="mt-4 border-t border-line pt-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">
        {t("models.capabilities")}
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {CAPABILITIES.map((key) => {
          const capability = capabilities[key];
          const tone = capability.status === "passed"
            ? "bg-status-ok-bg text-status-ok-fg"
            : capability.status === "failed"
              ? "bg-status-error-bg text-status-error-fg"
              : "bg-well text-muted";
          return (
            <div
              key={key}
              className="flex items-center justify-between gap-2 rounded-lg border border-line px-2.5 py-2 text-xs"
            >
              <span className="text-ink-soft">{label(key)}</span>
              <span className={`rounded-full px-2 py-0.5 ${tone}`}>
                {statusLabel(capability.status)}
                {capability.latency_ms !== null ? ` · ${capability.latency_ms}ms` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
