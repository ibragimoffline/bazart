"use client"

import * as React from "react"

import { formatSom, soumToTiyin, tiyinToSoum } from "@/lib/format"
import type { OfferTerms } from "@/lib/api/offers"
import { ApiError } from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import { PriceInput } from "@/components/seller/sell/price-input"

const MESSAGE_MAX = 500

/**
 * Taklif / qarshi taklif shakli: narx (har e'lon — 1 dona).
 *
 * Narx erkin: istalgan musbat summa (mo'ljal narxdan past ham, yuqori ham) —
 * mo'ljal narx bilan solishtirish faqat ma'lumot uchun, hech narsani bloklamaydi.
 * Yakuniy jami server tomonida hisoblanadi (bu yerda — ko'rsatish uchun).
 */
function OfferForm({
  idPrefix,
  askingTiyin,
  initialUnitTiyin,
  submitLabel,
  requireConsent = false,
  needsConsent = false,
  disabled = false,
  onSubmit,
  onCancel,
}: {
  idPrefix: string
  /** Sotuvchining mo'ljal narxi — solishtirish uchun. */
  askingTiyin: string
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
  const [unit, setUnit] = React.useState(
    initialUnitTiyin != null ? tiyinToSoum(initialUnitTiyin) : asking
  )
  const [message, setMessage] = React.useState("")
  const [agreed, setAgreed] = React.useState(false)
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const diffPct = asking > 0 && unit > 0 ? Math.round(((unit - asking) / asking) * 100) : 0
  const showConsent = requireConsent && needsConsent

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!(unit > 0)) {
      setError("Narxni kiriting.")
      return
    }
    setSubmitting(true)
    try {
      await onSubmit({
        quantity: 1,
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
      <Field>
        <FieldLabel htmlFor={`${idPrefix}-unit`}>Narx</FieldLabel>
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
