"use client"

import * as React from "react"
import Link from "next/link"
import { RadioIcon, TimerResetIcon, TrendingDownIcon } from "lucide-react"

import type { Lot } from "@/lib/api/types"
import { getLot, getAuction } from "@/lib/api/endpoints"
import { useAuctionSocket, type AuctionSocketMessage } from "@/lib/api/realtime"
import { ApiError } from "@/lib/api/client"
import { itemImageUrls } from "@/lib/item-image"
import { Gallery } from "@/components/product/gallery"
import { AssuranceBlock } from "@/components/product/assurance-block"
import { DeadlineBar } from "@/components/ui/deadline-bar"
import { BidPanel } from "@/components/lot/bid-panel"
import { DescendingPanel } from "@/components/lot/descending-panel"
import { MobileBidBar } from "@/components/lot/mobile-bid-bar"
import { BidHistory } from "@/components/lot/bid-history"
import { LotSpecs, CONDITION_LABEL } from "@/components/lot/lot-specs"
import { WatchButton } from "@/components/lot/watch-button"
import { ReportDialog } from "@/components/complaint/report-dialog"
import { AnimatedSom } from "@/components/animate-ui/animated-number"
import { MessageSellerButton } from "@/components/message/message-seller-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

function LotDetail({ auctionId }: { auctionId: number }) {
  const [lot, setLot] = React.useState<Lot | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  // Bid tarixi qayta yuklanishi uchun hisoblagich (bid, jonli xabar, qaytarib olish).
  const [historyKey, setHistoryKey] = React.useState(0)

  // auctionId o'zgarsa — render vaqtida qayta yuklash holatiga qaytamiz.
  const [dataId, setDataId] = React.useState(auctionId)
  if (dataId !== auctionId) {
    setDataId(auctionId)
    setLot(null)
    setError(null)
    setLoading(true)
  }

  React.useEffect(() => {
    let alive = true
    getLot(auctionId)
      .then((l) => {
        if (alive) {
          setLot(l)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (alive) {
          setError(e instanceof ApiError ? e.detail : "Mahsulotni yuklab boʻlmadi.")
          setLoading(false)
        }
      })
    return () => {
      alive = false
    }
  }, [auctionId])

  const refresh = React.useCallback(() => {
    getAuction(auctionId)
      .then((a) => setLot((prev) => (prev ? { ...prev, auction: a } : prev)))
      .catch(() => {})
    setHistoryKey((k) => k + 1)
  }, [auctionId])

  // Real-time: boshqa kuzatuvchi bid qo'yganda kanaldan yangi narx keladi.
  // Xabar maydonlarini joriy auksionga ustma-ust yozamiz — sahifani qayta
  // yuklamasdan joriy narx / peshqadam / tugash vaqti darhol yangilanadi.
  // Xabarda minimum_next_bid / bid_count yo'q — shu sabab ortidan auksion va
  // bid tarixi qayta yuklanadi (refresh), aks holda minimum eskirib qoladi.
  const handleLive = React.useCallback((msg: AuctionSocketMessage) => {
    setLot((prev) => {
      if (!prev || msg.current_price == null) return prev
      return {
        ...prev,
        auction: {
          ...prev.auction,
          current_price: msg.current_price,
          ...(msg.end_time ? { end_time: msg.end_time } : {}),
          ...(msg.highest_bidder_id !== undefined
            ? { highest_bidder_id: msg.highest_bidder_id }
            : {}),
        },
      }
    })
    if (msg.current_price != null) refresh()
  }, [refresh])

  const { status: liveStatus } = useAuctionSocket(auctionId, handleLive)

  if (loading) {
    return (
      <div className="grid gap-8 md:grid-cols-2">
        <Skeleton className="aspect-square w-full rounded-lg" />
        <div className="grid gap-4">
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  if (error || !lot) {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <p className="text-base font-medium text-foreground">
          {error ?? "Mahsulot topilmadi"}
        </p>
        <Button asChild variant="outline" size="sm">
          <Link href="/catalog/hammasi">Katalogga oʻtish</Link>
        </Button>
      </div>
    )
  }

  const { auction, item } = lot

  // Haqiqiy rasmlar (asosiysi birinchi, to'liq URL) — `lib/item-image`.
  const imageUrls = itemImageUrls(item)

  // Anti-sniping: so'nggi daqiqalardagi taklif tugash vaqtini KEYINGA surgan bo'lsa.
  // Buy-now muddatdan oldin yopganda end_time ertaroq bo'ladi — bu uzaytirish emas.
  const extended =
    auction.original_end_time != null &&
    Date.parse(auction.end_time) > Date.parse(auction.original_end_time)

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
          {/* Mobilda nom pastda sarlavhada bor — non-wrapping bir qator qolsin. */}
          <BreadcrumbSeparator className="max-sm:hidden" />
          <BreadcrumbItem className="max-sm:hidden">
            <BreadcrumbPage className="line-clamp-1">{item.title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {auction.continued_as_auction_id != null && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-brand-subtle px-4 py-3">
          <p className="flex items-center gap-2 text-sm text-foreground">
            <TrendingDownIcon className="size-4 shrink-0 text-brand" aria-hidden="true" />
            Taklif tushmadi — lot pasayuvchi auksionda davom etmoqda.
          </p>
          <Button asChild size="sm">
            <Link href={`/lot/${auction.continued_as_auction_id}`}>Joriy narxni koʻrish</Link>
          </Button>
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2 md:gap-10">
        <Gallery title={item.title} images={imageUrls} />

        <div className="grid gap-5">
          <div className="grid gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-foreground md:text-2xl">
              {item.title}
            </h1>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={item.condition === "new" ? "default" : "secondary"}>
                {CONDITION_LABEL[item.condition]}
              </Badge>
              {auction.status === "active" ? (
                <DeadlineBar endsAt={auction.end_time} inline />
              ) : auction.status === "scheduled" ? (
                <Badge variant="secondary">Rejalashtirilgan</Badge>
              ) : (
                <Badge variant="neutral">Tugagan</Badge>
              )}
            </div>
          </div>

          <div id="price-card" className="grid gap-1 rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-muted-foreground">
                {auction.status === "scheduled"
                  ? "Boshlangʻich narx"
                  : auction.pricing_mode === "descending"
                    ? "Hozirgi narx · pasaymoqda"
                    : "Joriy narx"}
              </span>
              {liveStatus === "open" && (
                <span className="flex items-center gap-1 text-xs font-medium text-success">
                  <RadioIcon className="size-3.5 shrink-0" aria-hidden="true" />
                  jonli
                </span>
              )}
            </div>
            <AnimatedSom
              tiyin={auction.current_price}
              className="text-2xl font-semibold text-foreground"
            />
            {auction.has_reserve && (
              <span
                className={
                  auction.reserve_met
                    ? "text-xs font-medium text-success"
                    : "text-xs text-muted-foreground"
                }
              >
                {auction.reserve_met
                  ? "Zaxira narx qoplandi"
                  : "Zaxira narx hali qoplanmagan"}
              </span>
            )}
            {auction.bid_count > 0 && (
              <span className="text-xs text-muted-foreground tabular-nums">
                {auction.bid_count} ta taklif · {auction.unique_bidder_count} ishtirokchi
              </span>
            )}
            {extended && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <TimerResetIcon className="size-3.5 shrink-0" aria-hidden="true" />
                Soʻnggi daqiqalardagi taklif tufayli muddat uzaytirildi
              </span>
            )}
          </div>

          <div id="bid-panel" className="scroll-mt-24">
            {auction.pricing_mode === "descending" ? (
              <DescendingPanel auction={auction} onRefresh={refresh} />
            ) : (
              <BidPanel auction={auction} onBid={refresh} />
            )}
          </div>
          <div className="flex gap-2 *:flex-1">
            <WatchButton auctionId={auction.id} className="w-full" />
            <MessageSellerButton
              itemId={item.id}
              sellerId={item.seller_id}
              className="w-full"
            />
          </div>
          <AssuranceBlock />
          <div className="flex justify-end">
            <ReportDialog targetType="auction" targetId={auction.id} />
          </div>
        </div>
      </div>

      <div className="mt-10 grid gap-10 md:mt-12 md:grid-cols-2 md:gap-12">
        <LotSpecs item={item} auction={auction} />

        <section>
          <h2 className="mb-4 text-xl font-semibold text-foreground">Tavsif</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {item.description?.trim()
              ? item.description
              : "Sotuvchi tavsif qoʻshmagan."}
          </p>
        </section>
      </div>

      <div className="mt-10 md:mt-12">
        {auction.pricing_mode !== "descending" && (
          <BidHistory auction={auction} reloadKey={historyKey} onChanged={refresh} />
        )}
      </div>

      <MobileBidBar auction={auction} targetId="bid-panel" priceId="price-card" />
      {/* Yopishqoq panel ostida kontent qolib ketmasin. */}
      {auction.status === "active" && <div className="h-16 md:hidden" aria-hidden="true" />}
    </div>
  )
}

export { LotDetail }
