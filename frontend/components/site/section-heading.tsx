import Link from "next/link"
import { ArrowRightIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Bo'lim sarlavhasi (v2): ixtiyoriy solid belgi (masalan "Bugun tugaydi") ustida
 * heading-2 (24/600, oddiy registr); o'ngda qo'shimcha boshqaruv va "Barchasi" havolasi.
 */
function SectionHeading({
  id,
  title,
  href,
  linkLabel = "Barchasi",
  badge,
  aside,
  className,
}: {
  id?: string
  title: string
  href?: string
  linkLabel?: string
  /** Sarlavha ustidagi belgi (solid Badge). */
  badge?: React.ReactNode
  /** O'ng tomondagi qo'shimcha boshqaruv (masalan desktop'da surish tugmalari). */
  aside?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-end justify-between gap-4", className)}>
      <div className="grid min-w-0 gap-1.5">
        {badge}
        <h2 id={id} className="text-xl font-semibold tracking-tight text-foreground">
          {title}
        </h2>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {aside}
        {href && (
          <Link
            href={href}
            className="inline-flex items-center gap-1 rounded-xs text-sm font-semibold text-brand outline-none underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            {linkLabel}
            <ArrowRightIcon className="size-4" aria-hidden="true" />
          </Link>
        )}
      </div>
    </div>
  )
}

export { SectionHeading }
