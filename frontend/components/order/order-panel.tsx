"use client"

import * as React from "react"
import Link from "next/link"
import { toast } from "sonner"
import { MessageCircleIcon, ShieldAlertIcon } from "lucide-react"

import type { DealCancelReason, Order } from "@/lib/api/types"
import { cancelDeal, confirmDeal, markDealSold } from "@/lib/api/order-flow"
import { ApiError } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"

export type OrderRole = "buyer" | "seller" | "other"

const CANCEL_REASONS: { value: DealCancelReason; label: string }[] = [
  { value: "no_response", label: "Ikkinchi tomon javob bermayapti (48 soatdan keyin)" },
  { value: "changed_mind", label: "Fikrimdan qaytdim" },
  { value: "not_as_described", label: "Mahsulot eʼlondagidek emas" },
  { value: "other", label: "Boshqa sabab" },
]

type Action = "complete" | "confirm" | "cancel"

/**
 * Kelishuv harakatlari (docs/DEALS.md §5). Toʻlov yoʻq: tomonlar oʻzlari uchrashadi.
 * Sotuvchi "Sotildi" belgilaydi, xaridor tasdiqlaydi — ikkalasi boʻlsa kelishuv yakunlanadi.
 * Kontakt kartasi va /deals sahifalari E2 ning keyingi qadamlarida.
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
  const [pending, setPending] = React.useState<Action | null>(null)
  const [cancelOpen, setCancelOpen] = React.useState(false)
  const [reason, setReason] = React.useState<DealCancelReason | "">("")
  const [error, setError] = React.useState<string | null>(null)
  const isOpen = order.status === "agreed"
  const sellerMarked = order.seller_marked_sold_at !== null
  const buyerConfirmed = order.buyer_confirmed_at !== null

  async function run(action: Action) {
    if (action === "cancel" && !reason) {
      setError("Sababni tanlang.")
      return
    }
    setPending(action)
    setError(null)
    try {
      if (action === "complete") await markDealSold(order.id)
      else if (action === "confirm") await confirmDeal(order.id)
      else await cancelDeal(order.id, reason as DealCancelReason)
      toast.success(
        action === "cancel"
          ? "Kelishuv bekor qilindi"
          : action === "complete"
            ? "Sotildi deb belgilandi"
            : "Tasdiqlandi"
      )
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
            ? sellerMarked
              ? "Siz «Sotildi» deb belgiladingiz. Xaridor tasdiqlaydi yoki 72 soatdan keyin kelishuv avtomatik yakunlanadi."
              : "Xaridor bilan uchrashib, mahsulotni topshiring. Hisob-kitob oʻzaro amalga oshiriladi — soʻng «Sotildi» deb belgilang."
            : buyerConfirmed
              ? "Siz tasdiqladingiz. Sotuvchi «Sotildi» deb belgilashi bilan kelishuv yakunlanadi."
              : "Sotuvchi bilan bogʻlanib, uchrashuvni kelishing. Mahsulotni olgach tasdiqlang."}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {order.status === "completed"
            ? "Kelishuv yakunlangan. Endi bir-biringizga sharh qoldirishingiz mumkin."
            : "Kelishuv bekor qilingan."}
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

      {isOpen && role !== "other" && (
        <div className="flex flex-wrap gap-2">
          {role === "seller" && !sellerMarked && (
            <Button
              size="sm"
              loading={pending === "complete"}
              disabled={pending !== null}
              onClick={() => void run("complete")}
            >
              Sotildi
            </Button>
          )}
          {role === "buyer" && !buyerConfirmed && (
            <Button
              size="sm"
              loading={pending === "confirm"}
              disabled={pending !== null}
              onClick={() => void run("confirm")}
            >
              Tasdiqlayman
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={pending !== null}
            onClick={() => {
              setError(null)
              setReason("")
              setCancelOpen(true)
            }}
          >
            Bekor qilish
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/messages">
              <MessageCircleIcon aria-hidden="true" />
              Xabarlar
            </Link>
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Kelishuvni bekor qilasizmi?"
        description="Bekor qilingan kelishuv qayta tiklanmaydi. Bekor qilish aybdor tomonning profilida hisobga olinadi."
        confirmLabel="Bekor qilish"
        cancelLabel="Yoʻq"
        variant="destructive"
        loading={pending === "cancel"}
        error={error}
        onConfirm={() => void run("cancel")}
      >
        <fieldset className="grid gap-3" disabled={pending !== null}>
          <legend className="mb-2 text-sm font-medium text-foreground">Sabab</legend>
          <RadioGroup
            value={reason}
            onValueChange={(v) => {
              setReason(v as DealCancelReason)
              setError(null)
            }}
          >
            {CANCEL_REASONS.map((r) => (
              <div key={r.value} className="flex items-center gap-3">
                <RadioGroupItem value={r.value} id={`deal-cancel-${r.value}`} />
                <Label htmlFor={`deal-cancel-${r.value}`} className="font-normal leading-snug">
                  {r.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </fieldset>
      </ConfirmDialog>
    </section>
  )
}

export { OrderPanel }
