import { useEffect, useState } from "react";
import {
  getInquiry,
  type Inquiry,
  type InquiryEvidence,
  type InquiryEvent,
  type InquiryGroundedItem,
  type InquiryHypothesis,
} from "../../api/client";
import { useT } from "../../i18n";
import { StatusChip, Tag } from "../ui/StatusChip";


export function InquiryList({ inquiries }: { inquiries: Inquiry[] }) {
  const { t: tr } = useT();
  if (inquiries.length === 0) {
    return <div className="p-4 text-muted sm:p-8">{tr("traces.emptyInquiries")}</div>;
  }
  return (
    <div>
      {inquiries.map((inquiry, index) => (
        <InquiryCard
          key={inquiry.id}
          inquiry={inquiry}
          initiallyOpen={index === 0}
        />
      ))}
    </div>
  );
}


function InquiryCard({
  inquiry,
  initiallyOpen,
}: {
  inquiry: Inquiry;
  initiallyOpen: boolean;
}) {
  const { t: tr } = useT();
  const [open, setOpen] = useState(initiallyOpen);
  const [events, setEvents] = useState<InquiryEvent[] | null>(null);
  const [historyError, setHistoryError] = useState("");
  const ledger = inquiry.ledger;
  const openUnknowns = ledger.blocking_unknowns.filter((item) => item.status === "open");

  useEffect(() => {
    if (!open || events !== null || historyError) return;
    let active = true;
    void getInquiry(inquiry.id)
      .then((detail) => {
        if (active) setEvents(detail.events);
      })
      .catch((error: unknown) => {
        if (active) {
          setHistoryError(error instanceof Error ? error.message : String(error));
        }
      });
    return () => { active = false; };
  }, [events, historyError, inquiry.id, open]);

  return (
    <section className="border-b border-line/70">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-11 w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left hover:bg-white/5 sm:px-4"
      >
        <span className="text-muted">{open ? "▾" : "▸"}</span>
        <span className="font-mono text-[11px] text-muted">#{inquiry.id}</span>
        <StatusChip status={inquiry.status} />
        <Tag>{tr("traces.inquiryRevision", { n: inquiry.revision })}</Tag>
        <span className="min-w-0 flex-1 truncate text-sm text-ink-soft">
          {inquiry.goal || ledger.goal?.text || tr("traces.inquiryUntitled")}
        </span>
        <span className="text-xs text-muted">
          {tr("traces.openUnknownCount", { n: openUnknowns.length })}
        </span>
      </button>

      {open && (
        <div className="space-y-4 px-3 pb-4 sm:px-4 sm:pl-8">
          <section>
            <SectionTitle>{tr("traces.inquiryGoal")}</SectionTitle>
            {ledger.goal ? (
              <div className="mt-2 border-l-2 border-line pl-3 text-sm text-ink-soft">
                <div>{ledger.goal.text}</div>
                <EvidenceList
                  label={tr("traces.inquiryEvidence")}
                  evidence={ledger.goal.evidence}
                />
              </div>
            ) : <Empty />}
          </section>
          <GroundedLedgerSection
            title={tr("traces.inquiryObservations")}
            items={ledger.observations}
          />
          <GroundedLedgerSection
            title={tr("traces.inquiryInterpretations")}
            items={ledger.interpretations}
          />
          <HypothesisSection items={ledger.hypotheses} />
          <section>
            <SectionTitle>{tr("traces.inquiryUnknowns")}</SectionTitle>
            {ledger.blocking_unknowns.length > 0 ? (
              <div className="mt-2 space-y-2">
                {ledger.blocking_unknowns.map((item) => (
                  <div key={item.id} className="rounded-lg border border-line bg-surface px-3 py-2">
                    <div className="flex items-center gap-2">
                      <StatusChip status={item.status} />
                      <span className="text-sm text-ink-soft">{item.question}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted">{item.why_material}</div>
                  </div>
                ))}
              </div>
            ) : <Empty />}
          </section>
          {ledger.provisional_conclusion && (
            <section>
              <SectionTitle>{tr("traces.inquiryProvisional")}</SectionTitle>
              <p className="mt-2 whitespace-pre-wrap text-sm text-ink-soft">
                {ledger.provisional_conclusion}
              </p>
            </section>
          )}
          <section>
            <SectionTitle>{tr("traces.inquiryAskedQuestions")}</SectionTitle>
            {ledger.asked_questions.length > 0 ? (
              <ul className="mt-2 space-y-1.5 text-sm text-ink-soft">
                {ledger.asked_questions.map((question, index) => (
                  <li key={`${question.after_turn}:${question.unknown_id}:${index}`}>
                    <span className="mr-2 font-mono text-[10px] text-muted">
                      turn {question.after_turn} · {question.unknown_id}
                    </span>
                    {question.text}
                  </li>
                ))}
              </ul>
            ) : <Empty />}
          </section>
          <section>
            <SectionTitle>{tr("traces.inquiryHistory")}</SectionTitle>
            {events ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {events.map((event) => (
                  <Tag key={event.id}>
                    r{event.revision_before}→{event.revision_after} · {event.action}
                  </Tag>
                ))}
              </div>
            ) : historyError ? (
              <div className="mt-2 text-xs text-status-fail-fg">{historyError}</div>
            ) : (
              <div className="mt-2 text-xs text-muted">{tr("traces.inquiryHistoryLoading")}</div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}


function GroundedLedgerSection({
  title,
  items,
}: {
  title: string;
  items: InquiryGroundedItem[];
}) {
  const { t } = useT();
  return (
    <section>
      <SectionTitle>{title}</SectionTitle>
      {items.length > 0 ? (
        <ul className="mt-2 space-y-2 text-sm text-ink-soft">
          {items.map((item) => (
            <li key={item.id} className="border-l-2 border-line pl-3">
              <div>{item.text}</div>
              <EvidenceList
                label={t("traces.inquiryEvidence")}
                evidence={item.evidence}
              />
            </li>
          ))}
        </ul>
      ) : <Empty />}
    </section>
  );
}


function HypothesisSection({ items }: { items: InquiryHypothesis[] }) {
  const { t } = useT();
  return (
    <section>
      <SectionTitle>{t("traces.inquiryHypotheses")}</SectionTitle>
      {items.length > 0 ? (
        <ul className="mt-2 space-y-2 text-sm text-ink-soft">
          {items.map((item) => (
            <li key={item.id} className="border-l-2 border-line pl-3">
              <div>{item.text}</div>
              <EvidenceList
                label={t("traces.inquirySupportingEvidence")}
                evidence={item.supporting_evidence}
              />
              <EvidenceList
                label={t("traces.inquiryDisconfirmingEvidence")}
                evidence={item.disconfirming_evidence}
              />
            </li>
          ))}
        </ul>
      ) : <Empty />}
    </section>
  );
}


function EvidenceList({
  label,
  evidence,
}: {
  label: string;
  evidence: InquiryEvidence[];
}) {
  if (evidence.length === 0) return null;
  return (
    <div className="mt-1 text-xs text-muted">
      <span className="mr-1 font-medium">{label}:</span>
      {evidence.map((item, index) => (
        <span key={`${item.turn}:${index}`} className="mr-2">
          turn {item.turn} · “{item.quote}”
        </span>
      ))}
    </div>
  );
}


function SectionTitle({ children }: { children: string }) {
  return <h3 className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">{children}</h3>;
}


function Empty() {
  return <div className="mt-2 text-xs text-muted">—</div>;
}
