"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { formatTiyin } from "@/lib/format"
import type { Order } from "@/lib/api/types"
import {
  getOrder,
  getOrderPayment,
  getHandover,
  type Payment,
  type Handover,
} from "@/lib/api/order-flow"
import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
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
import {
  OrderStatusBadge,
  PaymentStatusBadge,
} from "@/components/order/order-status"
import { EscrowPanel, type OrderRole } from "@/components/order/escrow-panel"

type Bundle = {
  order: Order
  payment: Payment | null
  handover: Handover | null
}

async function loadBundle(orderId: number): Promise<Bundle> {
  // Order MAJBURIY (egalik/mavjudlik shu yerda tekshiriladi); payment/handover
  // hali boʻlmasligi mumkin -> order-flow ichida 404 null'ga aylantiriladi.
  const order = await getOrder(orderId)
  const [payment, handover] = await Promise.all([
    getOrderPayment(orderId),
    getHandover(orderId),
  ])
  return { order, payment, handover }
}

function OrderDetail({ orderId }: { orderId: number }) {
  const authStatus = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const pathname = usePathname()

  const [data, setData] = React.useState<Bundle | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  // Har harakatdan keyin qayta yuklash uchun trigger (increment). Qayta yuklashda
  // mavjud maʼlumot ekranda qoladi (skelet chaqnamaydi) — yangi kelganda yangilanadi.
  const [reloadTick, setReloadTick] = React.useState(0)

  React.useEffect(() => {
    if (authStatus !== "authenticated") return
    let alive = true
    // Sinxron setState effekt tanasida chaqirilmaydi — faqat async .then/.catch da.
    loadBundle(orderId)
      .then((b) => {
        if (!alive) return
        setData(b)
        setError(null)
      })
      .catch((e) => {
        if (!alive) return
        setError(
          e instanceof ApiError ? e.detail : "Buyurtmani yuklab boʻlmadi."
        )
      })
    return () => {
      alive = false
    }
  }, [orderId, authStatus, reloadTick])

  const refetch = React.useCallback(() => {
    setReloadTick((t) => t + 1)
  }, [])

  if (authStatus === "idle") return <DetailSkeleton />

  if (authStatus === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-xl border border-border bg-card px-6 py-16 text-center">
        <p className="text-base font-medium text-foreground">
          Buyurtmani koʻrish uchun hisobingizga kiring.
        </p>
        <Button asChild>
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  // Hali hech narsa yuklanmagan (va xato yoʻq) -> skelet.
  if (!data && !error) return <DetailSkeleton />

  if (error || !data) {
    return (
      <div className="grid place-items-center gap-3 rounded-xl border border-border bg-card px-6 py-16 text-center">
        <p className="text-base font-medium text-foreground">
          {error ?? "Buyurtma topilmadi"}
        </p>
        <Button asChild variant="outline" size="sm">
          <Link href="/orders">Buyurtmalarga qaytish</Link>
        </Button>
      </div>
    )
  }

  const { order, payment, handover } = data
  const role: OrderRole =
    user?.id === order.buyer_id
      ? "buyer"
      : user?.id === order.seller_id
        ? "seller"
        : "other"

  return (
    <div className="grid gap-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/orders">Buyurtmalarim</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Buyurtma #{order.id}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Buyurtma #{order.id}
        </h1>
        <OrderStatusBadge status={order.status} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem] lg:items-start">
        <EscrowPanel
          order={order}
          payment={payment}
          handover={handover}
          role={role}
          onChanged={refetch}
        />

        <aside className="grid gap-3 rounded-xl border border-border bg-card p-4">
          <h2 className="text-sm font-semibold text-foreground">Xulosa</h2>
          <dl className="grid gap-2 text-sm">
            <Row label="Mahsulot">#{order.item_id}</Row>
            <Row label="Rolingiz">
              {role === "buyer"
                ? "Xaridor"
                : role === "seller"
                  ? "Sotuvchi"
                  : "Kuzatuvchi"}
            </Row>
            {order.quantity > 1 && (
              <Row label="Miqdor">
                <span className="tabular-nums">
                  {order.quantity} dona x {formatTiyin(order.unit_price)}
                </span>
              </Row>
            )}
            <Row label="Yakuniy narx">
              <span className="tabular-nums">{formatTiyin(order.final_price)}</span>
            </Row>
            {payment && (
              <>
                <Row label="Mukofot (8%)">
                  <span className="tabular-nums">{formatTiyin(payment.premium)}</span>
                </Row>
                <Row label="Jami (escrow)">
                  <span className="font-semibold tabular-nums text-foreground">
                    {formatTiyin(payment.total)}
                  </span>
                </Row>
              </>
            )}
            <div className="flex items-center justify-between gap-3 pt-1">
              <dt className="text-muted-foreground">Toʻlov holati</dt>
              <dd>
                {payment ? (
                  <PaymentStatusBadge status={payment.status} />
                ) : (
                  <span className="text-sm text-muted-foreground">Yaratilmagan</span>
                )}
              </dd>
            </div>
          </dl>
        </aside>
      </div>

      {/* Nizo / sharh — buyurtma bosqichiga qarab. */}
      {(order.status === "pickup_pending" || order.status === "paid") && (
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href={`/orders/${order.id}/dispute`}>Nizo ochish</Link>
          </Button>
        </div>
      )}
      {order.status === "completed" && (
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link href={`/orders/${order.id}/review`}>Sharh qoldirish</Link>
          </Button>
        </div>
      )}
    </div>
  )
}

function Row({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{children}</dd>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="grid gap-6">
      <Skeleton className="h-5 w-48" />
      <Skeleton className="h-8 w-56" />
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <Skeleton className="h-56 w-full rounded-xl" />
        <Skeleton className="h-56 w-full rounded-xl" />
      </div>
    </div>
  )
}

export { OrderDetail }
