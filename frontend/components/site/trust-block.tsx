import {
  ShieldCheckIcon,
  TimerIcon,
  PercentIcon,
  HandshakeIcon,
  type LucideIcon,
} from "lucide-react"

/**
 * Ishonch bloki — marketing shiorlarisiz, aniq faktlar bilan.
 * Faktlar loyihaning haqiqiy qoidalaridan (CLAUDE.md / docs).
 * Siyoh rangli to'liq kenglikdagi blok: sahifa ritmini bo'ladi (qog'oz -> siyoh -> qog'oz).
 */
const FACTS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: ShieldCheckIcon,
    title: "Tasdiqlangan kontaktlar",
    text: "Telefon raqamlar faqat kelishuvdan keyin ochiladi. Mahsulotni koʻrmasdan toʻlamang.",
  },
  {
    icon: TimerIcon,
    title: "Majburiy deadline",
    text: "Har eʼlon 3, 5 yoki 7 kunda yopiladi — narx muzlab qolmaydi.",
  },
  {
    icon: PercentIcon,
    title: "Xaridorga komissiya yoʻq",
    text: "Kelishilgan narxni toʻgʻridan-toʻgʻri sotuvchiga toʻlaysiz — Bazart toʻlovda ishtirok etmaydi.",
  },
  {
    icon: HandshakeIcon,
    title: "Erkin narx",
    text: "Istalgan narx va miqdorni taklif qiling — sotuvchi qabul qiladi yoki qarshi taklif beradi.",
  },
]

function TrustBlock() {
  return (
    <section
      aria-labelledby="ishonch-sarlavha"
      className="mx-auto mt-14 max-w-6xl sm:px-6 md:mt-20"
    >
      <div className="bg-foreground px-4 py-10 text-background sm:rounded-xl sm:px-10 sm:py-12">
        <h2
          id="ishonch-sarlavha"
          className="font-heading text-xl font-bold tracking-tight uppercase md:text-2xl"
        >
          Nega Bazart
        </h2>
        <p className="mt-2 max-w-md text-sm text-background/70">
          Oddiy eʼlonlar taxtasi emas — har savdoda muddat, raqobat va himoya bor.
        </p>
        <div className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-4">
          {FACTS.map((f) => {
            const Icon = f.icon
            return (
              <div key={f.title} className="grid content-start gap-2">
                <span className="grid size-10 place-items-center rounded-full border border-background/25">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <h3 className="mt-1 text-sm font-semibold">{f.title}</h3>
                <p className="text-xs text-background/70 sm:text-sm">{f.text}</p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

export { TrustBlock }
