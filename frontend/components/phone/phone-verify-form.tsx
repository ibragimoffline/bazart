"use client"

import * as React from "react"
import { RotateCwIcon } from "lucide-react"

import { ApiError } from "@/lib/api/client"
import { requestPhoneOtp, verifyPhoneOtp } from "@/lib/api/profile"
import { formatLocal, formatUzPhone, localDigits, normalizeUzPhone } from "@/lib/phone"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"

const CODE_LENGTH = 6

function mmss(totalSeconds: number): string {
  const s = Math.max(0, totalSeconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
}

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.detail : fallback
}

type Props = {
  /** Hozir tasdiqlangan raqam (almashtirish oqimi) yoki null (birinchi tasdiq). */
  verifiedPhone?: string | null
  /** Raqam tasdiqlangach chaqiriladi. */
  onVerified: () => void | Promise<void>
  /** Formadagi id'lar to'qnashmasin (sahifada ikki forma bo'lishi mumkin). */
  idPrefix?: string
}

/**
 * Telefonni SMS kod bilan tasdiqlash: raqam -> kod -> tasdiq. Server qoidalari (5 daqiqa,
 * 5 urinish, 60 soniya cooldown) shu yerda faqat ko'rsatiladi — tekshiruv serverda.
 * Tasdiqlangan raqamni almashtirishda server parol so'rasa (`reauth_required`), parol maydoni
 * ochiladi; Google bilan kirganlar o'rniga qayta kirishi mumkin.
 */
