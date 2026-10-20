"use client"

import * as React from "react"

import { formatTiyin, soumToTiyin, tiyinToSoum } from "@/lib/format"
import { buyNowError } from "@/lib/listing"
import type { Auction, PricingMode } from "@/lib/api/types"
import { updateAuctionPricing } from "@/lib/api/seller"
import { ApiError } from "@/lib/api/client"
import { useFeatures } from "@/lib/features"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PriceInput } from "@/components/seller/sell/price-input"

const INTERVALS = ["15", "30", "60", "180", "360", "720", "1440"] as const
const INTERVAL_LABEL: Record<(typeof INTERVALS)[number], string> = {
  "15": "15 daqiqa",
  "30": "30 daqiqa",
  "60": "1 soat",
  "180": "3 soat",
  "360": "6 soat",
  "720": "12 soat",
  "1440": "1 kun",
}

const choiceClass =
  "flex min-h-11 cursor-pointer items-start gap-2 rounded-lg border border-border bg-card px-3 py-2.5 text-sm font-normal transition-colors hover:border-foreground/30 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5 has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50"

/**
 * Boshlanmagan auksionning narx rejimini o'zgartirish (o'suvchi / pasayuvchi).
 * Server to'liq almashtiradi: berilmagan maydon tozalanadi. Rezerv va chegara qiymati
 * hech qachon brauzerga yuborilmaydi — shuning uchun ularni qaytadan kiritish kerak.
 */
function PricingDialog({
  auction,
  open,
  onOpenChange,
  onUpdated,
}: {
  auction: Auction
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpdated: (auction: Auction) => void
}) {
  const startSoum = tiyinToSoum(auction.starting_price)
  const [mode, setMode] = React.useState<PricingMode>(auction.pricing_mode)
  const [buyNow, setBuyNow] = React.useState(
    auction.buy_now_price ? tiyinToSoum(auction.buy_now_price) : 0
  )
  const [reserve, setReserve] = React.useState(0)
  const [step, setStep] = React.useState(
    auction.price_decrement ? tiyinToSoum(auction.price_decrement) : 0
  )
  const [interval, setInterval] = React.useState<(typeof INTERVALS)[number]>(
    (INTERVALS as readonly string[]).includes(String(auction.price_drop_interval_minutes))
      ? (String(auction.price_drop_interval_minutes) as (typeof INTERVALS)[number])
      : "60"
  )
  const [floor, setFloor] = React.useState(0)
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const descending = mode === "descending"
  // Bayroq o'chiq: yangi o'suvchi rejimga o'tib bo'lmaydi. Allaqachon o'suvchi auksion
  // o'z qoidasida qoladi (server ham shunday tekshiradi), shuning uchun unga tanlov ko'rinadi.
  const features = useFeatures()
  const ascendingAllowed =
    features?.ascending_auction === true || auction.pricing_mode === "ascending"
  const buyNowIssue = !descending ? buyNowError(buyNow, startSoum, reserve) : null

  const save = async () => {
    setError(null)
    if (descending) {
      if (!(step > 0)) return setError("Pasayish qadamini kiriting.")
      if (!(floor > 0) || floor >= startSoum)
        return setError("Eng past narx boshlangʻich narxdan past boʻlishi kerak.")
    } else if (buyNowIssue) {
      return setError(buyNowIssue)
    }
    setSaving(true)
    try {
      const updated = await updateAuctionPricing(
        auction.id,
        descending
          ? {
              pricing_mode: "descending",
              price_decrement: soumToTiyin(step),
              price_drop_interval_minutes: Number(interval),
              reserve_price: soumToTiyin(floor),
            }
          : {
              pricing_mode: "ascending",
              buy_now_price: buyNow > 0 ? soumToTiyin(buyNow) : undefined,
              reserve_price: reserve > 0 ? soumToTiyin(reserve) : undefined,
            }
      )
      onUpdated(updated)
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 409
          ? "Auksion boshlangan — narx rejimini endi oʻzgartirib boʻlmaydi."
          : e instanceof ApiError
            ? e.detail
            : "Saqlab boʻlmadi."
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Narx rejimini oʻzgartirish"
      description={`Boshlangʻich narx ${formatTiyin(auction.starting_price)}. Auksion boshlanguncha oʻzgartirish mumkin.`}
      confirmLabel="Saqlash"
      cancelLabel="Bekor qilish"
      loading={saving}
      error={error}
      onConfirm={() => void save()}
    >
      <div className="grid gap-4">
        {ascendingAllowed && (
          <RadioGroup
            aria-label="Narx yoʻnalishi"
            value={mode}
            onValueChange={(v) => setMode(v as PricingMode)}
            className="grid gap-2 sm:grid-cols-2"
            disabled={saving}
          >
            <Label htmlFor={`pd-asc-${auction.id}`} className={choiceClass}>
              <RadioGroupItem id={`pd-asc-${auction.id}`} value="ascending" className="mt-0.5" />
              <span className="grid gap-0.5">
                <span className="font-medium text-foreground">Oʻsuvchi</span>
                <span className="text-xs text-muted-foreground">Takliflar, eng yuqorisi yutadi</span>
              </span>
            </Label>
            <Label htmlFor={`pd-desc-${auction.id}`} className={choiceClass}>
              <RadioGroupItem id={`pd-desc-${auction.id}`} value="descending" className="mt-0.5" />
              <span className="grid gap-0.5">
                <span className="font-medium text-foreground">Pasayuvchi</span>
                <span className="text-xs text-muted-foreground">Narx tushadi, birinchi xarid yutadi</span>
              </span>
            </Label>
          </RadioGroup>
        )}

        {descending ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field>
              <FieldLabel htmlFor={`pd-step-${auction.id}`}>Pasayish qadami</FieldLabel>
              <PriceInput id={`pd-step-${auction.id}`} value={step} onChange={setStep} disabled={saving} />
            </Field>
            <Field>
              <FieldLabel id={`pd-int-${auction.id}`}>Har</FieldLabel>
              <Select
                value={interval}
                onValueChange={(v) => setInterval(v as (typeof INTERVALS)[number])}
                disabled={saving}
              >
                <SelectTrigger aria-labelledby={`pd-int-${auction.id}`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INTERVALS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {INTERVAL_LABEL[m]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor={`pd-floor-${auction.id}`}>Eng past narx</FieldLabel>
              <PriceInput id={`pd-floor-${auction.id}`} value={floor} onChange={setFloor} disabled={saving} />
            </Field>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor={`pd-bn-${auction.id}`}>Hoziroq sotib olish</FieldLabel>
              <PriceInput
                id={`pd-bn-${auction.id}`}
                placeholder="Yoʻq"
                value={buyNow}
                onChange={setBuyNow}
                disabled={saving}
                aria-invalid={buyNowIssue ? true : undefined}
              />
              <FieldError>{buyNowIssue}</FieldError>
            </Field>
            <Field>
              <FieldLabel htmlFor={`pd-res-${auction.id}`}>Zaxira narx</FieldLabel>
              <PriceInput
                id={`pd-res-${auction.id}`}
                placeholder="Yoʻq"
                value={reserve}
                onChange={setReserve}
                disabled={saving}
              />
            </Field>
          </div>
        )}
        <FieldDescription>
          {descending
            ? "Eng past narx xaridorlarga koʻrsatilmaydi (narx jadvali unga yetganda koʻrinadi)."
            : "Zaxira narx maxfiy saqlanadi va bu yerda koʻrsatilmaydi — kerak boʻlsa qaytadan kiriting."}
        </FieldDescription>
      </div>
    </ConfirmDialog>
  )
}

export { PricingDialog }
