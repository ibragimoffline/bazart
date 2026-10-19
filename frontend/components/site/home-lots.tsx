"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowRightIcon, GavelIcon, PackageIcon, PlusIcon } from "lucide-react"

import type { Category } from "@/lib/api/types"
import { listCategories } from "@/lib/api/endpoints"
import { byEndingSoon, byNewest, listCatalogEntries, type CatalogEntry } from "@/lib/catalog"
import { ApiError } from "@/lib/api/client"
import { categoryIcon } from "@/lib/category-icon"
import { Button } from "@/components/ui/button"
import { ProductCardSkeleton } from "@/components/ui/skeleton"
import { LotRail } from "@/components/lot/lot-rail"
import { TrustBlock } from "@/components/site/trust-block"
import { SectionHeading } from "@/components/site/section-heading"

/**
 * Bosh banner — lajuvard blok (brendning yagona katta rang maydoni). Telefonda
 * chetdan-chetga, kattaroq ekranda yumaloq panel. Ichida: qisqa va'da, ikki harakat,
 * uchta fakt. Bezak — faqat katta, och bolg'acha konturi (rasm emas, ikonka).
 */
function Hero({ activeCount }: { activeCount: number }) {
  return (
    <section className="mx-auto max-w-6xl sm:px-6 sm:pt-6">
      <div className="relative overflow-hidden bg-brand px-4 pt-8 pb-7 text-brand-foreground sm:rounded-xl sm:px-10 sm:pt-12 sm:pb-10">
        <GavelIcon
          className="pointer-events-none absolute -right-10 -bottom-10 size-64 text-brand-foreground/10 sm:size-96"
          strokeWidth={1}
          aria-hidden="true"
        />
        <p className="relative inline-flex items-center gap-2 rounded-full border border-brand-foreground/30 px-3 py-1 text-xs font-semibold tracking-wide uppercase">
          <span className="size-1.5 rounded-full bg-brand-foreground" aria-hidden="true" />
          Muddatli savdo{activeCount > 0 ? ` · ${activeCount} ta faol` : ""}
        </p>
        <h1 className="relative mt-5 max-w-3xl font-heading text-2xl leading-tight font-bold tracking-tight uppercase sm:text-3xl">
          Narxni oʻzingiz taklif qiling
        </h1>
        <p className="relative mt-3 max-w-xl text-sm text-brand-foreground/80 sm:text-base">
          Sotuvchi moʻljal narxni qoʻyadi, siz esa oʻz narxingiz va kerakli miqdorni
          taklif qilasiz — 3, 5 yoki 7 kun ichida kelishasiz. Toʻlov escrow orqali
          himoyalangan: tovarni olgach tasdiqlaysiz, keyin sotuvchiga oʻtadi.
        </p>
        <div className="relative mt-6 flex flex-wrap gap-2">
          <Button
            asChild
            size="lg"
            className="bg-brand-foreground text-brand hover:bg-brand-foreground/90"
          >
            <Link href="/catalog/hammasi">
              Katalogni koʻrish
              <ArrowRightIcon aria-hidden="true" />
            </Link>
          </Button>
          <Button
            asChild
            size="lg"
            variant="outline"
            className="border-brand-foreground/40 bg-transparent text-brand-foreground hover:bg-brand-foreground/10 hover:text-brand-foreground"
          >
            <Link href="/sell">
              <PlusIcon aria-hidden="true" />
              Sotish
            </Link>
          </Button>
        </div>
        <dl className="relative mt-8 grid grid-cols-3 gap-3 border-t border-brand-foreground/20 pt-5 sm:max-w-xl">
          {[
            ["3–7 kun", "muddat"],
            ["Escrow", "himoya"],
            ["8%", "komissiya"],
          ].map(([value, label]) => (
            <div key={value} className="grid gap-0.5">
              <dt className="sr-only">{label}</dt>
              <dd className="font-heading text-lg font-bold sm:text-xl">{value}</dd>
              <dd className="text-xs text-brand-foreground/70">{label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}

/**
 * Kategoriyalar — ilova uslubidagi plitkalar: och lajuvard kvadrat ichida ikonka,
 * ostida nom. Telefonda gorizontal suriladi, kattaroq ekranda bir qator to'r.
 */
function CategoryTiles({ categories }: { categories: Category[] }) {
  if (categories.length === 0) return null
  const items = [
    ...categories.map((c) => ({
      key: String(c.id),
      href: `/catalog/${c.slug}`,
      label: c.name,
      Icon: categoryIcon(c.slug),
    })),
  ]
  return (
    <nav aria-label="Kategoriyalar" className="mx-auto max-w-6xl pt-8 sm:px-6 md:pt-12">
      <SectionHeading title="Kategoriyalar" className="mx-4 mb-4 sm:mx-0" />
      <ul className="flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:grid sm:grid-cols-7 sm:overflow-visible sm:px-0">
        {items.map(({ key, href, label, Icon }) => (
          <li key={key} className="w-20 shrink-0 snap-start sm:w-auto">
            <Link
              href={href}
              className="group grid justify-items-center gap-2 rounded-xl text-center outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <span className="grid size-16 place-items-center rounded-xl bg-brand-soft text-brand transition-colors duration-150 group-hover:bg-brand group-hover:text-brand-foreground sm:size-20">
                <Icon className="size-7" strokeWidth={1.75} aria-hidden="true" />
              </span>
              <span className="line-clamp-2 text-xs font-medium text-foreground">{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function HomeLots() {
  const [lots, setLots] = React.useState<CatalogEntry[] | null>(null)
  const [categories, setCategories] = React.useState<Category[]>([])
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let alive = true
    Promise.all([listCatalogEntries(), listCategories().catch(() => [])])
      .then(([l, c]) => {
        if (alive) {
          setLots(l)
          setCategories(c)
        }
      })
      .catch((e) => {
        if (alive) {
          setError(e instanceof ApiError ? e.detail : "Ma'lumotni yuklab boʻlmadi.")
          setLots([])
        }
      })
    return () => {
      alive = false
    }
  }, [])

  const byEnding = React.useMemo(
    () =>
      [...(lots ?? [])].sort(byEndingSoon),
    [lots]
  )
  const byNew = React.useMemo(
    () =>
      [...(lots ?? [])].sort(byNewest),
    [lots]
  )

  return (
    <div className="pb-4">
      <Hero activeCount={lots?.length ?? 0} />
      <CategoryTiles categories={categories} />

      {lots === null ? (
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-4 px-4 pt-10 sm:grid-cols-3 sm:px-6 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <ProductCardSkeleton key={i} />
          ))}
        </div>
      ) : (
        <>
          <LotRail title="Tez tugaydi" href="/catalog/hammasi" entries={byEnding} />
          <LotRail title="Yangi mahsulotlar" href="/catalog/hammasi" entries={byNew} />
        </>
      )}

      {lots !== null && lots.length === 0 && (
        <section className="mx-auto max-w-6xl px-4 pt-10 sm:px-6">
          <div className="grid place-items-center gap-3 rounded-xl bg-brand-soft px-6 py-16 text-center">
            <PackageIcon className="size-8 text-brand" aria-hidden="true" />
            <p className="text-base font-medium text-foreground">Hozircha faol eʼlonlar yoʻq</p>
            <p className="max-w-md text-sm text-muted-foreground">
              {error ?? "Mahsulotlar qoʻshilgach, ular shu yerda koʻrinadi."}
            </p>
          </div>
        </section>
      )}

      <TrustBlock />
    </div>
  )
}

export { HomeLots }
