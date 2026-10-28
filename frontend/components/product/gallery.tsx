"use client"

import * as React from "react"
import { ImageIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Mahsulot galereyasi — asosiy rasm + thumbnail qatori.
 * Rasm bo'lsa haqiqiy fotolar ko'rsatiladi (backend `item_images`/`images`);
 * bo'lmasa — bitta neytral placeholder. Slaydlar soni haqiqiy rasm soniga teng.
 * Mobilda asosiy rasm gorizontal swipe (snap-scroll); thumbnail bosilsa
 * o'sha slaydga suriladi.
 */
function Gallery({ title, images = [] }: { title: string; images?: string[] }) {
  const trackRef = React.useRef<HTMLDivElement>(null)
  const [active, setActive] = React.useState(0)
  const hasImages = images.length > 0

  const goTo = (i: number) => {
    const track = trackRef.current
    if (!track) return
    track.scrollTo({ left: i * track.clientWidth, behavior: "smooth" })
    setActive(i)
  }

  const onScroll = () => {
    const track = trackRef.current
    if (!track) return
    const i = Math.round(track.scrollLeft / track.clientWidth)
    if (i !== active) setActive(i)
  }

  // Rasm yo'q — bitta neytral placeholder (soxta hisob ko'rsatilmaydi).
  if (!hasImages) {
    return (
      <div className="grid aspect-square w-full place-items-center rounded-lg bg-brand-subtle">
        <div className="flex flex-col items-center gap-2 p-6 text-center text-muted-foreground">
          <ImageIcon className="size-12 text-brand/30" aria-hidden="true" />
          <span className="text-xs">Rasm qoʻshilmagan</span>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-3">
      <div
        ref={trackRef}
        onScroll={onScroll}
        className="flex snap-x snap-mandatory overflow-x-auto rounded-lg border border-border [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {images.map((src, i) => (
          <div
            key={src}
            className="aspect-square w-full shrink-0 snap-center bg-muted"
          >
            {/* Backend host'idagi rasm — next/image emas, oddiy img (host prod'da o'zgaruvchan). */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={`${title} — ${i + 1}-rasm`}
              className="size-full object-cover"
              loading={i === 0 ? "eager" : "lazy"}
            />
          </div>
        ))}
      </div>

      {/* Thumbnaillar — bittadan ortiq rasm bo'lsa. */}
      {images.length > 1 && (
        <div className="flex gap-2">
          {images.map((src, i) => (
            <button
              key={src}
              type="button"
              aria-label={`${i + 1}-rasm`}
              aria-current={active === i ? "true" : undefined}
              onClick={() => goTo(i)}
              className={cn(
                "aspect-square w-16 shrink-0 overflow-hidden rounded-md border bg-muted outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
                active === i ? "border-primary" : "border-border hover:border-foreground/30"
              )}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt="" className="size-full object-cover" loading="lazy" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export { Gallery }
