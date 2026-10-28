"use client"

import * as React from "react"
import { CheckIcon, SendIcon } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import type { UserMe } from "@/lib/api/types"
import { linkTelegram } from "@/lib/api/profile"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldLabel, FieldError, FieldDescription } from "@/components/ui/field"

/** Chat ID shaxsiy kanal — ekranda faqat oxirgi 4 raqami ko'rsatiladi. */
function maskChatId(chatId: string): string {
  const tail = chatId.slice(-4)
  return chatId.length > 4 ? `•••• ${tail}` : tail
}

/** Telegram chat ID: ixtiyoriy minus (guruh) + raqamlar. */
const CHAT_ID_RE = /^-?\d{3,20}$/

/** Telegram bildirishnomalari: ulangan holat yoki chat ID kiritish formasi. */
function TelegramLink({ me, onChange }: { me: UserMe; onChange: (me: UserMe) => void }) {
  const linked = Boolean(me.telegram_chat_id)
  const [editing, setEditing] = React.useState(false)
  const [chatId, setChatId] = React.useState("")
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const showForm = !linked || editing

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const value = chatId.trim()
    if (!CHAT_ID_RE.test(value)) {
      setError("Chat ID faqat raqamlardan iborat boʻlsin.")
      return
    }
    setError(null)
    setSaving(true)
    try {
      const updated = await linkTelegram(value)
      onChange(updated)
      setEditing(false)
      setChatId("")
      toast.success("Telegram ulandi.")
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Telegramni ulab boʻlmadi. Qayta urinib koʻring.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="grid gap-4 rounded-lg border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-foreground">Telegram bildirishnomalari</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Taklif, gʻalaba va kelishuv haqidagi xabarlar Telegram orqali ham keladi.
          </p>
        </div>
        {linked && (
          <Badge variant="success">
            <CheckIcon aria-hidden="true" />
            Ulangan
          </Badge>
        )}
      </div>

      {linked && !editing && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-foreground">
            Chat ID:{" "}
            <span className="font-mono tabular-nums">{maskChatId(me.telegram_chat_id ?? "")}</span>
          </p>
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            Oʻzgartirish
          </Button>
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} noValidate className="grid gap-3">
          <Field>
            <FieldLabel htmlFor="telegram_chat_id">Chat ID</FieldLabel>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="telegram_chat_id"
                inputMode="numeric"
                autoComplete="off"
                placeholder="123456789"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                aria-invalid={error ? true : undefined}
                aria-describedby="telegram_hint"
                className="sm:max-w-60"
              />
              <div className="flex gap-2">
                <Button type="submit" loading={saving} disabled={chatId.trim() === ""}>
                  <SendIcon aria-hidden="true" />
                  Ulash
                </Button>
                {editing && (
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={saving}
                    onClick={() => {
                      setEditing(false)
                      setChatId("")
                      setError(null)
                    }}
                  >
                    Bekor qilish
                  </Button>
                )}
              </div>
            </div>
            <FieldDescription id="telegram_hint">
              Telegram chat ID raqamingizni kiriting. Uni chat ID koʻrsatuvchi istalgan
              Telegram bot orqali bilib olishingiz mumkin — botga xabar yozing, u raqamni
              qaytaradi.
            </FieldDescription>
            <FieldError>{error}</FieldError>
          </Field>
        </form>
      )}
    </section>
  )
}

export { TelegramLink }
