import type { ManagedPrompt } from "../../api/prompts";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";

export function PromptGuide({ prompt }: { prompt: ManagedPrompt }) {
  const { lang, t } = useT();
  const guide = prompt.documentation[lang] ?? prompt.documentation.en;

  return (
    <div className="space-y-4 pt-5">
      <GuideSection title={t("prompts.guideUsage")}>{guide.usage}</GuideSection>
      <GuideSection title={t("prompts.guideRuntime")}>{guide.runtime}</GuideSection>

      <section className="rounded-xl border border-line bg-well px-4 py-3.5">
        <h3 className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
          {t("prompts.guideEditing")}
        </h3>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-ink-soft">
          {guide.editing_guidance.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      <section className="rounded-xl border border-line bg-well px-4 py-3.5">
        <h3 className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
          {t("prompts.guideContract")}
        </h3>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Tag>{prompt.template_format}</Tag>
          {prompt.variables.length > 0 ? (
            prompt.variables.map((variable) => <Tag key={variable}>{variable}</Tag>)
          ) : (
            <span className="text-xs text-muted">{t("prompts.noVariables")}</span>
          )}
        </div>
      </section>

      <p className="rounded-lg border border-line/70 bg-surface px-3 py-2 text-xs leading-relaxed text-muted">
        {t("prompts.guideMetadataNote")}
      </p>
    </div>
  );
}

function GuideSection({ title, children }: { title: string; children: string }) {
  return (
    <section className="rounded-xl border border-line bg-well px-4 py-3.5">
      <h3 className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
        {title}
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-ink-soft">{children}</p>
    </section>
  );
}
