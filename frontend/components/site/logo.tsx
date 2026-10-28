import Link from "next/link"
import { GavelIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Bazart belgisi: brend ko'kidagi kvadrat ichida bolg'acha (auksion) + so'z-belgi.
 * Yagona aksent rangi — belgi sahifadagi boshqa elementlar bilan raqobatlashmaydi.
 */
function Logo({ className, size = "md" }: { className?: string; size?: "sm" | "md" }) {
  return (
    <Link
      href="/"
      aria-label="Bazart — bosh sahifa"
      className={cn(
        "inline-flex shrink-0 items-center gap-2 rounded-md outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        className
      )}
    >
      <span
        className={cn(
          "grid place-items-center rounded-sm bg-brand text-brand-foreground",
          size === "md" ? "size-8" : "size-7"
        )}
        aria-hidden="true"
      >
        <GavelIcon className={size === "md" ? "size-4.5" : "size-4"} />
      </span>
      <span
        className={cn(
          "font-heading font-bold tracking-tight text-foreground",
          size === "md" ? "text-xl" : "text-lg"
        )}
      >
        Bazart
      </span>
    </Link>
  )
}

export { Logo }
