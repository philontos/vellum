const DIARY_TIMELINE_PATH = "/app/diary";

export type DiaryRoute =
  | { kind: "timeline" }
  | { kind: "entry"; entryId: number }
  | { kind: "other" };

export function diaryTimelinePath(): string {
  return DIARY_TIMELINE_PATH;
}

export function diaryEntryPath(entryId: number): string {
  if (!Number.isSafeInteger(entryId) || entryId < 1) {
    throw new RangeError("Diary entry id must be a positive integer");
  }
  return `${DIARY_TIMELINE_PATH}/${entryId}`;
}

export function parseDiaryRoute(pathname: string): DiaryRoute {
  if (/^\/app\/diary\/?$/.test(pathname)) return { kind: "timeline" };
  const match = /^\/app\/diary\/([1-9]\d*)\/?$/.exec(pathname);
  if (!match) return { kind: "other" };
  const entryId = Number(match[1]);
  return Number.isSafeInteger(entryId)
    ? { kind: "entry", entryId }
    : { kind: "other" };
}
