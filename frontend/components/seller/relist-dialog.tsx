"use client"

import * as React from "react"

import { formatTiyin, soumToTiyin, tiyinToSoum } from "@/lib/format"
import {
  autoIncrementSoum,
  buyNowError,
  suggestDutchFloorSoum,
  suggestDutchStepSoum,
  suggestRelistSoum,
} from "@/lib/listing"
import type { Auction, Item } from "@/lib/api/types"
import { relistAuction } from "@/lib/api/seller"
import { ApiError } from "@/lib/api/client"
import { useFeatures } from "@/lib/features"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"
import { Field, FieldLabel, FieldError, FieldDescription } from "@/components/ui/field"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { PriceInput } from "@/components/seller/sell/price-input"

const DURATIONS = ["3", "5", "7"] as const
/** Pasayuvchi qayta joylashda narx har soatda tushadi (sell-form default'i bilan bir xil). */
const DROP_INTERVAL_MINUTES = 60

/** Radio "kartochka" — sell-form'dagi muddat tanlovi bilan bir xil ko'rinish. */
const choiceClass =
  "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-border bg-card px-3 py-2.5 text-sm font-normal transition-colors hover:border-foreground/30 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5 has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50"

/**
 * Sotilmagan lotni qayta joylash oynasi. Narx oldindan tavsiya bilan to'ldiriladi
 * (`suggestRelistSoum`): narx qotib qolmasin — loyihaning asosiy g'oyasi.
 * E'lon matni va rasmlari server tomonida nusxa ko'chiriladi.
 *
 * O'suvchi auksion bayroq bilan o'chirilgan bo'lsa (GET /features) lot pasayuvchi auksion
 * sifatida qayta joylanadi: eng past narx va pasayish qadami tavsiya bilan to'ldiriladi.
 */
