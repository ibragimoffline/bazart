"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { toast } from "sonner"
import { InboxIcon, PackageIcon } from "lucide-react"

import { formatTiyin } from "@/lib/format"
import type { Item } from "@/lib/api/types"
import { getItem } from "@/lib/api/endpoints"
import { listItemOffers, makeOffer, type Offer } from "@/lib/api/offers"
import { ApiError } from "@/lib/api/client"
import { itemImageUrls } from "@/lib/item-image"
import { useAuthStore } from "@/lib/store/auth"
import { Gallery } from "@/components/product/gallery"
import { AssuranceBlock } from "@/components/product/assurance-block"
import { DeadlineBar } from "@/components/ui/deadline-bar"
import { LotSpecs, CONDITION_LABEL } from "@/components/lot/lot-specs"
import { ReportDialog } from "@/components/complaint/report-dialog"
import { MessageSellerButton } from "@/components/message/message-seller-button"
import { OfferCard } from "@/components/offer/offer-card"
import { OfferForm } from "@/components/offer/offer-form"
import { useOfferConsent } from "@/components/offer/offer-meta"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

const CLOSED_TEXT: Partial<Record<Item["status"], string>> = {
  sold: "Sotildi.",
  expired: "Eʼlon muddati tugadi.",
  cancelled: "Eʼlon olib tashlangan.",
}

