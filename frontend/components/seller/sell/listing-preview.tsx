"use client"

import { CalendarClockIcon, InfoIcon, MapPinIcon, PencilIcon } from "lucide-react"

import { formatSom } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { PickedImage } from "@/components/seller/sell/image-dropzone"

export type PreviewData = {
  title: string
  description: string
  categoryName: string
  conditionLabel: string
  year?: string
  defects?: string
  equipment: string[]
  /** "offer" — narx takliflari (dona narxi + miqdor), "auction" — auksion. */
  mode: "offer" | "auction"
  /** Pasayuvchi auksion sozlamalari (bo'lsa). */
  descending?: { decrementSoum: number; intervalLabel: string; floorSoum: number }
  /** Rozilik berilgan bo'lsa — pasayuvchi zaxira bosqichining eng past narxi (so'm). */
  dutchFallbackFloorSoum?: number
  quantity: number
  startingSoum: number
  incrementSoum: number
  incrementIsAuto: boolean
  reserveSoum: number
  /** 0 — "hoziroq sotib olish" o'chiq. */
  buyNowSoum: number
  durationDays: number
  endsAt: string | null
  place: string
  videoUrl?: string
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-3 border-b border-border py-2.5 text-sm last:border-b-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium break-words text-foreground">{children}</dd>
    </div>
  )
}

/**
 * Joylashdan oldingi ko'rib chiqish. Auksion darhol boshlanadi va narx/muddatni
 * keyin o'zgartirib bo'lmaydi — shu sabab sotuvchi hammasini bir ko'rinishda tasdiqlaydi.
 */
function ListingPreview({
  data,
  images,
  publishing,
  error,
  onEdit,
  onPublish,
}: {
  data: PreviewData
  images: PickedImage[]
  publishing: boolean
  error: string | null
  onEdit: () => void
  onPublish: () => void
}) {
  const [primary, ...rest] = images

  return (
    <div className="grid gap-6">
      <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/50 p-4 text-sm text-muted-foreground">
        <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>
          Mahsulot xaridorlarga shunday koʻrinadi.{" "}
          {data.mode === "offer"
            ? "Joylangach eʼlon darhol ochiladi — miqdor va muddatni keyin oʻzgartirib boʻlmaydi."
            : "Joylangach auksion darhol boshlanadi — boshlangʻich narx va muddatni keyin oʻzgartirib boʻlmaydi."}
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="grid gap-2">
          {primary && (
            // eslint-disable-next-line @next/next/no-img-element -- lokal blob URL
            <img
              src={primary.url}
              alt={data.title}
              className="aspect-square w-full rounded-xl border border-border object-cover"
            />
          )}
          {rest.length > 0 && (
            <div className="grid grid-cols-5 gap-2">
              {rest.map((img, i) => (
                // eslint-disable-next-line @next/next/no-img-element -- lokal blob URL
                <img
                  key={img.id}
                  src={img.url}
                  alt={`${data.title} — ${i + 2}-rasm`}
                  className="aspect-square w-full rounded-lg border border-border object-cover"
                />
              ))}
            </div>
          )}
        </div>

        <div className="grid content-start gap-4">
          <div className="grid gap-2">
            <h2 className="font-heading text-2xl font-semibold text-foreground">{data.title}</h2>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{data.categoryName}</Badge>
              <Badge variant="outline">{data.conditionLabel}</Badge>
            </div>
          </div>

          <div className="grid gap-1 rounded-xl border border-border bg-card p-4">
            <span className="text-sm text-muted-foreground">
              {data.mode === "offer" ? "Narx (1 dona) — xaridorlar oʻz narxini taklif qiladi" : "Boshlangʻich narx"}
            </span>
            <span className="text-2xl font-semibold tabular-nums text-foreground">
              {formatSom(data.startingSoum)}
            </span>
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <CalendarClockIcon className="size-4 shrink-0" aria-hidden="true" />
              {data.durationDays} kun
              {data.endsAt ? ` · ${data.endsAt} da ${data.mode === "offer" ? "yopiladi" : "tugaydi"}` : ""}
              {data.mode === "offer" ? ` · ${data.quantity} dona` : ""}
            </span>
          </div>

          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <MapPinIcon className="size-4 shrink-0" aria-hidden="true" />
            {data.place}
          </p>
        </div>
      </div>

      <dl className="rounded-xl border border-border bg-card px-4">
        {data.description && <Row label="Tavsif">{data.description}</Row>}
        {data.defects && <Row label="Nuqsonlar">{data.defects}</Row>}
        {data.year && <Row label="Ishlab chiqarilgan yili">{data.year}</Row>}
        {data.equipment.length > 0 && <Row label="Komplektatsiya">{data.equipment.join(", ")}</Row>}
        {data.descending && (
          <>
            <Row label="Narx pasayishi">
              {formatSom(data.descending.decrementSoum)} / {data.descending.intervalLabel}
            </Row>
            <Row label="Eng past narx">{formatSom(data.descending.floorSoum)}</Row>
          </>
        )}
        {data.dutchFallbackFloorSoum != null && (
          <Row label="Taklif tushmasa">
            3 kunlik pasayuvchi auksion, eng past {formatSom(data.dutchFallbackFloorSoum)}
          </Row>
        )}
        {data.mode === "auction" && !data.descending && (
          <>
        <Row label="Minimal qadam">
          {formatSom(data.incrementSoum)}
          {data.incrementIsAuto && (
            <span className="font-normal text-muted-foreground"> · avtomatik</span>
          )}
        </Row>
        <Row label="Zaxira narx">{data.reserveSoum > 0 ? formatSom(data.reserveSoum) : "Yoʻq"}</Row>
        <Row label="Hoziroq sotib olish">
          {data.buyNowSoum > 0 ? formatSom(data.buyNowSoum) : "Yoʻq"}
        </Row>
          </>
        )}
        {data.videoUrl && <Row label="Video">{data.videoUrl}</Row>}
      </dl>

      {error && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" size="lg" onClick={onEdit} disabled={publishing}>
          <PencilIcon aria-hidden="true" />
          Tahrirlash
        </Button>
        <Button type="button" size="lg" loading={publishing} onClick={onPublish}>
          Tasdiqlash va joylash
        </Button>
      </div>
    </div>
  )
}

export { ListingPreview }
