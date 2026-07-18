export type PromptDiffLine = {
  kind: "same" | "removed" | "added";
  text: string;
  baselineLine: number | null;
  candidateLine: number | null;
};

function lines(value: string): string[] {
  return value === "" ? [] : value.split("\n");
}

function coarseDiff(baseline: string[], candidate: string[]): PromptDiffLine[] {
  return [
    ...baseline.map((text, index): PromptDiffLine => ({
      kind: "removed", text, baselineLine: index + 1, candidateLine: null,
    })),
    ...candidate.map((text, index): PromptDiffLine => ({
      kind: "added", text, baselineLine: null, candidateLine: index + 1,
    })),
  ];
}

export function diffPromptLines(
  baselineValue: string,
  candidateValue: string,
): PromptDiffLine[] {
  const baseline = lines(baselineValue);
  const candidate = lines(candidateValue);
  if (baseline.length * candidate.length > 1_000_000) {
    return coarseDiff(baseline, candidate);
  }

  const lengths = Array.from(
    { length: baseline.length + 1 },
    () => Array<number>(candidate.length + 1).fill(0),
  );
  for (let left = baseline.length - 1; left >= 0; left -= 1) {
    for (let right = candidate.length - 1; right >= 0; right -= 1) {
      lengths[left][right] = baseline[left] === candidate[right]
        ? lengths[left + 1][right + 1] + 1
        : Math.max(lengths[left + 1][right], lengths[left][right + 1]);
    }
  }

  const result: PromptDiffLine[] = [];
  let left = 0;
  let right = 0;
  while (left < baseline.length || right < candidate.length) {
    if (
      left < baseline.length
      && right < candidate.length
      && baseline[left] === candidate[right]
    ) {
      result.push({
        kind: "same",
        text: baseline[left],
        baselineLine: left + 1,
        candidateLine: right + 1,
      });
      left += 1;
      right += 1;
    } else if (
      left < baseline.length
      && (right >= candidate.length
        || lengths[left + 1][right] >= lengths[left][right + 1])
    ) {
      result.push({
        kind: "removed",
        text: baseline[left],
        baselineLine: left + 1,
        candidateLine: null,
      });
      left += 1;
    } else {
      result.push({
        kind: "added",
        text: candidate[right],
        baselineLine: null,
        candidateLine: right + 1,
      });
      right += 1;
    }
  }
  return result;
}
