"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { ArrowLeftIcon, MessageSquareIcon, SendIcon } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import {
  getConversation,
  sendMessage,
  markMessageRead,
  type ConversationDetail,
  type Message,
} from "@/lib/api/messages"
import { counterpartyLabel, formatMessageTime } from "@/components/message/message-meta"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const MAX_BODY = 5000

/**
 * Bitta suhbat oynasi — xabar puufakchalari + yuborish formasi.
 * O'z xabarlar o'ngda (primary), qarshi tomon chapda (muted).
 */
function MessageThread({ conversationId }: { conversationId: number }) {
  const authStatus = useAuthStore((s) => s.status)
  const userId = useAuthStore((s) => s.user?.id ?? null)
  const pathname = usePathname()

  const [conv, setConv] = React.useState<ConversationDetail | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)

  const [draft, setDraft] = React.useState("")
  const [sending, setSending] = React.useState(false)

  // conversationId o'zgarsa — render vaqtida yuklash holatiga qaytamiz.
  const [dataId, setDataId] = React.useState(conversationId)
  if (dataId !== conversationId) {
    setDataId(conversationId)
    setConv(null)
    setError(null)
    setLoading(true)
    setDraft("")
  }

  // Qarshi tomonning o'qilmagan xabarlarini o'qilgan deb belgilash (fire-and-forget).
  const markIncomingRead = React.useCallback(
    (detail: ConversationDetail, uid: number | null) => {
      if (uid == null) return
      for (const m of detail.messages) {
        if (m.sender_id !== uid && !m.is_read) {
          markMessageRead(m.id).catch(() => {
            // O'qilgan belgisi kritik emas — xatoni yutamiz.
          })
        }
      }
    },
    []
  )

  const load = React.useCallback(
    (opts: { silent?: boolean } = {}) => {
      return getConversation(conversationId)
        .then((detail) => {
          setConv(detail)
          setError(null)
          setLoading(false)
          markIncomingRead(detail, userId)
        })
        .catch((e) => {
          if (opts.silent) {
            // Yangilash muvaffaqiyatsiz — mavjud ko'rinishni saqlaymiz.
            return
          }
          setError(e instanceof ApiError ? e.detail : "Suhbatni yuklab boʻlmadi.")
          setLoading(false)
        })
    },
    [conversationId, userId, markIncomingRead]
  )

  React.useEffect(() => {
    if (authStatus !== "authenticated") return
    let alive = true
    getConversation(conversationId)
      .then((detail) => {
        if (!alive) return
        setConv(detail)
        setError(null)
        setLoading(false)
        markIncomingRead(detail, userId)
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof ApiError ? e.detail : "Suhbatni yuklab boʻlmadi.")
        setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [conversationId, authStatus, userId, markIncomingRead])

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const body = draft.trim()
    if (!body || sending) return
    setSending(true)
    sendMessage(conversationId, body)
      .then(() => {
        setDraft("")
        // Yuborilgandan keyin xabarlarni qayta yuklaymiz (yangi xabar bilan).
        return load({ silent: true })
      })
      .catch((err) => {
        toast.error(
          err instanceof ApiError ? err.detail : "Xabarni yuborib boʻlmadi."
        )
      })
      .finally(() => {
        setSending(false)
      })
  }

  if (authStatus === "idle") {
    return <ThreadSkeleton />
  }

  if (authStatus === "anonymous") {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <MessageSquareIcon className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-base font-medium text-foreground">
          Suhbatni koʻrish uchun hisobingizga kiring.
        </p>
        <Button asChild>
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  if (loading) {
    return <ThreadSkeleton />
  }

  if (error || !conv) {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <p className="text-base font-medium text-foreground">
          {error ?? "Suhbat topilmadi"}
        </p>
        <Button asChild variant="outline" size="sm">
          <Link href="/messages">Xabarlarga qaytish</Link>
        </Button>
      </div>
    )
  }

  const title = counterpartyLabel(conv, userId)

  return (
    <div className="grid gap-4">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="icon-sm" aria-label="Orqaga">
          <Link href="/messages">
            <ArrowLeftIcon aria-hidden="true" />
          </Link>
        </Button>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-foreground">{title}</h1>
          {conv.item_id != null && (
            <Link
              href={`/lot/${conv.item_id}`}
              className="text-sm text-primary underline-offset-4 outline-none underline decoration-foreground/30 hover:decoration-foreground focus-visible:underline"
            >
              Mahsulot #{conv.item_id}
            </Link>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        {conv.messages.length === 0 ? (
          <div className="grid place-items-center gap-2 py-12 text-center">
            <MessageSquareIcon
              className="size-7 text-muted-foreground"
              aria-hidden="true"
            />
            <p className="text-sm text-muted-foreground">
              Hali xabar yoʻq. Birinchi boʻlib yozing.
            </p>
          </div>
        ) : (
          <ul className="grid gap-3">
            {conv.messages.map((m) => (
              <li key={m.id}>
                <MessageBubble message={m} own={m.sender_id === userId} />
              </li>
            ))}
          </ul>
        )}
      </div>

      <form onSubmit={handleSend} className="grid gap-2">
        <label htmlFor="message-body" className="sr-only">
          Xabar matni
        </label>
        <textarea
          id="message-body"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={MAX_BODY}
          rows={3}
          placeholder="Xabar yozing…"
          disabled={sending}
          className="w-full min-w-0 resize-y rounded-md border border-input bg-transparent px-3 py-2 text-base transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 md:text-sm dark:bg-input/30"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground tabular-nums">
            {draft.length}/{MAX_BODY}
          </span>
          <Button type="submit" loading={sending} disabled={!draft.trim()}>
            {!sending && <SendIcon aria-hidden="true" />}
            Yuborish
          </Button>
        </div>
      </form>
    </div>
  )
}

function MessageBubble({ message, own }: { message: Message; own: boolean }) {
  return (
    <div className={own ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          "max-w-[80%] rounded-lg px-3 py-2 " +
          (own
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground")
        }
      >
        <p className="text-sm break-words whitespace-pre-wrap">{message.body}</p>
        <span
          className={
            "mt-1 block text-right text-xs tabular-nums " +
            (own ? "text-primary-foreground/70" : "text-muted-foreground")
          }
        >
          {formatMessageTime(message.created_at)}
        </span>
      </div>
    </div>
  )
}

function ThreadSkeleton() {
  return (
    <div className="grid gap-4">
      <Skeleton className="h-8 w-40" />
      <div className="grid gap-3 rounded-lg border border-border bg-card p-4">
        <Skeleton className="h-12 w-2/3 rounded-lg" />
        <Skeleton className="h-12 w-1/2 justify-self-end rounded-lg" />
        <Skeleton className="h-12 w-3/5 rounded-lg" />
      </div>
      <Skeleton className="h-24 w-full rounded-md" />
    </div>
  )
}

export { MessageThread }
