"use client"

import * as React from "react"

import { formatNumber, formatTiyin } from "@/lib/format"
import type { Offer, OfferEvent, OfferParty, OfferStatus } from "@/lib/api/offers"
import {
  hasConsented,
  listMyConsents,
  recordConsent,
  type ConsentDocumentType,
  type LegalConsent,
} from "@/lib/api/legal"
import type { BadgeVariant } from "@/components/admin/labels"

/**
 * Taklif matnlari va holat belgilari — sotuvchi va xaridor ekranlari bir xil gapirsin.
 * Ranglar faqat semantik Badge variantlari orqali.
 */

export const OFFER_STATUS_LABEL: Record<OfferStatus, string> = {
  pending: "Javob kutilmoqda",
  accepted: "Bitim tuzildi",
  rejected: "Rad etildi",
  withdrawn: "Qaytarib olindi",
  expired: "Muddati oʻtdi",
}

export const OFFER_STATUS_VARIANT: Record<OfferStatus, BadgeVariant> = {
  pending: "secondary",
  accepted: "success",
  rejected: "outline",
  withdrawn: "outline",
  expired: "outline",
}

/** "2 dona x 120 000 soʻm" — narx har doim DONA uchun. */
export function termsText(quantity: number | null, unitPrice: string | null): string {
  if (quantity == null || unitPrice == null) return ""
  return `${formatNumber(quantity)} dona x ${formatTiyin(unitPrice)}`
}

const PARTY_LABEL: Record<OfferParty, string> = { buyer: "Xaridor", seller: "Sotuvchi" }

/** Tarix qatori: kim nima qildi. */
export function eventText(event: OfferEvent): string {
  const who = event.actor ? PARTY_LABEL[event.actor] : "Tizim"
  const terms = termsText(event.quantity, event.unit_price)
  switch (event.action) {
    case "offer":
      return `${who} taklif berdi: ${terms}`
    case "counter":
      return `${who} qarshi taklif berdi: ${terms}`
    case "accept":
      return `${who} qabul qildi: ${terms}`
    case "reject":
      return `${who} rad etdi`
    case "withdraw":
      return "Xaridor taklifni qaytarib oldi"
    case "expire":
      return "Javob berilmadi — muddati oʻtdi"
    case "sold_out":
      return "Mahsulot tugadi — taklif yopildi"
    case "cancel":
      return "Eʼlon olib tashlandi — taklif yopildi"
  }
}

/** Kimning navbati: "me" — joriy foydalanuvchi javob beradi. */
export function turnOf(offer: Offer, viewer: OfferParty): "me" | "them" | null {
  if (offer.status !== "pending") return null
  return offer.awaiting === viewer ? "me" : "them"
}

/** "5 soat 20 daqiqa" / "2 kun" — qolgan vaqt (o'tib ketgan bo'lsa null). */
export function timeLeftText(iso: string, nowMs: number): string | null {
  const ms = Date.parse(iso) - nowMs
  if (!Number.isFinite(ms) || ms <= 0) return null
  const minutes = Math.floor(ms / 60_000)
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  if (days >= 1) return hours ? `${days} kun ${hours} soat` : `${days} kun`
  if (hours >= 1) return `${hours} soat ${minutes % 60} daqiqa`
  return `${Math.max(1, minutes)} daqiqa`
}

/** Joriy vaqt (render'da Date.now chaqirilmaydi — lint/SSR uchun xavfsiz). 0 — hali noma'lum. */
export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = React.useState(0)
  React.useEffect(() => {
    const tick = () => setNow(Date.now())
    tick()
    const id = window.setInterval(tick, intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

/**
 * Xaridor uchun huquqiy rozilik (auksion bilan bir xil hujjatlar): sotuvchi taklifni
 * qabul qilsa bitim (order) tuziladi — bu ommaviy oferta shartlarida.
 */
const OFFER_DOCUMENTS: ConsentDocumentType[] = ["auction_rules", "public_offer"]

export function useOfferConsent(enabled: boolean) {
  const [consents, setConsents] = React.useState<LegalConsent[] | null>(null)

  React.useEffect(() => {
    if (!enabled) return
    let alive = true
    listMyConsents()
      .then((list) => alive && setConsents(list))
      // Yuklanmasa — rozilik so'raymiz (xavfsiz tomon).
      .catch(() => alive && setConsents([]))
    return () => {
      alive = false
    }
  }, [enabled])

  const ready = !enabled || consents !== null
  const needsConsent = enabled && consents !== null && !hasConsented(consents, OFFER_DOCUMENTS)

  const ensure = React.useCallback(async () => {
    if (!needsConsent) return
    const recorded = await Promise.all(OFFER_DOCUMENTS.map((d) => recordConsent(d)))
    setConsents((prev) => [...(prev ?? []), ...recorded])
  }, [needsConsent])

  return { ready, needsConsent, ensure }
}
