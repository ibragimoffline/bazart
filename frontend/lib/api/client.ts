import {
  clearAccessToken,
  getAccessToken,
  hasSessionHint,
  isAccessFresh,
  restoreLegacyRefreshToken,
  setAccessToken,
  setSessionHint,
  takeLegacyRefreshToken,
} from "@/lib/api/token";

const BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export const API_BASE = `${BASE}/api/v1`;

/**
 * Media (yuklangan rasm) uchun to'liq URL quradi.
 * Backend `image_url` ni `/uploads/...` ko'rinishida (nisbiy) qaytaradi — u
 * `/api/v1` ostida EMAS, host ildizidagi static mount. To'liq URL kerak.
 * Allaqachon absolyut (http...) bo'lsa — o'zgartirmaymiz.
 */
export function mediaUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

/**
 * Backend mashina kodlari -> foydalanuvchi matni. `code` kodni saqlaydi (UI shunga qarab
 * harakat taklif qiladi), `detail` esa ko'rsatiladigan matn.
 */
const DETAIL_TEXT: Record<string, string> = {
  phone_verification_required:
    "Avval telefon raqamingizni tasdiqlang (Profil sahifasi). Kelishuvda raqamingiz ikkinchi tomonga koʻrinadi.",
  ascending_auction_disabled:
    "Oʻsuvchi auksion hozircha oʻchirilgan. Pasayuvchi auksion yoki narx taklifi bilan joylang.",
  trading_restricted:
    "Soʻnggi 30 kunda 3 ta kelishuv sizning sababingiz bilan bekor boʻlgan. 14 kun davomida taklif va bid berib boʻlmaydi.",
};

/** Backend qaytargan xatolik (detail matni bilan). */
export class ApiError extends Error {
  status: number;
  detail: string;
  /** Backend'ning asl `detail` qiymati (mashina kodi bo'lsa, masalan phone_verification_required). */
  code: string;
  constructor(status: number, detail: string, code: string = detail) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

const NETWORK_ERROR = "Serverga ulanib bo'lmadi. Internet yoki backend'ni tekshiring.";

// --- Sessiyani yangilash -------------------------------------------------
//
// Access token 30 daqiqa yashaydi; refresh token HttpOnly cookie'da. Yangilash:
//   * bitta tab ichida — bitta so'rov (single-flight): parallel 401'lar shu va'dani kutadi;
//   * tablar orasida — Web Lock: refresh'lar navbat bilan, har biri oldingisi qo'ygan
//     yangi cookie bilan ketadi (rotation zanjiri uzilmaydi).
// Natija: "ok" — yangi access token; "ended" — server sessiyani rad etdi (401), qayta
// kirish kerak. Tarmoq/5xx — ApiError otiladi va sessiya TEGILMAYDI.

export type RefreshOutcome = "ok" | "ended";

type SessionEndedListener = () => void;
const endedListeners = new Set<SessionEndedListener>();

/** Sessiya serverda tugaganda (refresh 401) chaqiriladi. Obunani bekor qiluvchi qaytaradi. */
export function onSessionEnded(listener: SessionEndedListener): () => void {
  endedListeners.add(listener);
  return () => endedListeners.delete(listener);
}

let inflight: Promise<RefreshOutcome> | null = null;

export function refreshSession(): Promise<RefreshOutcome> {
  if (!inflight) {
    inflight = withRefreshLock(doRefresh).finally(() => {
      inflight = null;
    });
  }
  return inflight;
}

function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (!locks?.request) return fn();
  return locks.request("bazart-auth-refresh", fn) as Promise<T>;
}

async function doRefresh(): Promise<RefreshOutcome> {
  const legacy = takeLegacyRefreshToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      ...(legacy
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: legacy }),
          }
        : {}),
    });
  } catch {
    if (legacy) restoreLegacyRefreshToken(legacy);
    throw new ApiError(0, NETWORK_ERROR);
  }

  if (res.ok) {
    const data = (await res.json()) as { access_token: string; expires_in: number };
    setAccessToken(data.access_token, data.expires_in);
    setSessionHint(true);
    return "ok";
  }
  if (res.status === 401) {
    endSession();
    return "ended";
  }
  if (legacy) restoreLegacyRefreshToken(legacy);
  throw new ApiError(res.status, res.statusText || "Sessiyani yangilab bo'lmadi");
}

/** Lokal sessiyani tozalaydi va obunachilarga xabar beradi (boshqa tablar — hint orqali). */
export function endSession(): void {
  clearAccessToken();
  setSessionHint(false);
  for (const listener of endedListeners) listener();
}

/**
 * Yaroqli access token (kerak bo'lsa jimgina yangilab). Sessiya yo'q yoki tugagan — null.
 * Vaqtinchalik xatoda eski token qaytadi: so'rov o'zi 401 olsa, qayta urinish bor.
 */
export async function getFreshAccessToken(): Promise<string | null> {
  if (!isAccessFresh() && hasSessionHint()) {
    try {
      await refreshSession();
    } catch {
      // Tarmoq/5xx — sessiyani buzmaymiz.
    }
  }
  return getAccessToken();
}

/**
 * Autentifikatsiyali fetch: Authorization qo'shadi, 401 bo'lsa BIR marta sessiyani
 * yangilab so'rovni takrorlaydi. Refresh 401 bo'lsa — javob 401 qoladi (sessiya tugadi).
 * Body qayta yuboriladigan bo'lishi kerak (string, FormData, URLSearchParams).
 */
export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const send = async (token: string | null): Promise<Response> => {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    try {
      return await fetch(url, { ...init, headers });
    } catch {
      throw new ApiError(0, NETWORK_ERROR);
    }
  };

  const res = await send(await getFreshAccessToken());
  if (res.status !== 401 || !hasSessionHint()) return res;
  if ((await refreshSession()) !== "ok") return res;
  return send(getAccessToken());
}

type FetchOptions = {
  method?: string;
  /** JSON body (obyekt) yoki URLSearchParams (form-urlencoded — login uchun). */
  body?: unknown;
  /** false — Authorization header qo'shilmaydi (ochiq endpointlar). */
  auth?: boolean;
  /** true — cookie yuboriladi/qabul qilinadi (login: refresh cookie o'rnatiladi). */
  withCookies?: boolean;
};

export async function apiFetch<T>(
  path: string,
  { method, body, auth = true, withCookies = false }: FetchOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;

  if (body instanceof URLSearchParams) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = body.toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const init: RequestInit = {
    method: method ?? (payload !== undefined ? "POST" : "GET"),
    headers,
    body: payload,
    ...(withCookies ? { credentials: "include" as const } : {}),
  };

  let res: Response;
  if (auth) {
    res = await authFetch(`${API_BASE}${path}`, init);
  } else {
    try {
      res = await fetch(`${API_BASE}${path}`, init);
    } catch {
      throw new ApiError(0, NETWORK_ERROR);
    }
  }

  if (!res.ok) {
    let detail = res.statusText || "Xatolik yuz berdi";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail))
        detail = data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ");
    } catch {
      // JSON emas — statusText qoladi.
    }
    throw new ApiError(res.status, DETAIL_TEXT[detail] ?? detail, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
