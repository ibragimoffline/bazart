"use client"

import * as React from "react"
import Link from "next/link"
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ImageIcon,
  LayoutGridIcon,
  PackageIcon,
  PlusIcon,
  ShieldCheckIcon,
  TimerIcon,
} from "lucide-react"

import type { Category } from "@/lib/api/types"
import { listCategories } from "@/lib/api/endpoints"
import {
  byEndingSoon,
  byNewest,
  entryEndsAt,
  entryHref,
  entryPrice,
  listCatalogEntries,
  type CatalogEntry,
} from "@/lib/catalog"
import { ApiError } from "@/lib/api/client"
import { categoryIcon } from "@/lib/category-icon"
import { formatTiyin } from "@/lib/format"
import { heroImage } from "@/lib/item-image"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DeadlineBar } from "@/components/ui/deadline-bar"
import { ProductCardSkeleton } from "@/components/ui/skeleton"
import { EntryCard } from "@/components/catalog/entry-card"
import { TrustBlock } from "@/components/site/trust-block"
import { SectionHeading } from "@/components/site/section-heading"

const HOUR = 3_600_000

/** Hali tugamagan yozuvlar (muddati kelajakda) — "tez tugaydi" qatori va hero uchun. */
function upcoming(entries: CatalogEntry[], now: number): CatalogEntry[] {
  return entries
    .filter((e) => {
      const end = entryEndsAt(e)
      return end != null && new Date(end).getTime() > now
    })
    .sort(byEndingSoon)
}

/** "2 soat qoldi" / "3 kun qoldi" — hero plitkasidagi belgi uchun qisqa ifoda. */
function leftLabel(endsAt: string, now: number): string {
  const ms = new Date(endsAt).getTime() - now
  if (ms < HOUR) return `${Math.max(1, Math.round(ms / 60_000))} daqiqa qoldi`
  if (ms < 24 * HOUR) return `${Math.floor(ms / HOUR)} soat qoldi`
  return `${Math.floor(ms / (24 * HOUR))} kun qoldi`
}

/** Eng shoshilinch mahsulot plitkasi (hero yonida): foto + qolgan vaqt + narx. */
function UrgentTile({ entry, now }: { entry: CatalogEntry; now: number }) {
  const { item } = entry
  const hero = heroImage(item)
  const endsAt = entryEndsAt(entry) as string
  const urgent = new Date(endsAt).getTime() - now <= 6 * HOUR
  return (
    <Link
      href={entryHref(entry)}
      className="group flex items-center gap-5 overflow-hidden rounded-xl border border-border bg-card p-5 outline-none transition-shadow duration-200 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:p-6"
    >
      <div className="relative grid size-28 shrink-0 place-items-center overflow-hidden rounded-lg bg-photo-1 sm:size-36">
        {hero ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={hero} alt="" className="absolute inset-0 size-full object-cover" />
        ) : (
          <ImageIcon className="size-2/5 text-foreground/30" strokeWidth={1.25} aria-hidden="true" />
        )}
        <DeadlineBar endsAt={endsAt} className="inset-x-2 bottom-2" />
      </div>
      <div className="grid min-w-0 content-center gap-1.5">
        <Badge variant={urgent ? "error-solid" : "warning-solid"}>
          <TimerIcon aria-hidden="true" />
          {leftLabel(endsAt, now)}
        </Badge>
        <h3 className="line-clamp-2 text-lg font-semibold text-foreground group-hover:underline">
          {item.title}
        </h3>
        <p className="text-xl font-bold tracking-tight tabular-nums text-foreground">
          {formatTiyin(String(entryPrice(entry)))}
        </p>
        <p className="text-xs text-muted-foreground">
          {entry.kind === "auction"
            ? entry.lot.auction.pricing_mode === "descending"
              ? "Narxi pasaymoqda"
              : `${entry.lot.auction.bid_count} ta taklif`
            : "Narx taklifi"}
        </p>
      </div>
    </Link>
  )
}

/**
 * Bento hero: chapda tekis brend blok (va'da + ikki harakat), o'ngda eng shoshilinch
 * mahsulot va "kontaktlar kelishuvdan keyin" plitkasi. Gradient va foto kollaj yo'q.
 */
