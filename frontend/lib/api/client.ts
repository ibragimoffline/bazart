import { getAccessToken } from "@/lib/api/token";

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

type FetchOptions = {
  method?: string;
  /** JSON body (obyekt) yoki URLSearchParams (form-urlencoded — login uchun). */
  body?: unknown;
  /** false — Authorization header qo'shilmaydi (ochiq endpointlar). */
  auth?: boolean;
};

export async function apiFetch<T>(
  path: string,
  { method, body, auth = true }: FetchOptions = {}
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

  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: method ?? (payload !== undefined ? "POST" : "GET"),
      headers,
      body: payload,
    });
  } catch {
    throw new ApiError(0, "Serverga ulanib bo'lmadi. Backend ishga tushganini tekshiring.");
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
