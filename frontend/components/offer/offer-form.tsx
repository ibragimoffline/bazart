"use client"

import * as React from "react"
import { MinusIcon, PlusIcon } from "lucide-react"

import { formatNumber, formatSom, soumToTiyin, tiyinToSoum } from "@/lib/format"
import type { OfferTerms } from "@/lib/api/offers"
import { ApiError } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { PriceInput } from "@/components/seller/sell/price-input"

const MESSAGE_MAX = 500

/**
 * Taklif / qarshi taklif shakli: miqdor + DONA narxi -> jami.
 *
 * Narx erkin: istalgan musbat summa (mo'ljal narxdan past ham, yuqori ham) —
 * mo'ljal narx bilan solishtirish faqat ma'lumot uchun, hech narsani bloklamaydi.
 * Yakuniy jami server tomonida hisoblanadi (bu yerda — ko'rsatish uchun).
 */
function OfferForm({
  idPrefix,
  maxQuantity,
  askingTiyin,
  initialQuantity = 1,
  initialUnitTiyin,
  submitLabel,
  requireConsent = false,
  needsConsent = false,
  disabled = false,
  onSubmit,
  onCancel,
}: {
  idPrefix: string
  maxQuantity: number
  /** Sotuvchining mo'ljal narxi (dona) — solishtirish uchun. */
  askingTiyin: string
  initialQuantity?: number
  initialUnitTiyin?: string
  submitLabel: string
  /** Xaridor tomoni: rozilik bayrog'i ko'rsatiladimi. */
  requireConsent?: boolean
  needsConsent?: boolean
  disabled?: boolean
  onSubmit: (terms: OfferTerms) => Promise<void>
  onCancel?: () => void
}) {
  const asking = tiyinToSoum(askingTiyin)
  const [quantity, setQuantity] = React.useState(Math.min(initialQuantity, maxQuantity))
  const [unit, setUnit] = React.useState(
    initialUnitTiyin != null ? tiyinToSoum(initialUnitTiyin) : asking
  )
  const [message, setMessage] = React.useState("")
  const [agreed, setAgreed] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const clamp = (n: number) => Math.min(maxQuantity, Math.max(1, Math.floor(n) || 1))
  const total = quantity * unit
  const diffPct = asking > 0 && unit > 0 ? Math.round(((unit - asking) / asking) * 100) : 0
  const showConsent = requireConsent && needsConsent

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!(unit > 0)) {
      setError("Dona narxini kiriting.")
      return
    }
    setSubmitting(true)
    try {
      await onSubmit({
        quantity,
        unit_price: soumToTiyin(unit),
        message: message.trim() || undefined,
      })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.detail)
      } else {
        setError(err instanceof ApiError ? err.detail : "Yuborib boʻlmadi. Qayta urinib koʻring.")
      }
    } finally {
      setSubmitting(false)
    }
  }

  const busy = submitting || disabled

  return (
    <form onSubmit={submit} noValidate className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor={`${idPrefix}-qty`}>Miqdor</FieldLabel>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Kamaytirish"
              disabled={busy || quantity <= 1}
              onClick={() => setQuantity((q) => clamp(q - 1))}
            >
              <MinusIcon aria-hidden="true" />
            </Button>
            <Input
              id={`${idPrefix}-qty`}
              inputMode="numeric"
              className="w-20 text-center tabular-nums"
              value={String(quantity)}
              disabled={busy}
              onChange={(e) => setQuantity(clamp(Number(e.target.value.replace(/\D/g, ""))))}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Koʻpaytirish"
              disabled={busy || quantity >= maxQuantity}
              onClick={() => setQuantity((q) => clamp(q + 1))}
            >
              <PlusIcon aria-hidden="true" />
            </Button>
          </div>
          <FieldDescription>Mavjud: {formatNumber(maxQuantity)} dona</FieldDescription>
        </Field>

        <Field>
          <FieldLabel htmlFor={`${idPrefix}-unit`}>Narx (1 dona uchun)</FieldLabel>
          <PriceInput
            id={`${idPrefix}-unit`}
            value={unit}
            onChange={setUnit}
            disabled={busy}
            aria-invalid={error && !(unit > 0) ? true : undefined}
          />
          <FieldDescription>
            {unit > 0 && diffPct !== 0
              ? `Sotuvchi narxidan ${Math.abs(diffPct)}% ${diffPct < 0 ? "past" : "yuqori"} — taklif qilish mumkin.`
              : `Sotuvchi narxi: ${formatSom(asking)}. Istalgan narxni taklif qiling.`}
          </FieldDescription>
        </Field>
      </div>

      <div className="flex items-baseline justify-between gap-3 rounded-lg bg-muted px-3 py-2.5">
        <span className="text-sm text-muted-foreground">
          Jami: {formatNumber(quantity)} x {formatSom(unit)}
        </span>
        <span className="font-heading text-lg font-semibold tabular-nums text-foreground">
          {formatSom(total)}
        </span>
      </div>

      <Field>
        <FieldLabel htmlFor={`${idPrefix}-msg`}>Izoh (ixtiyoriy)</FieldLabel>
        <Textarea
          id={`${idPrefix}-msg`}
          rows={2}
          maxLength={MESSAGE_MAX}
          placeholder="Masalan: bugun olib keta olaman"
          value={message}
          disabled={busy}
          onChange={(e) => setMessage(e.target.value)}
        />
      </Field>

      {showConsent && (
        <div className="flex items-start gap-3">
          <Checkbox
            id={`${idPrefix}-consent`}
            checked={agreed}
            disabled={busy}
            onCheckedChange={(v) => setAgreed(v === true)}
            className="mt-0.5"
            aria-required="true"
          />
          <label htmlFor={`${idPrefix}-consent`} className="text-sm leading-snug text-foreground">
            Savdo qoidalari va ommaviy ofertani qabul qilaman — sotuvchi qabul qilsa, bitim tuziladi
          </label>
        </div>
      )}

      <FieldError>{error}</FieldError>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={submitting} disabled={busy || (showConsent && !agreed)}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" disabled={submitting} onClick={onCancel}>
            Bekor qilish
          </Button>
        )}
      </div>
    </form>
  )
}

export { OfferForm }
