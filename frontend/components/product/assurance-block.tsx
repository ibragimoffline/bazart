import { ShieldCheckIcon, KeyRoundIcon, ScaleIcon, type LucideIcon } from "lucide-react"

/**
 * Xaridor kafolatlari bloki — platformaning HAQIQIY himoya mexanizmi.
 * Bu yerda hech qanday kuryer xizmati / bepul yetkazish / qaytarish-kafolat
 * VA'DASI yo'q — ular platformada mavjud emas. Faqat escrow + kod bilan
 * topshirish + nizo (docs/PAYMENTS.md, handover oqimi).
 */
const ROWS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: ShieldCheckIcon,
    title: "Escrow himoyasi",
    text: "Bitim tuzilgach (auksionda gʻalaba yoki qabul qilingan taklif) toʻlov kartangizda bloklanadi — sotuvchiga darhol oʻtmaydi. Tovarni olib tasdiqlaguningizcha mablagʻ sizniki.",
  },
  {
    icon: KeyRoundIcon,
    title: "Kod bilan topshirish",
    text: "Sotuvchi bilan kelishilgan tarzda (uchrashuv yoki yetkazish) tovarni oling, soʻng sotuvchi bergan maxfiy kodni kiriting. Kod — qabul dalili; faqat shundan keyin pul sotuvchiga oʻtadi.",
  },
  {
    icon: ScaleIcon,
    title: "Nizo himoyasi",
    text: "Tovar kelmasa yoki tavsifga mos boʻlmasa — kodni tasdiqlamang va nizo oching. Bloklangan mablagʻ qaytarilishi mumkin.",
  },
]

function AssuranceBlock() {
  return (
    <div className="grid gap-4 rounded-xl border border-border bg-card p-4 sm:p-5">
      {ROWS.map((r) => {
        const Icon = r.icon
        return (
          <div key={r.title} className="flex gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-muted text-foreground">
              <Icon className="size-5" aria-hidden="true" />
            </span>
            <div className="grid gap-0.5">
              <h3 className="text-sm font-semibold text-foreground">{r.title}</h3>
              <p className="text-sm text-muted-foreground">{r.text}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export { AssuranceBlock }
