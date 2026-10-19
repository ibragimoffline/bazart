"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { toast } from "sonner"
import { GavelIcon, ShieldCheckIcon, InfoIcon, ShoppingBagIcon } from "lucide-react"

import { formatTiyin, formatNumber } from "@/lib/format"
import type { Auction } from "@/lib/api/types"
import { buyNow, placeBid } from "@/lib/api/endpoints"
import { ApiError } from "@/lib/api/client"
import {
  listMyConsents,
  recordConsent,
  hasConsented,
  type ConsentDocumentType,
  type LegalConsent,
} from "@/lib/api/legal"
import { useAuthStore } from "@/lib/store/auth"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"
import { SecondChanceCard } from "@/components/lot/second-chance-card"
import { minNextBidTiyin, isSuspiciouslyHigh } from "@/components/lot/lot-rules"

/** Taklif berish shu hujjatlarni qabul qilishni anglatadi (huquqiy rozilik). */
const BID_DOCUMENTS: ConsentDocumentType[] = ["auction_rules", "public_offer"]

function digits(s: string): number {
  const n = Number(s.replace(/\D/g, ""))
  return Number.isFinite(n) ? n : 0
}

function BidPanel({
  auction,
  onBid,
}: {
  auction: Auction
  onBid: () => void
}) {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const pathname = usePathname()
  const router = useRouter()

  // Server hisoblagan minimum (qadam jadvali bilan) — frontend o'zi hisoblamaydi.
  const minNextTiyin = minNextBidTiyin(auction)
  const minNextSoum = Math.round(minNextTiyin / 100)

  const [amount, setAmount] = React.useState(minNextSoum)
  const [maxAmount, setMaxAmount] = React.useState(0)
  const [error, setError] = React.useState<string | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const [typoOpen, setTypoOpen] = React.useState(false)
  // null — rozilik ro'yxati hali yuklanmagan.
  const [consents, setConsents] = React.useState<LegalConsent[] | null>(null)
  const [agreed, setAgreed] = React.useState(false)
  const [nowMs, setNowMs] = React.useState(0)
  const [buyOpen, setBuyOpen] = React.useState(false)
  const [buying, setBuying] = React.useState(false)
  const [buyError, setBuyError] = React.useState<string | null>(null)

  // Minimal taklif o'zgarsa (bid, jonli xabar) — taklifni yangi minimumga tenglash.
  const [synced, setSynced] = React.useState(minNextTiyin)
  if (synced !== minNextTiyin) {
    setSynced(minNextTiyin)
    setAmount(minNextSoum)
    setError(null)
  }

  const ended = auction.status !== "active"
  const isSeller = user != null && user.id === auction.seller_id
  const canBid = status === "authenticated" && !isSeller && !ended

  React.useEffect(() => {
    if (!canBid) return
    let alive = true
    listMyConsents()
      .then((list) => {
        if (alive) setConsents(list)
      })
      .catch(() => {
        // Yuklanmasa — rozilik so'raymiz (xavfsiz tomon).
        if (alive) setConsents([])
      })
    return () => {
      alive = false
    }
  }, [canBid])

  // Ikkinchi imkoniyat muddatini tekshirish uchun soat (render'da Date.now yo'q).
  React.useEffect(() => {
    const tick = () => setNowMs(Date.now())
    const first = window.setTimeout(tick, 0)
    const id = window.setInterval(tick, 30_000)
    return () => {
      window.clearTimeout(first)
      window.clearInterval(id)
    }
  }, [])

  const secondChanceOpen =
    isSeller &&
    auction.status === "reserve_not_met" &&
    auction.second_chance_expires_at != null &&
    nowMs > 0 &&
    Date.parse(auction.second_chance_expires_at) > nowMs

  if (secondChanceOpen) {
    return <SecondChanceCard auction={auction} onAccepted={onBid} />
  }

  if (ended) {
    return (
      <div className="rounded-xl border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
        Bu auksion yakunlangan — yangi taklif qabul qilinmaydi.
      </div>
    )
  }

  if (status !== "authenticated") {
    return (
      <div className="grid gap-3 rounded-xl border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">
          Taklif berish uchun hisobingizga kiring.
        </p>
        <Button asChild size="lg">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  if (isSeller) {
    return (
      <div className="rounded-xl border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
        Oʻz mahsulotingizga taklif bera olmaysiz.
      </div>
    )
  }

  const needsConsent = consents !== null && !hasConsented(consents, BID_DOCUMENTS)
  const amountTiyin = amount * 100

  /** Rozilikni (kerak bo'lsa) yozadi. Xato bo'lsa matnini qaytaradi, aks holda null. */
  const ensureConsent = async (): Promise<string | null> => {
    if (!needsConsent) return null
    try {
      const recorded = await Promise.all(BID_DOCUMENTS.map((d) => recordConsent(d)))
      setConsents((prev) => [...(prev ?? []), ...recorded])
      return null
    } catch (e) {
      return e instanceof ApiError
        ? e.detail
        : "Roziligingizni saqlab boʻlmadi. Qayta urinib koʻring."
    }
  }

  /** Buy-now: tasdiq oynasidagi "Sotib olish" — rozilik (kerak bo'lsa) + xarid. */
  const confirmBuyNow = async () => {
    setBuyError(null)
    setBuying(true)
    try {
      const consentError = await ensureConsent()
      if (consentError) {
        setBuyError(consentError)
        return
      }
      await buyNow(auction.id)
      setBuyOpen(false)
      toast.success("Mahsulot sizniki! Endi toʻlovni amalga oshiring.")
      onBid()
      router.push("/orders")
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setBuyError("Kechikdingiz — bu imkoniyat yopildi yoki mahsulot allaqachon sotildi.")
        onBid()
      } else {
        setBuyError(e instanceof ApiError ? e.detail : "Sotib olib boʻlmadi. Qayta urinib koʻring.")
      }
    } finally {
      setBuying(false)
    }
  }

  /** Rozilikni (kerak bo'lsa) yozib, keyin taklifni yuboradi. */
  const send = async () => {
    setError(null)
    setSubmitting(true)
    try {
      const consentError = await ensureConsent()
      if (consentError) {
        setError(consentError)
        return
      }
      const bid = await placeBid(
        auction.id,
        String(amountTiyin),
        maxAmount > 0 ? String(maxAmount * 100) : undefined
      )
      toast.success("Taklifingiz qabul qilindi")
      if (bid.high_bid_warning) {
        toast.warning(
          `Taklifingiz (${formatTiyin(bid.amount)}) joriy narxdan ancha yuqori — summani tekshiring.`
        )
      }
      onBid()
    } catch (e) {
      setError(
        e instanceof ApiError ? e.detail : "Taklif yuborilmadi. Qayta urinib koʻring."
      )
    } finally {
      setSubmitting(false)
    }
  }

  const submit = () => {
    setError(null)
    if (amount < minNextSoum) {
      setError(`Taklif kamida ${formatTiyin(String(minNextTiyin))} boʻlishi kerak.`)
      return
    }
    if (maxAmount > 0 && maxAmount < amount) {
      setError("Avto-taklif summasi taklifdan kichik boʻlmasligi kerak.")
      return
    }
    if (needsConsent && !agreed) {
      setError("Taklif berish uchun auksion qoidalarini qabul qiling.")
      return
    }
    if (isSuspiciouslyHigh(amountTiyin, auction)) {
      setTypoOpen(true)
      return
    }
    void send()
  }

  const showBuyNow = auction.buy_now_available && auction.buy_now_price != null

  return (
    <div className="grid gap-3 rounded-xl border border-border bg-card p-4">
      {showBuyNow && auction.buy_now_price != null && (
        <div className="grid gap-2 border-b border-border pb-3">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm text-muted-foreground">Hoziroq sotib olish</span>
            <span className="font-heading text-lg font-semibold tabular-nums text-foreground">
              {formatTiyin(auction.buy_now_price)}
            </span>
          </div>
          <Button
            variant="outline"
            size="lg"
            disabled={consents === null}
            onClick={() => {
              setBuyError(null)
              setBuyOpen(true)
            }}
          >
            <ShoppingBagIcon aria-hidden="true" />
            Hoziroq sotib olish
          </Button>
          <p className="text-xs text-muted-foreground">
            Kutmasdan shu narxda olasiz.{" "}
            {auction.has_reserve
              ? "Takliflar zaxira narxga yetgach bu imkoniyat yopiladi."
              : "Birinchi taklif tushishi bilan bu imkoniyat yopiladi."}
          </p>
        </div>
      )}

      <div className="grid gap-1.5">
        <label htmlFor="bid-amount" className="text-sm font-medium text-foreground">
          Taklif summasi, soʻm
        </label>
        <Input
          id="bid-amount"
          inputMode="numeric"
          value={amount > 0 ? formatNumber(amount) : ""}
          onChange={(e) => setAmount(digits(e.target.value))}
          aria-invalid={error ? true : undefined}
        />
        <p className="text-xs text-muted-foreground">
          Minimal keyingi taklif: {formatTiyin(String(minNextTiyin))}
        </p>
      </div>

      <div className="grid gap-1.5">
        <div className="flex items-center gap-1.5">
          <label htmlFor="bid-max" className="text-sm font-medium text-foreground">
            Avto-taklif (ixtiyoriy), soʻm
          </label>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label="Avto-taklif qanday ishlaydi"
                className="rounded-full text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <InfoIcon className="size-4" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              Siz maksimal summani belgilaysiz. Tizim raqiblar taklifidan bittagina
              qadam yuqori koʻtaradi — shu summagacha. Maksimal summangiz boshqa
              ishtirokchilarga hech qachon koʻrsatilmaydi.
            </TooltipContent>
          </Tooltip>
        </div>
        <Input
          id="bid-max"
          inputMode="numeric"
          placeholder="Maksimal summa"
          value={maxAmount > 0 ? formatNumber(maxAmount) : ""}
          onChange={(e) => setMaxAmount(digits(e.target.value))}
        />
        <p className="text-xs text-muted-foreground">
          Tizim raqiblarga qarshi shu summagacha avtomatik koʻtaradi. Summa
          yashirin qoladi.
        </p>
      </div>

      {needsConsent && (
        <div className="flex items-start gap-3">
          <Checkbox
            id="bid-consent"
            checked={agreed}
            disabled={submitting}
            onCheckedChange={(v) => setAgreed(v === true)}
            className="mt-0.5"
            aria-required="true"
          />
          <label
            htmlFor="bid-consent"
            className="text-sm leading-snug text-foreground peer-disabled:opacity-50"
          >
            Auksion qoidalari va ommaviy ofertani qabul qilaman
          </label>
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}

      <Button
        size="lg"
        loading={submitting}
        disabled={consents === null || (needsConsent && !agreed)}
        onClick={submit}
      >
        <GavelIcon aria-hidden="true" />
        Taklif berish
      </Button>

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ShieldCheckIcon className="size-3.5 shrink-0" aria-hidden="true" />
        Gʻolib chiqsangiz toʻlov escrow orqali himoyalanadi.
      </p>

      {auction.buy_now_price != null && (
        <ConfirmDialog
          open={buyOpen}
          onOpenChange={setBuyOpen}
          title="Hoziroq sotib olasizmi?"
          description={`Auksion shu zahoti yakunlanadi va lot sizga oʻtadi${auction.bid_count > 0 ? " — mavjud takliflar ortda qoladi" : ""}. Toʻlov escrow orqali himoyalanadi.`}
          confirmLabel="Sotib olish"
          cancelLabel="Yoʻq"
          loading={buying}
          error={buyError}
          onConfirm={() => void confirmBuyNow()}
        >
          <dl className="grid gap-1 text-sm text-muted-foreground">
            <div className="flex justify-between gap-4">
              <dt>Narx</dt>
              <dd className="font-semibold tabular-nums text-foreground">
                {formatTiyin(auction.buy_now_price)}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Xaridor komissiyasi</dt>
              <dd className="text-foreground">8%, toʻlovda qoʻshiladi</dd>
            </div>
          </dl>
          {needsConsent && (
            <p className="text-xs text-muted-foreground">
              «Sotib olish» tugmasini bosib, auksion qoidalari va ommaviy ofertani qabul qilasiz.
            </p>
          )}
        </ConfirmDialog>
      )}

      <ConfirmDialog
        open={typoOpen}
        onOpenChange={setTypoOpen}
        title="Summani tekshiring"
        description="Taklifingiz joriy narxdan 3 barobardan koʻproq — summani tekshiring."
        confirmLabel="Ha, taklif berish"
        cancelLabel="Oʻzgartirish"
        onConfirm={() => {
          setTypoOpen(false)
          void send()
        }}
      >
        <dl className="grid gap-1 text-sm text-muted-foreground">
          <div className="flex justify-between gap-4">
            <dt>Joriy narx</dt>
            <dd className="tabular-nums text-foreground">
              {formatTiyin(auction.current_price)}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Sizning taklifingiz</dt>
            <dd className="font-semibold tabular-nums text-foreground">
              {formatTiyin(amountTiyin)}
            </dd>
          </div>
        </dl>
      </ConfirmDialog>
    </div>
  )
}

export { BidPanel }
