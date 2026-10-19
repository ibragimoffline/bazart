"use client"

import * as React from "react"
import { GavelIcon, ShoppingBagIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatTiyin } from "@/lib/format"
import type { Auction } from "@/lib/api/types"
import { useAuthStore } from "@/lib/store/auth"
import { Button } from "@/components/ui/button"

/**
 * Mobil: tab-bar ustida yopishqoq "joriy narx + Taklif berish" paneli
 * (docs/DESIGN.md — mahsulot sahifasining sticky asosiy CTA'si).
 * Narx kartasi yoki taklif paneli ekranda ko'ringanda yashirinadi — bir xil narx va
 * tugma ikki marta chiqmasin.
 * Bosilganda taklif paneliga aylantiradi va summa maydoniga fokus beradi.
 */
function MobileBidBar({
  auction,
  targetId,
  priceId,
}: {
  auction: Auction
  targetId: string
  /** Narx kartasi — u ko'ringanda panel ham yashirinadi. */
  priceId?: string
}) {
  const user = useAuthStore((s) => s.user)
  const [visibleIds, setVisibleIds] = React.useState<ReadonlySet<string>>(new Set())
  const panelVisible = visibleIds.size > 0

  React.useEffect(() => {
    const els = [targetId, priceId]
      .map((id) => (id ? document.getElementById(id) : null))
      .filter((el): el is HTMLElement => el !== null)
    if (els.length === 0) return
    const observer = new IntersectionObserver(
      (entries) =>
        setVisibleIds((prev) => {
          const next = new Set(prev)
          for (const e of entries) {
            if (e.isIntersecting) next.add(e.target.id)
            else next.delete(e.target.id)
          }
          return next
        }),
      { threshold: 0.15 }
    )
    els.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [targetId, priceId])

  if (auction.status !== "active" || user?.id === auction.seller_id) return null

  const goToPanel = () => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    document
      .getElementById(targetId)
      ?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" })
    window.setTimeout(
      () => document.getElementById("bid-amount")?.focus({ preventScroll: true }),
      reduce ? 0 : 250
    )
  }

  return (
    <div
      inert={panelVisible}
      className={cn(
        "fixed inset-x-0 bottom-16 z-20 border-t border-border bg-background px-4 py-2.5 transition-[opacity,translate] duration-200 md:hidden",
        panelVisible && "pointer-events-none translate-y-2 opacity-0"
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="grid min-w-0">
          <span className="text-xs text-muted-foreground">Joriy narx</span>
          <span className="truncate text-lg font-semibold tabular-nums text-foreground">
            {formatTiyin(auction.current_price)}
          </span>
        </div>
        <Button size="lg" className="shrink-0" onClick={goToPanel}>
          {auction.pricing_mode === "descending" ? (
            <ShoppingBagIcon aria-hidden="true" />
          ) : (
            <GavelIcon aria-hidden="true" />
          )}
          {auction.pricing_mode === "descending" ? "Sotib olish" : "Taklif berish"}
        </Button>
      </div>
    </div>
  )
}

export { MobileBidBar }
