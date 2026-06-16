// Hashing for the local privacy PIN.
//
// IMPORTANT — this is NOT security. It is a shoulder-surfing screen. A short PIN
// hashed with SHA-256 is trivially brute-forceable, and the protected text is
// still in memory and the DOM. Real data security is the SQLCipher at-rest
// encryption with the user-held key. This only deters a casual glance / click.

const enc = new TextEncoder();

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** 16 random bytes as a 32-char hex string. */
export function randomSalt(): string {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return toHex(b);
}

/** SHA-256 of `salt:pin`, hex-encoded. */
export async function hashPin(pin: string, salt: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", enc.encode(`${salt}:${pin}`));
  return toHex(new Uint8Array(digest));
}

export async function verifyPin(pin: string, salt: string, hash: string): Promise<boolean> {
  return (await hashPin(pin, salt)) === hash;
}
