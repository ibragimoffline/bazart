import {
  ShieldCheckIcon,
  TimerIcon,
  PercentIcon,
  HandshakeIcon,
  type LucideIcon,
} from "lucide-react"

import { SectionHeading } from "@/components/site/section-heading"

/**
 * Ishonch bloki — marketing shiorlarisiz, aniq faktlar bilan.
 * Faktlar loyihaning haqiqiy qoidalaridan (CLAUDE.md / docs). Har biri — oq karta:
 * 44px brand-subtle ikonka plitkasi + sarlavha + bitta jumla.
 */
const FACTS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: TimerIcon,
    title: "Majburiy deadline",
    text: "Har eʼlon 3, 5 yoki 7 kunda yopiladi — narx muzlab qolmaydi.",
  },
  {
    icon: HandshakeIcon,
    title: "Erkin narx",
    text: "Istalgan narxni taklif qiling — sotuvchi qabul qiladi yoki qarshi taklif beradi.",
  },
  {
    icon: ShieldCheckIcon,
    title: "Tasdiqlangan kontaktlar",
    text: "Telefon raqamlar faqat kelishuvdan keyin ochiladi. Mahsulotni koʻrmasdan toʻlamang.",
  },
  {
    icon: PercentIcon,
    title: "Xaridorga komissiya yoʻq",
    text: "Kelishilgan narxni sotuvchiga toʻgʻridan-toʻgʻri toʻlaysiz — Bazart toʻlovda ishtirok etmaydi.",
  },
]

function TrustBlock() {
  return (
    <section aria-labelledby="ishonch-sarlavha" className="pt-12">
      <SectionHeading id="ishonch-sarlavha" title="Nega Bazart" className="mb-5" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FACTS.map((f) => {
          const Icon = f.icon
          return (
            <div
              key={f.title}
              className="flex gap-4 rounded-lg border border-border bg-card p-5 sm:p-6"
            >
              <span className="grid size-11 shrink-0 place-items-center rounded-md bg-brand-subtle text-brand-subtle-foreground">
                <Icon className="size-5.5" aria-hidden="true" />
              </span>
              <div className="grid content-start gap-1">
                <h3 className="text-lg font-semibold text-foreground">{f.title}</h3>
                <p className="text-sm text-muted-foreground">{f.text}</p>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export { TrustBlock }
