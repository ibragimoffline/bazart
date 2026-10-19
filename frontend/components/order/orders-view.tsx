"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { PackageIcon, ChevronRightIcon } from "lucide-react"

import { formatTiyin } from "@/lib/format"
import type { Order } from "@/lib/api/types"
import { buyerOrders, sellerOrders } from "@/lib/api/order-flow"
import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { OrderStatusBadge } from "@/components/order/order-status"

type Tab = "buyer" | "seller"

function OrdersView() {
  const authStatus = useAuthStore((s) => s.status)
  const pathname = usePathname()

  const [tab, setTab] = React.useState<Tab>("buyer")
  const [orders, setOrders] = React.useState<Order[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  // Faol tab + auth holati kaliti. Yuklanish holati shu kalitni oxirgi
  // muvaffaqiyatli/xatolik bilan tugagan kalit bilan solishtirib chiqariladi —
  // shu bois effekt tanasida sinxron setState chaqirilmaydi (async .then/.catch da).
  const key = `${tab}:${authStatus}`
  const [loadedKey, setLoadedKey] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (authStatus !== "authenticated") return
    let alive = true
    const fetcher = tab === "buyer" ? buyerOrders : sellerOrders
    fetcher()
      .then((data) => {
        if (!alive) return
        setOrders(data)
        setError(null)
        setLoadedKey(key)
      })
      .catch((e) => {
        if (!alive) return
        setError(
          e instanceof ApiError ? e.detail : "Buyurtmalarni yuklab boʻlmadi."
        )
        setLoadedKey(key)
      })
    return () => {
      alive = false
    }
  }, [tab, authStatus, key])

  if (authStatus === "idle") {
    return <OrdersSkeleton />
  }

  if (authStatus === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-xl border border-border bg-card px-6 py-16 text-center">
        <PackageIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Buyurtmalaringizni koʻrish uchun hisobingizga kiring.
        </p>
        <Button asChild>
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  const showLoading = loadedKey !== key

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">
          Buyurtmalarim
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Xaridlaringiz va sotuvlaringiz — escrow toʻlov va topshirish holati.
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Buyurtma turlari"
        className="inline-flex w-fit gap-1 rounded-lg border border-border bg-muted/40 p-1"
      >
        <TabButton active={tab === "buyer"} onClick={() => setTab("buyer")}>
          Xaridlarim
        </TabButton>
        <TabButton active={tab === "seller"} onClick={() => setTab("seller")}>
          Sotuvlarim
        </TabButton>
      </div>

      {showLoading ? (
        <OrdersSkeleton />
      ) : error ? (
        <div className="rounded-xl border border-border bg-card px-6 py-12 text-center">
          <p className="text-sm font-medium text-destructive">{error}</p>
        </div>
      ) : orders && orders.length > 0 ? (
        <ul className="grid gap-3">
          {orders.map((order) => (
            <li key={order.id}>
              <OrderRow order={order} role={tab} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="grid place-items-center gap-2 rounded-xl border border-dashed border-border bg-card px-6 py-16 text-center">
          <PackageIcon className="size-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-base font-medium text-foreground">
            {tab === "buyer"
              ? "Hali xaridlaringiz yoʻq."
              : "Hali sotuvlaringiz yoʻq."}
          </p>
          <p className="text-sm text-muted-foreground">
            {tab === "buyer"
              ? "Auksionda gʻolib chiqsangiz buyurtma shu yerda paydo boʻladi."
              : "Mahsulotingiz sotilganda buyurtma shu yerda paydo boʻladi."}
          </p>
        </div>
      )}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={
        "rounded-md px-4 py-1.5 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 " +
        (active
          ? "bg-background text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground")
      }
    >
      {children}
    </button>
  )
}

function OrderRow({ order, role }: { order: Order; role: Tab }) {
  return (
    <Link
      href={`/orders/${order.id}`}
      className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 transition-colors outline-none hover:bg-muted/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="grid size-11 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
        <PackageIcon className="size-5" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">
            Buyurtma #{order.id}
          </span>
          <OrderStatusBadge status={order.status} />
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {role === "buyer" ? "Mahsulot" : "Sotilgan mahsulot"} #{order.item_id} ·{" "}
          {order.quantity > 1 && <span className="tabular-nums">{order.quantity} dona · </span>}
          <span className="font-medium tabular-nums text-foreground">
            {formatTiyin(order.final_price)}
          </span>
        </p>
      </div>
      <ChevronRightIcon
        className="size-5 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
    </Link>
  )
}

function OrdersSkeleton() {
  return (
    <div className="grid gap-3">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-[76px] w-full rounded-xl" />
      ))}
    </div>
  )
}

export { OrdersView }
