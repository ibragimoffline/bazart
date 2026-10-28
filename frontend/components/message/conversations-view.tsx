"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { MessageSquareIcon, ChevronRightIcon } from "lucide-react"

import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import { listConversations, type Conversation } from "@/lib/api/messages"
import { counterpartyLabel, formatMessageDateTime } from "@/components/message/message-meta"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * Foydalanuvchining suhbatlari ro'yxati. Auth talab qilinadi.
 *
 * Eslatma: ro'yxat endpointi (ConversationRead) xabar matnini yoki o'qilmagan
 * sonini QAYTARMAYDI — shuning uchun oxirgi xabar preview'i va o'qilmagan
 * hisoblagichi ko'rsatilmaydi (backend sxemasiga sodiq qolamiz).
 */
function ConversationsView() {
  const authStatus = useAuthStore((s) => s.status)
  const userId = useAuthStore((s) => s.user?.id ?? null)
  const pathname = usePathname()

  const [items, setItems] = React.useState<Conversation[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  // Yuklanish holati kaliti — effekt tanasida sinxron setState chaqirmaslik uchun
  // (react-hooks/set-state-in-effect). Natija .then/.catch da o'rnatiladi.
  const [loadedKey, setLoadedKey] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (authStatus !== "authenticated") return
    let alive = true
    listConversations()
      .then((data) => {
        if (!alive) return
        // Yangilangan vaqt bo'yicha kamayish tartibida.
        const sorted = [...data].sort(
          (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)
        )
        setItems(sorted)
        setError(null)
        setLoadedKey(authStatus)
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof ApiError ? e.detail : "Suhbatlarni yuklab boʻlmadi.")
        setLoadedKey(authStatus)
      })
    return () => {
      alive = false
    }
  }, [authStatus])

  if (authStatus === "idle") {
    return <ConversationsSkeleton />
  }

  if (authStatus === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <MessageSquareIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Xabarlaringizni koʻrish uchun hisobingizga kiring.
        </p>
        <Button asChild>
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  const showLoading = loadedKey !== authStatus

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Xabarlar</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Xaridor va sotuvchi bilan yozishmalaringiz.
        </p>
      </div>

      {showLoading ? (
        <ConversationsSkeleton />
      ) : error ? (
        <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
          <p className="text-sm font-medium text-destructive">{error}</p>
        </div>
      ) : items && items.length > 0 ? (
        <ul className="grid gap-3">
          {items.map((conv) => (
            <li key={conv.id}>
              <ConversationRow conv={conv} userId={userId} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="grid place-items-center gap-2 rounded-lg border border-dashed border-border bg-card px-6 py-16 text-center">
          <MessageSquareIcon className="size-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-base font-medium text-foreground">Hali xabar yoʻq</p>
          <p className="text-sm text-muted-foreground">
            Mahsulot sahifasida sotuvchiga yozib suhbat boshlashingiz mumkin.
          </p>
        </div>
      )}
    </div>
  )
}

function ConversationRow({
  conv,
  userId,
}: {
  conv: Conversation
  userId: number | null
}) {
  return (
    <Link
      href={`/messages/${conv.id}`}
      className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-colors outline-none hover:bg-muted/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="grid size-11 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
        <MessageSquareIcon className="size-5" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">
            {counterpartyLabel(conv, userId)}
          </span>
          {conv.item_id != null && (
            <span className="text-sm text-muted-foreground">Mahsulot #{conv.item_id}</span>
          )}
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Oxirgi faollik: {formatMessageDateTime(conv.updated_at)}
        </p>
      </div>
      <ChevronRightIcon
        className="size-5 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
    </Link>
  )
}

function ConversationsSkeleton() {
  return (
    <div className="grid gap-3">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-[76px] w-full rounded-lg" />
      ))}
    </div>
  )
}

export { ConversationsView }
