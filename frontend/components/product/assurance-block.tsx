import { PhoneIcon, ShieldAlertIcon, FlagIcon, type LucideIcon } from "lucide-react"

/**
 * Xaridor eslatmalari bloki — platformaning HAQIQIY himoya mexanizmi.
 * Bazart toʻlovda ishtirok etmaydi (Faza E, docs/DEALS.md): hech qanday escrow,
 * kuryer yoki qaytarish kafolati vaʼda qilinmaydi.
 */
const ROWS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: PhoneIcon,
    title: "Kelishuvdan keyin aloqa",
    text: "Taklif qabul qilinsa yoki auksionda gʻolib chiqsangiz, sotuvchining tasdiqlangan telefoni ochiladi. Uchrashuvni oʻzingiz kelishasiz.",
  },
  {
    icon: ShieldAlertIcon,
    title: "Oldindan toʻlamang",
    text: "Mahsulotni koʻrmasdan va tekshirmasdan pul oʻtkazmang. Bazart toʻlovda ishtirok etmaydi va pulni qaytara olmaydi.",
  },
  {
    icon: FlagIcon,
    title: "Shikoyat",
    text: "Sotuvchi aldasa yoki mahsulot tavsifga mos kelmasa — shikoyat qoldiring. Moderator koʻrib chiqadi va hisobni cheklashi mumkin.",
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
