"use client"

import * as React from "react"
import { toast } from "sonner"
import { GavelIcon, Undo2Icon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatTiyin } from "@/lib/format"
import { ApiError } from "@/lib/api/client"
import type { Auction, Bid, BidStatus } from "@/lib/api/types"
import { listAuctionBids, retractBid } from "@/lib/api/endpoints"
import { useAuthStore } from "@/lib/store/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatAbsolute, formatRelative } from "@/components/notification/notification-meta"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"
import { RETRACT_CUTOFF_SECONDS } from "@/components/lot/lot-rules"

/** Bekor bo'lgan takliflar — narxga ta'sir qilmaydi, xira ko'rsatiladi. */
const VOID_LABEL: Partial<Record<BidStatus, string>> = {
  retracted: "Qaytarib olingan",
  invalidated: "Bekor qilingan",
  cancelled: "Bekor qilingan",
}

const RETRACTABLE: BidStatus[] = ["valid", "outbid"]

/**
 * Backend ba'zan vaqtni zonasiz qaytaradi (UTC, lekin "Z"siz). Brauzer uni
 * mahalliy vaqt deb o'qimasligi uchun zonani qo'shib qo'yamiz.
 */
function asUtc(iso: string): string {
  return /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : `${iso}Z`
}

type LoadState = "loading" | "ready" | "error"

function BidHistory({
  auction,
  reloadKey,
  onChanged,
}: {
  auction: Auction
  /** O'zgarsa ro'yxat qayta yuklanadi (yangi bid, jonli xabar). */
  reloadKey: number
  /** Taklif qaytarib olingach — auksionni qayta yuklash uchun. */
  onChanged: () => void
}) {
  const user = useAuthStore((s) => s.user)
  const status = useAuthStore((s) => s.status)

  const [bids, setBids] = React.useState<Bid[]>([])
  const [state, setState] = React.useState<LoadState>("loading")
  const [nowMs, setNowMs] = React.useState(0)
  const [ownReload, setOwnReload] = React.useState(0)

  const [target, setTarget] = React.useState<Bid | null>(null)
  const [retracting, setRetracting] = React.useState(false)
  const [retractError, setRetractError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let alive = true
    listAuctionBids(auction.id)
      .then((data) => {
        if (!alive) return
        setBids(data)
        setNowMs(Date.now())
        setState("ready")
      })
      .catch(() => {
        if (alive) setState((s) => (s === "ready" ? s : "error"))
      })
    return () => {
      alive = false
    }
  }, [auction.id, reloadKey, ownReload])

  // Nisbiy vaqt va "qaytarib olish" muddati eskirmasligi uchun soatni yangilaymiz.
  React.useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 15_000)
    return () => window.clearInterval(id)
  }, [])

  const endMs = Date.parse(auction.end_time)
  const canRetractNow =
    status === "authenticated" &&
    user != null &&
    auction.status === "active" &&
    auction.highest_bidder_id !== user.id &&
    nowMs > 0 &&
    endMs - nowMs > RETRACT_CUTOFF_SECONDS * 1000

  const confirmRetract = async () => {
    if (!target) return
    setRetractError(null)
    setRetracting(true)
    try {
      await retractBid(target.id)
      toast.success("Taklifingiz qaytarib olindi")
      setTarget(null)
      // onChanged auksionni ham, reloadKey orqali shu ro'yxatni ham yangilaydi.
      onChanged()
    } catch (e) {
      setRetractError(
        e instanceof ApiError ? e.detail : "Taklifni qaytarib boʻlmadi. Qayta urinib koʻring."
      )
    } finally {
      setRetracting(false)
    }
  }

  return (
    <section aria-labelledby="bid-history-title">
      <h2 id="bid-history-title" className="mb-4 text-xl font-semibold text-foreground">
        Takliflar tarixi
      </h2>

      {state === "loading" ? (
        <div className="grid gap-2" aria-busy="true">
          <Skeleton className="h-14 w-full rounded-lg" />
          <Skeleton className="h-14 w-full rounded-lg" />
          <Skeleton className="h-14 w-full rounded-lg" />
        </div>
      ) : state === "error" ? (
        <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-10 text-center">
          <p className="text-sm text-muted-foreground">Takliflar tarixini yuklab boʻlmadi.</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState("loading")
              setOwnReload((n) => n + 1)
            }}
          >
            Qayta urinish
          </Button>
        </div>
      ) : bids.length === 0 ? (
        <div className="grid place-items-center gap-2 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center">
          <GavelIcon className="size-7 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">Hali takliflar yoʻq.</p>
          <p className="text-sm text-muted-foreground">
            Birinchi taklifni siz bering — boshlangʻich narxdan.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {bids.map((bid) => {
            const mine = user != null && bid.bidder_id === user.id
            const voidLabel = VOID_LABEL[bid.status]
            const time = asUtc(bid.created_at)
            const retractable = mine && canRetractNow && RETRACTABLE.includes(bid.status)
            return (
              <li
                key={bid.id}
                className={cn(
                  "flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3",
                  voidLabel && "text-muted-foreground"
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "truncate text-sm font-medium",
                        voidLabel ? "text-muted-foreground" : "text-foreground"
                      )}
                    >
                      {bid.bidder_display}
                    </span>
                    {mine && <Badge variant="secondary">Siz</Badge>}
                    {voidLabel && <Badge variant="outline">{voidLabel}</Badge>}
                  </div>
                  <time
                    dateTime={time}
                    title={formatAbsolute(time)}
                    className="mt-0.5 block text-xs text-muted-foreground tabular-nums"
                  >
                    {nowMs > 0 ? formatRelative(time, nowMs) : formatAbsolute(time)}
                  </time>
                </div>
                <span
                  className={cn(
                    "text-sm font-semibold tabular-nums",
                    voidLabel ? "text-muted-foreground line-through" : "text-foreground"
                  )}
                >
                  {formatTiyin(bid.amount)}
                </span>
                {retractable && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-foreground"
                    onClick={() => {
                      setRetractError(null)
                      setTarget(bid)
                    }}
                  >
                    <Undo2Icon aria-hidden="true" />
                    Qaytarib olish
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <ConfirmDialog
        open={target !== null}
        onOpenChange={(open) => {
          if (!open) setTarget(null)
        }}
        title="Taklifni qaytarib olasizmi?"
        description={
          target
            ? `${formatTiyin(target.amount)} miqdoridagi taklifingiz bekor qilinadi.`
            : undefined
        }
        confirmLabel="Qaytarib olish"
        variant="destructive"
        loading={retracting}
        error={retractError}
        onConfirm={confirmRetract}
      >
        <p className="text-sm leading-relaxed text-muted-foreground">
          Qaytarib olish tarixda qayd etiladi va joriy narx qolgan takliflar
          asosida qayta hisoblanadi. Bu amalni ortga qaytarib boʻlmaydi.
        </p>
      </ConfirmDialog>
    </section>
  )
}

export { BidHistory }
