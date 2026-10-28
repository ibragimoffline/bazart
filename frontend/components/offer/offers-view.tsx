"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { InboxIcon, SendIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { listMyOffers, type Offer, type OfferParty } from "@/lib/api/offers"
import { ApiError } from "@/lib/api/client"
import { useAuthStore } from "@/lib/store/auth"
import { OfferCard } from "@/components/offer/offer-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const TABS: { role: OfferParty; label: string; empty: string; Icon: typeof InboxIcon }[] = [
  {
    role: "seller",
    label: "Kelgan",
    empty: "Mahsulotlaringizga hali taklif kelmagan.",
    Icon: InboxIcon,
  },
  {
    role: "buyer",
    label: "Yuborilgan",
    empty: "Siz hali taklif yubormagansiz. Katalogdan mahsulot tanlab, oʻz narxingizni taklif qiling.",
    Icon: SendIcon,
  },
]

/** Javob kutayotganlari tepada, keyin ochiqlari, oxirida yopilganlar. */
function sortOffers(list: Offer[], viewer: OfferParty): Offer[] {
  const rank = (o: Offer) => (o.status !== "pending" ? 2 : o.awaiting === viewer ? 0 : 1)
  return [...list].sort((a, b) => rank(a) - rank(b))
}

/**
 * Mening takliflarim: "Kelgan" (sotuvchi sifatida) va "Yuborilgan" (xaridor sifatida).
 * Bildirishnomadan `?focus=<id>` bilan kelinsa, o'sha taklif ajratib ko'rsatiladi.
 */
function OffersView() {
  const status = useAuthStore((s) => s.status)
  const pathname = usePathname()
  const router = useRouter()
  const params = useSearchParams()
  const focus = Number(params.get("focus")) || null
  const role: OfferParty = params.get("role") === "buyer" ? "buyer" : "seller"

  const [data, setData] = React.useState<{ role: OfferParty; offers: Offer[] } | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (status !== "authenticated") return
    let alive = true
    listMyOffers(role)
      .then((offers) => {
        if (!alive) return
        // Fokusdagi taklif boshqa tabda bo'lsa — o'sha tabga o'tamiz.
        if (focus && !offers.some((o) => o.id === focus) && role === "seller") {
          router.replace(`/offers?role=buyer&focus=${focus}`, { scroll: false })
          return
        }
        setData({ role, offers })
        setError(null)
      })
      .catch((e) => alive && setError(e instanceof ApiError ? e.detail : "Takliflarni yuklab boʻlmadi."))
    return () => {
      alive = false
    }
  }, [status, role, focus, router])

  if (status === "idle") return <Skeleton className="h-64 w-full rounded-lg" />
  if (status !== "authenticated") {
    return (
      <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-16 text-center">
        <p className="text-base font-medium text-foreground">Takliflaringizni koʻrish uchun kiring</p>
        <Button asChild size="lg">
          <Link href={`/login?next=${encodeURIComponent(pathname)}`}>Kirish</Link>
        </Button>
      </div>
    )
  }

  const current = TABS.find((t) => t.role === role) ?? TABS[0]
  const offers = data && data.role === role ? data.offers : null

  const replace = (updated: Offer) =>
    setData((prev) =>
      prev ? { ...prev, offers: prev.offers.map((o) => (o.id === updated.id ? updated : o)) } : prev
    )

  return (
    <div className="grid gap-4">
      <div role="tablist" aria-label="Takliflar" className="flex gap-2">
        {TABS.map(({ role: r, label, Icon }) => (
          <button
            key={r}
            role="tab"
            type="button"
            aria-selected={r === role}
            onClick={() => router.replace(`/offers?role=${r}`, { scroll: false })}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded-full border px-4 text-sm font-medium outline-none transition-colors duration-150 focus-visible:ring-3 focus-visible:ring-ring/50",
              r === role
                ? "border-foreground bg-foreground text-background"
                : "border-border bg-card text-foreground hover:bg-muted"
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}

      <div role="tabpanel" className="grid gap-3">
        {offers === null ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full rounded-lg" />)
        ) : offers.length === 0 ? (
          <div className="grid place-items-center gap-3 rounded-lg border border-border bg-card px-6 py-14 text-center">
            <current.Icon className="size-7 text-muted-foreground" aria-hidden="true" />
            <p className="max-w-md text-sm text-muted-foreground">{current.empty}</p>
            {role === "buyer" && (
              <Button asChild variant="outline" size="sm">
                <Link href="/catalog/hammasi">Katalogga oʻtish</Link>
              </Button>
            )}
          </div>
        ) : (
          sortOffers(offers, role).map((o) => (
            <OfferCard
              key={o.id}
              offer={o}
              viewer={role}
              showItem
              highlight={o.id === focus}
              askingTiyin={o.item?.starting_price ?? o.unit_price}
              onChanged={replace}
            />
          ))
        )}
      </div>
    </div>
  )
}

export { OffersView }