/** Xaridor paneli: ochiq taklifi bo'lsa — muzokara kartasi, aks holda taklif shakli. */
function BuyerPanel({ item, onItemChanged }: { item: Item; onItemChanged: () => void }) {
  const [offers, setOffers] = React.useState<Offer[] | null>(null)
  const consent = useOfferConsent(true)

  const load = React.useCallback(() => {
    listItemOffers(item.id)
      .then(setOffers)
      .catch(() => setOffers([]))
  }, [item.id])

  React.useEffect(() => {
    load()
  }, [load])

  const replace = (updated: Offer) => {
    setOffers((prev) => (prev ?? []).map((o) => (o.id === updated.id ? updated : o)))
    onItemChanged()
  }

  if (offers === null || !consent.ready) return <Skeleton className="h-64 w-full rounded-lg" />

  const open = offers.find((o) => o.status === "pending")
  const past = offers.filter((o) => o !== open).slice(0, 3)

  return (
    <div className="grid gap-3">
      {open ? (
        <OfferCard
          offer={open}
          viewer="buyer"
          askingTiyin={item.starting_price}
          onChanged={replace}
        />
      ) : (
        <section
          aria-labelledby="make-offer-heading"
          className="grid gap-4 rounded-lg border border-border bg-card p-4"
        >
          <div className="grid gap-1">
            <h2 id="make-offer-heading" className="font-heading text-base font-semibold text-foreground">
              Narx taklif qilish
            </h2>
            <p className="text-sm text-muted-foreground">
              Sotuvchi narxi — moʻljal. Oʻzingizga mos narxni yozing: sotuvchi qabul
              qiladi, rad etadi yoki qarshi taklif beradi.
            </p>
          </div>
          <OfferForm
            idPrefix={`offer-${item.id}`}
            askingTiyin={item.starting_price}
            submitLabel="Taklif yuborish"
            requireConsent
            needsConsent={consent.needsConsent}
            onSubmit={async (terms) => {
              await consent.ensure()
              const created = await makeOffer(item.id, terms)
              setOffers((prev) => [created, ...(prev ?? [])])
              toast.success("Taklif yuborildi — sotuvchi javobi kutilmoqda.")
            }}
          />
        </section>
      )}
      {past.length > 0 && (
        <details className="rounded-lg border border-border bg-card p-4">
          <summary className="cursor-pointer rounded-sm text-sm font-medium text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
            Oldingi takliflarim ({past.length})
          </summary>
          <div className="mt-3 grid gap-3">
            {past.map((o) => (
              <OfferCard
                key={o.id}
                offer={o}
                viewer="buyer"
                askingTiyin={item.starting_price}
                onChanged={replace}
              />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

/** Sotuvchi paneli: kelgan takliflar — avval javob kutayotganlari. */
function SellerPanel({ item, onItemChanged }: { item: Item; onItemChanged: () => void }) {
  const [offers, setOffers] = React.useState<Offer[] | null>(null)

  const load = React.useCallback(() => {
    listItemOffers(item.id)
      .then(setOffers)
      .catch(() => setOffers([]))
  }, [item.id])

  React.useEffect(() => {
    load()
  }, [load])

  const replace = (updated: Offer) => {
    // Qabul qilish boshqa takliflarni ham yopishi mumkin (zaxira tugasa) — qayta yuklaymiz.
    setOffers((prev) => (prev ?? []).map((o) => (o.id === updated.id ? updated : o)))
    if (updated.status === "accepted") load()
    onItemChanged()
  }

  if (offers === null) return <Skeleton className="h-48 w-full rounded-lg" />

  const rank = (o: Offer) => (o.status !== "pending" ? 2 : o.awaiting === "seller" ? 0 : 1)
  const sorted = [...offers].sort((a, b) => rank(a) - rank(b))
  const waiting = offers.filter((o) => o.status === "pending" && o.awaiting === "seller").length

  return (
    <section aria-labelledby="incoming-heading" className="grid gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="incoming-heading" className="font-heading text-base font-semibold text-foreground">
          Kelgan takliflar
        </h2>
        {waiting > 0 && <Badge variant="warning">{waiting} ta javob kutmoqda</Badge>}
      </div>
      {sorted.length === 0 ? (
        <div className="grid place-items-center gap-2 rounded-lg border border-border bg-card px-6 py-10 text-center">
          <InboxIcon className="size-6 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            Hozircha taklif yoʻq. Xaridorlar narx taklif qilganda shu yerda koʻrasiz.
          </p>
        </div>
      ) : (
        sorted.map((o) => (
          <OfferCard
            key={o.id}
            offer={o}
            viewer="seller"
            askingTiyin={item.starting_price}
            onChanged={replace}
          />
        ))
      )}
    </section>
  )
}

/**
 * Taklifli e'lon sahifasi: narx (mo'ljal), muddat va
 * muzokara paneli (xaridorga — taklif, sotuvchiga — kelgan takliflar).
 */
function OfferListingDetail({ itemId }: { itemId: number }) {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const pathname = usePathname()
  const [item, setItem] = React.useState<Item | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)

  const reload = React.useCallback(() => {
    getItem(itemId)
      .then(setItem)
      .catch(() => {})
  }, [itemId])

  React.useEffect(() => {
    let alive = true
    getItem(itemId)
      .then((it) => alive && setItem(it))
      .catch((e) => alive && setError(e instanceof ApiError ? e.detail : "Mahsulotni yuklab boʻlmadi."))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [itemId])

  if (loading) {
    return (
      <div className="grid gap-8 md:grid-cols-2">
        <Skeleton className="aspect-square w-full rounded-lg" />
        <div className="grid gap-4">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  if (error || !item || item.listing_type !== "offer") {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <PackageIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          {error ?? (item ? "Bu mahsulot auksion orqali sotiladi." : "Mahsulot topilmadi")}
        </p>
        <Button asChild variant="outline" size="sm">
          <Link href="/catalog/hammasi">Katalogga oʻtish</Link>
        </Button>
      </div>
    )
  }

  const isSeller = user?.id === item.seller_id
  const active = item.status === "active"
  const imageUrls = itemImageUrls(item)

  return (
    <div>
      <Breadcrumb className="mb-4">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/">Bosh sahifa</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink href="/catalog/hammasi">Katalog</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="max-sm:hidden" />
          <BreadcrumbItem className="max-sm:hidden">
            <BreadcrumbPage className="line-clamp-1">{item.title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="grid gap-5 md:grid-cols-2 md:gap-10">
        <Gallery title={item.title} images={imageUrls} />

        <div className="grid content-start gap-5">
          <div className="grid gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-foreground md:text-2xl">
              {item.title}
            </h1>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={item.condition === "new" ? "default" : "secondary"}>
                {CONDITION_LABEL[item.condition]}
              </Badge>
              {active && item.listing_ends_at ? (
                <DeadlineBar endsAt={item.listing_ends_at} inline />
              ) : (
                <Badge variant="neutral">{CLOSED_TEXT[item.status] ?? "Yopilgan"}</Badge>
              )}
            </div>
          </div>

          <div className="grid gap-1 rounded-lg border border-border bg-card p-4">
            <span className="text-sm text-muted-foreground">Sotuvchi narxi</span>
            <span className="font-heading text-2xl font-semibold tabular-nums text-foreground">
              {formatTiyin(item.starting_price)}
            </span>
            <span className="text-xs text-muted-foreground">
              Narx majburiy emas — oʻz narxingizni taklif qiling.
            </span>
          </div>

          {status === "authenticated" && isSeller ? (
            <SellerPanel item={item} onItemChanged={reload} />
          ) : !active ? (
            <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
              {CLOSED_TEXT[item.status] ?? "Eʼlon yopilgan."} Yangi taklif qabul qilinmaydi.
            </p>
          ) : status === "authenticated" ? (
            <BuyerPanel item={item} onItemChanged={reload} />
          ) : status === "idle" ? (
            <Skeleton className="h-40 w-full rounded-lg" />
          ) : (
            <div className="grid gap-3 rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">
                Narx taklif qilish uchun hisobingizga kiring.
              </p>
              <Button asChild size="lg">
                <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
              </Button>
            </div>
          )}

          {!isSeller && (
            <MessageSellerButton itemId={item.id} sellerId={item.seller_id} className="w-full" />
          )}
          <AssuranceBlock />
          <div className="flex justify-end">
            <ReportDialog targetType="item" targetId={item.id} />
          </div>
        </div>
      </div>

      <div className="mt-10 grid gap-10 md:mt-12 md:grid-cols-2 md:gap-12">
        <LotSpecs item={item} />
        <section>
          <h2 className="mb-4 text-xl font-semibold text-foreground">Tavsif</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {item.description?.trim() ? item.description : "Sotuvchi tavsif qoʻshmagan."}
          </p>
        </section>
      </div>
    </div>
  )
}

export { OfferListingDetail }
