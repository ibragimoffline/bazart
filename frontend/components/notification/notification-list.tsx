"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BellIcon, CheckCheckIcon } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from "@/lib/api/engagement"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Spinner } from "@/components/ui/spinner"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty"
import {
  formatAbsolute,
  formatRelative,
  notificationMeta,
} from "@/components/notification/notification-meta"

type LoadState = "loading" | "ready" | "error"

/** Payload'dagi musbat butun id (raqam yoki raqamli satr). */
function payloadId(payload: Notification["payload"], key: string): number | null {
  const raw = payload?.[key]
  const n = typeof raw === "number" ? raw : typeof raw === "string" ? Number(raw) : NaN
  return Number.isInteger(n) && n > 0 ? n : null
}

/**
 * Bildirishnoma qayerga olib boradi. Buyurtma konteksti aniqroq — order_id
 * bo'lsa u ustun; aks holda lot sahifasi.
 */
function notificationHref(item: Notification): string | null {
  const orderId = payloadId(item.payload, "order_id")
  if (orderId !== null) return `/orders/${orderId}`
  const offerId = payloadId(item.payload, "offer_id")
  if (offerId !== null) return `/offers?focus=${offerId}`
  const auctionId = payloadId(item.payload, "auction_id")
  if (auctionId !== null) return `/lot/${auctionId}`
  return null
}

/** Bitta bildirishnoma qatori. */
function NotificationRow({
  item,
  nowMs,
  onMarkRead,
}: {
  item: Notification
  nowMs: number
  onMarkRead: (id: number) => void
}) {
  const { label, Icon, tone } = notificationMeta(item.type)
  const [busy, setBusy] = React.useState(false)
  const href = notificationHref(item)

  const handleMark = () => {
    if (busy || item.is_read) return
    setBusy(true)
    markNotificationRead(item.id)
      .then(() => onMarkRead(item.id))
      .catch((e) => {
        toast.error(
          e instanceof ApiError ? e.detail : "Belgilab boʻlmadi. Qayta urinib koʻring."
        )
      })
      .finally(() => setBusy(false))
  }

  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-xl border border-border p-4 transition-colors",
        item.is_read ? "bg-card" : "bg-muted/40"
      )}
    >
      <span
        className={cn(
          "mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-background",
          tone
        )}
        aria-hidden="true"
      >
        <Icon className="size-5" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-foreground">
            {href ? (
              <Link
                href={href}
                onClick={() => {
                  // Ochilgan bildirishnoma o'qilgan hisoblanadi (fon rejimida).
                  if (!item.is_read) {
                    markNotificationRead(item.id)
                      .then(() => onMarkRead(item.id))
                      .catch(() => {})
                  }
                }}
                className="rounded-sm outline-none transition-colors hover:text-primary underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 underline-offset-4"
              >
                {item.title || label}
              </Link>
            ) : (
              item.title || label
            )}
          </p>
          {!item.is_read && (
            <span
              className="size-2 shrink-0 rounded-full bg-primary"
              aria-label="Oʻqilmagan"
            />
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
        {item.body && (
          <p className="mt-1.5 text-sm text-muted-foreground">{item.body}</p>
        )}
        <time
          dateTime={item.created_at}
          title={formatAbsolute(item.created_at)}
          className="mt-1.5 block text-xs text-muted-foreground tabular-nums"
        >
          {formatRelative(item.created_at, nowMs)}
        </time>
      </div>

      {!item.is_read && (
        <Button
          variant="ghost"
          size="sm"
          loading={busy}
          onClick={handleMark}
          className="shrink-0"
        >
          Oʻqilgan
        </Button>
      )}
    </li>
  )
}

