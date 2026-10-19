import Link from "next/link"
import { ArrowRightIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Bo'lim sarlavhasi: yirik, qalin, bosh harfli nom + ingichka chiziq + "Barchasi" pill.
 * Sahifaga xarakter beradi (bezaksiz) — qutilar o'rniga tipografika ajratadi.
 */
function SectionHeading({
  title,
  href,
  linkLabel = "Barchasi",
  aside,
  className,
}: {
  title: string
  href?: string
  linkLabel?: string
  /** O'ng tomondagi qo'shimcha boshqaruv (masalan desktop'da surish tugmalari). */
  aside?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-end justify-between gap-4 border-b border-foreground/15 pb-3", className)}>
      <h2 className="font-heading text-xl font-bold tracking-tight text-foreground uppercase md:text-2xl">
        {title}
      </h2>
      <div className="flex shrink-0 items-center gap-2">
        {href && (
          <Link
            href={href}
            className="inline-flex h-8 items-center gap-1 rounded-full border border-foreground/25 px-3 text-xs font-semibold tracking-wide text-foreground uppercase outline-none transition-colors duration-150 hover:bg-foreground hover:text-background focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {linkLabel}
            <ArrowRightIcon className="size-3.5" aria-hidden="true" />
          </Link>
        )}
        {aside}
      </div>
    </div>
  )
}

export { SectionHeading }
