/** Visible character count — counts code points, so a CJK character or an emoji
 * each count as one (what a reader thinks of as "字数"). */
export function charCount(text: string): number {
  return [...text].length;
}

/** Rough token estimate. There's no real tokenizer client-side, so this is a
 * deliberate approximation: CJK ideographs and kana run ~1 token per character,
 * everything else is charged at ~4 chars/token (typical for BPE on Latin text).
 * Always surface it as "~N" — it is an estimate, not the model's real count. */
export function approxTokens(text: string): number {
  const cjk = (text.match(/[぀-ヿ㐀-鿿豈-﫿ｦ-ﾟ]/g) ?? []).length;
  const rest = [...text].length - cjk;
  return Math.round(cjk + rest / 4);
}
