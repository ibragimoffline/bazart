"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  ArrowUpDownIcon,
  CheckIcon,
  RotateCcwIcon,
  SearchXIcon,
  SlidersHorizontalIcon,
  XIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { formatSom } from "@/lib/format"
import type { Category, ItemCondition } from "@/lib/api/types"
import { listCategories, listItems } from "@/lib/api/endpoints"
import {
  byEndingSoon,
  byNewest,
  entryPrice,
  listCatalogEntries,
  type CatalogEntry,
} from "@/lib/catalog"
import { ApiError } from "@/lib/api/client"
import { EntryCard } from "@/components/catalog/entry-card"
import { ProductCardSkeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import {
  RegionSelect,
  DistrictSelect,
  useRegions,
  useDistricts,
} from "@/components/region/region-select"

type SortKey = "ending" | "price-asc" | "price-desc" | "new"
const SORTS: { value: SortKey; label: string; short: string }[] = [
  { value: "ending", label: "Tez tugaydigan", short: "Tugash vaqti" },
  { value: "price-asc", label: "Narx: arzon → qimmat", short: "Arzonroq" },
  { value: "price-desc", label: "Narx: qimmat → arzon", short: "Qimmatroq" },
  { value: "new", label: "Yangi", short: "Yangi" },
]
const CONDITIONS: { value: ItemCondition; label: string }[] = [
  { value: "new", label: "Yangi" },
  { value: "used", label: "Ishlatilgan" },
  { value: "refurbished", label: "Tiklangan" },
]
/** Savdo usuli: taklifli e'lon yoki auksion (pasayuvchi narx ham auksion yo'nalishi). */
type ModeKey = "offer" | "auction"
const MODES: { value: ModeKey; label: string }[] = [
  { value: "offer", label: "Narx taklifi" },
  { value: "auction", label: "Auksion" },
]

/** Faol filtr chipi (natijalar ustida) — bosilsa filtr olib tashlanadi. */
const chipClass =
  "inline-flex h-8 max-w-full items-center gap-1 rounded-full border border-brand bg-brand-subtle pr-2 pl-3 text-xs font-medium text-brand-subtle-foreground outline-none transition-colors duration-150 hover:bg-brand-subtle/70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"

/** Tanlov chipi (filtr panelida): tanlangan — brand-subtle fon, brend chegara, belgi. */
function ToggleChip({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "inline-flex h-10 items-center gap-1.5 rounded-full border px-4 text-sm font-medium outline-none transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        pressed
          ? "border-brand bg-brand-subtle text-brand-subtle-foreground"
          : "border-border bg-card text-foreground hover:border-border-strong"
      )}
    >
      {pressed && <CheckIcon className="size-3.5" aria-hidden="true" />}
      {children}
    </button>
  )
}

/** Filtr bo'limi: kichik sarlavha + tarkib, bo'limlar orasida ingichka chiziq. */
function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-2.5 border-b border-border pb-5 last:border-b-0 last:pb-0">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  )
}

function parseId(v: string | null): number | null {
  const n = Number(v)
  return Number.isInteger(n) && n > 0 ? n : null
}

function filterSortLots(
  lots: CatalogEntry[],
  opts: {
    catId: number | null
    matchIds: Set<number> | null
    conds: ItemCondition[]
    mode: ModeKey | null
    min: number
    max: number
    sort: SortKey
  }
): CatalogEntry[] {
  const { catId, matchIds, conds, mode, min, max, sort } = opts
  const list = lots.filter((l) => {
    if (catId != null && l.item.category_id !== catId) return false
    if (mode && l.kind !== mode) return false
    if (matchIds && !matchIds.has(l.item.id)) return false
    if (conds.length && !conds.includes(l.item.condition)) return false
    const priceSoum = entryPrice(l) / 100
    if (min && priceSoum < min) return false
    if (max && priceSoum > max) return false
    return true
  })
  if (sort === "price-asc") return list.sort((a, b) => entryPrice(a) - entryPrice(b))
  if (sort === "price-desc") return list.sort((a, b) => entryPrice(b) - entryPrice(a))
  if (sort === "new") return list.sort(byNewest)
  return list.sort(byEndingSoon)
}

