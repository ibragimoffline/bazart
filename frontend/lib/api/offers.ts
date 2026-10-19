/**
 * Taklifli savdo API'si (backend: app/api/v1/endpoints/offers.py, items.py).
 *
 * Narxlar — TIYIN (string), har doim DONA uchun. Jami = miqdor x dona narxi
 * (`total_price`, server hisoblaydi). Har qanday musbat narx taklif qilinadi —
 * mo'ljal narxdan past ham, yuqori ham; min qadam yo'q.
 */

import { apiFetch } from "@/lib/api/client";
import type { Item, ItemStatus } from "@/lib/api/types";

export type OfferStatus = "pending" | "accepted" | "rejected" | "withdrawn" | "expired";
export type OfferParty = "buyer" | "seller";
export type OfferAction =
  | "offer"
  | "counter"
  | "accept"
  | "reject"
  | "withdraw"
  | "expire"
  | "sold_out"
  | "cancel";

export interface OfferEvent {
  id: number;
  /** null — tizim (muddat o'tishi, zaxira tugashi). */
  actor: OfferParty | null;
  action: OfferAction;
  quantity: number | null;
  /** tiyin (string) */
  unit_price: string | null;
  message: string | null;
  created_at: string;
}

export interface Offer {
  id: number;
  item_id: number;
  item: {
    id: number;
    title: string;
    images: string[];
    /** tiyin (string) — moʻljal narx, dona */
    starting_price: string;
    quantity_available: number;
    status: ItemStatus;
  } | null;
  buyer_id: number;
  seller_id: number;
  /** Qabul qilinguncha maskalangan ism. */
  buyer_display: string;
  quantity: number;
  /** tiyin (string) — dona narxi */
  unit_price: string;
  /** tiyin (string) — miqdor x dona narxi */
  total_price: string;
  status: OfferStatus;
  /** Kimning javobi kutilmoqda. */
  awaiting: OfferParty;
  expires_at: string;
  order_id: number | null;
  events: OfferEvent[];
  created_at: string;
  updated_at: string;
}

export type OfferTerms = {
  quantity: number;
  /** tiyin (string) */
  unit_price: string;
  message?: string;
};

/** Qoralamani taklifli e'lon qilish (yoki muddati o'tganini qayta ochish). */
export function publishItem(itemId: number, durationDays: 3 | 5 | 7): Promise<Item> {
  return apiFetch<Item>(`/items/${itemId}/publish`, {
    method: "POST",
    body: { duration_days: durationDays },
  });
}

/** Faol taklifli e'lonlar (katalog). */
export function listOfferItems(limit = 100): Promise<Item[]> {
  const q = new URLSearchParams({ listing_type: "offer", status: "active", limit: String(limit) });
  return apiFetch<Item[]>(`/items?${q.toString()}`, { auth: false });
}

export function makeOffer(itemId: number, terms: OfferTerms): Promise<Offer> {
  return apiFetch<Offer>(`/items/${itemId}/offers`, { method: "POST", body: terms });
}

/** Sotuvchi — e'londagi barcha takliflar; boshqalar — faqat o'z takliflari. */
export function listItemOffers(itemId: number): Promise<Offer[]> {
  return apiFetch<Offer[]>(`/items/${itemId}/offers`);
}

export function listMyOffers(role: OfferParty, status?: OfferStatus): Promise<Offer[]> {
  const q = new URLSearchParams({ role });
  if (status) q.set("status", status);
  return apiFetch<Offer[]>(`/offers?${q.toString()}`);
}

export function acceptOffer(offerId: number): Promise<Offer> {
  return apiFetch<Offer>(`/offers/${offerId}/accept`, { method: "POST" });
}

export function counterOffer(offerId: number, terms: OfferTerms): Promise<Offer> {
  return apiFetch<Offer>(`/offers/${offerId}/counter`, { method: "POST", body: terms });
}

export function rejectOffer(offerId: number): Promise<Offer> {
  return apiFetch<Offer>(`/offers/${offerId}/reject`, { method: "POST" });
}

export function withdrawOffer(offerId: number): Promise<Offer> {
  return apiFetch<Offer>(`/offers/${offerId}/withdraw`, { method: "POST" });
}
