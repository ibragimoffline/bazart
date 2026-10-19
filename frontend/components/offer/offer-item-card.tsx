"use client"

import Link from "next/link"
import { ImageIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatNumber, formatTiyin } from "@/lib/format"
import type { Item, ItemCondition } from "@/lib/api/types"
import { heroImage } from "@/lib/item-image"
import { Badge } from "@/components/ui/badge"
import { DeadlineBar } from "@/components/ui/deadline-bar"

const CONDITION_LABEL: Record<ItemCondition, string> = {
  new: "Yangi",
  used: "Ishlatilgan",
  refurbished: "Tiklangan",
}

/**
 * Taklifli e'lon kartochkasi (LotCard bilan bir xil plitka uslubi): narx — DONA uchun
 * mo'ljal, ostida mavjud miqdor. Xaridor narxni o'zi taklif qiladi.
 */
function OfferItemCard({ item, className }: { item: Item; className?: string }) {
  const hero = heroImage(item)
  const open = item.status === "active"
  const tag = CONDITION_LABEL[item.condition]

  return (
    <Link
      href={`/item/${item.id}`}
      className={cn(
        "group flex flex-col gap-3 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-offset-4 focus-visible:ring-offset-background",
        className
      )}
    >
      <div className={cn("relative aspect-4/5 overflow-hidden rounded-xl", hero ? "bg-muted" : "bg-brand-soft")}>
        {hero ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={hero}
            alt={item.title}
            loading="lazy"
            className="absolute inset-0 size-full object-cover transition-transform duration-200 group-hover:scale-105"
          />
        ) : (
          <div className="absolute inset-0 grid place-items-center">
            <ImageIcon className="size-10 text-brand/30" aria-hidden="true" />
          </div>
        )}

        <span className="pointer-events-none absolute top-2.5 left-2.5 rounded-md border border-foreground/70 bg-card px-1.5 py-0.5 text-xs font-semibold tracking-wide text-foreground uppercase">
          {tag}
        </span>

        {open && item.listing_ends_at ? (
          <DeadlineBar endsAt={item.listing_ends_at} />
        ) : (
          <div className="absolute inset-0 grid place-items-center bg-background/60">
            <Badge variant="neutral" className="h-6 px-3 text-sm">
              {item.status === "sold" ? "Sotildi" : "Yopilgan"}
            </Badge>
          </div>
        )}
      </div>

      <div className="grid gap-1 px-0.5">
        <h3 className="line-clamp-2 text-sm font-semibold text-foreground underline-offset-2 group-hover:underline">
          {item.title}
        </h3>
        <p className="tabular-nums text-foreground">
          <span className="text-lg font-bold">{formatTiyin(item.starting_price)}</span>
          <span className="text-xs text-muted-foreground"> / dona</span>
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {formatNumber(item.quantity_available)} dona · narxni oʻzingiz taklif qiling
        </p>
      </div>
    </Link>
  )
}

export { OfferItemCard }
