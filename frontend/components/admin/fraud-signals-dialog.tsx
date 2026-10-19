"use client"

import * as React from "react"
import Link from "next/link"
import { InfoIcon, ShieldCheckIcon } from "lucide-react"

import type { User } from "@/lib/api/types"
import { ApiError } from "@/lib/api/client"
import { fraudSignals, type FraudSignals } from "@/lib/api/admin"
import type { BadgeVariant } from "@/components/admin/labels"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

/**
 * Backend (`fraud_service._risk_flags`) qaytaradigan bayroqlar. Noma'lum bayroq
 * xom holida ko'rsatiladi — backend yangi signal qo'shsa UI jim yo'qotmaydi.
 */
const FLAG_COPY: Record<string, { label: string; variant: BadgeVariant }> = {
  shared_device: { label: "Umumiy qurilma", variant: "warning" },
  shared_ip: { label: "Umumiy IP", variant: "warning" },
  shill_ip_overlap: { label: "Sotuvchi bilan IP/qurilma kesishuvi", variant: "sale" },
  high_velocity: { label: "Juda tez takliflar", variant: "warning" },
}

const linkClass =
  "rounded-sm font-medium tabular-nums text-primary underline-offset-4 outline-none transition-colors underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50"

function Metric({ value, label, hint }: { value: number; label: string; hint: string }) {
  return (
    <div className="grid gap-0.5 rounded-lg border border-border p-3">
      <span className="text-lg font-semibold tabular-nums text-foreground">{value}</span>
      <span className="text-sm font-medium text-foreground">{label}</span>
      <span className="text-xs text-muted-foreground">{hint}</span>
    </div>
  )
}

function UserIdList({ title, hint, ids }: { title: string; hint: string; ids: number[] }) {
  return (
    <div className="grid gap-1">
      <span className="text-sm font-medium text-foreground">
        {title} <span className="tabular-nums text-muted-foreground">({ids.length})</span>
      </span>
      <span className="text-xs text-muted-foreground">{hint}</span>
      {ids.length === 0 ? (
        <span className="text-sm text-muted-foreground">Yoʻq</span>
      ) : (
        <ul className="flex flex-wrap gap-x-3 gap-y-1">
          {ids.map((id) => (
            <li key={id}>
              <Link href={`/users/${id}`} className={linkClass}>
                #{id}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function SignalsBody({ signals }: { signals: FraudSignals }) {
  return (
    <div className="grid gap-4">
      <div className="grid gap-2">
        <span className="text-sm font-medium text-foreground">Xavf bayroqlari</span>
        {signals.risk_flags.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-border p-3 text-sm text-muted-foreground">
            <ShieldCheckIcon className="size-4 text-success" aria-hidden="true" />
            Signal topilmadi
          </div>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {signals.risk_flags.map((flag) => {
              const copy = FLAG_COPY[flag]
              return (
                <li key={flag}>
                  <Badge variant={copy?.variant ?? "warning"}>{copy?.label ?? flag}</Badge>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Metric
          value={signals.bid_count}
          label="Takliflar"
          hint="Jami qoʻyilgan takliflar soni"
        />
        <Metric
          value={signals.distinct_auctions}
          label="Auksionlar"
          hint="Nechta turli auksionda qatnashgan"
        />
        <Metric
          value={signals.rapid_bid_max_per_10s}
          label="10 soniyada eng koʻp"
          hint="Bir 10 soniyalik oynadagi maksimal takliflar (3+ — shubhali)"
        />
        <Metric
          value={signals.self_auction_ip_overlap}
          label="Sotuvchi bilan kesishuv"
          hint="Sotuvchisi bilan bir IP/qurilmani ulashgan auksionlar soni"
        />
      </div>

      <UserIdList
        title="Umumiy qurilma"
        hint="Xuddi shu qurilmadan taklif qoʻygan boshqa akkauntlar"
        ids={signals.shared_device_user_ids}
      />
      <UserIdList
        title="Umumiy IP"
        hint="Xuddi shu IP manzildan taklif qoʻygan boshqa akkauntlar (NAT tufayli 2+ da bayroq)"
        ids={signals.shared_ip_user_ids}
      />
    </div>
  )
}

/**
 * Foydalanuvchi firibgarlik signallari oynasi. Ma'lumot har ochilganda qayta
 * yuklanadi — signallar takliflar bilan o'zgarib turadi, keshlash chalg'itadi.
 */
function FraudSignalsDialog({
  user,
  onClose,
}: {
  user: User | null
  onClose: () => void
}) {
  const [signals, setSignals] = React.useState<FraudSignals | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const userId = user?.id

  React.useEffect(() => {
    if (userId === undefined) return
    let alive = true
    // Oldingi foydalanuvchi ma'lumoti ko'rinmasligi uchun — mikrotaskda tozalash.
    Promise.resolve().then(() => {
      if (!alive) return
      setSignals(null)
      setError(null)
    })
    fraudSignals(userId)
      .then((result) => {
        if (alive) setSignals(result)
      })
      .catch((e) => {
        if (alive) setError(e instanceof ApiError ? e.detail : "Signallarni yuklab boʻlmadi.")
      })
    return () => {
      alive = false
    }
  }, [userId])

  const loading = user !== null && signals?.user_id !== user.id && !error

  return (
    <Dialog open={user !== null} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="sm:max-w-lg">
        {user && (
          <>
            <DialogHeader>
              <DialogTitle>Firibgarlik signallari</DialogTitle>
              <DialogDescription>
                {user.full_name || user.email} · #{user.id}
              </DialogDescription>
            </DialogHeader>

            <p className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm text-foreground">
              <InfoIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              Signal — hukm emas, qoʻlda tekshirish uchun.
            </p>

            {error ? (
              <p role="alert" className="text-sm font-medium text-destructive">
                {error}
              </p>
            ) : loading || !signals ? (
              <div className="grid gap-3" aria-busy="true">
                <Skeleton className="h-6 w-40" />
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-20" />
                  ))}
                </div>
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <SignalsBody signals={signals} />
            )}

            <DialogFooter>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/admin/bids?bidder_id=${user.id}`}>Takliflarini koʻrish</Link>
              </Button>
              <Button variant="ghost" size="sm" onClick={onClose}>
                Yopish
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export { FraudSignalsDialog }
