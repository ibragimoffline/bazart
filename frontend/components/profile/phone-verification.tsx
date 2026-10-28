"use client"

import * as React from "react"
import { BadgeCheckIcon, PencilIcon } from "lucide-react"
import { toast } from "sonner"

import type { UserMe } from "@/lib/api/types"
import { formatUzPhone } from "@/lib/phone"
import { useAuthStore } from "@/lib/store/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PhoneVerifyForm } from "@/components/phone/phone-verify-form"

type Props = {
  me: UserMe
  /** Profilni serverdan qayta o'qish (badge server holatini aks ettirishi uchun). */
  onRefresh: () => Promise<void>
}

/**
 * Telefon tasdig'i bloki (profil). Raqam faqat SMS kod orqali yoziladi va almashtiriladi:
 * tasdiqlangan raqam yangisi tasdiqlanmaguncha joyida qoladi (bid/taklif uzilmaydi).
 * Badge faqat server holatidan (`phone_verified_at`) kelib chiqadi.
 */
function PhoneVerification({ me, onRefresh }: Props) {
  const verified = Boolean(me.phone_verified_at && me.phone)
  const [editing, setEditing] = React.useState(false)

  const done = async () => {
    await Promise.all([onRefresh(), useAuthStore.getState().loadMe()])
    setEditing(false)
    toast.success(verified ? "Telefon raqami almashtirildi." : "Telefon raqami tasdiqlandi.")
  }

  return (
    <section className="grid gap-4 rounded-lg border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-foreground">Telefon tasdigʻi</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Bid, taklif va xarid uchun kerak. Kelishuvda raqam ikkinchi tomonga koʻrinadi.
          </p>
        </div>
        {verified ? (
          <Badge variant="success">
            <BadgeCheckIcon aria-hidden="true" />
            Tasdiqlangan
          </Badge>
        ) : (
          <Badge variant="outline">Tasdiqlanmagan</Badge>
        )}
      </div>

      {verified && !editing && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm font-medium tabular-nums text-foreground">
            {formatUzPhone(me.phone)}
          </p>
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <PencilIcon aria-hidden="true" />
            Raqamni oʻzgartirish
          </Button>
        </div>
      )}

      {(!verified || editing) && (
        <div className="grid gap-3">
          <PhoneVerifyForm
            idPrefix="profile-phone"
            verifiedPhone={verified ? me.phone : null}
            onVerified={done}
          />
          {editing && (
            <div>
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                Bekor qilish
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export { PhoneVerification }