function NotificationList() {
  const status = useAuthStore((s) => s.status)
  const pathname = usePathname()

  const [items, setItems] = React.useState<Notification[]>([])
  const [state, setState] = React.useState<LoadState>("loading")
  const [error, setError] = React.useState<string | null>(null)
  const [nowMs, setNowMs] = React.useState(0)
  const [markingAll, setMarkingAll] = React.useState(false)
  // "Faqat oʻqilmaganlar" filtri — backend `?only_unread=true` ni qoʻllaydi.
  const [onlyUnread, setOnlyUnread] = React.useState(false)
  const [refetching, setRefetching] = React.useState(false)

  React.useEffect(() => {
    if (status !== "authenticated") return
    let alive = true
    listNotifications(onlyUnread)
      .then((data) => {
        if (!alive) return
        setItems(data)
        setNowMs(Date.now())
        setState("ready")
      })
      .catch((e) => {
        if (!alive) return
        setError(
          e instanceof ApiError ? e.detail : "Bildirishnomalarni yuklab boʻlmadi."
        )
        setState("error")
      })
      .finally(() => {
        if (alive) setRefetching(false)
      })
    return () => {
      alive = false
    }
  }, [status, onlyUnread])

  const markOneReadLocal = React.useCallback((id: number) => {
    setItems((prev) =>
      prev.map((n) =>
        n.id === id ? { ...n, is_read: true, read_at: n.read_at } : n
      )
    )
  }, [])

  const handleMarkAll = () => {
    if (markingAll) return
    setMarkingAll(true)
    markAllNotificationsRead()
      .then((count) => {
        setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
        toast.success(
          count > 0
            ? `${count} ta bildirishnoma oʻqilgan deb belgilandi`
            : "Barcha bildirishnomalar allaqachon oʻqilgan"
        )
      })
      .catch((e) => {
        toast.error(
          e instanceof ApiError ? e.detail : "Belgilab boʻlmadi. Qayta urinib koʻring."
        )
      })
      .finally(() => setMarkingAll(false))
  }

  // --- Auth gate -------------------------------------------------------
  if (status === "idle") {
    return (
      <div className="grid gap-3">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>
    )
  }

  if (status === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-xl border border-border bg-card px-6 py-16 text-center">
        <BellIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Bildirishnomalarni koʻrish uchun kiring
        </p>
        <Button asChild size="sm">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  const hasUnread = items.some((n) => !n.is_read)

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">Bildirishnomalar</h1>
          {refetching && <Spinner className="text-muted-foreground" />}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Switch
              id="only-unread"
              checked={onlyUnread}
              onCheckedChange={(checked) => {
                setRefetching(true)
                setOnlyUnread(checked)
              }}
            />
            <label
              htmlFor="only-unread"
              className="text-sm text-muted-foreground select-none"
            >
              Faqat oʻqilmaganlar
            </label>
          </div>
          {state === "ready" && items.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleMarkAll}
              loading={markingAll}
              disabled={!hasUnread}
            >
              <CheckCheckIcon aria-hidden="true" />
              Hammasini oʻqilgan deb belgilash
            </Button>
          )}
        </div>
      </div>

      {state === "loading" && (
        <div className="grid gap-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      )}

      {state === "error" && (
        <div className="grid place-items-center gap-2 rounded-xl border border-border bg-card px-6 py-16 text-center">
          <p className="text-base font-medium text-foreground">{error}</p>
        </div>
      )}

      {state === "ready" && items.length === 0 && (
        <Empty className="rounded-xl border border-border bg-card">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <BellIcon aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>
              {onlyUnread ? "Oʻqilmagan bildirishnoma yoʻq" : "Hozircha bildirishnoma yoʻq"}
            </EmptyTitle>
            <EmptyDescription>
              Taklifingiz ortda qolsa, auksionda gʻalaba qozonsangiz yoki taklifingizga
              javob kelsa — shu yerda koʻrasiz.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {state === "ready" && items.length > 0 && (
        <ul className="grid gap-3">
          {items.map((n) => (
            <NotificationRow
              key={n.id}
              item={n}
              nowMs={nowMs}
              onMarkRead={markOneReadLocal}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

export { NotificationList }
