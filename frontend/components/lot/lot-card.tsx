"use client"

import Link from "next/link"
import { ImageIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatTiyin } from "@/lib/format"
import type { Lot, ItemCondition } from "@/lib/api/types"
import { heroImage } from "@/lib/item-image"
import { Badge } from "@/components/ui/badge"
import { DeadlineBar } from "@/components/ui/deadline-bar"

const CONDITION_LABEL: Record<ItemCondition, string> = {
  new: "Yangi",
  used: "Ishlatilgan",
  refurbished: "Tiklangan",
}

/** "Auksion · 3 ta taklif" — narx ostidagi bir qator jim tafsilot. */
function detailLine(lot: Lot): string {
  const { auction } = lot
  const descending = auction.pricing_mode === "descending"
  return [
    descending ? "Narxi pasaymoqda" : "Auksion",
    descending ? null : auction.bid_count > 0 ? `${auction.bid_count} ta taklif` : "Taklif yoʻq",
  ]
    .filter(Boolean)
    .join(" · ")
}

/**
 * Mahsulot kartochkasi (do'kon katalogi uslubi): yumshoq plitka ustida foto,
 * burchakda ingichka chegarali teg (holat · daraja), muddat "pill"i; ostida qalin
 * nom va narx. Butun karta — bitta havola, telefonda katta bosish maydoni.
 */
function LotCard({ lot, className }: { lot: Lot; className?: string }) {
  const { auction, item } = lot
  const ended = auction.status !== "active"
  const hero = heroImage(item)
  const tag = CONDITION_LABEL[item.condition]

  return (
    <Link
      href={`/lot/${auction.id}`}
      className={cn(
        "group flex flex-col gap-3 rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-offset-4 focus-visible:ring-offset-background",
        className
      )}
    >
      <div
        className={cn(
          "relative aspect-4/5 overflow-hidden rounded-xl",
          hero ? "bg-muted" : "bg-brand-soft"
        )}
      >
        {hero ? (
          // Backend host'idagi rasm — next/image emas, oddiy img: host prod'da
          // o'zgaruvchan va `remotePatterns` ga bog'lanib qolmaslik uchun.
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

        {ended ? (
          <div className="absolute inset-0 grid place-items-center bg-background/60">
            <Badge variant="neutral" className="h-6 px-3 text-sm">
              Tugagan
            </Badge>
          </div>
        ) : (
          <DeadlineBar endsAt={auction.end_time} />
        )}
      </div>

      <div className="grid gap-1 px-0.5">
        <h3 className="line-clamp-2 text-sm font-semibold text-foreground underline-offset-2 group-hover:underline">
          {item.title}
        </h3>
        <p className="text-lg font-bold tabular-nums text-foreground">
          {formatTiyin(auction.current_price)}
        </p>
        <p className="truncate text-xs text-muted-foreground">{detailLine(lot)}</p>
      </div>
    </Link>
  )
}

export { LotCard }
