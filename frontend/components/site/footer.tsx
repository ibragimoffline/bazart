import Link from "next/link"

import { Logo } from "@/components/site/logo"

/** Faqat mavjud sahifalarga havolalar — yo'q sahifaga "o'lik" havola qo'yilmaydi. */
const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Xaridorlarga",
    links: [
      { href: "/catalog/hammasi", label: "Barcha mahsulotlar" },
      { href: "/catalog/hammasi?sort=ending", label: "Tez tugaydi" },
      { href: "/offers", label: "Takliflarim" },
      { href: "/my/watchlist", label: "Kuzatuvlarim" },
    ],
  },
  {
    title: "Sotuvchilarga",
    links: [
      { href: "/sell", label: "Mahsulot joylash" },
      { href: "/my/listings", label: "Mening mahsulotlarim" },
      { href: "/orders", label: "Buyurtmalarim" },
    ],
  },
  {
    title: "Bazart",
    links: [{ href: "mailto:yordam@bazart.uz", label: "Aloqa: yordam@bazart.uz" }],
  },
]

function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border bg-card">
      <div className="mx-auto grid max-w-page gap-8 px-4 py-10 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
        <div className="grid content-start gap-3">
          <Logo size="sm" className="w-fit" />
          <p className="max-w-xs text-sm text-muted-foreground">
            Har bir eʼlonda majburiy muddat: narx taklifi yoki auksion. Mahsulotlar oylab
            emas, kunlarda sotiladi.
          </p>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.title} className="grid content-start gap-3">
            <h3 className="text-sm font-semibold text-foreground">{col.title}</h3>
            <ul className="grid gap-2 text-sm text-muted-foreground">
              {col.links.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className="rounded-xs outline-none transition-colors duration-150 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-border">
        <div className="mx-auto flex max-w-page flex-wrap justify-between gap-2 px-4 py-5 text-sm text-muted-foreground sm:px-6">
          <span>© 2026 Bazart. Toshkent</span>
          <span>Bazart toʻlovda ishtirok etmaydi — hisob-kitob tomonlar oʻrtasida.</span>
        </div>
      </div>
    </footer>
  )
}

export { SiteFooter }
