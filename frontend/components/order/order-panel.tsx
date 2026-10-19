"use client"

import * as React from "react"
import Link from "next/link"
import { toast } from "sonner"
import { MessageCircleIcon, ShieldAlertIcon } from "lucide-react"

import type { Order, OrderStatus } from "@/lib/api/types"
import { updateOrderStatus } from "@/lib/api/order-flow"
import { ApiError } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"

export type OrderRole = "buyer" | "seller" | "other"

const OPEN: OrderStatus[] = ["pending_payment", "pickup_pending"]

/**
 * Buyurtma harakatlari (Faza E oʻtish davri). Toʻlov yoʻq: tomonlar oʻzlari
 * uchrashadi, sotuvchi sotuvni yakunlaydi yoki bekor qiladi. E2 da kelishuv
 * sahifasi (kontaktlar, ikki tomonlama tasdiq) bilan almashadi.
 */
function OrderPanel({
  order,
  role,
  onChanged,
}: {
  order: Order
  role: OrderRole
  onChanged: () => void
}) {
  const [pending, setPending] = React.useState<OrderStatus | null>(null)
  const [cancelOpen, setCancelOpen] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const isOpen = OPEN.includes(order.status)

  async function change(status: OrderStatus) {
    setPending(status)
    setError(null)
    try {
      await updateOrderStatus(order.id, status)
      toast.success(status === "completed" ? "Sotuv yakunlandi" : "Buyurtma bekor qilindi")
      setCancelOpen(false)
      onChanged()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Amalni bajarib boʻlmadi.")
    } finally {
      setPending(null)
    }
  }

  return (
    <section className="grid gap-4 rounded-xl border border-border bg-card p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-foreground">Keyingi qadam</h2>

      {isOpen ? (
        <p className="text-sm text-muted-foreground">
          {role === "seller"
            ? "Xaridor bilan uchrashib, mahsulotni topshiring. Hisob-kitob oʻzaro amalga oshiriladi — soʻng sotuvni yakunlang."
            : "Sotuvchi bilan bogʻlanib, uchrashuvni kelishing. Mahsulotni koʻrib tekshirgandan keyingina toʻlang."}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {order.status === "completed"
            ? "Sotuv yakunlangan. Endi bir-biringizga sharh qoldirishingiz mumkin."
            : "Buyurtma bekor qilingan."}
        </p>
      )}

      {isOpen && (
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-foreground">
          <ShieldAlertIcon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          Mahsulotni koʻrmasdan oldindan toʻlamang. Bazart toʻlovda ishtirok etmaydi.
        </p>
      )}

      {error && !cancelOpen && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {isOpen && role === "seller" && (
          <>
            <Button
              size="sm"
              loading={pending === "completed"}
              disabled={pending !== null}
              onClick={() => void change("completed")}
            >
              Sotildi deb belgilash
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending !== null}
              onClick={() => {
                setError(null)
                setCancelOpen(true)
              }}
            >
              Bekor qilish
            </Button>
          </>
        )}
        {isOpen && role !== "other" && (
          <Button asChild size="sm" variant="outline">
            <Link href="/messages">
              <MessageCircleIcon aria-hidden="true" />
              Xabarlar
            </Link>
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Buyurtmani bekor qilasizmi?"
        description="Bekor qilingan buyurtma qayta tiklanmaydi. Taklif orqali sotilgan donalar zaxiraga qaytadi."
        confirmLabel="Bekor qilish"
        cancelLabel="Yoʻq"
        variant="destructive"
        loading={pending === "cancelled"}
        error={error}
        onConfirm={() => void change("cancelled")}
      />
    </section>
  )
}

export { OrderPanel }
