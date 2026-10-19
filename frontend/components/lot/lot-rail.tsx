"use client"

import * as React from "react"
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import type { CatalogEntry } from "@/lib/catalog"
import { Button } from "@/components/ui/button"
import { EntryCard } from "@/components/catalog/entry-card"
import { SectionHeading } from "@/components/site/section-heading"

function LotRail({
  title,
  href,
  entries,
}: {
  title: string
  href?: string
  /** Auksion lotlari va taklifli e'lonlar aralash. */
  entries: CatalogEntry[]
}) {
  const ref = React.useRef<HTMLDivElement>(null)
  const scrollBy = (dir: 1 | -1) =>
    ref.current?.scrollBy({ left: dir * 320, behavior: "smooth" })

  if (entries.length === 0) return null

  return (
    <section aria-label={title} className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 md:pt-14">
      <SectionHeading
        title={title}
        href={href}
        className="mb-4 md:mb-5"
        aside={
          <div className="hidden items-center gap-1 md:flex">
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Chapga surish"
              onClick={() => scrollBy(-1)}
            >
              <ChevronLeftIcon aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Oʻngga surish"
              onClick={() => scrollBy(1)}
            >
              <ChevronRightIcon aria-hidden="true" />
            </Button>
          </div>
        }
      />

      <div
        ref={ref}
        className="-mx-4 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:gap-4 sm:px-0 sm:[scrollbar-width:thin]"
      >
        {entries.map((entry) => (
          <EntryCard
            key={entry.key}
            entry={entry}
            className="w-40 shrink-0 snap-start sm:w-52"
          />
        ))}
      </div>
    </section>
  )
}

export { LotRail }