function Hero({ urgent, now }: { urgent: CatalogEntry | null; now: number }) {
  return (
    <section className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
      <div className="grid content-between gap-8 rounded-xl bg-brand p-6 text-brand-foreground sm:p-10 lg:min-h-90">
        <div className="grid gap-4">
          <span className="inline-flex h-8 w-fit items-center gap-2 rounded-full bg-brand-foreground/15 px-3 text-sm font-semibold">
            <TimerIcon className="size-4" aria-hidden="true" />
            Har eʼlon 3–7 kunda yakunlanadi
          </span>
          <h1 className="max-w-140 text-xl font-bold tracking-tight sm:text-2xl lg:text-3xl">
            Narx muzlamaydi. Savdo kunlarda tugaydi.
          </h1>
          <p className="max-w-120 text-base text-brand-foreground/90 sm:text-lg">
            Narxingizni taklif qiling yoki auksionda qatnashing. Kelishuvdan soʻng
            sotuvchi bilan bevosita bogʻlanib, uchrashuvda hisob-kitob qilasiz.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="lg" className="bg-card text-foreground hover:bg-muted">
            <Link href="/catalog/hammasi">
              <LayoutGridIcon aria-hidden="true" />
              Katalogni koʻrish
            </Link>
          </Button>
          <Button
            asChild
            size="lg"
            variant="ghost"
            className="text-brand-foreground ring-1 ring-brand-foreground/40 ring-inset hover:bg-brand-foreground/10 max-sm:hidden"
          >
            <Link href="/sell">
              <PlusIcon aria-hidden="true" />
              Mahsulot joylash
            </Link>
          </Button>
        </div>
      </div>

      <div className={cn("hidden gap-4 sm:grid lg:grid-cols-1", urgent && "md:grid-cols-2 lg:grid-rows-2")}>
        {urgent && <UrgentTile entry={urgent} now={now} />}
        <div className="flex items-center gap-5 rounded-xl bg-brand-subtle p-5 lg:p-6">
          <span className="grid size-11 shrink-0 place-items-center rounded-md bg-card text-brand-subtle-foreground">
            <ShieldCheckIcon className="size-5.5" aria-hidden="true" />
          </span>
          <div className="grid gap-1 text-brand-subtle-foreground">
            <h3 className="text-lg font-semibold">Kontaktlar kelishuvdan keyin</h3>
            <p className="text-sm">
              Bazart toʻlovda ishtirok etmaydi: kelishuvdan soʻng tasdiqlangan telefon
              raqamlar ochiladi — mahsulotni koʻrib, keyin toʻlaysiz.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

/**
 * Kategoriya plitkalari: 64px oq kvadrat (border) ichida 24px ikonka, ostida nom.
 * Telefonda gorizontal suriladi; hover — brend chegara.
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
    { key: "all", href: "/catalog/hammasi", label: "Hammasi", Icon: LayoutGridIcon },
  ]
  return (
    <nav aria-label="Kategoriyalar" className="pt-8 md:pt-10">
      <ul className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0 lg:justify-between">
        {items.map(({ key, href, label, Icon }) => (
          <li key={key} className="w-18 shrink-0 lg:w-auto lg:flex-1">
            <Link
              href={href}
              className="group grid justify-items-center gap-2 rounded-md text-center text-xs font-medium text-foreground outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              <span className="grid size-16 place-items-center rounded-lg border border-border bg-card transition-colors duration-150 group-hover:border-brand">
                <Icon className="size-6" aria-hidden="true" />
              </span>
              <span className="line-clamp-2">{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/**
 * "Tez tugaydi" qatori — sahifaning umurtqasi: muddat bo'yicha o'sish tartibida.
 * Telefonda suriladi (keyingi karta chetdan ko'rinib turadi), desktop'da 5 ustun.
 */
function EndingRail({ entries, now }: { entries: CatalogEntry[]; now: number }) {
  const ref = React.useRef<HTMLUListElement>(null)
  if (entries.length === 0) return null
  const scrollBy = (dir: 1 | -1) =>
    ref.current?.scrollBy({ left: dir * ref.current.clientWidth * 0.8, behavior: "smooth" })
  const today = new Date(entryEndsAt(entries[0]) as string).getTime() - now < 24 * HOUR

  return (
    <section aria-labelledby="tez-tugaydi" className="pt-12">
      <SectionHeading
        id="tez-tugaydi"
        title="Tez tugaydi"
        href="/catalog/hammasi?sort=ending"
        className="mb-5"
        badge={
          today ? (
            <Badge variant="error-solid">
              <TimerIcon aria-hidden="true" />
              Bugun tugaydi
            </Badge>
          ) : undefined
        }
        aside={
          <div className="hidden items-center gap-1 sm:flex lg:hidden">
            <Button variant="outline" size="icon-sm" aria-label="Orqaga" onClick={() => scrollBy(-1)}>
              <ChevronLeftIcon aria-hidden="true" />
            </Button>
            <Button variant="outline" size="icon-sm" aria-label="Oldinga" onClick={() => scrollBy(1)}>
              <ChevronRightIcon aria-hidden="true" />
            </Button>
          </div>
        }
      />
      <ul
        ref={ref}
        className="-mx-4 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:gap-5 sm:px-0 lg:grid lg:grid-cols-5 lg:overflow-visible"
      >
        {entries.slice(0, 10).map((entry, i) => (
          <li
            key={entry.key}
            className={cn(
              "grid w-2/5 shrink-0 snap-start sm:w-1/4 lg:w-auto",
              i >= 5 && "lg:hidden"
            )}
          >
            <EntryCard entry={entry} />
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * "Yangi mahsulotlar" — kategoriya chiplari bilan to'r (2 / 3 / 4 ustun) va
 * "Yana koʻrsatish" (har bosishda 8 ta).
 */
function NewGrid({ entries, categories }: { entries: CatalogEntry[]; categories: Category[] }) {
  const [catId, setCatId] = React.useState<number | null>(null)
  const [limit, setLimit] = React.useState(8)
  const list = catId == null ? entries : entries.filter((e) => e.item.category_id === catId)
  // Faqat mahsuloti bor kategoriyalar chip bo'ladi.
  const used = categories.filter((c) => entries.some((e) => e.item.category_id === c.id))
  if (entries.length === 0) return null

  const chip = (on: boolean) =>
    cn(
      "inline-flex h-8 shrink-0 items-center rounded-full border px-3 text-xs font-medium whitespace-nowrap outline-none transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
      on
        ? "border-foreground bg-foreground text-background"
        : "border-border bg-card text-foreground hover:border-border-strong"
    )

  return (
    <section aria-labelledby="yangi-mahsulotlar" className="pt-12">
      <div className="mb-5 grid gap-3 md:flex md:items-end md:justify-between">
        <SectionHeading id="yangi-mahsulotlar" title="Yangi mahsulotlar" />
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0">
          <button type="button" aria-pressed={catId == null} className={chip(catId == null)} onClick={() => setCatId(null)}>
            Hammasi
          </button>
          {used.slice(0, 6).map((c) => (
            <button
              key={c.id}
              type="button"
              aria-pressed={catId === c.id}
              className={chip(catId === c.id)}
              onClick={() => {
                setCatId(c.id)
                setLimit(8)
              }}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-5 md:grid-cols-3 lg:grid-cols-4">
        {list.slice(0, limit).map((entry) => (
          <li key={entry.key} className="grid min-w-0">
            <EntryCard entry={entry} />
          </li>
        ))}
      </ul>
      {list.length > limit && (
        <div className="mt-8 grid place-items-center">
          <Button variant="outline" onClick={() => setLimit((n) => n + 8)}>
            Yana koʻrsatish
          </Button>
        </div>
      )}
    </section>
  )
}

function HomeLots() {
  const [lots, setLots] = React.useState<CatalogEntry[] | null>(null)
  const [categories, setCategories] = React.useState<Category[]>([])
  const [error, setError] = React.useState<string | null>(null)
  // "Hozir" yuklanganda bir marta olinadi — render paytida Date.now chaqirilmaydi.
  const [now, setNow] = React.useState(0)

  React.useEffect(() => {
    let alive = true
    Promise.all([listCatalogEntries(), listCategories().catch(() => [])])
      .then(([l, c]) => {
        if (alive) {
          setNow(Date.now())
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

  const ending = React.useMemo(() => upcoming(lots ?? [], now), [lots, now])
  const newest = React.useMemo(() => [...(lots ?? [])].sort(byNewest), [lots])

  return (
    <div className="mx-auto max-w-page px-4 pt-6 pb-4 sm:px-6 md:pt-8">
      <Hero urgent={ending[0] ?? null} now={now} />
      <CategoryTiles categories={categories} />

      {lots === null ? (
        <div className="grid grid-cols-2 gap-x-3 gap-y-6 pt-12 sm:gap-x-5 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <ProductCardSkeleton key={i} />
          ))}
        </div>
      ) : (
        <EndingRail entries={ending} now={now} />
      )}

      {lots !== null && lots.length === 0 && (
        <section className="pt-12">
          <div className="grid justify-items-center gap-3 rounded-lg border border-border px-6 py-12 text-center">
            <span className="mb-2 grid size-18 place-items-center rounded-xl border border-border bg-muted text-muted-foreground">
              <PackageIcon className="size-8" aria-hidden="true" />
            </span>
            <p className="text-lg font-semibold text-foreground">Hozircha faol eʼlonlar yoʻq</p>
            <p className="max-w-md text-sm text-muted-foreground">
              {error ?? "Mahsulotlar qoʻshilgach, ular shu yerda koʻrinadi. Birinchi boʻlib joylang."}
            </p>
            <Button asChild>
              <Link href="/sell">
                <PlusIcon aria-hidden="true" />
                Mahsulot joylash
              </Link>
            </Button>
          </div>
        </section>
      )}

      <TrustBlock />

      {lots !== null && <NewGrid entries={newest} categories={categories} />}
    </div>
  )
}

export { HomeLots }
