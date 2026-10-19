import Link from "next/link"
import { MailIcon, CreditCardIcon } from "lucide-react"

import { Logo } from "@/components/site/logo"

const PAYMENTS = ["Uzcard", "Humo", "Visa", "Mastercard"]

function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border bg-background">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-3">
        <div className="grid gap-3">
          <Logo size="sm" className="w-fit" />
          <p className="max-w-xs text-sm text-muted-foreground">
            Muddatli savdo: narx taklifi yoki auksion. Har eʼlonda majburiy deadline va escrow
            himoyasi.
          </p>
          <Link
            href="/catalog/hammasi"
            className="w-fit rounded-sm text-sm font-medium text-primary outline-none underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 underline-offset-4"
          >
            Barcha mahsulotlar
          </Link>
        </div>

        <div className="grid gap-3">
          <h3 className="text-sm font-semibold text-foreground">Aloqa</h3>
          <ul className="grid gap-2 text-sm text-muted-foreground">
            <li className="flex items-center gap-2">
              <MailIcon className="size-4 shrink-0" aria-hidden="true" />
              <a
                href="mailto:yordam@bazart.uz"
                className="rounded-sm outline-none hover:text-foreground focus-visible:text-foreground"
              >
                yordam@bazart.uz
              </a>
            </li>
          </ul>
        </div>

        <div className="grid gap-3">
          <h3 className="text-sm font-semibold text-foreground">Toʻlov usullari</h3>
          <div className="flex items-center gap-2">
            <CreditCardIcon className="size-4 text-muted-foreground" aria-hidden="true" />
            <ul className="flex flex-wrap items-center gap-1.5">
              {PAYMENTS.map((p) => (
                <li
                  key={p}
                  className="rounded-md border border-border px-2 py-0.5 text-xs font-medium text-foreground"
                >
                  {p}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-5 text-sm text-muted-foreground sm:px-6">
          © 2026 Bazart. Barcha huquqlar himoyalangan.
        </div>
      </div>
    </footer>
  )
}

export { SiteFooter }