function PhoneVerifyForm({ verifiedPhone = null, onVerified, idPrefix = "phone" }: Props) {
  const [local, setLocal] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [needPassword, setNeedPassword] = React.useState(false)
  const [sentTo, setSentTo] = React.useState<string | null>(null)
  const [code, setCode] = React.useState("")
  const [debugCode, setDebugCode] = React.useState<string | null>(null)
  const [expiresAt, setExpiresAt] = React.useState(0)
  const [resendAt, setResendAt] = React.useState(0)
  const [now, setNow] = React.useState(() => Date.now())
  const [busy, setBusy] = React.useState<"send" | "verify" | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const phone = normalizeUzPhone(local)
  const sameAsVerified = verifiedPhone != null && phone === verifiedPhone
  const secondsLeft = Math.ceil((expiresAt - now) / 1000)
  const resendIn = Math.ceil((resendAt - now) / 1000)
  const expired = sentTo !== null && secondsLeft <= 0

  React.useEffect(() => {
    if (sentTo === null) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [sentTo])

  const send = async (target: string) => {
    setError(null)
    setBusy("send")
    try {
      const res = await requestPhoneOtp(target, needPassword ? password : undefined)
      const t = Date.now()
      setSentTo(target)
      setCode("")
      setDebugCode(res.debug_code)
      setNow(t)
      setExpiresAt(Date.parse(res.expires_at))
      setResendAt(t + res.resend_after_seconds * 1000)
    } catch (e) {
      if (e instanceof ApiError && e.code === "reauth_required") setNeedPassword(true)
      if (e instanceof ApiError && e.status === 429) {
        const wait = Number(/(\d+) soniya/.exec(e.detail)?.[1] ?? 0)
        if (wait > 0) setResendAt(Date.now() + wait * 1000)
      }
      setError(errorText(e, "Kod yuborib boʻlmadi. Qayta urinib koʻring."))
    } finally {
      setBusy(null)
    }
  }

  const submitPhone = (e: React.FormEvent) => {
    e.preventDefault()
    if (!phone) {
      setError("Raqamni toʻliq kiriting: +998 XX XXX XX XX.")
      return
    }
    if (sameAsVerified) {
      setError("Bu raqam allaqachon tasdiqlangan.")
      return
    }
    if (needPassword && !password) {
      setError("Joriy parolni kiriting yoki qaytadan tizimga kiring.")
      return
    }
    void send(phone)
  }

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sentTo || code.length !== CODE_LENGTH || busy) return
    setError(null)
    setBusy("verify")
    try {
      await verifyPhoneOtp(sentTo, code)
      await onVerified()
    } catch (err) {
      setError(errorText(err, "Kodni tekshirib boʻlmadi. Qayta urinib koʻring."))
    } finally {
      setBusy(null)
    }
  }

  if (sentTo === null) {
    return (
      <form onSubmit={submitPhone} noValidate className="grid gap-4">
        <Field>
          <FieldLabel htmlFor={`${idPrefix}-number`}>
            {verifiedPhone ? "Yangi telefon raqam" : "Telefon raqam"}
          </FieldLabel>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-border bg-muted px-3 py-1.5 text-sm tabular-nums text-muted-foreground">
              +998
            </span>
            <Input
              id={`${idPrefix}-number`}
              type="tel"
              inputMode="numeric"
              autoComplete="tel-national"
              placeholder="90 123 45 67"
              className="tabular-nums"
              value={formatLocal(local)}
              onChange={(e) => setLocal(localDigits(e.target.value))}
              disabled={busy !== null}
              aria-invalid={error ? true : undefined}
              aria-describedby={`${idPrefix}-number-hint`}
            />
          </div>
          <FieldDescription id={`${idPrefix}-number-hint`}>
            Shu raqamga 6 xonali kod yuboriladi. Kelishuvda raqamingiz ikkinchi tomonga koʻrinadi.
          </FieldDescription>
        </Field>

        {needPassword && (
          <Field>
            <FieldLabel htmlFor={`${idPrefix}-password`}>Joriy parol</FieldLabel>
            <Input
              id={`${idPrefix}-password`}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy !== null}
            />
            <FieldDescription>
              Google orqali kirgan boʻlsangiz, chiqib qaytadan kiring — keyingi 15 daqiqada parol
              soʻralmaydi.
            </FieldDescription>
          </Field>
        )}

        <FieldError role="alert">{error}</FieldError>
        <Button type="submit" loading={busy === "send"} disabled={busy !== null}>
          Kod yuborish
        </Button>
      </form>
    )
  }

  return (
    <form onSubmit={submitCode} noValidate className="grid gap-4">
      <p className="text-sm text-muted-foreground">
        Kod <span className="font-medium tabular-nums text-foreground">{formatUzPhone(sentTo)}</span>{" "}
        raqamiga yuborildi.{" "}
        <button
          type="button"
          className="rounded-sm text-foreground underline decoration-foreground/30 underline-offset-4 outline-none hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          onClick={() => {
            setSentTo(null)
            setError(null)
          }}
          disabled={busy !== null}
        >
          Raqamni oʻzgartirish
        </button>
      </p>

      <Field>
        <FieldLabel htmlFor={`${idPrefix}-code`}>SMS kod</FieldLabel>
        <Input
          // Kod bosqichi ochilganda kursor darhol kod maydonida (klaviatura / SMS autofill).
          autoFocus
          id={`${idPrefix}-code`}
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]*"
          maxLength={CODE_LENGTH}
          placeholder="______"
          className="max-w-40 text-center font-mono text-lg tracking-widest"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, CODE_LENGTH))}
          disabled={busy !== null || expired}
          aria-invalid={error ? true : undefined}
          aria-describedby={`${idPrefix}-code-timer`}
        />
        <FieldDescription id={`${idPrefix}-code-timer`} aria-live="polite">
          {expired
            ? "Kod muddati tugadi — yangi kod soʻrang."
            : `Kod ${mmss(secondsLeft)} davomida amal qiladi.`}
          {debugCode ? ` Test kodi: ${debugCode}` : ""}
        </FieldDescription>
      </Field>

      <FieldError role="alert">{error}</FieldError>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="submit"
          loading={busy === "verify"}
          disabled={busy !== null || expired || code.length !== CODE_LENGTH}
        >
          Tasdiqlash
        </Button>
        <Button
          type="button"
          variant="outline"
          loading={busy === "send"}
          disabled={busy !== null || resendIn > 0}
          onClick={() => void send(sentTo)}
        >
          <RotateCwIcon aria-hidden="true" />
          {resendIn > 0 ? `Qayta yuborish (${resendIn})` : "Qayta yuborish"}
        </Button>
      </div>
    </form>
  )
}

export { PhoneVerifyForm }
