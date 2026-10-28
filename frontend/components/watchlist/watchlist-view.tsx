"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { HeartIcon, HeartOffIcon, LayoutGridIcon } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import type { Lot } from "@/lib/api/types"
import { getLot } from "@/lib/api/endpoints"
import { listWatchlist, removeFromWatchlist } from "@/lib/api/watchlist"
import { useAuthStore } from "@/lib/store/auth"
import { Button } from "@/components/ui/button"
import { ProductCardSkeleton } from "@/components/ui/skeleton"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from "@/components/ui/empty"
import { LotCard } from "@/components/lot/lot-card"

type LoadState = "loading" | "ready" | "error"

const GRID = "grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"

/** Hali taklif qabul qiladigan auksionlar — qolganlari "Tugaganlar" guruhiga. */
function isOpen(lot: Lot): boolean {
  return lot.auction.status === "active" || lot.auction.status === "scheduled"
}

/** Lot kartasi + ustidagi "kuzatuvdan olib tashlash" tugmasi (kartaning o'zi o'zgarmaydi). */
function WatchedLot({ lot, onRemoved }: { lot: Lot; onRemoved: (auctionId: number) => void }) {
  const [busy, setBusy] = React.useState(false)

  const remove = async () => {
    if (busy) return
    setBusy(true)
    try {
      await removeFromWatchlist(lot.auction.id)
      onRemoved(lot.auction.id)
      toast.success("Kuzatuvdan olib tashlandi.")
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Olib tashlab boʻlmadi. Qayta urinib koʻring.")
      setBusy(false)
    }
  }

  return (
    <div className="relative">
      <LotCard lot={lot} className={isOpen(lot) ? undefined : "opacity-80"} />
      <Button
        variant="outline"
        size="icon-sm"
        loading={busy}
        onClick={remove}
        aria-label={`Kuzatuvdan olib tashlash: ${lot.item.title}`}
        title="Kuzatuvdan olib tashlash"
        className="absolute top-2 right-2 z-10 bg-background shadow-xs"
      >
        {!busy && <HeartOffIcon aria-hidden="true" />}
      </Button>
    </div>
  )
}

function WatchlistSkeleton() {
  return (
    <div className={GRID} aria-busy="true" aria-label="Kuzatuvlar yuklanmoqda">
      {Array.from({ length: 4 }).map((_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  )
}

/**
 * Kuzatuv ro'yxati. Har yozuv uchun lot parallel yuklanadi; bittasi yiqilsa
 * (masalan lot o'chirilgan) qolganlari baribir ko'rsatiladi.
 */
function WatchlistView() {
  const status = useAuthStore((s) => s.status)
  const pathname = usePathname()

  const [lots, setLots] = React.useState<Lot[]>([])
  const [failedCount, setFailedCount] = React.useState(0)
  const [state, setState] = React.useState<LoadState>("loading")
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (status !== "authenticated") return
    let alive = true
    listWatchlist()
      .then(async (entries) => {
        const results = await Promise.allSettled(entries.map((e) => getLot(e.auction_id)))
        if (!alive) return
        const loaded: Lot[] = []
        let failed = 0
        for (const r of results) {
          if (r.status === "fulfilled") loaded.push(r.value)
          else failed += 1
        }
        setLots(loaded)
        setFailedCount(failed)
        setState("ready")
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof ApiError ? e.detail : "Kuzatuvlarni yuklab boʻlmadi.")
        setState("error")
      })
    return () => {
      alive = false
    }
  }, [status])

  const handleRemoved = React.useCallback((auctionId: number) => {
    setLots((prev) => prev.filter((l) => l.auction.id !== auctionId))
  }, [])

  if (status === "idle") return <WatchlistSkeleton />

  if (status === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <HeartIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Kuzatuvlaringizni koʻrish uchun kiring
        </p>
        <Button asChild size="sm">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  if (state === "loading") return <WatchlistSkeleton />

  if (state === "error") {
    return (
      <div className="grid place-items-center gap-2 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <p role="alert" className="text-base font-medium text-foreground">
          {error}
        </p>
      </div>
    )
  }

  const open = lots.filter(isOpen)
  const ended = lots.filter((l) => !isOpen(l))

  if (lots.length === 0) {
    return (
      <Empty className="rounded-lg border border-border bg-card">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <HeartIcon aria-hidden="true" />
          </EmptyMedia>
          <EmptyTitle>Kuzatuvda mahsulot yoʻq</EmptyTitle>
          <EmptyDescription>
            {failedCount > 0
              ? "Kuzatilayotgan mahsulotlarni yuklab boʻlmadi. Keyinroq qayta urinib koʻring."
              : "Mahsulot sahifasida kuzatuvga qoʻshing — tugashiga oz qolganda eslatamiz."}
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild size="lg">
            <Link href="/catalog/hammasi">
              <LayoutGridIcon aria-hidden="true" />
              Katalogga oʻtish
            </Link>
          </Button>
        </EmptyContent>
      </Empty>
    )
  }

  return (
    <div className="grid gap-8">
      {failedCount > 0 && (
        <p className="text-sm text-muted-foreground">
          {failedCount} ta mahsulotni yuklab boʻlmadi — u oʻchirilgan boʻlishi mumkin.
        </p>
      )}

      {open.length > 0 && (
        <section aria-labelledby="watch_open" className="grid gap-4">
          <h2 id="watch_open" className="text-lg font-semibold text-foreground">
            Davom etayotganlar
            <span className="ml-2 text-sm font-normal text-muted-foreground tabular-nums">
              {open.length}
            </span>
          </h2>
          <div className={GRID}>
            {open.map((lot) => (
              <WatchedLot key={lot.auction.id} lot={lot} onRemoved={handleRemoved} />
            ))}
          </div>
        </section>
      )}

      {ended.length > 0 && (
        <section aria-labelledby="watch_ended" className="grid gap-4">
          <h2 id="watch_ended" className="text-lg font-semibold text-foreground">
            Tugaganlar
            <span className="ml-2 text-sm font-normal text-muted-foreground tabular-nums">
              {ended.length}
            </span>
          </h2>
          <div className={GRID}>
            {ended.map((lot) => (
              <WatchedLot key={lot.auction.id} lot={lot} onRemoved={handleRemoved} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

export { WatchlistView }
