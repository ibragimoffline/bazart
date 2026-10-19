"use client"

import * as React from "react"
import Link from "next/link"
import { toast } from "sonner"
import {
  CheckIcon,
  ChevronDownIcon,
  HistoryIcon,
  MessageSquareReplyIcon,
  ReceiptTextIcon,
  TimerIcon,
  Undo2Icon,
  XIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { formatTiyin } from "@/lib/format"
import {
  acceptOffer,
  counterOffer,
  rejectOffer,
  withdrawOffer,
  type Offer,
  type OfferParty,
} from "@/lib/api/offers"
import { ApiError } from "@/lib/api/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"
import { OfferForm } from "@/components/offer/offer-form"
import {
  OFFER_STATUS_LABEL,
  OFFER_STATUS_VARIANT,
  eventText,
  termsText,
  timeLeftText,
  turnOf,
  useNow,
  useOfferConsent,
} from "@/components/offer/offer-meta"

const timeFormatter = new Intl.DateTimeFormat("uz-UZ", {
  timeZone: "Asia/Tashkent",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
})

type Pending = "accept" | "reject" | "withdraw" | null

/**
 * Bitta taklif — ishtirokchi nuqtai nazaridan. Navbat kimda bo'lsa, o'sha qabul
 * qiladi / qarshi taklif beradi; sotuvchi istalgan payt rad eta oladi, xaridor esa
 * o'z taklifini qaytarib oladi. Qabul qilinsa — buyurtmaga havola.
 */
function OfferCard({
  offer,
  viewer,
  askingTiyin,
  maxQuantity,
  showItem = false,
  highlight = false,
  onChanged,
}: {
  offer: Offer
  viewer: OfferParty
  /** Sotuvchining mo'ljal narxi (qarshi taklif shaklida solishtirish uchun). */
  askingTiyin: string
  /** Hozir mavjud zaxira — qarshi taklif shu bilan cheklanadi. */
  maxQuantity: number
  showItem?: boolean
  highlight?: boolean
  onChanged: (offer: Offer) => void
}) {
  const now = useNow()
  const [countering, setCountering] = React.useState(false)
  const [pending, setPending] = React.useState<Pending>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [agreed, setAgreed] = React.useState(false)
  const [historyOpen, setHistoryOpen] = React.useState(false)
  const ref = React.useRef<HTMLElement>(null)

  const turn = turnOf(offer, viewer)
  const isOpen = offer.status === "pending"
  // Xaridor qarshi taklifni qabul qilsa ham bitim tuziladi — rozilik shart.
  const consent = useOfferConsent(viewer === "buyer" && isOpen)
  const left = now ? timeLeftText(offer.expires_at, now) : null

  React.useEffect(() => {
    if (highlight) ref.current?.scrollIntoView({ block: "center" })
  }, [highlight])

  const run = async (action: Exclude<Pending, null>) => {
    setBusy(true)
    setError(null)
    try {
      if (action === "accept" && viewer === "buyer") await consent.ensure()
      const updated =
        action === "accept"
          ? await acceptOffer(offer.id)
          : action === "reject"
            ? await rejectOffer(offer.id)
            : await withdrawOffer(offer.id)
      setPending(null)
      onChanged(updated)
      toast.success(
        action === "accept"
          ? "Bitim tuzildi — buyurtma yaratildi."
          : action === "reject"
            ? "Taklif rad etildi."
            : "Taklif qaytarib olindi."
      )
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Amalni bajarib boʻlmadi.")
    } finally {
      setBusy(false)
    }
  }

  const statusLabel =
    turn === "me" ? "Javobingiz kutilmoqda" : OFFER_STATUS_LABEL[offer.status]
  const statusVariant = turn === "me" ? "warning" : OFFER_STATUS_VARIANT[offer.status]
  const who = viewer === "seller" ? offer.buyer_display : "Sizning taklifingiz"

  return (
    <article
      ref={ref}
      className={cn(
        "grid gap-3 rounded-xl border bg-card p-4",
        highlight ? "border-primary" : "border-border"
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="grid min-w-0 gap-0.5">
          {showItem && offer.item && (
            <Link
              href={`/item/${offer.item_id}`}
              className="truncate rounded-sm text-sm font-semibold text-foreground underline decoration-foreground/30 underline-offset-4 outline-none hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {offer.item.title}
            </Link>
          )}
          <span className="text-sm text-muted-foreground">{who}</span>
        </div>
        <Badge variant={statusVariant}>{statusLabel}</Badge>
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-sm text-foreground tabular-nums">
          {termsText(offer.quantity, offer.unit_price)}
        </span>
        <span className="font-heading text-lg font-semibold tabular-nums text-foreground">
          {formatTiyin(offer.total_price)}
        </span>
      </div>

      {isOpen && left && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <TimerIcon className="size-3.5 shrink-0" aria-hidden="true" />
          {turn === "me"
            ? `Javob bering: ${left} ichida, aks holda taklif yopiladi`
            : `Javob ${left} ichida kutiladi`}
        </p>
      )}

      {error && !pending && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}

      {isOpen && !countering && (
        <div className="flex flex-wrap gap-2">
          {turn === "me" && (
            <>
              <Button size="sm" onClick={() => { setError(null); setAgreed(false); setPending("accept") }}>
                <CheckIcon aria-hidden="true" />
                Qabul qilish
              </Button>
              <Button size="sm" variant="outline" onClick={() => setCountering(true)}>
                <MessageSquareReplyIcon aria-hidden="true" />
                Qarshi taklif
              </Button>
            </>
          )}
          {(viewer === "seller" || turn === "me") && (
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive hover:text-destructive"
              onClick={() => { setError(null); setPending("reject") }}
            >
              <XIcon aria-hidden="true" />
              Rad etish
            </Button>
          )}
          {viewer === "buyer" && (
            <Button size="sm" variant="ghost" onClick={() => { setError(null); setPending("withdraw") }}>
              <Undo2Icon aria-hidden="true" />
              Qaytarib olish
            </Button>
          )}
        </div>
      )}

      {countering && (
        <div className="rounded-lg border border-border p-3">
          <OfferForm
            idPrefix={`counter-${offer.id}`}
            maxQuantity={Math.max(1, maxQuantity)}
            askingTiyin={askingTiyin}
            initialQuantity={offer.quantity}
            initialUnitTiyin={offer.unit_price}
            submitLabel="Qarshi taklif yuborish"
            onCancel={() => setCountering(false)}
            onSubmit={async (terms) => {
              const updated = await counterOffer(offer.id, terms)
              setCountering(false)
              onChanged(updated)
              toast.success("Qarshi taklif yuborildi.")
            }}
          />
        </div>
      )}

      {offer.status === "accepted" && offer.order_id != null && (
        <Button asChild size="sm" variant="outline" className="w-fit">
          <Link href={`/orders/${offer.order_id}`}>
            <ReceiptTextIcon aria-hidden="true" />
            Buyurtmaga oʻtish
          </Link>
        </Button>
      )}

      {offer.events.length > 0 && (
        <div>
          <button
            type="button"
            aria-expanded={historyOpen}
            onClick={() => setHistoryOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-sm text-xs font-medium text-muted-foreground outline-none transition-colors duration-150 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <HistoryIcon className="size-3.5" aria-hidden="true" />
            Muzokara tarixi ({offer.events.length})
            <ChevronDownIcon
              className={cn("size-3.5 transition-transform duration-150", historyOpen && "rotate-180")}
              aria-hidden="true"
            />
          </button>
          {historyOpen && (
            <ol className="mt-2 grid gap-2 border-l border-border pl-3">
              {offer.events.map((e) => (
                <li key={e.id} className="grid gap-0.5 text-xs">
                  <span className="text-foreground">{eventText(e)}</span>
                  {e.message && <span className="text-muted-foreground">«{e.message}»</span>}
                  <time className="text-muted-foreground" dateTime={e.created_at}>
                    {timeFormatter.format(new Date(e.created_at))}
                  </time>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      <ConfirmDialog
        open={pending === "accept"}
        onOpenChange={(open) => !open && setPending(null)}
        title="Shartlarni qabul qilasizmi?"
        description={`${termsText(offer.quantity, offer.unit_price)} — jami ${formatTiyin(offer.total_price)}. Bitim tuziladi va buyurtma yaratiladi.`}
        confirmLabel="Ha, qabul qilaman"
        cancelLabel="Yoʻq"
        loading={busy}
        error={error}
        onConfirm={() => {
          if (viewer === "buyer" && consent.needsConsent && !agreed) {
            setError("Davom etish uchun shartlarni qabul qiling.")
            return
          }
          void run("accept")
        }}
      >
        {viewer === "buyer" && (
          <div className="grid gap-2 text-sm text-muted-foreground">
            <p>Toʻlovda xaridor komissiyasi (8%) qoʻshiladi; pul escrow orqali himoyalanadi.</p>
            {consent.needsConsent && (
              <div className="flex items-start gap-2">
                <Checkbox
                  id={`accept-consent-${offer.id}`}
                  checked={agreed}
                  disabled={busy}
                  onCheckedChange={(v) => setAgreed(v === true)}
                  className="mt-0.5"
                  aria-required="true"
                />
                <label htmlFor={`accept-consent-${offer.id}`} className="text-foreground">
                  Savdo qoidalari va ommaviy ofertani qabul qilaman
                </label>
              </div>
            )}
          </div>
        )}
      </ConfirmDialog>

      <ConfirmDialog
        open={pending === "reject" || pending === "withdraw"}
        onOpenChange={(open) => !open && setPending(null)}
        title={pending === "withdraw" ? "Taklifni qaytarib olasizmi?" : "Taklifni rad etasizmi?"}
        description="Muzokara yopiladi. Keyin yangi taklif berish mumkin."
        confirmLabel={pending === "withdraw" ? "Qaytarib olish" : "Rad etish"}
        cancelLabel="Yoʻq"
        variant="destructive"
        loading={busy}
        error={error}
        onConfirm={() => pending && void run(pending)}
      />
    </article>
  )
}

export { OfferCard }