/**
 * Backend qidiruvi / hudud filtri boʻyicha mos tovar id'lari.
 * Backend'da lot (auksion + tovar) qidiruvi yoʻq — mos tovarlarni olib, aktiv lotlar bilan
 * kesishtiramiz. Lotin/kirill translitini backend oʻzi hisobga oladi.
 * Filtr yoʻq boʻlsa — null (hamma lot mos).
 */
function useMatchingItemIds(
  q: string,
  regionId: number | null,
  districtId: number | null,
  retry: number
): { ids: Set<number> | null; loading: boolean; error: string | null } {
  const active = q !== "" || regionId != null || districtId != null
  const key = `${q}|${regionId ?? ""}|${districtId ?? ""}|${retry}`
  const [state, setState] = React.useState<{
    key: string
    ids: Set<number> | null
    error: string | null
  }>({ key: "", ids: null, error: null })

  React.useEffect(() => {
    if (!active) return
    let alive = true
    listItems({
      q: q || undefined,
      region_id: regionId ?? undefined,
      district_id: districtId ?? undefined,
      status: "active",
      limit: 100,
    })
      .then((items) => {
        if (alive) setState({ key, ids: new Set(items.map((i) => i.id)), error: null })
      })
      .catch((e) => {
        if (alive)
          setState({
            key,
            ids: new Set(),
            error: e instanceof ApiError ? e.detail : "Qidiruv natijalarini yuklab boʻlmadi.",
          })
      })
    return () => {
      alive = false
    }
  }, [active, key, q, regionId, districtId])

  if (!active) return { ids: null, loading: false, error: null }
  if (state.key !== key) return { ids: null, loading: true, error: null }
  return { ids: state.ids, loading: false, error: state.error }
}

/**
 * Katalog va qidiruv natijalari. Telefon/planshetda: natijalar soni + "Saralash" va
 * "Filtr" tugmalari (pastdan ochiladigan panellar). Desktop'da filtrlar chap tomonda
 * oq panelda, saralash — ro'yxat ustida.
 */
