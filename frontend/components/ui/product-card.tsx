"use client"

import * as React from "react"
import Image from "next/image"
import { StarIcon, ShoppingCartIcon, ImageIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatSom, discountPercent } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DeadlineBar } from "@/components/ui/deadline-bar"

type ProductCardProps = {
  title: string
  /** Joriy narx — so'mda. */
  price: number
  /** Eski narx — so'mda (chegirma bo'lsa). */
  oldPrice?: number
  rating?: number
  ratingCount?: number
  /** Rasm manzili. Berilmasa neytral placeholder (kulrang blok + nom) chiziladi. */
  image?: string
  href?: string
  /** Sotilgan lot — savatga qo'shib bo'lmaydi. */
  sold?: boolean
  /** "Yangi" belgisi. */
  isNew?: boolean
  /** Auksion lot — tugashiga qolgan daqiqa (muddat chizig'i chiziladi). */
  endsInMinutes?: number
  windowMinutes?: number
  onAddToCart?: () => void
  className?: string
}

function ProductCard({
  title,
  price,
  oldPrice,
  rating,
  ratingCount,
  image,
  href = "#",
  sold = false,
  isNew = false,
  endsInMinutes,
  windowMinutes,
  onAddToCart,
  className,
}: ProductCardProps) {
  const discount = oldPrice ? discountPercent(oldPrice, price) : 0

  return (
    <div
      data-slot="product-card"
      className={cn(
        "group/card flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-xs transition-shadow duration-200 hover:shadow-md",
        className
      )}
    >
      <a
        href={href}
        aria-label={title}
        className="relative block aspect-square overflow-hidden rounded-t-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {image ? (
          <Image
            src={image}
            alt={title}
            fill
            sizes="(max-width: 768px) 50vw, 240px"
            className="object-cover"
          />
        ) : (
          // Neytral placeholder — tashqi rasm servisisiz.
          <div className="absolute inset-0 grid place-items-center bg-muted p-3">
            <div className="flex flex-col items-center gap-2 text-center text-muted-foreground">
              <ImageIcon className="size-6" aria-hidden="true" />
              <span className="line-clamp-3 text-xs">{title}</span>
            </div>
          </div>
        )}

        {/* Belgilar rasm ustida. */}
        <div className="pointer-events-none absolute inset-x-2 top-2 flex flex-col items-start gap-1">
          {discount > 0 && <Badge variant="sale">−{discount}%</Badge>}
          {isNew && <Badge variant="default">Yangi</Badge>}
        </div>

        {/* Muddat chizig'i (auksion mahsuloti). */}
        {typeof endsInMinutes === "number" && !sold && (
          <DeadlineBar
            endsInMinutes={endsInMinutes}
            windowMinutes={windowMinutes}
          />
        )}

        {/* Sotilgan holat qoplamasi. */}
        {sold && (
          <div className="absolute inset-0 grid place-items-center bg-background/60">
            <Badge variant="neutral" className="h-6 px-3 text-sm">
              Sotildi
            </Badge>
          </div>
        )}
      </a>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <a
          href={href}
          className="outline-none focus-visible:underline"
          tabIndex={-1}
        >
          <h3 className="line-clamp-2 min-h-10 text-sm font-medium text-foreground">
            {title}
          </h3>
        </a>

        {typeof rating === "number" && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <StarIcon
              className="size-3.5 fill-warning text-warning"
              aria-hidden="true"
            />
            <span className="font-medium text-foreground">
              {rating.toFixed(1)}
            </span>
            {typeof ratingCount === "number" && <span>({ratingCount})</span>}
          </div>
        )}

        <div className="mt-auto flex flex-wrap items-baseline gap-x-2">
          <span className="text-base font-semibold tabular-nums text-foreground">
            {formatSom(price)}
          </span>
          {oldPrice && oldPrice > price && (
            <span className="text-sm tabular-nums text-muted-foreground line-through">
              {formatSom(oldPrice)}
            </span>
          )}
        </div>

        <Button
          variant="secondary"
          size="sm"
          className="mt-1 w-full"
          disabled={sold}
          onClick={onAddToCart}
        >
          <ShoppingCartIcon aria-hidden="true" />
          {sold ? "Mavjud emas" : "Savatga"}
        </Button>
      </div>
    </div>
  )
}

export { ProductCard, type ProductCardProps }
