"use client"

import Link from "next/link"
import { GavelIcon, ImageIcon, TrendingDownIcon, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatTiyin } from "@/lib/format"
import type { Item, ItemCondition, Lot } from "@/lib/api/types"
import { heroImage } from "@/lib/item-image"
import { Badge } from "@/components/ui/badge"
import { DeadlineBar } from "@/components/ui/deadline-bar"

const CONDITION_LABEL: Record<ItemCondition, string> = {
  new: "Yangi",
  used: "Ishlatilgan",
  refurbished: "Tiklangan",
}

/** Foto o'rni fonlari — rasmsiz e'lonlar bir xil kulrang devor bo'lib qolmasin. */
const PHOTO_GROUNDS = [
  "bg-photo-1",
  "bg-photo-2",
  "bg-photo-3",
  "bg-photo-4",
  "bg-photo-5",
  "bg-photo-6",
] as const

/** Mahsulot joylashuvi (karta meta qatori uchun). */
function placeOf(item: Item): string | null {
  return item.item_location || item.location || null
}

/**
 * Mahsulot kartochkasi (v2): ramka yo'q — FOTO kartaning o'zi. Kvadrat foto
 * (holat belgisi chapda tepada, muddat chizig'i pastda) -> nom (2 qator) -> narx
 * -> jim meta qatori (ikonka + tafsilot · joy). Butun karta — bitta havola.
 */
function ProductTile({
  href,
  item,
  price,
  meta,
  MetaIcon,
  ended,
  endedLabel,
  endsAt,
  windowDays,
  className,
}: {
  href: string
  item: Item
  /** Narx, tiyin (string). */
  price: string
  meta: string
  MetaIcon: LucideIcon
  ended: boolean
  endedLabel: string
  endsAt: string | null
  windowDays: number | null
  className?: string
}) {
  const hero = heroImage(item)
  const place = placeOf(item)

  return (
    <Link
      href={href}
      className={cn(
        "group grid min-w-0 content-start gap-3 rounded-lg outline-none focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring",
        className
      )}
    >
      <div
        className={cn(
          "relative grid aspect-square place-items-center overflow-hidden rounded-lg transition-shadow duration-200 group-hover:shadow-md",
          PHOTO_GROUNDS[item.id % PHOTO_GROUNDS.length]
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
            className="absolute inset-0 size-full object-cover"
          />
        ) : (
          <ImageIcon className="size-2/5 text-foreground/30" strokeWidth={1.25} aria-hidden="true" />
        )}

        <div className="pointer-events-none absolute top-2.5 left-2.5">
          <Badge variant="on-photo">{CONDITION_LABEL[item.condition]}</Badge>
        </div>

        {ended || !endsAt ? (
          <div className="absolute inset-0 grid place-items-center bg-background/55">
            <Badge variant="neutral">{endedLabel}</Badge>
          </div>
        ) : (
          <DeadlineBar
            endsAt={endsAt}
            windowMinutes={windowDays ? windowDays * 1440 : undefined}
          />
        )}
      </div>

      <div className="grid gap-1 px-0.5">
        <h3 className="line-clamp-2 min-h-10 text-sm font-medium break-words text-foreground underline-offset-2 group-hover:underline">
          {item.title}
        </h3>
        <p className="text-lg font-bold tracking-tight break-words tabular-nums text-foreground">
          {formatTiyin(price)}
        </p>
        <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-muted-foreground">
          <MetaIcon className="size-3 shrink-0" aria-hidden="true" />
          <span>{meta}</span>
          {place && (
            <>
              <span className="size-0.75 shrink-0 rounded-full bg-current" aria-hidden="true" />
              <span className="min-w-0 truncate">{place}</span>
            </>
          )}
        </p>
      </div>
    </Link>
  )
}

/** Auksion loti: o'suvchi auksionda bid soni, pasayuvchida "Narxi pasaymoqda". */
function LotCard({ lot, className }: { lot: Lot; className?: string }) {
  const { auction, item } = lot
  const descending = auction.pricing_mode === "descending"
  const meta = descending
    ? "Narxi pasaymoqda"
    : auction.bid_count > 0
      ? `${auction.bid_count} ta taklif`
      : "Taklif yoʻq"

  return (
    <ProductTile
      href={`/lot/${auction.id}`}
      item={item}
      price={auction.current_price}
      meta={meta}
      MetaIcon={descending ? TrendingDownIcon : GavelIcon}
      ended={auction.status !== "active"}
      endedLabel="Tugagan"
      endsAt={auction.end_time}
      windowDays={auction.duration_days}
      className={className}
    />
  )
}

export { LotCard, ProductTile, CONDITION_LABEL }
