"use client"

import * as React from "react"
import { toast } from "sonner"
import { HandCoinsIcon } from "lucide-react"

import { formatTiyin } from "@/lib/format"
import { ApiError } from "@/lib/api/client"
import type { Auction } from "@/lib/api/types"
import { acceptSecondChance } from "@/lib/api/endpoints"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/lot/confirm-dialog"

const deadlineFormatter = new Intl.DateTimeFormat("uz-UZ", {
  day: "numeric",
  month: "long",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Tashkent",
})

/**
 * Sotuvchi uchun "ikkinchi imkoniyat": rezerv qoplanmagan auksionni muddat
 * ichida eng yuqori taklifga sotish. Ko'rsatish shartini chaqiruvchi tekshiradi.
 */
function SecondChanceCard({
  auction,
  onAccepted,
}: {
  auction: Auction
  onAccepted: () => void
}) {
  const [open, setOpen] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const deadline = auction.second_chance_expires_at
    ? deadlineFormatter.format(new Date(auction.second_chance_expires_at))
    : null

  const accept = async () => {
    setError(null)
    setBusy(true)
    try {
      await acceptSecondChance(auction.id)
      toast.success("Mahsulot eng yuqori taklifga sotildi — buyurtma yaratildi")
      setOpen(false)
      onAccepted()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Sotib boʻlmadi. Qayta urinib koʻring.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="grid gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-2">
        <HandCoinsIcon className="size-5 shrink-0 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold text-foreground">
          Rezerv narx qoplanmadi
        </h2>
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">
        Auksion yakunlandi, lekin eng yuqori taklif siz belgilagan rezerv narxga
        yetmadi. Xohlasangiz, mahsulotni shu taklifga sotishingiz mumkin.
      </p>
      <ul className="grid gap-1 text-sm text-muted-foreground">
        <li className="flex justify-between gap-4">
          <span>Eng yuqori taklif</span>
          <span className="font-semibold tabular-nums text-foreground">
            {formatTiyin(auction.current_price)}
          </span>
        </li>
        {deadline && (
          <li className="flex justify-between gap-4">
            <span>Qaror muddati</span>
            <span className="tabular-nums text-foreground">{deadline}</span>
          </li>
        )}
      </ul>
      <Button size="lg" onClick={() => setOpen(true)}>
        <HandCoinsIcon aria-hidden="true" />
        Eng yuqori taklifga sotish
      </Button>

      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Eng yuqori taklifga sotasizmi?"
        description={`Mahsulot ${formatTiyin(auction.current_price)} narxga sotiladi va gʻolib bilan buyurtma yaratiladi.`}
        confirmLabel="Sotish"
        loading={busy}
        error={error}
        onConfirm={accept}
      >
        <p className="text-sm leading-relaxed text-muted-foreground">
          Tasdiqlangandan keyin qarorni bekor qilib boʻlmaydi.
        </p>
      </ConfirmDialog>
    </section>
  )
}

export { SecondChanceCard }
