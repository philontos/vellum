/** Keep browser-only preferences separate when several family members share a device. */
export function userStorageKey(userId: string | undefined, suffix: string): string {
  return userId
    ? `vellum.user.${encodeURIComponent(userId)}.${suffix}`
    : `vellum.${suffix}`;
}
