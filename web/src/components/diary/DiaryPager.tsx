import { useEffect, useRef, type ReactNode } from "react";

export function DiaryPager({
  detailOpen,
  timeline,
  detail,
}: {
  detailOpen: boolean;
  timeline: ReactNode;
  detail: ReactNode;
}) {
  const timelineRef = useRef<HTMLElement>(null);
  const detailRef = useRef<HTMLElement>(null);

  useEffect(() => {
    timelineRef.current?.toggleAttribute("inert", detailOpen);
    detailRef.current?.toggleAttribute("inert", !detailOpen);
  }, [detailOpen]);

  return (
    <div
      data-diary-page={detailOpen ? "detail" : "timeline"}
      className="min-h-0 flex-1 overflow-hidden"
    >
      <div
        data-diary-track="true"
        className={
          "flex h-full w-[200%] will-change-transform transition-transform duration-300 ease-out motion-reduce:transition-none " +
          (detailOpen ? "-translate-x-1/2" : "translate-x-0")
        }
      >
        <section
          ref={timelineRef}
          data-diary-surface="timeline"
          data-active={!detailOpen}
          aria-hidden={detailOpen}
          className={
            "h-full min-h-0 w-1/2 flex-none " +
            (detailOpen ? "pointer-events-none" : "")
          }
        >
          {timeline}
        </section>
        <section
          ref={detailRef}
          data-diary-surface="detail"
          data-active={detailOpen}
          aria-hidden={!detailOpen}
          className={
            "h-full min-h-0 w-1/2 flex-none " +
            (!detailOpen ? "pointer-events-none" : "")
          }
        >
          {detail}
        </section>
      </div>
    </div>
  );
}
