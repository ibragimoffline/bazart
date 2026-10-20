/**
 * Sessiya holati (client-only).
 *
 * - Access token — FAQAT xotirada (sahifa yangilansa yo'qoladi, refresh bilan tiklanadi).
 * - Refresh token — backend qo'ygan HttpOnly cookie'da; JS uni ko'rmaydi va saqlamaydi.
 * - `bazart-session` — maxfiy bo'lmagan belgi: "bu brauzerda sessiya bor". U bo'lmasa
 *   anonim mehmon har sahifada behuda /auth/refresh chaqirmaydi. Boshqa tablar shu kalit
 *   o'zgarishidan (storage event) login/logout'ni biladi.
 * - `bazart-auth` — eski format (tokenlar localStorage'da). Faqat bir martalik ko'chirish
 *   uchun o'qiladi va darhol o'chiriladi.
 */

const HINT_KEY = "bazart-session";
const LEGACY_KEY = "bazart-auth";

/** Muddatdan shuncha oldin access token "eskirgan" deb hisoblanadi (soat farqi, tarmoq). */
const EXPIRY_SKEW_MS = 60_000;

let access: { token: string; expiresAt: number } | null = null;

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return access?.token ?? null;
}

/** Token bor va muddatigacha kamida EXPIRY_SKEW_MS qolgan. */
export function isAccessFresh(now: number = Date.now()): boolean {
  return access !== null && access.expiresAt - EXPIRY_SKEW_MS > now;
}

export function setAccessToken(token: string, expiresInSeconds: number): void {
  access = { token, expiresAt: Date.now() + expiresInSeconds * 1000 };
}

export function clearAccessToken(): void {
  access = null;
}

/** Bu brauzerda tiklanishi mumkin bo'lgan sessiya bormi (cookie yoki eski token). */
export function hasSessionHint(): boolean {
  const s = storage();
  if (!s) return false;
  try {
    return s.getItem(HINT_KEY) === "1" || s.getItem(LEGACY_KEY) !== null;
  } catch {
    return false;
  }
}

export function setSessionHint(on: boolean): void {
  const s = storage();
  if (!s) return;
  try {
    if (on) s.setItem(HINT_KEY, "1");
    else s.removeItem(HINT_KEY);
  } catch {
    // Saqlash bloklangan (private rejim) — sessiya shu tab ichida ishlayveradi.
  }
}

/** Boshqa tabda login/logout bo'lganini bildiradi. Obunani bekor qiluvchi funksiya qaytaradi. */
export function onSessionHintChange(listener: (active: boolean) => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = (event: StorageEvent) => {
    if (event.key === HINT_KEY) listener(event.newValue === "1");
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

/** Eski localStorage refresh tokenini oladi va o'chiradi (bir martalik ko'chirish). */
export function takeLegacyRefreshToken(): string | null {
  const s = storage();
  if (!s) return null;
  try {
    const raw = s.getItem(LEGACY_KEY);
    if (raw === null) return null;
    s.removeItem(LEGACY_KEY);
    const parsed = JSON.parse(raw) as { refresh?: unknown };
    return typeof parsed.refresh === "string" ? parsed.refresh : null;
  } catch {
    return null;
  }
}

/** Ko'chirish vaqtinchalik xato bilan to'xtasa — keyingi urinish uchun qaytarib qo'yiladi. */
export function restoreLegacyRefreshToken(refresh: string): void {
  const s = storage();
  try {
    s?.setItem(LEGACY_KEY, JSON.stringify({ refresh }));
  } catch {
    // e'tiborsiz
  }
}
