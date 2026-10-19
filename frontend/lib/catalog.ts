/**
 * Katalog yozuvi: auksion loti YOKI taklifli e'lon. Katalog, bosh sahifa qatorlari
 * va kartochkalar shu umumiy ko'rinish bilan ishlaydi; auksion sahifasi va kuzatuv
 * ro'yxati esa o'z `Lot` turida qoladi.
 */

import type { Item, Lot } from "@/lib/api/types"
import { listLots } from "@/lib/api/endpoints"
import { listOfferItems } from "@/lib/api/offers"

export type CatalogEntry =
  | { kind: "auction"; key: string; item: Item; lot: Lot }
  | { kind: "offer"; key: string; item: Item }

export const auctionEntry = (lot: Lot): CatalogEntry => ({
  kind: "auction",
  key: `a${lot.auction.id}`,
  item: lot.item,
  lot,
})

export const offerEntry = (item: Item): CatalogEntry => ({
  kind: "offer",
  key: `o${item.id}`,
  item,
})

/** Saralash/filtr narxi, tiyin: auksionda joriy narx, taklifli e'londa dona narxi. */
export function entryPrice(e: CatalogEntry): number {
  return Number(e.kind === "auction" ? e.lot.auction.current_price : e.item.starting_price)
}

/** Tugash vaqti (ISO) yoki null. */
export function entryEndsAt(e: CatalogEntry): string | null {
  return e.kind === "auction" ? e.lot.auction.end_time : e.item.listing_ends_at
}

export function entryCreatedAt(e: CatalogEntry): string {
  return e.kind === "auction"
    ? e.lot.auction.created_at
    : (e.item.published_at ?? e.item.created_at)
}

export function entryHref(e: CatalogEntry): string {
  return e.kind === "auction" ? `/lot/${e.lot.auction.id}` : `/item/${e.item.id}`
}

/** Faol auksionlar + faol taklifli e'lonlar. Taklif ro'yxati yuklanmasa — faqat auksionlar. */
export async function listCatalogEntries(): Promise<CatalogEntry[]> {
  const [lots, offers] = await Promise.all([listLots(), listOfferItems().catch(() => [])])
  return [...offers.map(offerEntry), ...lots.map(auctionEntry)]
}

const time = (iso: string | null) => (iso ? new Date(iso).getTime() : Number.POSITIVE_INFINITY)

export const byEndingSoon = (a: CatalogEntry, b: CatalogEntry) =>
  time(entryEndsAt(a)) - time(entryEndsAt(b))

export const byNewest = (a: CatalogEntry, b: CatalogEntry) =>
  time(entryCreatedAt(b)) - time(entryCreatedAt(a))
