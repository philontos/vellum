import type { ToolEvent } from "./sse";

/** One tool call surfaced live in the chat process block. */
export type ActivityItem = {
  name: string;
  query?: string;
  status: "running" | "done" | "error";
};

/**
 * Fold a tool start/end event into the running activity list (pure — returns a
 * new array). `start` appends a running item; `end` flips the most recent still-
 * running item of the same name to done/error.
 */
export function applyTool(activity: ActivityItem[] | undefined, ev: ToolEvent): ActivityItem[] {
  const list = activity ? activity.map((x) => ({ ...x })) : [];
  if (ev.phase === "start") {
    list.push({ name: ev.name, query: ev.query, status: "running" });
    return list;
  }
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].name === ev.name && list[i].status === "running") {
      list[i].status = ev.ok === false ? "error" : "done";
      break;
    }
  }
  return list;
}
