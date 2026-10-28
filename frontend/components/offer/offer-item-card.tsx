"use client"

import { HandshakeIcon } from "lucide-react"

import type { Item } from "@/lib/api/types"
import { ProductTile } from "@/components/lot/lot-card"

/**
 * Taklifli e'lon kartochkasi (LotCard bilan bir xil foto-karta): narx — DONA uchun
 * mo'ljal. Xaridor narxni o'zi taklif qiladi.
 */
function OfferItemCard({ item, className }: { item: Item; className?: string }) {
  return (
    <ProductTile
      href={`/item/${item.id}`}
      item={item}
      price={item.starting_price}
      meta="Narx taklifi"
      MetaIcon={HandshakeIcon}
      ended={item.status !== "active"}
      endedLabel={item.status === "sold" ? "Sotildi" : "Yopilgan"}
      endsAt={item.listing_ends_at}
      windowDays={item.listing_duration_days}
      className={className}
    />
  )
}

export { OfferItemCard }
