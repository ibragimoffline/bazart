"use client"

import * as React from "react"
import { toast } from "sonner"

import { ApiError } from "@/lib/api/client"
import type { UserMe } from "@/lib/api/types"
import { updatePreferences } from "@/lib/api/profile"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"

type Language = UserMe["preferred_language"]

const OPTIONS: { value: Language; label: string }[] = [
  { value: "uz", label: "Oʻzbekcha" },
  { value: "ru", label: "Русский" },
]

/**
 * Bildirishnoma tili (SMS, Telegram, email). Interfeys o'zbekcha qoladi —
 * bu sozlama faqat server yuboradigan xabarlar tiliga ta'sir qiladi.
 */
function LanguagePreference({ me, onChange }: { me: UserMe; onChange: (me: UserMe) => void }) {
  const [saving, setSaving] = React.useState<Language | null>(null)

  const change = async (value: string) => {
    const lang = value as Language
    if (lang === me.preferred_language || saving) return
    setSaving(lang)
    try {
      const updated = await updatePreferences(lang)
      onChange(updated)
      toast.success("Til sozlamasi saqlandi.")
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : "Sozlamani saqlab boʻlmadi.")
    } finally {
      setSaving(null)
    }
  }

  return (
    <section className="grid gap-4 rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="lang_heading" className="text-base font-semibold text-foreground">
            Bildirishnoma tili
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            SMS, Telegram va email xabarlari shu tilda yuboriladi.
          </p>
        </div>
        {saving && <Spinner className="mt-1 text-muted-foreground" />}
      </div>

      <RadioGroup
        aria-labelledby="lang_heading"
        value={saving ?? me.preferred_language}
        onValueChange={change}
        disabled={saving !== null}
        className="flex flex-wrap gap-3"
      >
        {OPTIONS.map((o) => (
          <Label
            key={o.value}
            htmlFor={`lang_${o.value}`}
            className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md border border-border px-3 text-sm font-normal transition-colors hover:bg-muted has-data-[state=checked]:border-primary has-disabled:cursor-not-allowed has-disabled:opacity-50"
          >
            <RadioGroupItem
              id={`lang_${o.value}`}
              value={o.value}
              className="data-[state=checked]:border-primary data-[state=checked]:bg-primary"
            />
            {o.label}
          </Label>
        ))}
      </RadioGroup>
    </section>
  )
}

export { LanguagePreference }
