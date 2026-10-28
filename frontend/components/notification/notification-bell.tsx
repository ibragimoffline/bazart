"use client"

import * as React from "react"
import Link from "next/link"
import { BellIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useAuthStore } from "@/lib/store/auth"
import { unreadNotificationsCount } from "@/lib/api/engagement"

/**
 * Header uchun bildirishnoma qo'ng'irog'i.
 *
 * Faqat autentifikatsiyadan o'tgan foydalanuvchiga ko'rinadi (anonim ->
 * hech narsa render qilinmaydi — header uni sahifada joylashtiradi).
 * O'qilmagan sonini backend'dan oladi va nishoncha ko'rsatadi.
 */
function NotificationBell({ className }: { className?: string }) {
  const status = useAuthStore((s) => s.status)
  const authed = status === "authenticated"
  const [unread, setUnread] = React.useState(0)

  React.useEffect(() => {
    // Anonim holatda komponent null render qiladi — sonni yangilash shart emas.
    if (!authed) return
    let alive = true
    unreadNotificationsCount()
      .then((count) => {
        if (alive) setUnread(count)
      })
      .catch(() => {
        // Sonini olib bo'lmasa — nishonchasiz qo'ng'iroq ko'rsatamiz.
        if (alive) setUnread(0)
      })
    return () => {
      alive = false
    }
  }, [authed])

  // Anonim yoki holat aniqlanmagan bo'lsa — qo'ng'iroq ko'rsatilmaydi.
  if (!authed) return null

  const hasUnread = unread > 0
  const badgeText = unread > 99 ? "99+" : String(unread)

  return (
    <Link
      href="/notifications"
      aria-label={
        hasUnread
          ? `Bildirishnomalar, ${unread} ta oʻqilmagan`
          : "Bildirishnomalar"
      }
      className={cn(
        "relative inline-flex size-11 shrink-0 items-center justify-center rounded-full text-foreground outline-none transition-colors duration-150 hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className
      )}
    >
      <BellIcon className="size-5.5" aria-hidden="true" />
      {hasUnread && (
        <span
          className="absolute top-1 right-1 inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-error px-1 text-xs font-bold text-error-foreground tabular-nums ring-2 ring-card"
          aria-hidden="true"
        >
          {badgeText}
        </span>
      )}
    </Link>
  )
}

export { NotificationBell }