function CatalogLots({ categorySlug }: { categorySlug: string }) {
  const router = useRouter()
  const pathname = usePathname()
  const sp = useSearchParams()

  const [lots, setLots] = React.useState<CatalogEntry[] | null>(null)
  const [categories, setCategories] = React.useState<Category[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [retry, setRetry] = React.useState(0)
  const [sheetOpen, setSheetOpen] = React.useState(false)
  const [sortOpen, setSortOpen] = React.useState(false)

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
          setError(e instanceof ApiError ? e.detail : "Yuklab boʻlmadi.")
          setLots([])
        }
      })
    return () => {
      alive = false
    }
  }, [])

  const q = sp.get("q")?.trim() ?? ""
  const regionId = parseId(sp.get("region"))
  // Tuman faqat viloyat bilan birga maʼnoga ega.
  const districtId = regionId != null ? parseId(sp.get("district")) : null
  const sort = (SORTS.find((s) => s.value === sp.get("sort"))?.value ??
    "ending") as SortKey
  const conds = (sp.get("cond") ?? "")
    .split(",")
    .filter((c): c is ItemCondition =>
      CONDITIONS.some((x) => x.value === c)
    )
  const mode = MODES.find((m) => m.value === sp.get("mode"))?.value ?? null
  const min = Number(sp.get("min")) || 0
  const max = Number(sp.get("max")) || 0

  const regions = useRegions()
  const districts = useDistricts(regionId)
  const regionName = regions.data?.find((r) => r.id === regionId)?.name_uz
  const districtName = districts.data?.find((d) => d.id === districtId)?.name_uz

  const match = useMatchingItemIds(q, regionId, districtId, retry)

  const category =
    categorySlug === "hammasi"
      ? null
      : categories.find((c) => c.slug === categorySlug)
  const label = q ? `«${q}» boʻyicha natijalar` : category ? category.name : "Barcha mahsulotlar"

  const update = (patch: Record<string, string | null>) => {
    const params = new URLSearchParams(sp.toString())
    for (const [k, v] of Object.entries(patch)) {
      if (v) params.set(k, v)
      else params.delete(k)
    }
    const qs = params.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const toggleCond = (c: ItemCondition, on: boolean) => {
    const next = on ? [...conds, c] : conds.filter((x) => x !== c)
    update({ cond: next.join(",") || null })
  }

  const catId = category?.id ?? null
  const loading = lots === null || match.loading
  const results =
    lots && !match.loading
      ? filterSortLots(lots, { catId, matchIds: match.ids, conds, mode, min, max, sort })
      : []

  const hasRegion = regionId != null
  const hasFilters = conds.length > 0 || mode != null || min > 0 || max > 0 || hasRegion
  const filterCount =
    conds.length + (mode ? 1 : 0) + (min > 0 || max > 0 ? 1 : 0) + (hasRegion ? 1 : 0)
  const clearFilters = {
    cond: null,
    mode: null,
    min: null,
    max: null,
    region: null,
    district: null,
  }
  const loadError = error ?? match.error
  // Kategoriya almashganda qidiruv va filtrlar saqlanadi.
  const query = sp.toString()
  const categoryHref = (slug: string) => `/catalog/${slug}${query ? `?${query}` : ""}`
  const sortLabel = SORTS.find((s) => s.value === sort)?.label

  const renderFilters = (prefix: string) => (
    <div className="grid gap-5">
      <FilterSection title="Kategoriya">
        <ul className="grid gap-0.5">
          {[{ id: 0, slug: "hammasi", name: "Barcha kategoriyalar" }, ...categories].map((c) => {
            const current = c.slug === categorySlug
            return (
              <li key={c.id}>
                <Link
                  href={categoryHref(c.slug)}
                  aria-current={current ? "page" : undefined}
                  onClick={() => setSheetOpen(false)}
                  className={cn(
                    "flex h-10 items-center justify-between gap-2 rounded-sm px-2.5 text-sm outline-none transition-colors duration-150 hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                    current
                      ? "bg-brand-subtle font-semibold text-brand-subtle-foreground hover:bg-brand-subtle"
                      : "text-foreground"
                  )}
                >
                  <span className="truncate">{c.name}</span>
                  {current && <CheckIcon className="size-4 shrink-0" aria-hidden="true" />}
                </Link>
              </li>
            )
          })}
        </ul>
      </FilterSection>
      <FilterSection title="Savdo usuli">
        <div className="flex flex-wrap gap-2">
          {MODES.map((m) => (
            <ToggleChip
              key={m.value}
              pressed={mode === m.value}
              onClick={() => update({ mode: mode === m.value ? null : m.value })}
            >
              {m.label}
            </ToggleChip>
          ))}
        </div>
      </FilterSection>
      <FilterSection title="Holati">
        <div className="flex flex-wrap gap-2">
          {CONDITIONS.map((c) => (
            <ToggleChip
              key={c.value}
              pressed={conds.includes(c.value)}
              onClick={() => toggleCond(c.value, !conds.includes(c.value))}
            >
              {c.label}
            </ToggleChip>
          ))}
        </div>
      </FilterSection>
      <FilterSection title="Hudud">
        <RegionSelect
          id={`${prefix}-region`}
          aria-label="Viloyat"
          allLabel="Barcha viloyatlar"
          regions={regions}
          value={regionId != null ? String(regionId) : undefined}
          onValueChange={(v) => update({ region: v ?? null, district: null })}
        />
        <DistrictSelect
          id={`${prefix}-district`}
          aria-label="Tuman"
          allLabel={regionId != null ? "Barcha tumanlar" : undefined}
          regionId={regionId}
          value={districtId != null ? String(districtId) : undefined}
          onValueChange={(v) => update({ district: v ?? null })}
        />
      </FilterSection>
      <FilterSection title="Narx, soʻm">
        <div className="grid grid-cols-2 gap-2">
          {/* key — chip orqali tozalanganda maydon ham bo'shasin. */}
          <Input
            key={`min-${min}`}
            inputMode="numeric"
            aria-label="Eng past narx"
            placeholder="dan"
            defaultValue={min || ""}
            onBlur={(e) => update({ min: e.target.value.replace(/\D/g, "") || null })}
          />
          <Input
            key={`max-${max}`}
            inputMode="numeric"
            aria-label="Eng yuqori narx"
            placeholder="gacha"
            defaultValue={max || ""}
            onBlur={(e) => update({ max: e.target.value.replace(/\D/g, "") || null })}
          />
        </div>
      </FilterSection>
    </div>
  )

  let emptyText: string
  if (loadError) emptyText = loadError
  else if (q)
    emptyText = hasFilters
      ? `«${q}» boʻyicha filtrlarga mos aktiv mahsulot yoʻq. Filtrlarni kengaytirib koʻring.`
      : `«${q}» boʻyicha aktiv mahsulot topilmadi. Boshqa soʻz bilan qidirib koʻring.`
  else if (hasRegion && conds.length === 0 && !mode && !min && !max)
    emptyText = "Bu hududda hozircha aktiv mahsulot yoʻq. Boshqa viloyatni tanlab koʻring."
  else if (hasFilters) emptyText = "Filtrlarga mos mahsulot yoʻq. Filtrlarni kengaytiring."
  else emptyText = "Bu kategoriyada hozircha aktiv auksion yoʻq."

  const resultsLabel = loading ? "Yuklanmoqda…" : `${results.length} ta natija`

  return (
    <div>
      <div className="mb-4 flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="min-w-0 break-words font-heading text-xl font-bold tracking-tight text-foreground md:text-2xl">{label}</h1>
        {q && (
          <button
            type="button"
            onClick={() => update({ q: null })}
            className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-sm font-medium text-primary outline-none underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 underline-offset-4"
          >
            <XIcon className="size-3.5" aria-hidden="true" />
            Qidiruvni tozalash
          </button>
        )}
      </div>

      <div className="flex gap-6">
        <aside
          aria-label="Filtrlar"
          className="sticky top-32 hidden max-h-[calc(100svh-9rem)] w-62 shrink-0 self-start overflow-y-auto rounded-lg border border-border bg-card p-5 lg:block"
        >
          {renderFilters("d")}
        </aside>

        <div className="min-w-0 flex-1">
          {/* Natijalar paneli: son chapda; telefon/planshetda "Saralash" va "Filtr" o'ngda. */}
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-sm tabular-nums text-muted-foreground" aria-live="polite">
              {resultsLabel}
            </p>
            <div className="flex items-center gap-2">
              <Sheet open={sortOpen} onOpenChange={setSortOpen}>
                <SheetTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full lg:hidden"
                    aria-label={`Saralash: ${sortLabel}`}
                  >
                    <ArrowUpDownIcon aria-hidden="true" />
                    Saralash
                  </Button>
                </SheetTrigger>
                <SheetContent side="bottom">
                  <span className="mx-auto mt-2 h-1 w-10 rounded-full bg-border-strong/60" aria-hidden="true" />
                  <SheetHeader className="pt-0 pb-0">
                    <SheetTitle>Saralash</SheetTitle>
                    <SheetDescription className="sr-only">
                      Natijalar tartibini tanlang.
                    </SheetDescription>
                  </SheetHeader>
                  <RadioGroup
                    value={sort}
                    onValueChange={(v) => {
                      update({ sort: v })
                      setSortOpen(false)
                    }}
                    className="gap-0 px-4 pb-6"
                  >
                    {SORTS.map((o) => (
                      <Label
                        key={o.value}
                        htmlFor={`sort-${o.value}`}
                        className="flex cursor-pointer items-center gap-3 border-b border-border py-3.5 text-sm font-normal last:border-b-0"
                      >
                        <RadioGroupItem id={`sort-${o.value}`} value={o.value} />
                        {o.label}
                      </Label>
                    ))}
                  </RadioGroup>
                </SheetContent>
              </Sheet>

              <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm" className="rounded-full lg:hidden">
                    <SlidersHorizontalIcon aria-hidden="true" />
                    Filtrlar
                    {filterCount > 0 && (
                      <span className="grid size-5 place-items-center rounded-full bg-brand text-xs font-semibold tabular-nums text-brand-foreground">
                        {filterCount}
                      </span>
                    )}
                  </Button>
                </SheetTrigger>
                <SheetContent side="bottom" className="max-h-[90svh] gap-0" showCloseButton={false}>
                  <span className="mx-auto mt-2 h-1 w-10 rounded-full bg-border-strong/60" aria-hidden="true" />
                  <SheetHeader className="flex-row items-center justify-between border-b border-border">
                    <div className="grid gap-0.5">
                      <SheetTitle className="text-lg">Filtrlar</SheetTitle>
                      <SheetDescription>Natijalar darhol yangilanadi.</SheetDescription>
                    </div>
                    {hasFilters && (
                      <Button variant="link" onClick={() => update(clearFilters)}>
                        Tozalash
                      </Button>
                    )}
                  </SheetHeader>
                  <div className="overflow-y-auto px-4 py-5">{renderFilters("m")}</div>
                  <SheetFooter className="border-t border-border">
                    <Button size="lg" className="w-full" onClick={() => setSheetOpen(false)}>
                      {loading ? "Koʻrsatish" : `${results.length} ta natijani koʻrsatish`}
                    </Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>

              <div
                role="radiogroup"
                aria-label="Saralash"
                className="hidden gap-1 rounded-md border border-border bg-muted p-1 lg:inline-flex"
              >
                {SORTS.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    role="radio"
                    aria-checked={sort === o.value}
                    onClick={() => update({ sort: o.value })}
                    className={cn(
                      "h-9 rounded-sm px-3.5 text-sm outline-none transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                      sort === o.value
                        ? "bg-card font-semibold text-foreground shadow-sm ring-1 ring-border"
                        : "font-medium text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {o.short}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {hasFilters && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {hasRegion && (
                <button
                  type="button"
                  onClick={() => update({ region: null, district: null })}
                  className={chipClass}
                  aria-label="Hudud filtrini olib tashlash"
                >
                  <span className="truncate">
                    {regionName ?? "Viloyat"}
                    {districtId != null && `, ${districtName ?? "tuman"}`}
                  </span>
                  <XIcon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                </button>
              )}
              {mode && (
                <button type="button" onClick={() => update({ mode: null })} className={chipClass}>
                  {MODES.find((m) => m.value === mode)?.label}
                  <XIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                </button>
              )}
              {conds.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleCond(c, false)}
                  className={chipClass}
                >
                  {CONDITIONS.find((x) => x.value === c)?.label}
                  <XIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                </button>
              ))}
              {(min > 0 || max > 0) && (
                <button
                  type="button"
                  onClick={() => update({ min: null, max: null })}
                  className={chipClass}
                >
                  {formatSom(min)} – {max ? formatSom(max) : "∞"}
                  <XIcon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                </button>
              )}
              <button
                type="button"
                onClick={() => update(clearFilters)}
                className="rounded-md px-2 py-1 text-xs font-medium text-primary outline-none underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 underline-offset-4"
              >
                Tozalash
              </button>
            </div>
          )}

          {loading ? (
            <div
              className="grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-5 md:grid-cols-3 xl:grid-cols-4"
              aria-busy="true"
              aria-label="Mahsulotlar yuklanmoqda"
            >
              {Array.from({ length: 8 }).map((_, i) => (
                <ProductCardSkeleton key={i} />
              ))}
            </div>
          ) : results.length > 0 ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-6 sm:gap-x-5 md:grid-cols-3 xl:grid-cols-4">
              {results.map((lot) => (
                <EntryCard key={lot.key} entry={lot} />
              ))}
            </div>
          ) : (
            <div className="grid justify-items-center gap-3 rounded-lg border border-border px-6 py-12 text-center">
              <span className="mb-2 grid size-18 place-items-center rounded-xl border border-border bg-muted text-muted-foreground">
                <SearchXIcon className="size-8" aria-hidden="true" />
              </span>
              <p className="text-lg font-semibold text-foreground">
                Mahsulot topilmadi
              </p>
              <p
                role={loadError ? "alert" : undefined}
                className="max-w-sm text-sm text-muted-foreground"
              >
                {emptyText}
              </p>
              {match.error && !error ? (
                <Button variant="outline" size="sm" onClick={() => setRetry((n) => n + 1)}>
                  <RotateCcwIcon aria-hidden="true" />
                  Qayta urinish
                </Button>
              ) : q || hasFilters ? (
                <Button variant="outline" size="sm" onClick={() => update({ q: null, ...clearFilters })}>
                  Barcha mahsulotlarni koʻrsatish
                </Button>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export { CatalogLots }
