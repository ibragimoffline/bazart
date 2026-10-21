/**
 * Profil (foydalanuvchi) endpointlari.
 *
 * MUHIM (backend haqiqati): app/api/v1/endpoints/users.py da ochiq
 * `GET /users/{id}` YO'Q — faqat `GET /users/me` va `PATCH /users/me` bor.
 * Shu sabab `getUser(id)` faqat JORIY foydalanuvchi (self) uchun ishlaydi:
 * `/auth/me` chaqiriladi va id mos kelsagina User qaytadi, aks holda null.
 * Ochiq sotuvchi profili sahifasi reyting/sharhlarni `listUserReviews` (ochiq)
 * orqali oladi.
 */

import { apiFetch } from "@/lib/api/client";
import type { User, UserMe } from "@/lib/api/types";

/** UserUpdate (app/schemas/user.py) — barcha maydon ixtiyoriy. */
export interface UserUpdateInput {
  full_name?: string | null;
  phone?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
  location?: string | null;
}

/** Joriy foydalanuvchi (self). GET /auth/me. */
export function getMe(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

/**
 * Foydalanuvchini id bo'yicha olish.
 * Backend'da ochiq GET /users/{id} yo'q — faqat self (/auth/me) mavjud.
 * Boshqa foydalanuvchi yoki anonim uchun null qaytadi (xato tashlamaydi).
 */
export async function getUser(id: number): Promise<User | null> {
  try {
    const me = await apiFetch<User>("/auth/me");
    return me.id === id ? me : null;
  } catch {
    return null;
  }
}

/** Profilni yangilash. PATCH /users/me (UserUpdate). */
export function updateMe(payload: UserUpdateInput): Promise<User> {
  return apiFetch<User>("/users/me", { method: "PATCH", body: payload });
}

/** Kengaytirilgan profil (faqat ega): Telegram, til, telefon tasdig'i. GET /users/me. */
export function getMyProfile(): Promise<UserMe> {
  return apiFetch<UserMe>("/users/me");
}

/** Telegram chat'ini ulash — bildirishnomalar shu chat'ga ham yuboriladi. */
export function linkTelegram(chatId: string): Promise<UserMe> {
  return apiFetch<UserMe>("/users/me/telegram", { body: { chat_id: chatId } });
}

/** Interfeys / bildirishnoma tili. */
export function updatePreferences(language: "uz" | "ru"): Promise<UserMe> {
  return apiFetch<UserMe>("/users/me/preferences", {
    method: "PATCH",
    body: { preferred_language: language },
  });
}

// --- Telefon tasdiqlash (OTP) -----------------------------------------------
// Kod login qilgan akkauntga bog'lanadi; to'g'ri kod raqamni shu akkauntga yozadi va
// tasdiqlaydi (profilga oldindan saqlash shart emas). Tasdiqlangan raqamni almashtirishda
// `password` (yoki yaqinda login) kerak — aks holda 403 `reauth_required`.

export interface OtpRequestResult {
  message: string;
  expires_at: string;
  /** Qayta yuborishgacha soniya (taymer uchun). */
  resend_after_seconds: number;
  /** Faqat local/test muhitda keladi (SMS'siz sinash uchun). Prod'da doim null. */
  debug_code: string | null;
}

export interface OtpVerifyResult {
  message: string;
  verified: boolean;
  phone_verified: boolean;
}

export function requestPhoneOtp(phone: string, password?: string): Promise<OtpRequestResult> {
  return apiFetch<OtpRequestResult>("/auth/otp/request", {
    body: { phone, purpose: "phone_verify", ...(password ? { password } : {}) },
  });
}

export function verifyPhoneOtp(phone: string, code: string): Promise<OtpVerifyResult> {
  return apiFetch<OtpVerifyResult>("/auth/otp/verify", {
    body: { phone, code, purpose: "phone_verify" },
  });
}
