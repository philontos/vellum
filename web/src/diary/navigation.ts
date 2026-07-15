export type TouchPoint = { x: number; y: number };

const BACK_SWIPE_DISTANCE = 72;
const HORIZONTAL_INTENT_RATIO = 1.25;

export function isDiaryBackSwipe(start: TouchPoint, end: TouchPoint): boolean {
  const horizontal = end.x - start.x;
  const vertical = Math.abs(end.y - start.y);
  return (
    horizontal >= BACK_SWIPE_DISTANCE &&
    horizontal > vertical * HORIZONTAL_INTENT_RATIO
  );
}
