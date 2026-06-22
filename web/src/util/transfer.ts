// Get text out of the app: copy to clipboard or download as a file. Thin
// imperative wrappers over browser APIs — the data they move is built by pure
// functions elsewhere (e.g. traces/export.ts), which is where the testable logic lives.

/** Copy text to the clipboard. Resolves false instead of throwing if blocked. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Trigger a download of `text` as a file named `filename`. */
export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
