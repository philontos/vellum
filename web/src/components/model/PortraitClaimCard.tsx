import type { PortraitClaim } from "../../api/client";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";

function humanize(value: string): string {
  return value.split("_").join(" ");
}

export function PortraitClaimCard({ claim }: { claim: PortraitClaim }) {
  const { t } = useT();
  return (
    <li className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <Tag>{humanize(claim.claim_type)}</Tag>
        <Tag>{claim.basis}</Tag>
      </div>
      <p className="mt-2 text-sm leading-6 text-ink-soft">{claim.text}</p>
      <ul className="mt-3 space-y-1.5 border-l-2 border-line pl-3 text-xs text-muted">
        {claim.evidence.map((item, index) => (
          <li key={`${item.turn}:${index}`}>
            <span className="mr-2 font-mono text-[10px]">
              {t("model.evidenceTurn", { turn: item.turn })}
            </span>
            <span>“{item.quote}”</span>
          </li>
        ))}
      </ul>
    </li>
  );
}
