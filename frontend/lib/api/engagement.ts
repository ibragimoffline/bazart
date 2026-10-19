/**
 * Bildirishnoma va sharh (engagement) endpointlari.
 *
 * Turlar backend sxemalariga (app/schemas/notification.py, review.py) 1:1 mos
 * keladi. Maydon nomlari AYNAN backend'dagidek — review'da `stars`/`text`
 * (rating/comment emas).
 */

import { apiFetch } from "@/lib/api/client";

// --- Bildirishnomalar --------------------------------------------------

/** NotificationType (app/models/enums.py). */
export type NotificationType =
  | "outbid"
  | "won"
  | "sold"
  /** Rezervga yetmadi — sotuvchiga "eng yuqori taklifga sotish" taklifi. payload: auction_id, expires_at. */
  | "second_chance"
  /** Kuzatilayotgan auksion tugashiga oz qoldi. */
  | "ending_soon"
  /** Taklifli savdo: payload — offer_id, item_id (qabulda order_id ham). */
  | "offer_received"
  | "offer_countered"
  | "offer_accepted"
  | "offer_closed"
  /** Taklifsiz tugagan lot pasayuvchi auksionga o'tdi. payload: auction_id (yangi). */
  | "dutch_started"
  /** Pasayuvchi auksionda narx sezilarli tushdi (kuzatuvchilarga). payload: auction_id, previous_price, current_price, at_floor. */
  | "price_dropped";

/** NotificationRead sxemasi. */
export interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  body: string | null;
  /** Ixtiyoriy kontekst (masalan auction_id/order_id) — turi erkin. */
  payload: Record<string, unknown> | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

interface UnreadCount {
  count: number;
}

/** Joriy foydalanuvchi bildirishnomalari (yangi -> eski, backend tartibi). */
export function listNotifications(onlyUnread = false): Promise<Notification[]> {
  const q = onlyUnread ? "?only_unread=true" : "";
  return apiFetch<Notification[]>(`/notifications${q}`);
}

/** O'qilmagan bildirishnomalar soni (qo'ng'iroq nishoni uchun). */
export function unreadNotificationsCount(): Promise<number> {
  return apiFetch<UnreadCount>("/notifications/unread-count").then((r) => r.count);
}

/** Bitta bildirishnomani o'qilgan deb belgilash. */
export function markNotificationRead(id: number): Promise<Notification> {
  return apiFetch<Notification>(`/notifications/${id}/read`, { method: "POST" });
}

/** Hammasini o'qilgan deb belgilash. Qaytadi: o'zgargan (o'qilgan) soni. */
export function markAllNotificationsRead(): Promise<number> {
  return apiFetch<UnreadCount>("/notifications/read-all", { method: "POST" }).then(
    (r) => r.count
  );
}

// --- Sharhlar (reviews) ------------------------------------------------

/** ReviewRead sxemasi. `to_id` — orderning ikkinchi tomoni (serverda aniqlanadi). */
export interface Review {
  id: number;
  order_id: number;
  from_id: number;
  to_id: number;
  stars: number;
  text: string | null;
  created_at: string;
}

/** ReviewCreate — `to_id` klientdan olinmaydi. */
export interface ReviewCreateInput {
  order_id: number;
  /** 1..5; chegaradan tashqari -> 422. */
  stars: number;
  text?: string;
}

/** Sharh yaratish (order COMPLETED bo'lgach). */
export function createReview(input: ReviewCreateInput): Promise<Review> {
  return apiFetch<Review>("/reviews", { method: "POST", body: input });
}

/** Foydalanuvchi haqidagi sharhlar (ochiq — auth shart emas). */
export function listUserReviews(userId: number): Promise<Review[]> {
  return apiFetch<Review[]>(`/reviews/user/${userId}`, { auth: false });
}
