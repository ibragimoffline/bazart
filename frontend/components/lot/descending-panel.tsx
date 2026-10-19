"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { toast } from "sonner"
import { BellRingIcon, ShoppingBagIcon, TrendingDownIcon } from "lucide-react"

import { formatTiyin } from "@/lib/format"
import type { Auction } from "@/lib/api/types"
import { buyNow } from "@/lib/api/endpoints"
import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import { useNow, useOfferConsent } from "@/components/offer/offer-meta"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"

// Oy nomlari qo'lda: ayrim brauzerlarda "uz-UZ" ICU ma'lumoti yo'q va "M10" chiqadi.
const MONTHS = [
  "yanvar", "fevral", "mart", "aprel", "may", "iyun",
  "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]
const tashkentParts = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Tashkent",
  day: "numeric",
  month: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

/** "19-oktabr, 17:17" (Toshkent vaqti). */
function formatStart(iso: string): string {
  const parts = Object.fromEntries(
    tashkentParts.formatToParts(new Date(iso)).map((p) => [p.type, p.value])
  )
  return `${parts.day}-${MONTHS[Number(parts.month) - 1]}, ${parts.hour}:${parts.minute}`
}

/** 90 -> "1 soat 30 daqiqa", 60 -> "1 soat", 15 -> "15 daqiqa". */
export function intervalText(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h && m) return `${h} soat ${m} daqiqa`
  return h ? `${h} soat` : `${m} daqiqa`
}

/** Qolgan vaqt "1:05:09" / "4:09" — keyingi narx tushishigacha. */
function countdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, "0")
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

/**
 * Pasayuvchi (golland) auksion paneli: narx vaqt bilan pasayadi, birinchi xarid yutadi.
 *
 * Narxni brauzer HISOBLAMAYDI — server qiymatini ko'rsatadi; keyingi pasayish vaqti
 * kelganda auksion qayta yuklanadi (`onRefresh`). Xarid serverda qulf ostida, o'sha
 * lahzadagi narxda bajariladi — narx faqat pasaygani uchun ko'rsatilgandan oshmaydi.
 */
