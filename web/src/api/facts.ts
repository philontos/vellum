import type { Fact } from "./client";


export class FactMutationError extends Error {
  readonly status: number;

  constructor(action: "update" | "delete", status: number) {
    super(`${action} fact failed: ${status}`);
    this.name = "FactMutationError";
    this.status = status;
  }
}


export async function updateFact(id: number, text: string): Promise<Fact> {
  const response = await fetch(`/facts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new FactMutationError("update", response.status);
  return (await response.json()).fact as Fact;
}


export async function deleteFact(id: number): Promise<void> {
  const response = await fetch(`/facts/${id}`, { method: "DELETE" });
  if (!response.ok) throw new FactMutationError("delete", response.status);
}
