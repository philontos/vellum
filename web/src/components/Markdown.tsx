import { Fragment, type ReactNode } from "react";

/**
 * A small, dependency-free Markdown renderer for Vellum's replies.
 *
 * It covers exactly the subset the model actually writes — section headings,
 * hairline breaks, emphasis, and bullet/numbered lists — and renders unknown
 * or half-streamed syntax as plain text rather than guessing. Styling lives in
 * `.v-md` (index.css) so the manuscript voice stays in one place.
 */

export type Block =
  | { type: "hr" }
  | { type: "heading"; level: number; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "p"; text: string };

const HR = /^\s*([-*_])\1{2,}\s*$/;
const ATX = /^\s*(#{1,6})\s+(.*\S)\s*$/;
// A line that is one whole bold span (no inner **), optional trailing punctuation
// outside the span — the model's "**一、…？**" section titles.
const BOLD_LINE = /^\s*\*\*((?:(?!\*\*).)+)\*\*[：:。.!?！？]*\s*$/;
const UL = /^\s*[-*]\s+(.*\S)\s*$/;
const OL = /^\s*\d+[.)]\s+(.*\S)\s*$/;

/** Parse source markdown into a flat list of blocks. Pure — unit-tested directly. */
export function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) {
      blocks.push({ type: "p", text: para.join("\n") });
      para = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) {
      flush();
      continue;
    }
    if (HR.test(line)) {
      flush();
      blocks.push({ type: "hr" });
      continue;
    }
    const atx = ATX.exec(line);
    if (atx) {
      flush();
      blocks.push({ type: "heading", level: atx[1].length, text: atx[2] });
      continue;
    }
    const bold = BOLD_LINE.exec(line);
    if (bold) {
      flush();
      blocks.push({ type: "heading", level: 4, text: bold[1] });
      continue;
    }
    if (UL.test(line)) {
      flush();
      const items: string[] = [];
      while (i < lines.length && UL.test(lines[i])) {
        items.push(UL.exec(lines[i]!)![1]);
        i++;
      }
      i--; // step back so the outer for-loop's ++ lands on the stopping line
      blocks.push({ type: "ul", items });
      continue;
    }
    if (OL.test(line)) {
      flush();
      const items: string[] = [];
      while (i < lines.length && OL.test(lines[i])) {
        items.push(OL.exec(lines[i]!)![1]);
        i++;
      }
      i--;
      blocks.push({ type: "ol", items });
      continue;
    }
    para.push(line.trim());
  }
  flush();
  return blocks;
}

// Inline emphasis: bold first (so ** wins over *), then code, then italic.
// NOTE: renderInline recurses (bold can contain emphasis), so each call must own
// a fresh regex — a shared /g regex's lastIndex would be clobbered by the inner
// call and loop forever. Build a new one per invocation.
const inlineRe = () => /(\*\*(?:(?!\*\*).)+\*\*)|(`[^`]+`)|(\*(?:(?!\*).)+\*)|(_(?:(?!_).)+_)/g;

function withBreaks(text: string, key: string): ReactNode[] {
  return text.split("\n").map((part, i) =>
    i === 0 ? (
      <Fragment key={`${key}-l${i}`}>{part}</Fragment>
    ) : (
      <Fragment key={`${key}-l${i}`}>
        <br />
        {part}
      </Fragment>
    ),
  );
}

/** Render inline emphasis within a run of text. Unmatched markers stay literal. */
export function renderInline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = inlineRe();
  let last = 0;
  let n = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(...withBreaks(text.slice(last, m.index), `${key}-${n++}`));
    const tok = m[0];
    if (m[1]) out.push(<strong key={`${key}-${n++}`}>{renderInline(tok.slice(2, -2), `${key}-${n}`)}</strong>);
    else if (m[2]) out.push(<code key={`${key}-${n++}`}>{tok.slice(1, -1)}</code>);
    else out.push(<em key={`${key}-${n++}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(...withBreaks(text.slice(last), `${key}-${n++}`));
  return out;
}

export function Markdown({ text, caret = false }: { text: string; caret?: boolean }) {
  const blocks = parseBlocks(text);
  const lastIdx = blocks.length - 1;

  return (
    <div className="v-md">
      {blocks.map((b, i) => {
        const tail = caret && i === lastIdx ? <span className="v-caret" aria-hidden /> : null;
        switch (b.type) {
          case "hr":
            return <hr key={i} />;
          case "heading": {
            const Tag = `h${Math.min(Math.max(b.level + 1, 2), 6)}` as keyof JSX.IntrinsicElements;
            return (
              <Tag key={i} className="v-md-h">
                {renderInline(b.text, `h${i}`)}
                {tail}
              </Tag>
            );
          }
          case "ul":
            return (
              <ul key={i}>
                {b.items.map((it, j) => (
                  <li key={j}>{renderInline(it, `ul${i}-${j}`)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={i}>
                {b.items.map((it, j) => (
                  <li key={j}>{renderInline(it, `ol${i}-${j}`)}</li>
                ))}
              </ol>
            );
          default:
            return (
              <p key={i}>
                {renderInline(b.text, `p${i}`)}
                {tail}
              </p>
            );
        }
      })}
    </div>
  );
}