function DescendingPanel({
  auction,
  onRefresh,
}: {
  auction: Auction
  onRefresh: () => void
}) {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const pathname = usePathname()
  const router = useRouter()
  const now = useNow(1000)
  const [open, setOpen] = React.useState(false)
  const [buying, setBuying] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [agreed, setAgreed] = React.useState(false)

  const isSeller = user?.id === auction.seller_id
  const active = auction.status === "active" && auction.buy_now_available
  const scheduled = auction.status === "scheduled"
  const canBuy = status === "authenticated" && !isSeller && active
  const consent = useOfferConsent(canBuy)

  const dropAt = auction.next_price_drop_at ? Date.parse(auction.next_price_drop_at) : null
  const msToDrop = dropAt != null && now ? dropAt - now : null

  // Pasayish vaqti keldi — yangi narxni serverdan olamiz (bir marta, har pasayishga).
  const refreshedFor = React.useRef<number | null>(null)
  React.useEffect(() => {
    if (dropAt != null && msToDrop != null && msToDrop <= 0 && refreshedFor.current !== dropAt) {
      refreshedFor.current = dropAt
      onRefresh()
    }
  }, [dropAt, msToDrop, onRefresh])

  const confirm = async () => {
    if (consent.needsConsent && !agreed) {
      setError("Davom etish uchun shartlarni qabul qiling.")
      return
    }
    setBuying(true)
    setError(null)
    try {
      await consent.ensure()
      await buyNow(auction.id)
      setOpen(false)
      toast.success("Mahsulot sizniki! Sotuvchi bilan bogʻlaning.")
      onRefresh()
      router.push("/orders")
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Kechikdingiz — mahsulotni boshqa xaridor sotib oldi yoki auksion tugadi.")
        onRefresh()
      } else {
        setError(e instanceof ApiError ? e.detail : "Sotib olib boʻlmadi. Qayta urinib koʻring.")
      }
    } finally {
      setBuying(false)
    }
  }

  return (
    <div className="grid gap-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <TrendingDownIcon className="size-4 shrink-0 text-brand" aria-hidden="true" />
        Pasayuvchi auksion
      </div>
      {auction.price_decrement && auction.price_drop_interval_minutes ? (
        <p className="text-sm text-muted-foreground">
          Narx har {intervalText(auction.price_drop_interval_minutes)}da{" "}
          {formatTiyin(auction.price_decrement)} ga tushadi. Birinchi sotib olgan xaridor
          yutadi — kutsangiz arzonlashadi, lekin boshqasi oldinroq olishi mumkin.
        </p>
      ) : null}

      {(active || scheduled) && auction.price_forecast.length > 0 && (
        <section aria-labelledby={`forecast-${auction.id}`} className="grid gap-1.5">
          <h3 id={`forecast-${auction.id}`} className="text-sm font-medium text-foreground">
            Narx jadvali
          </h3>
          <ul className="grid gap-1 text-sm">
            {auction.price_forecast.map((p) => (
              <li key={p.at} className="flex items-baseline justify-between gap-3">
                <span className="text-muted-foreground">
                  {p.is_end
                    ? "Auksion tugashida"
                    : `${p.days_from_now} kundan keyin`}
                </span>
                <span className="font-medium tabular-nums text-foreground">
                  {formatTiyin(p.price)}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            {(() => {
              const last = auction.price_forecast[auction.price_forecast.length - 1]
              const when = last.is_end ? "auksion tugashida" : `${last.days_from_now} kundan keyin`
              return `Narx ${when} ${formatTiyin(last.price)}gacha tushadi — kutish arzonroq, lekin boshqa xaridor oldinroq sotib olishi mumkin.`
            })()}
          </p>
        </section>
      )}

      {active && (
        <div className="flex items-baseline justify-between gap-3 rounded-lg bg-muted px-3 py-2.5 text-sm">
          {msToDrop != null ? (
            <>
              <span className="text-muted-foreground">Keyingi pasayishgacha</span>
              <span className="font-medium tabular-nums text-foreground" aria-live="off">
                {countdown(msToDrop)}
              </span>
            </>
          ) : (
            <span className="text-muted-foreground">Narx eng past darajaga yetdi</span>
          )}
        </div>
      )}

      {(active || scheduled) && !isSeller && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <BellRingIcon className="size-3.5 shrink-0" aria-hidden="true" />
          Kuzatsangiz, narx sezilarli tushganda va tugashiga 2 soat qolganda Telegram orqali
          xabar olasiz.
        </p>
      )}

      {scheduled ? (
        <p className="text-sm text-muted-foreground">
          Auksion {formatStart(auction.start_time)} da boshlanadi (Toshkent vaqti).
        </p>
      ) : !active ? (
        <p className="text-sm text-muted-foreground">Auksion yakunlangan.</p>
      ) : isSeller ? (
        <p className="text-sm text-muted-foreground">Bu sizning lotingiz.</p>
      ) : status !== "authenticated" ? (
        <Button asChild size="lg">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Sotib olish uchun kiring</Link>
        </Button>
      ) : (
        <Button
          size="lg"
          disabled={!consent.ready}
          onClick={() => {
            setError(null)
            setAgreed(false)
            setOpen(true)
          }}
        >
          <ShoppingBagIcon aria-hidden="true" />
          {formatTiyin(auction.current_price)} ga sotib olish
        </Button>
      )}

      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Hozirgi narxda sotib olasizmi?"
        description={`Joriy narx ${formatTiyin(auction.current_price)}. Narx faqat pasayadi — kelishuv narxi bundan oshmaydi. Auksion shu zahoti yakunlanadi.`}
        confirmLabel="Sotib olish"
        cancelLabel="Yoʻq"
        loading={buying}
        error={error}
        onConfirm={() => void confirm()}
      >
        <div className="grid gap-2 text-sm text-muted-foreground">
          <p>Xarid kelishuv tuzadi — sotuvchi kontaktlari ochiladi. Mahsulotni koʻrmasdan oldindan toʻlamang.</p>
          {consent.needsConsent && (
            <div className="flex items-start gap-2">
              <Checkbox
                id={`dutch-consent-${auction.id}`}
                checked={agreed}
                disabled={buying}
                onCheckedChange={(v) => setAgreed(v === true)}
                className="mt-0.5"
                aria-required="true"
              />
              <label htmlFor={`dutch-consent-${auction.id}`} className="text-foreground">
                Auksion qoidalari va ommaviy ofertani qabul qilaman
              </label>
            </div>
          )}
        </div>
      </ConfirmDialog>
    </div>
  )
}

export { DescendingPanel }
