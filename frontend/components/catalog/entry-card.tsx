"use client"

import type { CatalogEntry } from "@/lib/catalog"
import { LotCard } from "@/components/lot/lot-card"
import { OfferItemCard } from "@/components/offer/offer-item-card"

/** Katalog yozuvi kartochkasi: auksion — LotCard, taklifli e'lon — OfferItemCard. */
function EntryCard({ entry, className }: { entry: CatalogEntry; className?: string }) {
  return entry.kind === "auction" ? (
    <LotCard lot={entry.lot} className={className} />
  ) : (
    <OfferItemCard item={entry.item} className={className} />
  )
}

export { EntryCard }
