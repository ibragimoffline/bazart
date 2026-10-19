"use client"

import * as React from "react"
import { ExternalLinkIcon, TriangleAlertIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { formatNumber, formatTiyin } from "@/lib/format"
import type { Auction, Item, ItemCondition } from "@/lib/api/types"
import { listRegions, listDistricts } from "@/lib/api/regions"
import { NO_DEFECTS_TEXT } from "@/lib/listing"

export const CONDITION_LABEL: Record<ItemCondition, string> = {
  new: "Yangi",
  used: "Ishlatilgan",
  refurbished: "Tiklangan",
}

type Place = { region: string | null; district: string | null }

/**
 * Viloyat/tuman nomlarini id bo'yicha topadi. Xato bo'lsa jimgina bo'sh
 * qoladi — bu ikkilamchi ma'lumot, sahifani buzmasligi kerak.
 */
function usePlace(regionId: number | null, districtId: number | null): Place {
  const [place, setPlace] = React.useState<Place>({ region: null, district: null })

  React.useEffect(() => {
    if (regionId == null) return
    let alive = true
    Promise.all([
      listRegions(),
      districtId != null ? listDistricts(regionId) : Promise.resolve([]),
    ])
      .then(([regions, districts]) => {
        if (!alive) return
        setPlace({
          region: regions.find((r) => r.id === regionId)?.name_uz ?? null,
          district: districts.find((d) => d.id === districtId)?.name_uz ?? null,
        })
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [regionId, districtId])

  return place
}

type Spec = { label: string; value: React.ReactNode; tone?: "notice" }

/** auction yo'q — taklifli e'lon: dona narxi, zaxira va e'lon muddati ko'rsatiladi. */
function LotSpecs({ item, auction }: { item: Item; auction?: Auction }) {
  const place = usePlace(item.region_id, item.district_id)
  const placeText = [place.region, place.district].filter(Boolean).join(", ")
  // Faqat http(s) havola — `javascript:` kabi sxemalar hech qachon href'ga tushmaydi.
  const videoUrl =
    item.video_url && /^https?:\/\//i.test(item.video_url) ? item.video_url : null

  const specs: Spec[] = [
    { label: "Holati", value: CONDITION_LABEL[item.condition] },
    ...(item.year != null ? [{ label: "Ishlab chiqarilgan yili", value: String(item.year) }] : []),
    ...(item.equipment?.trim() ? [{ label: "Komplektatsiya", value: item.equipment }] : []),
    ...(item.defects?.trim()
      ? [
          // "Nuqsonlari yoʻq" — oddiy qator; haqiqiy nuqson esa ko'zga tashlanadigan eslatma.
          item.defects.trim() === NO_DEFECTS_TEXT
            ? { label: "Nuqsonlar", value: NO_DEFECTS_TEXT }
            : { label: "Nuqsonlar", value: item.defects, tone: "notice" as const },
        ]
      : []),
    ...(auction
      ? [
          { label: "Boshlangʻich narx", value: formatTiyin(auction.starting_price) },
          { label: "Minimal qadam", value: formatTiyin(auction.minimum_bid_increment) },
          ...(auction.duration_days
            ? [{ label: "Muddat", value: `${auction.duration_days} kun` }]
            : []),
        ]
      : [
          { label: "Sotuvchi narxi (1 dona)", value: formatTiyin(item.starting_price) },
          {
            label: "Mavjud",
            value: `${formatNumber(item.quantity_available)} / ${formatNumber(item.quantity_total)} dona`,
          },
          ...(item.listing_duration_days
            ? [{ label: "Muddat", value: `${item.listing_duration_days} kun` }]
            : []),
        ]),
    ...(placeText ? [{ label: "Hudud", value: placeText }] : []),
    ...(item.location ? [{ label: "Manzil", value: item.location }] : []),
    ...(item.view_count > 0
      ? [{ label: "Koʻrishlar", value: formatNumber(item.view_count) }]
      : []),
  ]

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold text-foreground">Xarakteristikalar</h2>
      <table className="w-full border-collapse text-sm">
        <tbody>
          {specs.map((s) => (
            <tr key={s.label} className="border-b border-border last:border-b-0">
              <th
                scope="row"
                className="w-2/5 py-2.5 pr-4 text-left align-top font-normal text-muted-foreground"
              >
                {s.label}
              </th>
              <td
                className={cn(
                  "py-2.5 font-medium whitespace-pre-line text-foreground",
                  s.tone === "notice" && "font-normal"
                )}
              >
                {s.tone === "notice" ? (
                  <span className="flex items-start gap-1.5 rounded-lg border border-warning/40 bg-warning/10 px-2.5 py-2">
                    <TriangleAlertIcon
                      className="mt-0.5 size-4 shrink-0 text-warning"
                      aria-hidden="true"
                    />
                    <span>{s.value}</span>
                  </span>
                ) : (
                  s.value
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {videoUrl && (
        <a
          href={videoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-primary underline-offset-4 outline-none transition-colors underline decoration-foreground/30 hover:decoration-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <ExternalLinkIcon className="size-4" aria-hidden="true" />
          Videoni koʻrish
        </a>
      )}
    </section>
  )
}

export { LotSpecs }