function RelistDialog({
  auction,
  item,
  open,
  onOpenChange,
  onRelisted,
}: {
  auction: Auction
  item: Item
  open: boolean
  onOpenChange: (open: boolean) => void
  onRelisted: (auction: Auction) => void
}) {
  const hadBids = auction.status === "reserve_not_met" && auction.bid_count > 0
  const previousStart = tiyinToSoum(auction.starting_price)
  const suggested = suggestRelistSoum(previousStart, hadBids ? tiyinToSoum(auction.current_price) : null)

  const [duration, setDuration] = React.useState<(typeof DURATIONS)[number]>("5")
  const [starting, setStarting] = React.useState(suggested)
  const [reserve, setReserve] = React.useState(0)
  const [buyNow, setBuyNow] = React.useState(0)
  // null — tavsiya qiymati (boshlang'ich narx o'zgarsa qayta hisoblanadi).
  const [floorInput, setFloorInput] = React.useState<number | null>(null)
  const [stepInput, setStepInput] = React.useState<number | null>(null)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Oyna har ochilganda tavsiya qilingan qiymatlardan boshlanadi.
  const [wasOpen, setWasOpen] = React.useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setDuration("5")
      setStarting(suggested)
      setReserve(0)
      setBuyNow(0)
      setFloorInput(null)
      setStepInput(null)
      setError(null)
    }
  }

  const features = useFeatures()
  const descending = features?.ascending_auction !== true
  const floor = floorInput ?? suggestDutchFloorSoum(starting)
  const step = stepInput ?? suggestDutchStepSoum(starting, floor, Number(duration))
  const floorIssue =
    descending && starting > 0 && !(floor > 0 && floor < starting)
      ? "Boshlangʻich narxdan past boʻlishi kerak."
      : null

  const reserveTooLow = reserve > 0 && starting > 0 && reserve < starting
  const buyNowIssue = buyNowError(buyNow, starting, reserve)
  const secondChanceOpen =
    auction.status === "reserve_not_met" && auction.second_chance_expires_at != null

  const submit = async () => {
    setError(null)
    if (!(starting > 0)) {
      setError("Boshlangʻich narxni kiriting.")
      return
    }
    if (descending ? floorIssue || !(step > 0) : reserveTooLow || buyNowIssue) {
      if (descending && !(step > 0)) setError("Pasayish qadamini kiriting.")
      return
    }
    setSubmitting(true)
    try {
      const common = {
        duration_days: Number(duration) as 3 | 5 | 7,
        starting_price: soumToTiyin(starting),
        minimum_bid_increment: soumToTiyin(autoIncrementSoum(starting)),
      }
      const created = await relistAuction(
        auction.id,
        descending
          ? {
              ...common,
              pricing_mode: "descending",
              reserve_price: soumToTiyin(floor),
              price_decrement: soumToTiyin(step),
              price_drop_interval_minutes: DROP_INTERVAL_MINUTES,
            }
          : {
              ...common,
              reserve_price: reserve > 0 ? soumToTiyin(reserve) : undefined,
              buy_now_price: buyNow > 0 ? soumToTiyin(buyNow) : undefined,
            }
      )
      onRelisted(created)
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 409 && e.code !== "ascending_auction_disabled"
          ? "Bu mahsulot allaqachon qayta joylangan yoki sotilgan."
          : e instanceof ApiError
            ? e.detail
            : "Qayta joylab boʻlmadi. Qayta urinib koʻring."
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Mahsulotni qayta joylash"
      description={
        <>
          <span className="font-medium text-foreground">{item.title}</span>{" "}
          {descending ? "pasayuvchi auksion" : "yangi auksion"} sifatida joylanadi — matn va
          rasmlar saqlanadi.
        </>
      }
      confirmLabel="Qayta joylash"
      cancelLabel="Bekor qilish"
      loading={submitting}
      error={error}
      onConfirm={() => void submit()}
    >
      <div className="grid gap-4">
        <Field>
          <FieldLabel htmlFor="relist-starting">Boshlangʻich narx</FieldLabel>
          <PriceInput
            id="relist-starting"
            value={starting}
            onChange={setStarting}
            disabled={submitting}
            aria-invalid={!(starting > 0) && error ? true : undefined}
          />
          <FieldDescription>
            {hadBids
              ? `Tavsiya — eng yuqori taklif (${formatTiyin(auction.current_price)}). Xaridorlar shu narxni allaqachon taklif qilgan.`
              : `Avvalgi narx ${formatTiyin(auction.starting_price)} edi. Taklif tushmagan — narxni pasaytirish mahsulotni tezroq sotadi.`}
          </FieldDescription>
        </Field>

        <Field>
          <FieldLabel id="relist-duration-label">Muddat</FieldLabel>
          <RadioGroup
            value={duration}
            onValueChange={(v) => setDuration(v as (typeof DURATIONS)[number])}
            aria-labelledby="relist-duration-label"
            className="grid grid-cols-3 gap-2"
            disabled={submitting}
          >
            {DURATIONS.map((d) => (
              <Label key={d} htmlFor={`relist-duration-${d}`} className={choiceClass}>
                <RadioGroupItem id={`relist-duration-${d}`} value={d} />
                {d} kun
              </Label>
            ))}
          </RadioGroup>
        </Field>

        {descending ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="relist-floor">Eng past narx</FieldLabel>
              <PriceInput
                id="relist-floor"
                value={floor}
                onChange={setFloorInput}
                disabled={submitting}
                aria-invalid={floorIssue ? true : undefined}
              />
              <FieldError>{floorIssue}</FieldError>
            </Field>
            <Field>
              <FieldLabel htmlFor="relist-step">Har soatda pasayish</FieldLabel>
              <PriceInput
                id="relist-step"
                value={step}
                onChange={setStepInput}
                disabled={submitting}
              />
            </Field>
            <FieldDescription className="sm:col-span-2">
              Narx boshlangʻich summadan har soatda shu qadam bilan tushadi va eng past narxdan
              pastga tushmaydi. Birinchi sotib olgan xaridor yutadi.
            </FieldDescription>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="relist-reserve">Zaxira narx</FieldLabel>
              <PriceInput
                id="relist-reserve"
                placeholder="Yoʻq"
                value={reserve}
                onChange={setReserve}
                disabled={submitting}
                aria-invalid={reserveTooLow ? true : undefined}
              />
              <FieldError>
                {reserveTooLow ? "Boshlangʻich narxdan past boʻlishi mumkin emas." : null}
              </FieldError>
            </Field>
            <Field>
              <FieldLabel htmlFor="relist-buy-now">Hoziroq sotib olish</FieldLabel>
              <PriceInput
                id="relist-buy-now"
                placeholder="Yoʻq"
                value={buyNow}
                onChange={setBuyNow}
                disabled={submitting}
                aria-invalid={buyNowIssue ? true : undefined}
              />
              <FieldError>{buyNowIssue}</FieldError>
            </Field>
          </div>
        )}

        {auction.has_reserve && !descending && (
          <p className="text-xs text-muted-foreground">
            Avvalgi zaxira narx koʻchirilmaydi — kerak boʻlsa yuqorida qaytadan kiriting.
          </p>
        )}

        {secondChanceOpen && (
          <p className="text-xs text-muted-foreground">
            Qayta joylasangiz, eski auksiondagi «eng yuqori taklifga sotish» imkoniyati yopiladi.
          </p>
        )}
      </div>
    </ConfirmDialog>
  )
}

export { RelistDialog }
