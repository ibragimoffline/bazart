"use client"

import * as React from "react"
import { ChevronDownIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Ixtiyoriy maydonlar guruhi — yopiq holatda asosiy formani shovqinsiz qoldiradi.
 * Ichida xato bo'lsa (`forceOpen`) avtomatik ochiladi, aks holda xato ko'rinmay qolardi.
 */
function CollapsibleSection({
  title,
  summary,
  forceOpen,
  children,
}: {
  title: string
  /** Yopiq holatda sarlavha yonida — nima kiritilgani yoki nima borligi. */
  summary?: string
  forceOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = React.useState(false)
  const contentId = React.useId()
  const expanded = open || Boolean(forceOpen)

  return (
    <section className="rounded-lg border border-border bg-card">
      <h2>
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-3 rounded-lg px-4 py-3 text-left outline-none transition-colors hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="grid gap-0.5">
            <span className="text-base font-semibold text-foreground">{title}</span>
            {summary && <span className="text-sm text-muted-foreground">{summary}</span>}
          </span>
          <ChevronDownIcon
            className={cn(
              "size-5 shrink-0 text-muted-foreground transition-transform duration-200",
              expanded && "rotate-180"
            )}
            aria-hidden="true"
          />
        </button>
      </h2>
      <div id={contentId} hidden={!expanded} className="grid gap-4 border-t border-border px-4 py-4">
        {children}
      </div>
    </section>
  )
}

export { CollapsibleSection }
