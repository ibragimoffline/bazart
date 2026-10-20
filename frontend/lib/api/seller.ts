/**
 * Sotuvchi (listing yaratish) oqimi uchun API funksiyalari.
 *
 * Pul maydonlari — TIYIN (string). soʻm kiritilsa `soumToTiyin` bilan aylantiring.
 * Rasm yuklash multipart/form-data orqali — bu holda `apiFetch` emas, toʻgʻridan-toʻgʻri
 * `fetch` ishlatiladi (Content-Type'ni brauzer boundary bilan oʻzi qoʻyadi).
 */

import { apiFetch, API_BASE, ApiError, authFetch } from "@/lib/api/client";
import type {
  Item,
  ItemImage,
  Auction,
  AuctionStatus,
  ItemCondition,
  PricingMode,
} from "@/lib/api/types";

export type CreateItemPayload = {
  title: string;
  /** Necha dona sotiladi (taklifli e'lon). Auksion — faqat 1. */
  quantity?: number;
  description?: string;
  category_id?: number;
  condition: ItemCondition;
  /** Erkin matnli aniq manzil (koʻcha, moʻljal). */
  location?: string;
  /** Ishlab chiqarilgan yil, 1900–2100. */
  year?: number;
  /** Komplektatsiya, koʻpi 2000 belgi. */
  equipment?: string;
  /** Nuqsonlar, koʻpi 2000 belgi. */
  defects?: string;
  /** Video havola (http/https), koʻpi 500 belgi. */
  video_url?: string;
  /** Viloyat — GET /regions dan. */
  region_id?: number;
  /** Tuman — tanlangan viloyatning GET /regions/{id}/districts roʻyxatidan. */
  district_id?: number;
  /** tiyin (string) */
  starting_price: string;
  /** tiyin (string) */
  reserve_price?: string;
};

/** Qoralamani yangilash (PATCH /items/{id}). Miqdor faqat e'lon qilinguncha o'zgaradi. */
export function updateItem(itemId: number, payload: Partial<CreateItemPayload>): Promise<Item> {
  return apiFetch<Item>(`/items/${itemId}`, { method: "PATCH", body: payload });
}

/**
 * Boshlanmagan auksionning narx rejimini to'liq almashtirish (PATCH /auctions/{id}/pricing).
 * Berilmagan maydon tozalanadi. reserve_price: o'suvchida — rezerv, pasayuvchida — chegara.
 */
export function updateAuctionPricing(
  auctionId: number,
  payload: {
    pricing_mode: PricingMode;
    price_decrement?: string;
    price_drop_interval_minutes?: number;
    reserve_price?: string;
    buy_now_price?: string;
    dutch_fallback_floor?: string;
  }
): Promise<Auction> {
  return apiFetch<Auction>(`/auctions/${auctionId}/pricing`, { method: "PATCH", body: payload });
}

/** Tovar (item) yaratish. POST /items → Item. */
export function createItem(payload: CreateItemPayload): Promise<Item> {
  return apiFetch<Item>("/items", { method: "POST", body: payload });
}

/**
 * Tovarga rasm yuklash. POST /items/{id}/images (multipart).
 * FormData ishlatilgani uchun Content-Type qoʻlda qoʻyilmaydi — brauzer
 * multipart boundary bilan avtomatik qoʻyadi. Bearer va 401-yangilash — authFetch.
 */
export async function uploadItemImage(
  itemId: number,
  file: File,
  isPrimary: boolean
): Promise<ItemImage> {
  const form = new FormData();
  form.append("file", file);
  form.append("is_primary", isPrimary ? "true" : "false");

  const res = await authFetch(`${API_BASE}/items/${itemId}/images`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    let detail = res.statusText || "Rasm yuklanmadi";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail))
        detail = data.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ");
    } catch {
      // JSON emas — statusText qoladi.
    }
    throw new ApiError(res.status, detail);
  }

  // Backend {"image": ItemImage} qaytaradi.
  const data = (await res.json()) as { image: ItemImage };
  return data.image;
}

export type CreateAuctionPayload = {
  item_id: number;
  /** ISO datetime */
  start_time: string;
  duration_days: 3 | 5 | 7;
  /** tiyin (string) */
  minimum_bid_increment: string;
  /** tiyin (string) */
  reserve_price?: string;
  /** tiyin (string) — "hoziroq sotib olish" narxi, boshlang'ich narxdan yuqori. */
  buy_now_price?: string;
  /** "descending" — golland auksioni: reserve_price (pastki chegara) majburiy, buy_now_price yo'q. */
  pricing_mode?: PricingMode;
  /**
   * tiyin (string) — sotuvchi roziligi: taklifsiz tugasa 3 kunlik pasayuvchi auksionga
   * o'tadi, bu — o'sha bosqichning eng past narxi. Faqat o'suvchi auksionda; ommaga oshkor emas.
   */
  dutch_fallback_floor?: string;
  /** tiyin (string) — har oraliqdagi pasayish (faqat descending). */
  price_decrement?: string;
  /** 5..1440 daqiqa (faqat descending). */
  price_drop_interval_minutes?: number;
};

/** Auksion ochish. POST /auctions → Auction. duration_days beriladi (end_time EMAS). */
export function createAuction(payload: CreateAuctionPayload): Promise<Auction> {
  return apiFetch<Auction>("/auctions", { method: "POST", body: payload });
}

/**
 * Lotni bekor qilish. DELETE /items/{id} → Item.
 * Jonli auksion bo'lsa u ham bekor qilinadi; taklif tushgan yoki yakunlangan
 * auksion uchun backend 409 qaytaradi.
 */
export function cancelListing(itemId: number): Promise<Item> {
  return apiFetch<Item>(`/items/${itemId}`, { method: "DELETE" });
}

export type RelistPayload = {
  duration_days: 3 | 5 | 7;
  /** tiyin (string) */
  starting_price: string;
  /** tiyin (string) */
  minimum_bid_increment?: string;
  /** tiyin (string) */
  reserve_price?: string;
  /** tiyin (string) */
  buy_now_price?: string;
};

/**
 * Sotilmagan lotni qayta joylash. POST /auctions/{id}/relist → YANGI Auction.
 * E'lon nusxa ko'chiriladi (rasmlar bilan); har lot faqat bir marta qayta joylanadi.
 */
export function relistAuction(auctionId: number, payload: RelistPayload): Promise<Auction> {
  return apiFetch<Auction>(`/auctions/${auctionId}/relist`, { method: "POST", body: payload });
}

/** Sotuvchining auksionlari (berilgan holatda). GET /auctions?seller_id&status → Auction[]. */
export function listSellerAuctions(sellerId: number, status: AuctionStatus): Promise<Auction[]> {
  const q = new URLSearchParams();
  q.set("seller_id", String(sellerId));
  q.set("status", status);
  q.set("limit", "100");
  return apiFetch<Auction[]>(`/auctions?${q.toString()}`, { auth: false });
}

/** Sotuvchining tovarlari. GET /items?seller_id={id} → Item[]. */
export function listSellerItems(sellerId: number): Promise<Item[]> {
  const q = new URLSearchParams();
  q.set("seller_id", String(sellerId));
  q.set("limit", "100");
  return apiFetch<Item[]>(`/items?${q.toString()}`, { auth: false });
}
