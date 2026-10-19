"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { RotateCcwIcon, SearchXIcon, SlidersHorizontalIcon, XIcon } from "lucide-react"

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
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
const SORTS: { value: SortKey; label: string }[] = [
  { value: "ending", label: "Tez tugaydigan" },
  { value: "price-asc", label: "Narx: arzon → qimmat" },
  { value: "price-desc", label: "Narx: qimmat → arzon" },
  { value: "new", label: "Yangi" },
]
const CONDITIONS: { value: ItemCondition; label: string }[] = [
  { value: "new", label: "Yangi" },
  { value: "used", label: "Ishlatilgan" },
  { value: "refurbished", label: "Tiklangan" },
]

const chipClass =
  "inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-card py-1 pr-1.5 pl-2.5 text-xs font-medium text-foreground outline-none transition-colors duration-150 hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"

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
    min: number
    max: number
    sort: SortKey
  }
): CatalogEntry[] {
  const { catId, matchIds, conds, min, max, sort } = opts
  const list = lots.filter((l) => {
    if (catId != null && l.item.category_id !== catId) return false
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

function CatalogLots({ categorySlug }: { categorySlug: string }) {
  const router = useRouter()
  const pathname = usePathname()
  const sp = useSearchParams()

  const [lots, setLots] = React.useState<CatalogEntry[] | null>(null)
  const [categories, setCategories] = React.useState<Category[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [retry, setRetry] = React.useState(0)
  const [sheetOpen, setSheetOpen] = React.useState(false)

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
      ? filterSortLots(lots, { catId, matchIds: match.ids, conds, min, max, sort })
      : []

  const hasRegion = regionId != null
  const hasFilters = conds.length > 0 || min > 0 || max > 0 || hasRegion
  const filterCount = conds.length + (min > 0 || max > 0 ? 1 : 0) + (hasRegion ? 1 : 0)
  const loadError = error ?? match.error

  const renderFilters = (prefix: string) => (
    <div className="grid gap-5">
      <div className="grid gap-2">
        <h3 className="text-sm font-semibold text-foreground">Hudud</h3>
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
      </div>
      <div className="grid gap-2">
        <h3 className="text-sm font-semibold text-foreground">Holati</h3>
        {CONDITIONS.map((c) => (
          <div key={c.value} className="flex items-center gap-2">
            <Checkbox
              id={`${prefix}-cond-${c.value}`}
              checked={conds.includes(c.value)}
              onCheckedChange={(v) => toggleCond(c.value, v === true)}
            />
            <Label htmlFor={`${prefix}-cond-${c.value}`} className="font-normal">
              {c.label}
            </Label>
          </div>
        ))}
      </div>
      <div className="grid gap-2">
        <h3 className="text-sm font-semibold text-foreground">Narx, soʻm</h3>
        <div className="flex items-center gap-2">
          <Input
            inputMode="numeric"
            aria-label="Eng past narx"
            placeholder="dan"
            defaultValue={min || ""}
            onBlur={(e) => update({ min: e.target.value.replace(/\D/g, "") || null })}
          />
          <span className="text-muted-foreground">—</span>
          <Input
            inputMode="numeric"
            aria-label="Eng yuqori narx"
            placeholder="gacha"
            defaultValue={max || ""}
            onBlur={(e) => update({ max: e.target.value.replace(/\D/g, "") || null })}
          />
        </div>
      </div>
    </div>
  )

  let emptyText: string
  if (loadError) emptyText = loadError
  else if (q)
    emptyText = hasFilters
      ? `«${q}» boʻyicha filtrlarga mos aktiv mahsulot yoʻq. Filtrlarni kengaytirib koʻring.`
      : `«${q}» boʻyicha aktiv mahsulot topilmadi. Boshqa soʻz bilan qidirib koʻring.`
  else if (hasRegion && conds.length === 0 && !min && !max)
    emptyText = "Bu hududda hozircha aktiv mahsulot yoʻq. Boshqa viloyatni tanlab koʻring."
  else if (hasFilters) emptyText = "Filtrlarga mos mahsulot yoʻq. Filtrlarni kengaytiring."
  else emptyText = "Bu kategoriyada hozircha aktiv auksion yoʻq."

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
          <h1 className="min-w-0 break-words font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">{label}</h1>
          <span className="text-sm tabular-nums text-muted-foreground">
            {loading ? "…" : `${results.length} ta`}
          </span>
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
        <div className="flex items-center gap-2">
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 md:hidden">
                <SlidersHorizontalIcon aria-hidden="true" />
                Filtrlar
                {filterCount > 0 && (
                  <span className="tabular-nums text-muted-foreground">({filterCount})</span>
                )}
              </Button>
            </SheetTrigger>
            <SheetContent side="bottom" className="max-h-[85svh] overflow-y-auto">
              <SheetHeader className="pb-0">
                <SheetTitle>Filtrlar</SheetTitle>
                <SheetDescription>Natijalar darhol yangilanadi.</SheetDescription>
              </SheetHeader>
              <div className="px-4">{renderFilters("m")}</div>
              <SheetFooter className="flex-row gap-2">
                {hasFilters && (
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() =>
                      update({ cond: null, min: null, max: null, region: null, district: null })
                    }
                  >
                    Tozalash
                  </Button>
                )}
                <Button className="flex-1" onClick={() => setSheetOpen(false)}>
                  {loading ? "Koʻrsatish" : `${results.length} ta mahsulotni koʻrsatish`}
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
          <Select value={sort} onValueChange={(v) => update({ sort: v })}>
            <SelectTrigger className="w-48" aria-label="Saralash">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
            onClick={() => update({ cond: null, min: null, max: null, region: null, district: null })}
            className="rounded-md px-2 py-1 text-xs font-medium text-primary outline-none underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50 underline-offset-4"
          >
            Tozalash
          </button>
        </div>
      )}

      <div className="flex gap-6">
        <aside className="hidden w-56 shrink-0 md:block">{renderFilters("d")}</aside>
        <div className="min-w-0 flex-1">
          {loading ? (
            <div
              className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
              aria-busy="true"
              aria-label="Mahsulotlar yuklanmoqda"
            >
              {Array.from({ length: 8 }).map((_, i) => (
                <ProductCardSkeleton key={i} />
              ))}
            </div>
          ) : results.length > 0 ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {results.map((lot) => (
                <EntryCard key={lot.key} entry={lot} />
              ))}
            </div>
          ) : (
            <div className="grid place-items-center gap-3 rounded-xl border border-border bg-card px-6 py-16 text-center">
              <SearchXIcon className="size-8 text-muted-foreground" aria-hidden="true" />
              <p className="text-base font-medium text-foreground">
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
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    update({
                      q: null,
                      cond: null,
                      min: null,
                      max: null,
                      region: null,
                      district: null,
                    })
                  }
                >
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
