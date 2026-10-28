"use client"

import * as React from "react"
import { TimerIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * "Muddat chizigʻi" — platformaning imzo elementi.
 *
 * Har mahsulot fotosining pastki chetida jonli countdown chipi + 4px o'lchagich.
 * Qolgan vaqt sari kuchayadi: xotirjam (scrim, > 6 soat) -> diqqat (warning,
 * ≤ 6 soat, quyuq matn) -> shoshilinch (error, ≤ 30 daqiqa). Matn rangli fon
 * USTIDA — scrim ustidagi amber matn kontrasti (2.4:1) muammosi shu bilan yopiladi.
 * Faqat raqam yangilanadi (CSS animatsiya yo'q) — prefers-reduced-motion'ga mos.
 */

function pad(n: number): string {
  return n.toString().padStart(2, "0")
}

function format(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (days >= 1) return `${days} kun ${pad(hours)}:${pad(mins)}`
  return `${pad(hours)}:${pad(mins)}:${pad(secs)}`
}

type Level = "calm" | "warn" | "urgent"

function levelFor(minutesLeft: number): Level {
  if (minutesLeft <= 30) return "urgent"
  if (minutesLeft <= 360) return "warn"
  return "calm"
}

/** Foto ustidagi chip: rangli fon + unga mos matn. */
const PHOTO_CHIP: Record<Level, string> = {
  calm: "bg-scrim text-scrim-foreground",
  warn: "bg-warning text-warning-foreground",
  urgent: "bg-error text-error-foreground",
}
const PHOTO_FILL: Record<Level, string> = {
  calm: "bg-scrim-foreground",
  warn: "bg-warning",
  urgent: "bg-error",
}
/** Matn ichidagi (flat) chip: tonal juftliklar. */
const FLAT_CHIP: Record<Level, string> = {
  calm: "border border-border bg-muted text-foreground",
  warn: "bg-warning-subtle text-warning-subtle-foreground",
  urgent: "bg-error-subtle text-error-subtle-foreground",
}

function DeadlineBar({
  endsAt,
  endsInMinutes,
  windowMinutes = 4320,
  inline = false,
  size = "md",
  className,
}: {
  /** Haqiqiy tugash vaqti (ISO/Date) — backend auction.end_time / listing_ends_at. */
  endsAt?: string | number | Date
  /** Muqobil: mount'dan boshlab qolgan daqiqa (namuna ma'lumot uchun). */
  endsInMinutes?: number
  /** Savdo oynasi uzunligi (3/5/7 kun) — o'lchagich shu bo'yicha to'ladi. */
  windowMinutes?: number
  /** true — matn ichidagi chip (sahifa sarlavhasi, ro'yxat qatorlari). */
  inline?: boolean
  /** Inline chip o'lchami: md 28px, lg 36px. */
  size?: "md" | "lg"
  className?: string
}) {
  // Boshlang'ich qiymat deterministik (Date.now yo'q) — birinchi render xavfsiz.
  const [remaining, setRemaining] = React.useState((endsInMinutes ?? windowMinutes) * 60_000)

  React.useEffect(() => {
    const end =
      endsAt != null ? new Date(endsAt).getTime() : Date.now() + (endsInMinutes ?? 0) * 60_000
    const tick = () => setRemaining(Math.max(0, end - Date.now()))
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [endsAt, endsInMinutes])

  const level = levelFor(remaining / 60_000)
  const pct = Math.max(0, Math.min(100, (remaining / (windowMinutes * 60_000)) * 100))
  const ended = remaining <= 0
  const label = ended ? "Tugadi" : format(remaining)

  if (inline) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full font-semibold tabular-nums",
          size === "lg" ? "h-9 pr-3.5 pl-3 text-sm" : "h-7 pr-2.5 pl-2 text-xs",
          FLAT_CHIP[level],
          className
        )}
      >
        <TimerIcon className="size-3.5" aria-hidden="true" />
        {ended ? label : `${label} qoldi`}
      </span>
    )
  }

  // Foto ustida: pastki chetdan 10px ichkarida chip + qolgan joyni to'ldiruvchi o'lchagich.
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-x-2.5 bottom-2.5 flex items-center gap-2",
        className
      )}
    >
      <span
        className={cn(
          "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full pr-2.5 pl-2 text-xs font-semibold whitespace-nowrap tabular-nums",
          PHOTO_CHIP[level]
        )}
      >
        <TimerIcon className="size-3.5" aria-hidden="true" />
        {label}
      </span>
      {!ended && (
        <span
          role="progressbar"
          aria-label="Savdo muddati"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pct)}
          className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-scrim-foreground/55"
        >
          <span
            className={cn("block h-full rounded-full", PHOTO_FILL[level])}
            style={{ width: `${pct}%` }}
          />
        </span>
      )}
    </div>
  )
}

export { DeadlineBar }
